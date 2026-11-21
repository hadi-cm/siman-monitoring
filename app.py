import re
import pandas as pd
import streamlit as st
import base64
import plotly.express as px
from datetime import datetime

# ==============================================================================
# 0. تنظیمات صفحه
# ==============================================================================
st.set_page_config(page_title='سامانه پایش وضعیت تجهیزات سیمان تهران', layout='wide')

st.markdown("""
<style>
    html, body, [class*="css"] { font-family: Tahoma, Vazirmatn, sans-serif; }
    .pmap-wrap { display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; direction:rtl; }
    .pmap-chip {
        background:#e6efff; border:1px solid #b9d0f5; border-radius:8px;
        padding:5px 10px; font-size:13px; color:#12306e; white-space:nowrap;
        unicode-bidi:isolate; direction:rtl; font-family:Tahoma;
    }
    .pmap-chip b { color:#1E3A8D; }
    .iso { unicode-bidi:isolate; direction:rtl; display:inline-block; }
    .spec-box { background:#f0f7ff; padding:18px; border-radius:15px;
        border-right:10px solid #1E3A8D; margin-bottom:14px; direction:rtl;
        text-align:right; box-shadow:2px 2px 8px rgba(0,0,0,0.06); }
    .spec-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
        gap:10px; font-size:15px; color:#333; }
    .spec-grid span { unicode-bidi:isolate; }
    .ann-card { padding:14px 18px; border-radius:12px; margin-bottom:10px; color:#fff;
        direction:rtl; text-align:right; box-shadow:0 2px 6px rgba(0,0,0,0.12); }
    .ann-head { display:flex; justify-content:space-between; align-items:center; gap:10px; }
    .ann-body { margin-top:6px; font-size:14px; opacity:0.95; line-height:1.9; }
    .ann-meta { margin-top:8px; font-size:11px; opacity:0.85; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 1. ورود کاربران
# ==============================================================================
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
        st.markdown('<h2 style="text-align:center;">🔐 ورود به سامانه هوشمند پایش وضعیت سیمان تهران</h2>',
                    unsafe_allow_html=True)
        with st.form('login_form'):
            email = st.text_input('ایمیل کاربری:')
            password = st.text_input('رمز عبور:', type='password')
            submitted = st.form_submit_button('ورود به داشبورد')
            if submitted:
                email_clean = email.strip().lower()
                found = next((k for k in USER_CREDENTIALS if k.strip().lower() == email_clean), None)
                if found and USER_CREDENTIALS[found].strip() == password.strip():
                    st.session_state['authenticated'] = True
                    st.rerun()
                else:
                    st.error('❌ ایمیل یا رمز عبور اشتباه است.')
        return False
    return True

if not check_password():
    st.stop()

# ==============================================================================
# 2. توابع کمکی
# ==============================================================================
FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'
EN_DIGITS = '0123456789'

def norm(x):
    if x is None:
        return ''
    try:
        if isinstance(x, float) and pd.isna(x):
            return ''
    except Exception:
        pass
    s = str(x).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = (s.replace('ي', 'ی').replace('ى', 'ی').replace('ك', 'ک')
          .replace('ۀ', 'ه').replace('ة', 'ه').replace('ئ', 'ی'))
    s = s.replace('\u200c', ' ').replace('\xa0', ' ')
    s = s.replace('-', ' ').replace('_', ' ').replace('.', ' ')
    return ' '.join(s.split()).lower()

def clean_num_text(x):
    s = str(x).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = s.replace('٫', '.').replace('،', '.').replace(',', '.')
    return s.replace(' ', '')

def to_num(series):
    s = series.map(clean_num_text)
    s = s.replace({'': None, 'nan': None, 'None': None, '---': None, 'NaN': None, '': None})
    return pd.to_numeric(s, errors='coerce')

def get_image_base64(path):
    try:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ''

def smart_find_column(columns, keywords):
    if columns is None:
        return None
    cols = list(columns)
    normed = {c: norm(c) for c in cols}
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if normed[c] == nk:
                return c
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if nk and nk in normed[c]:
                return c
    return None

# ---- تاریخ شمسی ----
def g2j(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2, gm2, gd2 = gy - 1600, gm - 1, gd - 1
    g_day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    g_day_no += g_d_m[gm2]
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        g_day_no += 1
    g_day_no += gd2
    j_day_no = g_day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm, jd = 1 + j_day_no // 31, 1 + j_day_no % 31
    else:
        jm, jd = 7 + (j_day_no - 186) // 30, 1 + (j_day_no - 186) % 30
    return jy, jm, jd

def today_jalali_tuple():
    n = datetime.now()
    return g2j(n.year, n.month, n.day)

def jalali_tuple(val):
    s = norm(val)
    m = re.search(r'(\d{4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})', s)
    if not m:
        m = re.search(r'(\d{4})(\d{2})(\d{2})', s)
    if not m:
        return None
    try:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 1400
        return (y, mo, d)
    except Exception:
        return None

def date_sort_key(val):
    t = jalali_tuple(val)
    return t[0] * 10000 + t[1] * 100 + t[2] if t else 0

# ---- ترتیب عددی طبیعی ----
def natural_key(s):
    parts = re.split(r'(\d+)', str(s))
    return [int(p) if p.isdigit() else p for p in parts]

# ==============================================================================
# 3. طبقه‌بندی تجهیزات و نقشه نقاط اندازه‌گیری (P-Map)
# ==============================================================================
def detect_equipment_class(eq_type, eq_name=''):
    t = norm(eq_type)
    n = norm(eq_name)
    src = t if t else n

    if 'کراشر' in src or 'سنگ شکن' in src or 'crusher' in src:
        return 'crusher'
    if 'کمپرسور' in src or 'کامپرسور' in src or 'ایرند' in src or 'compressor' in src:
        return 'compressor'
    if 'بلوور' in src or 'بلوئر' in src or 'blower' in src or 'فن هواده' in src:
        return 'blower'
    if 'گیربکس' in src or 'گیر بکس' in src or 'gearbox' in src:
        if 'کوه' in src or 'کوهی' in src:
            return 'gearbox_11'
        return 'gearbox'
    if 'فن' in src or 'fan' in src:
        return 'fan'
    return 'generic'

POINT_MAPS = {
    'fan': [
        ('P1', 'انتهای موتور'),
        ('P2', 'سر موتور'),
        ('P3', 'یاتاقان فیکس'),
        ('P4', 'یاتاقان آزاد'),
    ],
    'blower': [
        ('P1', 'انتهای موتور'),
        ('P2', 'سر موتور'),
        ('P3', 'محور ورود بلوئر'),
        ('P4', 'انتهای بلوئر'),
    ],
    'compressor': [
        ('P1', 'انتهای موتور'),
        ('P2', 'سر موتور'),
        ('P3', 'سر ایرند'),
        ('P4', 'انتهای ایرند'),
    ],
    'gearbox': [
        ('P1', 'انتهای موتور'),
        ('P2', 'سر موتور'),
        ('P3', 'محور ورود گیربکس'),
        ('P4', 'محور خروج گیربکس'),
    ],
    'gearbox_11': [
        ('P1', 'انتهای موتور'),
        ('P2', 'سر موتور'),
        ('P3', 'محور ورودی (سمت فیکس پینیون)'),
        ('P4', 'انتهای سمت آزاد پینیون'),
        ('P5', 'محور دوم سمت فیکس'),
        ('P6', 'سمت آزاد محور دوم'),
        ('P7', 'سمت فیکس محور سوم'),
        ('P8', 'سمت آزاد محور سوم'),
        ('P9', 'بابیت سمت گیربکس'),
        ('P10', 'بابیت وسط'),
        ('P11', 'بابیت سمت پینیون آسیاب'),
    ],
    'crusher': [
        ('P1', 'انتهای موتور'),
        ('P2', 'سر موتور'),
        ('P3', 'یاتاقان سمت فیکس (پولی کوچک)'),
        ('P4', 'یاتاقان سمت آزاد (پولی کوچک)'),
        ('P5', 'یاتاقان فیکس روتور'),
        ('P6', 'یاتاقان سمت آزاد روتور'),
    ],
    'generic': [
        ('P1', 'نقطه ۱'),
        ('P2', 'نقطه ۲'),
        ('P3', 'نقطه ۳'),
        ('P4', 'نقطه ۴'),
    ],
}

CLASS_TITLE = {
    'fan': 'فن',
    'blower': 'بلوئر',
    'compressor': 'کمپرسور',
    'gearbox': 'گیربکس (۴ نقطه‌ای)',
    'gearbox_11': 'گیربکس سمت کوه (۱۱ نقطه‌ای)',
    'crusher': 'کراشر / سنگ‌شکن',
    'generic': 'عمومی',
}

def get_point_guide(eq_type, eq_name=''):
    cls = detect_equipment_class(eq_type, eq_name)
    return cls, POINT_MAPS.get(cls, POINT_MAPS['generic'])

def render_pmap(cls, points, active_codes=None):
    chips = []
    for code, desc in points:
        on = '' if not active_codes else ('' if code in active_codes else 'opacity:.35;')
        chips.append(f"<span class='pmap-chip' style='{on}'><b>{code}</b> : {desc}</span>")
    st.markdown(
        "<div class='spec-box'>"
        f"<div style='color:#1E3A8D; font-weight:bold; margin-bottom:4px;'>"
        f"📍 راهنمای نقاط اندازه‌گیری (P-Map) — نوع تجهیز شناسایی‌شده: {CLASS_TITLE.get(cls, cls)}</div>"
        f"<div class='pmap-wrap'>{''.join(chips)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )

# ==============================================================================
# 4. تشخیص و مرتب‌سازی ستون‌های نقطه
# ==============================================================================
POINT_RE = re.compile(r'(?:^|\s)(?:p|پی|نقطه)\s*(\d{1,2})')
VIB_WORDS = ['عمودی', 'افقی', 'محوری', 'ارتعاش', 'ویبره', 'شتاب', 'سرعت', 'vib']

def point_index(col):
    s = norm(col)
    m = POINT_RE.search(' ' + s)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d{1,2})', s)
    return int(m.group(1)) if m else 999

def is_point_col(col):
    s = norm(col)
    return bool(POINT_RE.search(' ' + s))

def is_vib_col(col):
    s = norm(col)
    return is_point_col(col) or any(w in s for w in VIB_WORDS)

def order_vib_cols(cols):
    idx = {c: i for i, c in enumerate(cols)}
    def key(c):
        pc = is_point_col(c)
        return (0 if pc else 1, point_index(c) if pc else 0, idx[c])
    return sorted(cols, key=key)

# ==============================================================================
# 5. بارگذاری داده‌ها
# ==============================================================================
SHEET_ID = '1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs'
VIB_GID = '0'
ASSETS_GID = '1276803564'
ANN_GID = '2057447521'

def gurl(gid):
    return f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}'

@st.cache_data(ttl=600)
def load_all_data():
    frames = {}
    for name, gid in (('vib', VIB_GID), ('assets', ASSETS_GID), ('ann', ANN_GID)):
        try:
            frames[name] = pd.read_csv(gurl(gid), dtype=str,
                                       keep_default_na=False, encoding='utf-8-sig')
        except Exception:
            frames[name] = pd.DataFrame()
    return frames['vib'], frames['assets'], frames['ann']

df, df_assets, df_ann = load_all_data()

# ==============================================================================
# 6. هدر
# ==============================================================================
logo_siman = get_image_base64('client_logo.png')
logo_faz = get_image_base64('my_logo.png')

st.markdown(f'''
<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;
            background:white; padding:14px 28px; border-radius:15px;
            box-shadow:0 4px 8px rgba(0,0,0,0.1);'>
    <img src='data:image/png;base64,{logo_faz}' style='width:105px; height:auto;'>
    <div style='text-align:center; color:#1E3A8D; font-size:24px; font-weight:bold; font-family:Tahoma;'>
        🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران
    </div>
    <img src='data:image/png;base64,{logo_siman}' style='width:105px; height:auto;'>
</div>
''', unsafe_allow_html=True)

# ==============================================================================
# 7. اعلانیه‌ها (از شیت جداگانه + فیلتر تاریخ)
# ==============================================================================
def render_announcements(df_a):
    if df_a.empty:
        return
    c_title = smart_find_column(df_a.columns, ['عنوان'])
    c_text = smart_find_column(df_a.columns, ['متن'])
    c_type = smart_find_column(df_a.columns, ['نوع'])
    c_active = smart_find_column(df_a.columns, ['فعال'])
    c_start = smart_find_column(df_a.columns, ['تاریخ شروع'])
    c_end = smart_find_column(df_a.columns, ['تاریخ انقضا', 'تاریخ پایان'])
    c_label = smart_find_column(df_a.columns, ['برچسب'])

    if not (c_title and c_text):
        return

    today = today_jalali_tuple()

    def is_active(v):
        return norm(v) in ('بله', 'yes', 'true', '1', 'فعال')

    rows = []
    for _, r in df_a.iterrows():
        if c_active and not is_active(r.get(c_active, '')):
            continue
        t_start = jalali_tuple(r.get(c_start, '')) if c_start else None
        t_end = jalali_tuple(r.get(c_end, '')) if c_end else None
        if t_start and today < t_start:
            continue
        if t_end and today > t_end:
            continue
        rows.append(r)

    if not rows:
        return

    styles = {
        'خطر': ('#d32f2f', '🚨'),
        'بحرانی': ('#d32f2f', '🚨'),
        'هشدار': ('#f9a825', '⚠️'),
        'اطلاعیه': ('#2e7d32', '✅'),
        'گزارش': ('#1565c0', '📄'),
        'موفق': ('#2e7d32', '✅'),
    }

    st.markdown('### 📢 اعلانیه‌ها و هشدارهای فعال')
    for r in rows:
        t = str(r.get(c_type, '')).strip()
        colors = styles.get(norm(t), None)
        if colors is None:
            for k, v in styles.items():
                if k in t:
                    colors = v
                    break
        color, icon = colors if colors else ('#455a64', 'ℹ️')
        title = str(r.get(c_title, '')).strip()
        text = str(r.get(c_text, '')).strip()
        label = str(r.get(c_label, '')).strip() if c_label else ''
        s_str = str(r.get(c_start, '')).strip() if c_start else ''
        e_str = str(r.get(c_end, '')).strip() if c_end else ''
        period = f'{s_str} تا {e_str}' if (s_str or e_str) else ''
        label_html = (f"<span style='background:rgba(255,255,255,.22); padding:2px 9px;"
                      f" border-radius:6px; font-size:11px;'>{label}</span>") if label else ''
        st.markdown(f"""
        <div class='ann-card' style='background:{color};'>
            <div class='ann-head'>
                <b style='font-size:16px;'>{icon} {title}</b>
                {label_html}
            </div>
            <div class='ann-body'>{text}</div>
            <div class='ann-meta'>🗓 {period}</div>
        </div>
        """, unsafe_allow_html=True)

render_announcements(df_ann)

# ==============================================================================
# 8. آماده‌سازی داده ارتعاشات
# ==============================================================================
if df.empty:
    st.error('❌ خطا در اتصال به منبع داده ارتعاشات.')
    st.stop()

col_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
col_unit = smart_find_column(df.columns, ['واحد'])
eq_col = smart_find_column(df.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'Asset'])
date_col = smart_find_column(df.columns, ['تاریخ', 'Date'])

for c, key in ((col_line, '_k_line'), (col_unit, '_k_unit'),
               (eq_col, '_k_eq'), (date_col, '_k_date')):
    df[key] = df[c].map(norm) if c else ''

df['_dkey'] = df[date_col].map(date_sort_key) if date_col else 0

visible_cols = [c for c in df.columns if not str(c).startswith('_')]
vib_cols_all = [c for c in visible_cols if is_vib_col(c)]
vib_cols = order_vib_cols(vib_cols_all)

# ---- ادغام ردیف‌های هم‌نام و هم‌تاریخ (ساختار Long) ----
def consolidate(frame, key_fields, data_cols):
    if not key_fields or frame.empty:
        return frame
    out_rows = []
    for _, grp in frame.groupby(key_fields, sort=False, dropna=False):
        if len(grp) == 1:
            out_rows.append(grp.iloc[0].to_dict())
            continue
        buckets, current = [], []
        for _, row in grp.iterrows():
            rd = row.to_dict()
            trial = current + [rd]
            used = set()
            conflict = False
            for r_ in trial:
                for c_ in data_cols:
                    v_ = str(r_.get(c_, '')).strip()
                    if v_ in ('', 'nan', 'None', 'NaN', '---'):
                        continue
                    if c_ in used:
                        conflict = True
                        break
                    used.add(c_)
                if conflict:
                    break
            if conflict and current:
                buckets.append(current)
                current = [rd]
            else:
                current = trial
        if current:
            buckets.append(current)
        for b in buckets:
            merged = {}
            for c_ in frame.columns:
                picked = ''
                for r_ in b:
                    v_ = str(r_.get(c_, '')).strip()
                    if v_ not in ('', 'nan', 'None', 'NaN'):
                        picked = v_
                        break
                merged[c_] = picked
            out_rows.append(merged)
    return pd.DataFrame(out_rows)

if eq_col and date_col:
    df = consolidate(df, ['_k_eq', '_k_date'], vib_cols_all)
    for c, key in ((col_line, '_k_line'), (col_unit, '_k_unit'),
                   (eq_col, '_k_eq'), (date_col, '_k_date')):
        df[key] = df[c].map(norm) if c else ''
    df['_dkey'] = df[date_col].map(date_sort_key)

# ==============================================================================
# 9. سایدبار
# ==============================================================================
st.sidebar.header('🔍 فیلترهای پیشرفته')

def _mode(series):
    v = series.astype(str).str.strip()
    v = v[v != '']
    return v.value_counts().idxmax() if not v.empty else ''

def display_map(key_col, original_col):
    if original_col is None:
        return {}
    tmp = df[df[key_col] != '']
    return tmp.groupby(key_col)[original_col].agg(_mode).to_dict() if not tmp.empty else {}

line_map = display_map('_k_line', col_line)
unit_map = display_map('_k_unit', col_unit)
eq_map = display_map('_k_eq', eq_col)

sel_line_k = st.sidebar.selectbox(
    '📍 خط تولید:', ['همه'] + sorted(line_map.keys(), key=natural_key),
    format_func=lambda k: 'همه' if k == 'همه' else line_map.get(k, k))

tmp_u = df.copy()
if sel_line_k != 'همه':
    tmp_u = tmp_u[tmp_u['_k_line'] == sel_line_k]

unit_keys = sorted({u for u in tmp_u['_k_unit'].unique() if u != ''}, key=natural_key)
sel_unit_k = st.sidebar.selectbox(
    '🏢 واحد:', ['همه'] + unit_keys,
    format_func=lambda k: 'همه' if k == 'همه' else unit_map.get(k, k))

if sel_unit_k != 'همه':
    tmp_u = tmp_u[tmp_u['_k_unit'] == sel_unit_k]

eq_keys = sorted({e for e in tmp_u['_k_eq'].unique() if e != ''}, key=natural_key)
sel_eq_k = st.sidebar.selectbox(
    '⚙️ انتخاب تجهیز:', ['همه تجهیزات'] + eq_keys,
    format_func=lambda k: 'همه تجهیزات' if k == 'همه تجهیزات' else eq_map.get(k, k))

search_eq = st.sidebar.text_input('🔎 جستجوی سریع تجهیز:', placeholder='مثلاً: میل فن')

st.sidebar.markdown('**📅 فیلتر تاریخ**')
date_search = st.sidebar.text_input('جستجوی تاریخ (مثلاً 1405/08):')

date_map = {}
if date_col:
    tmp_d = df[df['_k_date'] != '']
    date_map = tmp_d.groupby('_k_date')[date_col].agg(_mode).to_dict()
date_keys = sorted(date_map.keys(), reverse=True)
sel_date_k = st.sidebar.selectbox(
    '🌙 انتخاب تاریخ:', ['همه تاریخ‌ها'] + date_keys,
    format_func=lambda k: 'همه تاریخ‌ها' if k == 'همه تاریخ‌ها' else date_map.get(k, k))

# ---- پنل عیب‌یابی ----
with st.sidebar.expander('🩺 عیب‌یابی داده'):
    st.write('**ستون تجهیز:**', eq_col)
    st.write('**ستون تاریخ:**', date_col)
    st.write('**تعداد ردیف خام بعد از ادغام:**', len(df))
    st.write('**ستون‌های نقطه (به ترتیب نمایش):**')
    for c in vib_cols:
        st.write(f'- `{c}` → P{point_index(c)}' if is_point_col(c) else f'- `{c}`')
    st.write('**همه ستون‌های شیت:**')
    st.write(list(df.columns))

# ==============================================================================
# 10. اعمال فیلترها
# ==============================================================================
fdf = df.copy()
if sel_line_k != 'همه':
    fdf = fdf[fdf['_k_line'] == sel_line_k]
if sel_unit_k != 'همه':
    fdf = fdf[fdf['_k_unit'] == sel_unit_k]
if sel_eq_k != 'همه تجهیزات':
    fdf = fdf[fdf['_k_eq'] == sel_eq_k]
if search_eq.strip():
    tokens = [t for t in norm(search_eq).split() if t]
    if tokens:
        fdf = fdf[fdf['_k_eq'].map(lambda v: all(t in v for t in tokens))]
if date_search.strip():
    fdf = fdf[fdf['_k_date'].str.contains(norm(date_search), na=False, regex=False)]
if sel_date_k != 'همه تاریخ‌ها':
    fdf = fdf[fdf['_k_date'] == sel_date_k]
if date_col:
    fdf = fdf.sort_values('_dkey', ascending=False)

# ==============================================================================
# 11. نمایش اصلی
# ==============================================================================
st.title('📊 تحلیل روند ارتعاشات تجهیزات')

selected_asset_cls = None
selected_asset_points = None

if sel_eq_k != 'همه تجهیزات':
    eq_display = eq_map.get(sel_eq_k, sel_eq_k)
    matched = False

    if not df_assets.empty:
        a_name = smart_find_column(df_assets.columns,
                                   ['نام تجهیز', 'عنوان تجهیز', 'نام', 'تجهیز', 'Asset'])
        if a_name:
            n_assets = df_assets[a_name].map(norm)
            rows = df_assets[n_assets == sel_eq_k]
            if rows.empty:
                rows = df_assets[n_assets.map(
                    lambda x: x != '' and (sel_eq_k in x or x in sel_eq_k))]

            if not rows.empty:
                matched = True
                r0 = rows.iloc[0]

                def gv(keys, default='---'):
                    c = smart_find_column(df_assets.columns, keys)
                    if not c:
                        return default
                    v = str(r0[c]).strip()
                    return v if v not in ('', 'nan', 'None', 'NaN') else default

                e_type = gv(['نوع تجهیز', 'نوع'])
                e_rpm = gv(['دور', 'RPM'])
                e_line = gv(['خط'])
                e_unit = gv(['واحد'])
                e_drive = gv(['نوع انتقال', 'کوپلینگ', 'اتصال', 'درایو'])
                e_brg = gv(['بیرینگ', 'Bearing'])
                e_bush = gv(['بوش', 'Bush'])

                selected_asset_cls, selected_asset_points = get_point_guide(e_type, eq_display)

                st.markdown(f'''
                <div class='spec-box'>
                    <h3 style='color:#1E3A8D; margin:0 0 12px 0;'>🛠️ مشخصات فنی:
                        <span class='iso'>{eq_display}</span></h3>
                    <div class='spec-grid'>
                        <span><b style='color:#1E3A8D;'>🔹 نوع تجهیز:</b>
                            <span class='iso'>{e_type}</span></span>
                        <span><b style='color:#1E3A8D;'>🔹 دور:</b>
                            <span class='iso'>{e_rpm} RPM</span></span>
                        <span><b style='color:#1E3A8D;'>🔹 خط تولید:</b>
                            <span class='iso'>{e_line}</span></span>
                        <span><b style='color:#1E3A8D;'>🔹 واحد:</b>
                            <span class='iso'>{e_unit}</span></span>
                        <span><b style='color:#1E3A8D;'>🔹 انتقال قدرت:</b>
                            <span class='iso'>{e_drive}</span></span>
                        <span><b style='color:#1E3A8D;'>🧩 شماره بیرینگ:</b>
                            <span class='iso'>{e_brg}</span></span>
                        <span><b style='color:#1E3A8D;'>🧩 شماره بوش:</b>
                            <span class='iso'>{e_bush}</span></span>
                    </div>
                </div>
                ''', unsafe_allow_html=True)

                pts = smart_find_column(df_assets.columns, ['نقطه', 'Point'])
                brg = smart_find_column(df_assets.columns, ['بیرینگ', 'Bearing'])
                bsh = smart_find_column(df_assets.columns, ['بوش', 'Bush'])
                if any([pts, brg, bsh]):
                    log_cols = [c for c in [pts, brg, bsh] if c]
                    logistics = (rows[log_cols].copy()
                                 .replace({'': '---', 'nan': '---', 'None': '---', 'NaN': '---'}))
                    logistics = logistics.rename(
                        columns={k: v for k, v in {pts: 'نقطه', brg: 'بیرینگ', bsh: 'بوش'}.items()
                                 if k in logistics.columns})
                    with st.expander('📦 اطلاعات قطعات و لجستیک (بیرینگ / بوش)', expanded=True):
                        st.dataframe(logistics, hide_index=True, use_container_width=True)

    if not matched:
        st.info('ℹ️ مشخصات فنی برای این تجهیز یافت نشد. نقشه نقاط بر اساس نام تجهیز ساخته شد.')
        selected_asset_cls, selected_asset_points = get_point_guide('', eq_display)

    # ---- نقشه نقاط، بالای جدول داده‌ها ----
    present_codes = {f'P{point_index(c)}' for c in vib_cols if is_point_col(c)}
    render_pmap(selected_asset_cls, selected_asset_points, present_codes)

# ==============================================================================
# 12. جدول داده‌ها
# ==============================================================================
if fdf.empty:
    st.warning('⚠️ هیچ داده‌ای با این فیلترها پیدا نشد.')
else:
    st.markdown(f'### 📋 داده‌های ارتعاشات ({len(fdf)} مورد)')

    def color_vib(val):
        try:
            v = float(clean_num_text(val))
        except Exception:
            return ''
        if v > 7.1:
            return 'background-color:#ff4b4b; color:white'
        if v > 4.5:
            return 'background-color:#ffa500; color:white'
        return 'background-color:#2e7d32; color:white'

    head_order = []
    for c in [col_line, col_unit, eq_col, date_col]:
        if c and c in visible_cols and c not in head_order:
            head_order.append(c)
    rest = [c for c in visible_cols if c not in head_order and c not in vib_cols]
    table_cols = head_order + vib_cols + rest
    table = fdf[table_cols].copy()

    if vib_cols:
        st.dataframe(table.style.map(color_vib, subset=vib_cols),
                     use_container_width=True, hide_index=True)
    else:
        st.dataframe(table, use_container_width=True, hide_index=True)

    # ---- نمودار روند ----
    if vib_cols and sel_eq_k != 'همه تجهیزات' and date_col and len(fdf) > 1:
        with st.expander('📈 نمودار روند ارتعاشات', expanded=False):
            trend = fdf[[date_col] + vib_cols].copy()
            trend['_dkey'] = trend[date_col].map(date_sort_key)
            trend = trend.sort_values('_dkey')
            trend['تاریخ'] = trend[date_col].astype(str)
            long_df = trend.melt(id_vars=['تاریخ', '_dkey'], value_vars=vib_cols,
                                 var_name='نقطه', value_name='ارتعاش')
            long_df['ارتعاش'] = to_num(long_df['ارتعاش'])
            long_df = long_df.dropna(subset=['ارتعاش'])
            if not long_df.empty:
                cat_order = order_vib_cols(vib_cols)
                fig_line = px.line(long_df, x='تاریخ', y='ارتعاش', color='نقطه',
                                   markers=True, title='روند ارتعاش (mm/s)',
                                   category_orders={'نقطه': cat_order})
                fig_line.add_hline(y=4.5, line_dash='dash', line_color='orange',
                                   annotation_text='هشدار')
                fig_line.add_hline(y=7.1, line_dash='dash', line_color='red',
                                   annotation_text='بحرانی')
                st.plotly_chart(fig_line, use_container_width=True)

    # ---- نمودار وضعیت سلامت ----
    st.markdown('---')
    st.markdown('### 📈 تحلیل وضعیت سلامت تجهیزات')
    with st.expander('نمایش نمودار دایره‌ای وضعیت سلامت', expanded=False):
        if vib_cols:
            v_max = fdf[vib_cols].apply(to_num).max(axis=1)

            def cat(v):
                if pd.isna(v):
                    return 'نامشخص'
                if v > 7.1:
                    return 'بحرانی'
                if v > 4.5:
                    return 'هشدار'
                return 'سالم'

            status = v_max.map(cat).value_counts()
            if not status.empty:
                fig_pie = px.pie(
                    values=status.values, names=status.index, color=status.index, hole=0.35,
                    color_discrete_map={'سالم': '#2e7d32', 'هشدار': '#ffa500',
                                        'بحرانی': '#ff4b4b', 'نامشخص': '#9e9e9e'})
                st.plotly_chart(fig_pie, use_container_width=True)

st.markdown(
    '<div style="text-align:center; margin-top:50px; color:#555;">'
    'طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>',
    unsafe_allow_html=True)
