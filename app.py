import re
import base64
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime

st.set_page_config(page_title='سامانه پایش وضعیت تجهیزات سیمان تهران', layout='wide')

# =====================================================================
# 1) ورود
# =====================================================================
USER_CREDENTIALS = {
    'alireza76ir@gmail.com': 'siman123',
    'vah.rezaei@gmail.com': 'siman123',
    'cm.zandiyeh@gmail.com': 'siman123',
    'm.babahasan@gmail.com': 'siman123',
    'freedocs.ir@gmail.com': 'siman123',
    'tehrancement@gmail.com': 'siman123',
    'masoud.sa.1989823@gmail.com': 'siman123',
}


def check_password():
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    if not st.session_state['authenticated']:
        st.markdown('<h2 style="text-align:center;">🔐 ورود به سامانه پایش وضعیت سیمان تهران</h2>',
                    unsafe_allow_html=True)
        with st.form('login_form'):
            email = st.text_input('ایمیل کاربری:')
            password = st.text_input('رمز عبور:', type='password')
            ok = st.form_submit_button('ورود به داشبورد')
            if ok:
                e = email.strip().lower()
                found = next((k for k in USER_CREDENTIALS if k.strip().lower() == e), None)
                if found and USER_CREDENTIALS[found].strip() == password.strip():
                    st.session_state['authenticated'] = True
                    st.rerun()
                else:
                    st.error('❌ ایمیل یا رمز عبور اشتباه است.')
        return False
    return True


if not check_password():
    st.stop()

# =====================================================================
# 2) توابع پایه
# =====================================================================
FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'
EN_DIGITS = '0123456789'
EMPTY = {'', 'nan', 'none', 'null', '---', '-', 'na', 'n/a', 'NaN'}


def fa2en(x):
    s = str(x)
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    return s


def norm(x):
    if x is None:
        return ''
    try:
        if isinstance(x, float) and pd.isna(x):
            return ''
    except Exception:
        pass
    s = fa2en(x).strip()
    s = (s.replace('ي', 'ی').replace('ى', 'ی').replace('ك', 'ک')
         .replace('ۀ', 'ه').replace('ة', 'ه'))
    s = s.replace('\u200c', ' ').replace('\xa0', ' ')
    s = s.replace('-', ' ').replace('_', ' ').replace('.', ' ')
    return ' '.join(s.split()).lower()


def clean_num_text(x):
    s = fa2en(x).strip()
    s = s.replace('٫', '.').replace('،', '.').replace(',', '.')
    s = s.replace(' ', '').replace('\u200c', '')
    return s


def num_or_none(v):
    try:
        t = clean_num_text(v)
        if t in EMPTY:
            return None
        return float(t)
    except Exception:
        return None


def to_num(series):
    return series.map(num_or_none)


def is_empty(v):
    return str(v).strip().lower() in EMPTY


def smart_find_column(columns, keywords):
    if columns is None:
        return None
    cols = list(columns)
    n = {c: norm(c) for c in cols}
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if n[c] == nk:
                return c
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if nk and nk in n[c]:
                return c
    return None


# ------------------------------------------------------------------
# شماره نقطه – ریشه ترتیب P1..P11
# ------------------------------------------------------------------
POINT_PATTERN = re.compile(r'(?:پی|pt|point|نقطه|[pP])\s*[-_ ]?\s*(\d{1,3})(?!\d)')
VIB_WORDS = ['عمودی', 'افقی', 'محوری', 'ارتعاش', 'ویبره', 'vib', 'mm s']


def point_index(colname):
    raw = fa2en(colname).strip()
    if re.fullmatch(r'\d{1,3}', raw):
        return int(raw)
    m = POINT_PATTERN.search(raw)
    if m:
        return int(m.group(1))
    n = norm(raw)
    if any(k in n for k in VIB_WORDS):
        return 500
    nums = re.findall(r'\d{1,3}', raw)
    if nums:
        return int(nums[-1])
    return 900


def is_vib_col(colname):
    n = norm(colname)
    if any(k in n for k in VIB_WORDS):
        return True
    return POINT_PATTERN.search(fa2en(colname)) is not None


def natural_key(txt):
    s = fa2en(str(txt))
    return [int(p) if p.isdigit() else p for p in re.split(r'(\d+)', s)]


def split_point(name):
    s = fa2en(str(name)).strip()
    m = re.search(r'(?:[\s\-_/]+)(?:پی|[pP]|pt|point)\s*[-_ ]?\s*\d{1,3}\s*$', s)
    return s[:m.start()].strip() if m else s


def same_value(a, b):
    """تضاد ندارد اگر هر دو خالی، یا هر دو عددی و برابر، یا متن نرمال‌شده برابر."""
    ea, eb = is_empty(a), is_empty(b)
    if ea or eb:
        return True
    na, nb = num_or_none(a), num_or_none(b)
    if na is not None and nb is not None:
        return abs(na - nb) < 1e-9
    return norm(a) == norm(b)


# ------------------------- تاریخ شمسی -------------------------
def parse_jdate(val):
    nums = re.findall(r'\d+', fa2en(str(val)))
    if len(nums) < 3:
        return None
    try:
        y, m, d = int(nums[0]), int(nums[1]), int(nums[2])
    except Exception:
        return None
    if y < 100:
        y += 1400
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    return y, m, d


def jdate_key(val):
    t = parse_jdate(val)
    return t[0] * 10000 + t[1] * 100 + t[2] if t else 0


def g2j(gy, gm, gd):
    dim = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2, gm2, gd2 = gy - 1600, gm - 1, gd - 1
    gdn = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    gdn += dim[gm2] + gd2
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        gdn += 1
    jdn = gdn - 79
    jnp = jdn // 12053
    jdn %= 12053
    jy = 979 + 33 * jnp + 4 * (jdn // 1461)
    jdn %= 1461
    if jdn >= 366:
        jy += (jdn - 1) // 365
        jdn = (jdn - 1) % 365
    jdn += 1
    months = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]
    jm = 0
    while jm < 12 and jdn > months[jm]:
        jdn -= months[jm]
        jm += 1
    return jy, jm + 1, jdn


def today_jalali():
    n = datetime.now()
    return g2j(n.year, n.month, n.day)


def get_image_base64(path):
    try:
        with open(path, 'rb') as fp:
            return base64.b64encode(fp.read()).decode()
    except Exception:
        return ''


# ---------------- نقشه نقاط بر اساس نوع تجهیز ----------------
POINT_MAPS = {
    'گیربکس کوه': [(1, 'انتهای موتور'), (2, 'سر موتور'),
                   (3, 'محور ورودی – سمت فیکس (پینیون)'), (4, 'محور ورودی – سمت آزاد (لوز)'),
                   (5, 'محور دوم – سمت فیکس'), (6, 'محور دوم – سمت آزاد'),
                   (7, 'محور سوم – سمت فیکس'), (8, 'محور سوم – سمت آزاد'),
                   (9, 'بابیت سمت گیربکس'), (10, 'بابیت وسط'), (11, 'بابیت سمت پینیون آسیاب')],
    'گیربکس': [(1, 'انتهای موتور'), (2, 'سر موتور'),
               (3, 'محور ورودی گیربکس'), (4, 'محور خروجی گیربکس')],
    'فن': [(1, 'انتهای موتور'), (2, 'سر موتور'),
           (3, 'یاتاقان سمت فیکس'), (4, 'یاتاقان سمت آزاد')],
    'بلوئر': [(1, 'انتهای موتور'), (2, 'سر موتور'),
              (3, 'محور ورودی بلوئر'), (4, 'انتهای بلوئر')],
    'کمپرسور': [(1, 'انتهای موتور'), (2, 'سر موتور'),
                (3, 'سر ایرند'), (4, 'انتهای ایرند')],
    'کراشر': [(1, 'انتهای موتور'), (2, 'سر موتور'),
              (3, 'یاتاقان سمت فیکس (پولی کوچک)'), (4, 'یاتاقان سمت آزاد (پولی کوچک)'),
              (5, 'یاتاقان سمت فیکس (روتور)'), (6, 'یاتاقان سمت آزاد (روتور)')],
}


def detect_type(text):
    s = norm(text)
    if 'کوه' in s and 'گیرب' in s:
        return 'گیربکس کوه'
    if 'کراشر' in s or 'سنگ شکن' in s:
        return 'کراشر'
    if 'کمپرس' in s or 'کمپرسر' in s:
        return 'کمپرسور'
    if 'بلو' in s:
        return 'بلوئر'
    if 'گیرب' in s:
        return 'گیربکس'
    if 'فن' in s:
        return 'فن'
    return None


def point_guide_html(eq_name, eq_type, filled_points):
    tname = detect_type(f'{eq_type} {eq_name}')
    mapping = POINT_MAPS.get(tname)
    if not mapping:
        return ("<div style='margin-top:12px;padding:10px 12px;background:#fff8e1;border-radius:10px;"
                "border:1px dashed #f0c36d;color:#8a6d3b;font-size:14px;'>"
                "ℹ️ نوع تجهیز تشخیص داده نشد؛ نقشه نقاط نمایش داده نمی‌شود. "
                "(ستون «نوع تجهیز» در شیت Assets را پر کنید.)</div>")
    chips = ''
    for idx, desc in mapping:
        has = idx in filled_points
        bg, fg = ('#1E3A8D', '#ffffff') if has else ('#e7ecf6', '#7a8699')
        chips += ("<span style='display:inline-block;margin:4px;padding:6px 11px;border-radius:9px;"
                  "background:%s;color:%s;font-size:14px;unicode-bidi:isolate;direction:rtl;"
                  "white-space:nowrap;'><b>%s P%s</b>&nbsp; %s</span>"
                  % (bg, fg, '●' if has else '○', idx, desc))
    return ("<div style='margin-top:12px;padding:11px 13px;background:#f5f8ff;border-radius:10px;"
            "border:1px dashed #b9c8e6;unicode-bidi:isolate;'>"
            "<div style='color:#1E3A8D;font-weight:bold;margin-bottom:6px;'>"
            "📍 نقشه نقاط اندازه‌گیری (P-Map) – دسته: %s</div>"
            "<div style='line-height:2.1;'>%s</div></div>" % (tname, chips))


# =====================================================================
# 3) داده‌ها
# =====================================================================
SHEET_ID = '1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs'
VIB_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0'
ASSETS_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=1276803564'
ANN_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=2057447521'


@st.cache_data(ttl=300)
def load_all_data():
    def rd(url):
        try:
            return pd.read_csv(url, dtype=str, keep_default_na=False, encoding='utf-8-sig')
        except Exception:
            return pd.DataFrame()
    return rd(VIB_URL), rd(ASSETS_URL), rd(ANN_URL)


df_raw, df_assets, df_ann = load_all_data()

# =====================================================================
# 4) هدر
# =====================================================================
logo_siman = get_image_base64('client_logo.png')
logo_faz = get_image_base64('my_logo.png')

st.markdown(f'''
<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;
            background:white;padding:14px 26px;border-radius:14px;box-shadow:0 3px 10px rgba(0,0,0,.08);'>
    <img src='data:image/png;base64,{logo_faz}' style='width:105px;height:auto;'>
    <div style='text-align:center;color:#1E3A8D;font-size:24px;font-weight:bold;font-family:Tahoma;'>
        🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران
    </div>
    <img src='data:image/png;base64,{logo_siman}' style='width:105px;height:auto;'>
</div>
''', unsafe_allow_html=True)

# =====================================================================
# 5) اعلانیه‌ها
# =====================================================================
if not df_ann.empty:
    c_title = smart_find_column(df_ann.columns, ['عنوان'])
    c_text = smart_find_column(df_ann.columns, ['متن', 'توضیحات'])
    c_type = smart_find_column(df_ann.columns, ['نوع'])
    c_act = smart_find_column(df_ann.columns, ['فعال'])
    c_start = smart_find_column(df_ann.columns, ['تاریخ شروع', 'شروع'])
    c_end = smart_find_column(df_ann.columns, ['تاریخ انقضا', 'انقضا'])
    c_lbl = smart_find_column(df_ann.columns, ['برچسب', 'تگ'])

    if c_title and c_text:
        ty, tm, td = today_jalali()
        tk = ty * 10000 + tm * 100 + td
        for _, r in df_ann.iterrows():
            if c_act and str(r[c_act]).strip() not in ('بله', 'بلي', 'yes', 'YES', 'True', '1', '۱'):
                continue
            ks = jdate_key(r[c_start]) if c_start else 0
            ke = jdate_key(r[c_end]) if c_end else 99999999
            if (ks and tk < ks) or (ke and tk > ke):
                continue

            ttl = str(r[c_title]).strip()
            msg = str(r[c_text]).strip()
            typ = norm(r[c_type]) if c_type else ''
            lbl_txt = str(r[c_lbl]).strip() if c_lbl else ''
            if not ttl and not msg:
                continue

            if 'خطر' in typ or 'بحران' in typ:
                bg, ic, bd = '#ffe8e8', '🚨', '#e53935'
            elif 'هشدار' in typ:
                bg, ic, bd = '#fff5e0', '⚠️', '#f0a500'
            elif 'اطلاع' in typ or 'گزارش' in typ or 'موفق' in typ:
                bg, ic, bd = '#e8f7ec', '✅', '#2e7d32'
            else:
                bg, ic, bd = '#eaf1ff', 'ℹ️', '#1E3A8D'

            rng = ''
            if c_start or c_end:
                a = str(r[c_start]).strip() if c_start else ''
                b = str(r[c_end]).strip() if c_end else ''
                rng = f'{a} → {b}'.strip(' →')

            lbl_html = (f"<span style='background:{bd};color:#fff;padding:2px 9px;border-radius:6px;"
                        f"font-size:12px;unicode-bidi:isolate;'>{lbl_txt}</span>") if lbl_txt else ''
            rng_html = (f"<span style='color:#6b7280;font-size:12px;unicode-bidi:isolate;'>{rng}</span>"
                        ) if rng else ''

            st.markdown(f'''
            <div style='background:{bg};border-right:6px solid {bd};border-radius:10px;
                        padding:11px 15px;margin-bottom:8px;direction:rtl;text-align:right;
                        font-family:Tahoma;unicode-bidi:isolate;'>
                <div style='display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;'>
                    <b style='color:#1f2937;font-size:16px;'>{ic} {ttl}</b>
                    <span>{lbl_html} {rng_html}</span>
                </div>
                <div style='margin-top:5px;color:#374151;font-size:14px;line-height:1.9;'>{msg}</div>
            </div>
            ''', unsafe_allow_html=True)

# =====================================================================
# 6) ستون‌ها
# =====================================================================
if df_raw.empty:
    st.error('❌ خطا در خواندن شیت ارتعاشات.')
    st.stop()

df = df_raw.copy()
col_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
col_unit = smart_find_column(df.columns, ['واحد', 'بخش'])
equip_col = smart_find_column(df.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'ماشین', 'equipment', 'asset'])
date_col = smart_find_column(df.columns, ['تاریخ', 'date'])

if date_col is None:
    best, best_score = None, 0
    for c in df.columns:
        score = df[c].head(300).map(lambda v: 1 if parse_jdate(v) else 0).sum()
        if score > best_score:
            best, best_score = c, score
    date_col = best if best_score else None

if equip_col is None or date_col is None:
    st.error('❌ ستون «نام تجهیز» یا «تاریخ» در شیت پیدا نشد.')
    st.write('ستون‌های موجود:', list(df.columns))
    st.stop()

visible_cols = [c for c in df.columns if not str(c).startswith('_')]
vib_cols = sorted([c for c in visible_cols if is_vib_col(c)], key=point_index)
other_cols = [c for c in visible_cols if c not in vib_cols]

df['_k_eq'] = df[equip_col].map(lambda v: norm(split_point(v)))
df['_k_line'] = df[col_line].map(norm) if col_line else ''
df['_k_unit'] = df[col_unit].map(norm) if col_unit else ''
df['_k_date'] = df[date_col].map(norm)
df['_dkey'] = df[date_col].map(jdate_key)
df['_mkey'] = df.apply(lambda r: f"{r['_k_eq']}|{r['_dkey'] or ('t' + r['_k_date'])}", axis=1)

# =====================================================================
# 7) ادغام ردیف‌ها – منطق بازنویسی‌شده
# =====================================================================
def merge_group(rows, strict):
    """
    rows : لیست ردیف‌های هم‌گروه (یک تجهیز، یک تاریخ)
    strict=False  → ادغام کامل: برای هر ستون، اولین مقدار غیرخالی نگه داشته می‌شود
    strict=True   → ادغام محافظه‌کارانه: اگر در یک ستون ارتعاش دو مقدار متفاوت بود،
                     ردیف‌ها جدا می‌مانند و در گزارش «تضاد» ثبت می‌شود
    """
    check_cols = vib_cols if vib_cols else data_cols
    buckets = []
    conflicts_log = []

    for r in rows:
        placed = False
        for b in buckets:
            bad = []
            if strict:
                for c in check_cols:
                    if not same_value(b[c], r[c]):
                        bad.append(c)
            if not bad:
                for c in data_cols:
                    if is_empty(b[c]) and not is_empty(r[c]):
                        b[c] = r[c]
                placed = True
                break
            conflicts_log.append(
                f"{r[equip_col]} | {r[date_col]} → ستون‌های با مقدار متفاوت: "
                + '، '.join(f'{c}(«{b[c]}»≠«{r[c]}»)' for c in bad)
            )
        if not placed:
            buckets.append(r.copy())
    return buckets, conflicts_log


def consolidate(frame, strict):
    out, report, conflicts = [], [], []
    for mkey, g in frame.groupby('_mkey', sort=False):
        rows = [r for _, r in g.iterrows()]
        if not str(mkey).split('|')[0]:
            out.extend(rows)
            continue
        buckets, clog = merge_group(rows, strict)
        conflicts.extend(clog)
        out.extend(buckets)
        report.append({
            'تجهیز': split_point(g.iloc[0][equip_col]),
            'تاریخ': g.iloc[0][date_col],
            'ردیف خام': len(rows),
            'ردیف پس از ادغام': len(buckets),
        })
    res = pd.DataFrame(out).reset_index(drop=True) if out else pd.DataFrame(columns=frame.columns)
    return res, pd.DataFrame(report), conflicts


# =====================================================================
# 8) سایدبار
# =====================================================================
st.sidebar.header('🔍 فیلترها')

merge_mode = st.sidebar.radio(
    '⚙️ روش ادغام ردیف‌های هم‌نام',
    ['ادغام کامل (توصیه‌شده)', 'ادغام محافظه‌کارانه'],
    index=0,
    help='در حالت کامل، ردیف‌های هم‌نام و هم‌تاریخ در یک ردیف جمع می‌شوند و '
         'هر ستون نقطه اولین مقدار موجود را می‌گیرد. در حالت محافظه‌کارانه اگر '
         'یک نقطه دو مقدار متفاوت داشته باشد، ردیف‌ها جدا می‌مانند.')
strict_mode = merge_mode.startswith('ادغام محافظه')

data_cols = [c for c in visible_cols if c not in (col_line, col_unit, equip_col, date_col)]
df_cons, merge_report, conflict_log = consolidate(df, strict_mode)

line_map = df_cons[df_cons['_k_line'] != ''].groupby('_k_line')[col_line].first().to_dict() if col_line else {}
unit_map = df_cons[df_cons['_k_unit'] != ''].groupby('_k_unit')[col_unit].first().to_dict() if col_unit else {}
eq_map = (df_cons.groupby('_k_eq')[equip_col]
          .agg(lambda s: sorted({str(v).strip() for v in s if str(v).strip()}, key=len)[0]).to_dict())


def lbl(k, mp):
    return k if k in ('همه', 'همه تجهیزات', 'همه تاریخ‌ها') else mp.get(k, k)


s_line = st.sidebar.selectbox('📍 خط تولید', ['همه'] + sorted(line_map.keys(), key=natural_key),
                              format_func=lambda k: lbl(k, line_map))
tmp = df_cons if s_line == 'همه' else df_cons[df_cons['_k_line'] == s_line]

s_unit = st.sidebar.selectbox('🏢 واحد',
                              ['همه'] + sorted([u for u in tmp['_k_unit'].unique() if u], key=natural_key),
                              format_func=lambda k: lbl(k, unit_map))
tmp = tmp if s_unit == 'همه' else tmp[tmp['_k_unit'] == s_unit]

s_eq = st.sidebar.selectbox('⚙️ تجهیز',
                            ['همه تجهیزات'] + sorted([e for e in tmp['_k_eq'].unique() if e], key=natural_key),
                            format_func=lambda k: lbl(k, eq_map))

s_search = st.sidebar.text_input('🔎 جستجوی تجهیز', placeholder='مثلاً: 607')
date_map = df_cons[df_cons['_k_date'] != ''].groupby('_dkey')[date_col].first().to_dict()
s_date = st.sidebar.selectbox('📅 تاریخ', ['همه تاریخ‌ها'] + sorted(date_map.keys(), reverse=True),
                              format_func=lambda k: lbl(k, {kk: str(vv) for kk, vv in date_map.items()}))

with st.sidebar.expander('🩺 عیب‌یابی داده', expanded=False):
    ty, tm, td = today_jalali()
    st.caption(f'امروز: {ty:04d}/{tm:02d}/{td:02d}')
    st.write('ستون تجهیز:', equip_col)
    st.write('ستون تاریخ:', date_col)
    st.write('ردیف خام شیت:', len(df), '| پس از ادغام:', len(df_cons))
    st.markdown('**شماره تشخیص‌شده هر ستون نقطه:**')
    for c in vib_cols:
        st.write(f'• `{c}` → P{point_index(c)}')

# =====================================================================
# 9) فیلتر
# =====================================================================
f = df_cons.copy()
if s_line != 'همه':
    f = f[f['_k_line'] == s_line]
if s_unit != 'همه':
    f = f[f['_k_unit'] == s_unit]
if s_eq != 'همه تجهیزات':
    f = f[f['_k_eq'] == s_eq]
if s_search.strip():
    toks = [t for t in norm(s_search).split() if t]
    if toks:
        f = f[f['_k_eq'].map(lambda v: all(t in v for t in toks))]
if s_date != 'همه تاریخ‌ها':
    f = f[f['_dkey'] == s_date]
f = f.sort_values('_dkey', ascending=False)

# =====================================================================
# 10) کارت مشخصات + نقشه نقاط
# =====================================================================
st.title('📊 تحلیل روند ارتعاشات تجهیزات')

if s_eq != 'همه تجهیزات':
    eq_name = lbl(s_eq, eq_map)
    e = {k: '---' for k in ('type', 'rpm', 'line', 'unit', 'drive', 'brg', 'bush')}

    if not df_assets.empty:
        a_name = smart_find_column(df_assets.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'asset'])
        if a_name:
            nm = df_assets[a_name].map(lambda v: norm(split_point(v)))
            rows = df_assets[nm == s_eq]
            if rows.empty:
                rows = df_assets[nm.map(lambda x: bool(x) and (s_eq in x or x in s_eq))]
            if not rows.empty:
                r0 = rows.iloc[0]

                def gv(keys):
                    c = smart_find_column(df_assets.columns, keys)
                    if not c:
                        return '---'
                    v = str(r0[c]).strip()
                    return v if not cell_empty_ok(v) else '---'

                def cell_empty_ok(v):
                    return str(v).strip().lower() in EMPTY

                e['type'] = gv(['نوع تجهیز', 'نوع'])
                e['rpm'] = gv(['دور', 'rpm', 'سرعت'])
                e['line'] = gv(['خط'])
                e['unit'] = gv(['واحد'])
                e['drive'] = gv(['نوع انتقال', 'کوپلینگ', 'اتصال', 'درایو', 'تسمه'])
                e['brg'] = gv(['بیرینگ', 'bearing'])
                e['bush'] = gv(['بوش', 'bush'])

    filled = set()
    for c in vib_cols:
        if c in f.columns and f[c].map(lambda v: not is_empty(v)).any():
            filled.add(point_index(c))

    st.markdown(f'''
    <div style='background:#f0f7ff;padding:18px;border-radius:14px;border-right:9px solid #1E3A8D;
                margin-bottom:16px;direction:rtl;text-align:right;font-family:Tahoma;'>
        <h3 style='color:#1E3A8D;margin:0 0 12px 0;'>🛠️ مشخصات فنی: {eq_name}</h3>
        <div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px;
                    font-size:15px;color:#333;'>
            <span><b style='color:#1E3A8D;'>نوع:</b> {e['type']}</span>
            <span><b style='color:#1E3A8D;'>دور:</b> {e['rpm']} RPM</span>
            <span><b style='color:#1E3A8D;'>خط:</b> {e['line']}</span>
            <span><b style='color:#1E3A8D;'>واحد:</b> {e['unit']}</span>
            <span><b style='color:#1E3A8D;'>انتقال قدرت:</b> {e['drive']}</span>
            <span><b style='color:#1E3A8D;'>بیرینگ:</b> {e['brg']}</span>
            <span><b style='color:#1E3A8D;'>بوش:</b> {e['bush']}</span>
        </div>
        {point_guide_html(eq_name, e['type'], filled)}
    </div>
    ''', unsafe_allow_html=True)

# =====================================================================
# 11) جدول
# =====================================================================
if f.empty:
    st.warning('⚠️ هیچ داده‌ای با این فیلترها پیدا نشد.')
else:
    st.markdown(f'### 📋 داده‌های ارتعاشات ({len(f)} ردیف پس از ادغام)')

    view = f.copy()
    view['تجهیز'] = view[equip_col].map(lambda v: split_point(v))
    view['نقطه‌های ثبت‌شده'] = view.apply(
        lambda r: '، '.join(f'P{point_index(c)}' for c in vib_cols
                            if c in r.index and not is_empty(r[c])), axis=1)

    base = [c for c in [col_line, col_unit] if c] + ['تجهیز', date_col, 'نقطه‌های ثبت‌شده']
    ordered = [c for c in base if c in view.columns]
    ordered += [c for c in vib_cols if c in view.columns]
    ordered += [c for c in other_cols if c in view.columns and c not in ordered]
    table = view[ordered].copy()

    def color_vib(val):
        n = num_or_none(val)
        if n is None:
            return ''
        if n > 7.1:
            return 'background-color:#ff4b4b;color:white'
        if n > 4.5:
            return 'background-color:#ffa500;color:white'
        return 'background-color:#2e7d32;color:white'

    styled = table.style
    if vib_cols:
        styled = styled.map(color_vib, subset=[c for c in vib_cols if c in table.columns])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ------- نمودار روند -------
    if vib_cols and s_eq != 'همه تجهیزات' and len(f) > 1:
        with st.expander('📈 نمودار روند ارتعاشات', expanded=False):
            tr = f[[date_col] + [c for c in vib_cols if c in f.columns]].copy()
            tr['_d'] = tr[date_col].map(jdate_key)
            tr = tr.sort_values('_d')
            tr['تاریخ'] = tr[date_col].astype(str)
            long = tr.melt(id_vars=['تاریخ', '_d'],
                           value_vars=[c for c in vib_cols if c in tr.columns],
                           var_name='نقطه', value_name='ارتعاش')
            long['ارتعاش'] = to_num(long['ارتعاش'])
            long = long.dropna(subset=['ارتعاش'])
            if not long.empty:
                fig = px.line(long, x='تاریخ', y='ارتعاش', color='نقطه', markers=True,
                              title='روند ارتعاش (mm/s)')
                fig.add_hline(y=4.5, line_dash='dash', line_color='orange', annotation_text='هشدار')
                fig.add_hline(y=7.1, line_dash='dash', line_color='red', annotation_text='بحرانی')
                st.plotly_chart(fig, use_container_width=True)

    with st.expander('📈 تحلیل وضعیت سلامت تجهیزات', expanded=False):
        if vib_cols:
            vmax = f[[c for c in vib_cols if c in f.columns]].apply(to_num, axis=0).max(axis=1)

            def cat(v):
                if pd.isna(v):
                    return 'نامشخص'
                if v > 7.1:
                    return 'بحرانی'
                if v > 4.5:
                    return 'هشدار'
                return 'سالم'

            stt = vmax.map(cat).value_counts()
            if not stt.empty:
                pie = px.pie(values=stt.values, names=stt.index, color=stt.index, hole=0.35,
                             color_discrete_map={'سالم': '#2e7d32', 'هشدار': '#ffa500',
                                                 'بحرانی': '#ff4b4b', 'نامشخص': '#9e9e9e'})
                st.plotly_chart(pie, use_container_width=True)

    # ------- عیب‌یابی -------
    with st.expander('🩺 عیب‌یابی ادغام (اینجا معلوم می‌شود چرا ردیف تکراری داشتی)', expanded=False):
        st.markdown('**۱) گزارش ادغام** – هر تجهیز/تاریخ چند ردیف خام داشته و چند ردیف مانده:')
        if not merge_report.empty:
            rep = merge_report
            if s_eq != 'همه تجهیزات':
                rep = rep[rep['تجهیز'].map(lambda v: norm(split_point(v)) == s_eq)]
            st.dataframe(rep, use_container_width=True, hide_index=True)
        else:
            st.caption('گزارشی موجود نیست.')

        st.markdown('**۲) تضادهای شناسایی‌شده** (فقط در حالت محافظه‌کارانه):')
        if conflict_log:
            for t in conflict_log[:40]:
                st.write('• ' + t)
        else:
            st.caption('تضادی ثبت نشده است.')

        st.markdown('**۳) ردیف‌های خام شیت برای انتخاب فعلی:**')
        rv = df
        if s_eq != 'همه تجهیزات':
            rv = rv[rv['_k_eq'] == s_eq]
        if s_date != 'همه تاریخ‌ها':
            rv = rv[rv['_dkey'] == s_date]
        sc = [c for c in ([equip_col, date_col] + [c for c in vib_cols if c in df.columns]) if c in rv.columns]
        st.dataframe(rv[sc].head(80), use_container_width=True, hide_index=True)

st.markdown(
    '<div style="text-align:center;margin-top:45px;color:#666;font-family:Tahoma;font-size:13px;">'
    'طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>',
    unsafe_allow_html=True)
