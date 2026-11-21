import re
import pandas as pd
import streamlit as st
import base64
import plotly.express as px
from datetime import datetime

# ==============================================================================
# 0. تنظیمات صفحه
# ==============================================================================
st.set_page_config(page_title='داشبورد فنی ارتعاشات سیمان تهران', layout='wide')

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
    if x is None: return ''
    try:
        if isinstance(x, float) and pd.isna(x): return ''
    except Exception:
        pass
    s = str(x).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS): s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS): s = s.replace(a, e)
    s = (s.replace('ي', 'ی').replace('ى', 'ی').replace('ك', 'ک').replace('ۀ', 'ه').replace('ة', 'ه'))
    s = s.replace('\u200c', ' ').replace('\xa0', ' ').replace('-', ' ').replace('_', ' ').replace('.', ' ')
    return ' '.join(s.split()).lower()

def clean_num_text(x):
    s = str(x).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS): s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS): s = s.replace(a, e)
    s = s.replace('٫', '.').replace('،', '.').replace(',', '.').replace(' ', '')
    return s

def to_num(series):
    s = series.map(clean_num_text)
    s = s.replace({'': None, 'nan': None, 'None': None, '---': None, 'NaN': None})
    return pd.to_numeric(s, errors='coerce')

def get_image_base64(path):
    try:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ''

def smart_find_column(columns, keywords):
    if columns is None: return None
    cols = list(columns)
    normed = {c: norm(c) for c in cols}
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if normed[c] == nk: return c
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if nk and nk in normed[c]: return c
    return None

def date_key_from_text(val):
    s = norm(val)
    m = re.search(r'(\d{2,4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})', s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100: y += 1400
        return y * 10000 + mo * 100 + d
    m = re.search(r'(\d{4})(\d{2})(\d{2})', s)
    if m:
        return int(m.group(1)) * 10000 + int(m.group(2)) * 100 + int(m.group(3))
    return 0

# --- تبدیل تاریخ میلادی به شمسی (برای فیلتر خودکار اعلانیه‌ها) ---
def g2j(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2, gm2, gd2 = gy - 1600, gm - 1, gd - 1
    g_day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    g_day_no += g_d_m[gm2]
    if gm2 > 1 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
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
        j_day_no -= 186
        jm, jd = 7 + j_day_no // 30, 1 + j_day_no % 30
    return jy, jm, jd

def today_jkey():
    now = datetime.now()
    y, m, d = g2j(now.year, now.month, now.day)
    return y * 10000 + m * 100 + d

def jalali_today_str():
    now = datetime.now()
    y, m, d = g2j(now.year, now.month, now.day)
    return f'{y:04d}/{m:02d}/{d:02d}'

def is_true_flag(v):
    s = norm(v)
    if not s: return False
    return s in ('بله', 'فعال', 'yes', 'true', '1', 'y', 'on', 'دارد')

# --- راهنمای نقاط ---
def get_point_items(eq_name, eq_type=''):
    name = norm(eq_name) + ' ' + norm(eq_type)
    if 'گیربکس' in name:
        return ['P1: انتهای موتور', 'P2: جلوی موتور', 'P3: محور ورودی گیربکس',
                'P4: سمت آزاد محور ورودی', 'P5: سمت فیکس محور دوم', 'P6: سمت آزاد محور دوم',
                'P7: سمت فیکس محور سوم', 'P8: سمت آزاد محور سوم', 'P9: بابیت اول سمت گیربکس',
                'P10: بابیت دوم', 'P11: بابیت نزدیک پینیون آسیاب']
    if 'کراشر' in name or 'سنگ شکن' in name:
        return ['P1: انتهای موتور', 'P2: سر موتور', 'P3: یاتاقان سمت فیکس (پولی کوچک)',
                'P4: یاتاقان سمت آزاد (پولی کوچک)', 'P5: یاتاقان فیکس (روتور)',
                'P6: یاتاقان سمت آزاد (روتور)']
    if 'فن' in name:
        return ['P1: انتهای موتور', 'P2: سر موتور', 'P3: یاتاقان فیکس', 'P4: یاتاقان آزاد']
    return []

# --- سازنده‌های HTML با ایزوله‌سازی جهت متن (حل به‌هم‌ریختگی) ---
def spec_box(label, value):
    return (
        "<div style='background:#ffffff; border:1px solid #d7e3f7; border-radius:10px; "
        "padding:9px 14px; direction:rtl; unicode-bidi:isolate; text-align:right; min-width:150px;'>"
        f"<div style='font-size:12px; color:#7d8ea8; font-family:Tahoma;'>{label}</div>"
        f"<div style='font-size:15px; color:#1E3A8D; font-weight:bold; margin-top:3px; "
        f"font-family:Tahoma; unicode-bidi:isolate;'>{value}</div>"
        "</div>"
    )

def point_chip(text):
    return (
        "<div style='background:#ffffff; border:1px solid #cfdcf5; border-radius:20px; "
        "padding:5px 14px; font-size:14px; color:#1E3A8D; font-family:Tahoma; "
        "direction:rtl; unicode-bidi:isolate; white-space:nowrap;'>"
        f"{text}"
        "</div>"
    )

def render_points(items):
    if not items:
        return ("<div style='font-size:14px; color:#8a97ad; font-family:Tahoma; direction:rtl;'>"
                "راهنمای نقاط برای این نوع تجهیز تعریف نشده است.</div>")
    chips = ''.join(point_chip(i) for i in items)
    return ("<div style='display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; "
            "justify-content:flex-start;'>" + chips + "</div>")

ANN_STYLES = {
    'danger': ('#fdecec', '#e53935', '#b71c1c', '🚨'),
    'warning': ('#fff8e1', '#f9a825', '#8d6e00', '⚠️'),
    'success': ('#eaf7ec', '#2e7d32', '#1b5e20', '✅'),
    'info': ('#eaf1fb', '#1E3A8D', '#14295f', 'ℹ️'),
}

def ann_kind(t):
    s = norm(t)
    if any(k in s for k in ['خطر', 'بحرانی', 'اضطراری', 'critical', 'danger']): return 'danger'
    if any(k in s for k in ['هشدار', 'اخطار', 'warning', 'alert']): return 'warning'
    if any(k in s for k in ['اطلاعیه', 'موفق', 'گزارش', 'success', 'info']): return 'success'
    return 'info'

def render_announcement(title, text, kind, label, start_txt, end_txt):
    bg, border, dark, icon = ANN_STYLES.get(kind, ANN_STYLES['info'])
    date_line = ''
    if start_txt or end_txt:
        s = f'از {start_txt}' if start_txt else ''
        e = f' تا {end_txt}' if end_txt else ''
        date_line = (f"<div style='font-size:12px; color:{dark}; opacity:.75; margin-top:8px; "
                     f"font-family:Tahoma; direction:rtl; unicode-bidi:isolate;'>🗓{s}{e}</div>")
    badge = ''
    if label:
        badge = (f"<span style='background:{border}; color:#fff; padding:3px 12px; border-radius:12px; "
                 f"font-size:12px; font-family:Tahoma; white-space:nowrap; "
                 f"unicode-bidi:isolate;'>{label}</span>")
    return (
        f"<div style='background:{bg}; border-right:8px solid {border}; border-radius:12px; "
        f"padding:14px 18px; margin-bottom:12px; direction:rtl; text-align:right; "
        f"box-shadow:0 2px 6px rgba(0,0,0,.05);'>"
        f"<div style='display:flex; justify-content:space-between; align-items:center; gap:12px; "
        f"flex-wrap:wrap;'>"
        f"<div style='font-size:17px; font-weight:bold; color:{dark}; font-family:Tahoma; "
        f"unicode-bidi:isolate;'>{icon} {title}</div>"
        f"{badge}</div>"
        f"<div style='margin-top:8px; font-size:14.5px; color:#333; line-height:1.9; "
        f"font-family:Tahoma; unicode-bidi:plaintext;'>{text}</div>"
        f"{date_line}"
        "</div>"
    )

# ==============================================================================
# 3. بارگذاری داده‌ها
# ==============================================================================
BASE = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid='
VIB_URL = BASE + '0'
ASSETS_URL = BASE + '1276803564'
ANN_URL = BASE + '2057447521'

@st.cache_data(ttl=600)
def load_all_data():
    df_vib, df_assets, df_ann = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        df_vib = pd.read_csv(VIB_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception:
        pass
    try:
        df_assets = pd.read_csv(ASSETS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception:
        pass
    try:
        df_ann = pd.read_csv(ANN_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception:
        pass
    return df_vib, df_assets, df_ann

df, df_assets, df_ann = load_all_data()

# ==============================================================================
# 4. هدر
# ==============================================================================
logo_siman = get_image_base64('client_logo.png')
logo_faz = get_image_base64('my_logo.png')

st.markdown(f'''
<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;
            background:white; padding:14px 28px; border-radius:15px;
            box-shadow:0 4px 8px rgba(0,0,0,0.08);'>
    <img src='data:image/png;base64,{logo_faz}' style='width:105px; height:auto;'>
    <div style='text-align:center; color:#1E3A8D; font-size:25px; font-weight:bold;
                font-family:Tahoma;'>🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران</div>
    <img src='data:image/png;base64,{logo_siman}' style='width:105px; height:auto;'>
</div>
''', unsafe_allow_html=True)

# ==============================================================================
# 5. اعلانیه‌ها و هشدارها (از شیت جداگانه + فیلتر تاریخ خودکار)
# ==============================================================================
if not df_ann.empty:
    c_title = smart_find_column(df_ann.columns, ['عنوان'])
    c_text = smart_find_column(df_ann.columns, ['متن', 'محتوا', 'توضیحات'])
    c_type = smart_find_column(df_ann.columns, ['نوع'])
    c_active = smart_find_column(df_ann.columns, ['فعال'])
    c_start = smart_find_column(df_ann.columns, ['تاریخ شروع', 'شروع'])
    c_end = smart_find_column(df_ann.columns, ['تاریخ انقضا', 'انقضا', 'پایان'])
    c_label = smart_find_column(df_ann.columns, ['برچسب', 'تگ'])

    if c_title and c_text:
        tkey = today_jkey()
        shown = 0
        cards = []

        for _, row in df_ann.iterrows():
            if c_active and not is_true_flag(row[c_active]):
                continue
            if c_start:
                sk = date_key_from_text(row[c_start])
                if sk and tkey < sk:
                    continue
            if c_end:
                ek = date_key_from_text(row[c_end])
                if ek and tkey > ek:
                    continue

            title = str(row[c_title]).strip()
            if not title:
                continue

            cards.append(render_announcement(
                title=title,
                text=str(row[c_text]).strip(),
                kind=ann_kind(row[c_type] if c_type else ''),
                label=str(row[c_label]).strip() if c_label else '',
                start_txt=str(row[c_start]).strip() if c_start else '',
                end_txt=str(row[c_end]).strip() if c_end else '',
            ))
            shown += 1

        if shown:
            st.markdown(
                f"<div style='font-size:13px; color:#7d8ea8; font-family:Tahoma; direction:rtl; "
                f"margin-bottom:8px;'>📌 اعلانیه‌های فعال — امروز {jalali_today_str()} "
                f"({shown} مورد)</div>",
                unsafe_allow_html=True
            )
            st.markdown(''.join(cards), unsafe_allow_html=True)
        else:
            st.markdown(
                "<div style='background:#eaf7ec; border-right:8px solid #2e7d32; border-radius:12px; "
                "padding:12px 18px; font-family:Tahoma; color:#1b5e20; direction:rtl;'>"
                "✅ در حال حاضر اعلانیه فعالی وجود ندارد.</div>",
                unsafe_allow_html=True
            )
    else:
        st.info('ℹ️ ستون‌های «عنوان» و «متن» در شیت اعلانیه پیدا نشد.')
else:
    st.warning('⚠️ شیت اعلانیه خوانده نشد. دسترسی را روی Anyone with the link بگذارید.')

# ==============================================================================
# 6. فیلترهای سایدبار
# ==============================================================================
st.sidebar.header('🔍 فیلترهای پیشرفته')

if not df.empty:
    col_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
    col_unit = smart_find_column(df.columns, ['واحد'])
    equip_col = smart_find_column(df.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'Asset', 'Equipment'])
    date_col = smart_find_column(df.columns, ['تاریخ', 'Date'])

    df['_k_line'] = df[col_line].map(norm) if col_line else ''
    df['_k_unit'] = df[col_unit].map(norm) if col_unit else ''
    df['_k_eq'] = df[equip_col].map(norm) if equip_col else ''
    df['_k_date'] = df[date_col].map(norm) if date_col else ''
    df['_dkey'] = df[date_col].map(date_key_from_text) if date_col else 0

    def _mode(series):
        v = series.astype(str).str.strip()
        v = v[v != '']
        return v.value_counts().idxmax() if not v.empty else ''

    def display_map(key_col, original_col):
        if original_col is None: return {}
        tmp = df[df[key_col] != '']
        if tmp.empty: return {}
        return tmp.groupby(key_col)[original_col].agg(_mode).to_dict()

    line_map = display_map('_k_line', col_line)
    unit_map = display_map('_k_unit', col_unit)
    eq_map = display_map('_k_eq', equip_col)

    sel_line_k = st.sidebar.selectbox(
        '📍 خط تولید:', ['همه'] + sorted(line_map.keys()),
        format_func=lambda k: 'همه' if k == 'همه' else line_map.get(k, k))

    tmp_u = df.copy()
    if sel_line_k != 'همه':
        tmp_u = tmp_u[tmp_u['_k_line'] == sel_line_k]
    unit_keys = sorted([u for u in tmp_u['_k_unit'].unique() if u != ''])
    sel_unit_k = st.sidebar.selectbox(
        '🏢 واحد:', ['همه'] + unit_keys,
        format_func=lambda k: 'همه' if k == 'همه' else unit_map.get(k, k))

    if sel_unit_k != 'همه':
        tmp_u = tmp_u[tmp_u['_k_unit'] == sel_unit_k]
    eq_keys = sorted([e for e in tmp_u['_k_eq'].unique() if e != ''])
    sel_eq_k = st.sidebar.selectbox(
        '⚙️ انتخاب تجهیز:', ['همه تجهیزات'] + eq_keys,
        format_func=lambda k: 'همه تجهیزات' if k == 'همه تجهیزات' else eq_map.get(k, k))

    search_eq = st.sidebar.text_input('🔎 جستجوی سریع تجهیز:', placeholder='مثلاً: میل فن')

    st.sidebar.markdown('**📅 فیلتر تاریخ**')
    date_map = {}
    if date_col:
        tmp_d = df[df['_k_date'] != '']
        if not tmp_d.empty:
            date_map = tmp_d.groupby('_k_date')[date_col].agg(_mode).to_dict()
    date_keys = sorted(list(date_map.keys()), reverse=True)
    sel_date_k = st.sidebar.selectbox(
        '🌙 انتخاب تاریخ:', ['همه تاریخ‌ها'] + date_keys,
        format_func=lambda k: 'همه تاریخ‌ها' if k == 'همه تاریخ‌ها' else date_map.get(k, k))

    fdf = df.copy()
    if sel_line_k != 'همه': fdf = fdf[fdf['_k_line'] == sel_line_k]
    if sel_unit_k != 'همه': fdf = fdf[fdf['_k_unit'] == sel_unit_k]
    if sel_eq_k != 'همه تجهیزات': fdf = fdf[fdf['_k_eq'] == sel_eq_k]
    if search_eq.strip():
        tokens = [t for t in norm(search_eq).split() if t]
        if tokens:
            fdf = fdf[fdf['_k_eq'].map(lambda v: all(t in v for t in tokens))]
    if sel_date_k != 'همه تاریخ‌ها': fdf = fdf[fdf['_k_date'] == sel_date_k]
    if date_col: fdf = fdf.sort_values(by='_dkey', ascending=False)

    # ==========================================================================
    # 7. نمایش اصلی
    # ==========================================================================
    st.title('📊 تحلیل روند ارتعاشات تجهیزات')

    visible_cols = [c for c in df.columns if not str(c).startswith('_')]
    vib_cols = [
        c for c in visible_cols
        if any(k in norm(c) for k in ['عمودی', 'افقی', 'محوری'])
        or re.match(r'^p\s*\d+', norm(c))
    ]

    # --- کارت مشخصات فنی ---
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
                    rows = df_assets[n_assets.map(lambda x: x != '' and (sel_eq_k in x or x in sel_eq_k))]

                if not rows.empty:
                    matched = True
                    r0 = rows.iloc[0]

                    def gv(keys, default='---'):
                        c = smart_find_column(df_assets.columns, keys)
                        if not c: return default
                        v = str(r0[c]).strip()
                        return v if v not in ('', 'nan', 'None', 'NaN') else default

                    e_type = gv(['نوع تجهیز', 'نوع'])
                    e_rpm = gv(['دور گردش', 'دور', 'RPM', 'سرعت'])
                    e_line = gv(['خط تولید', 'خط'])
                    e_unit = gv(['واحد'])
                    e_drive = gv(['نوع انتقال', 'انتقال قدرت', 'سیستم انتقال', 'کوپلینگ',
                                  'کوپل', 'اتصال', 'درایو', 'تسمه', 'پولی'])
                    e_brg = gv(['شماره بیرینگ', 'بیرینگ', 'برینگ', 'Bearing'])
                    e_bush = gv(['شماره بوش', 'بوش', 'Bush'])

                    boxes = ''.join([
                        spec_box('نوع تجهیز', e_type),
                        spec_box('دور گردش (RPM)', e_rpm),
                        spec_box('خط تولید', e_line),
                        spec_box('واحد', e_unit),
                        spec_box('نوع انتقال قدرت', e_drive),
                        spec_box('شماره بیرینگ', e_brg),
                        spec_box('شماره بوش', e_bush),
                    ])

                    st.markdown(
                        "<div style='background:#f0f7ff; padding:20px 24px; border-radius:15px; "
                        "border-right:10px solid #1E3A8D; margin-bottom:18px; direction:rtl; "
                        "text-align:right; box-shadow:0 2px 8px rgba(0,0,0,.06);'>"
                        "<div style='color:#1E3A8D; font-size:19px; font-weight:bold; font-family:Tahoma; "
                        "margin-bottom:14px; unicode-bidi:isolate;'>"
                        f"🛠️ مشخصات فنی: {eq_display}</div>"
                        "<div style='display:flex; flex-wrap:wrap; gap:10px;'>"
                        f"{boxes}</div>"
                        "<div style='margin-top:16px; background:#e6efff; border-radius:10px; "
                        "padding:12px 16px; direction:rtl;'>"
                        "<div style='font-size:14px; color:#1E3A8D; font-weight:bold; "
                        "font-family:Tahoma;'>📍 راهنمای نقاط (P-Map)</div>"
                        f"{render_points(get_point_items(eq_display, e_type))}"
                        "</div>"
                        "</div>",
                        unsafe_allow_html=True
                    )

                    pts = smart_find_column(df_assets.columns, ['نقطه', 'پوینت', 'Point'])
                    brg = smart_find_column(df_assets.columns, ['بیرینگ', 'برینگ', 'Bearing'])
                    bsh = smart_find_column(df_assets.columns, ['بوش', 'Bush'])
                    log_cols = [c for c in [pts, brg, bsh] if c]

                    if log_cols:
                        logistics = rows[log_cols].copy()
                        logistics = logistics.replace({'': '---', 'nan': '---', 'None': '---', 'NaN': '---'})
                        rename = {}
                        if pts: rename[pts] = 'نقطه اندازه‌گیری'
                        if brg: rename[brg] = 'شماره بیرینگ'
                        if bsh: rename[bsh] = 'شماره بوش'
                        logistics = logistics.rename(columns=rename)
                        with st.expander('📦 اطلاعات قطعات و لجستیک (بیرینگ / بوش)', expanded=True):
                            st.dataframe(
                                logistics.style.set_properties(
                                    **{'direction': 'rtl', 'text-align': 'right', 'font-family': 'Tahoma'}),
                                hide_index=True, use_container_width=True)

                    with st.expander('📋 مشاهده تمام مشخصات ثبت‌شده این تجهیز', expanded=False):
                        full = pd.DataFrame({
                            'عنوان': list(df_assets.columns),
                            'مقدار': [str(x).strip() for x in r0.values]
                        })
                        full = full[~full['مقدار'].isin(['', 'nan', 'None', 'NaN'])]
                        st.dataframe(
                            full.style.set_properties(
                                **{'direction': 'rtl', 'text-align': 'right', 'font-family': 'Tahoma'}),
                            hide_index=True, use_container_width=True)

        if not matched:
            st.info('ℹ️ برای این تجهیز، ردیفی در شیت مشخصات فنی (Assets) پیدا نشد.')

    # --- جدول ارتعاشات ---
    if not fdf.empty:
        st.markdown(f'### 📋 داده‌های ارتعاشات ({len(fdf)} مورد)')

        def color_vib(val):
            try:
                v = float(clean_num_text(val))
                if v > 7.1: return 'background-color:#ff4b4b; color:white; font-weight:bold;'
                if v > 4.5: return 'background-color:#ffa500; color:white; font-weight:bold;'
                return 'background-color:#2e7d32; color:white;'
            except Exception:
                return ''

        table = fdf[visible_cols].copy()
        styler = table.style
        if vib_cols:
            styler = styler.map(color_vib, subset=vib_cols)
        styler = styler.set_properties(
            **{'direction': 'rtl', 'text-align': 'right', 'font-family': 'Tahoma'})
        st.dataframe(styler, use_container_width=True, hide_index=True)

        if vib_cols and not fdf.empty:
            legend = ("<div style='display:flex; gap:18px; flex-wrap:wrap; font-family:Tahoma; "
                      "font-size:13px; direction:rtl; margin:6px 0 10px 0;'>"
                      "<span>🟢 سالم (≤ 4.5)</span>"
                      "<span>🟠 هشدار (4.5 – 7.1)</span>"
                      "<span>🔴 بحرانی (&gt; 7.1)</span></div>")
            st.markdown(legend, unsafe_allow_html=True)

        # --- نمودار روند ---
        if vib_cols and sel_eq_k != 'همه تجهیزات' and date_col and len(fdf) > 1:
            with st.expander('📈 نمودار روند ارتعاشات این تجهیز در طول زمان', expanded=False):
                trend = fdf[[date_col] + vib_cols].copy()
                trend['_dkey'] = trend[date_col].map(date_key_from_text)
                trend = trend.sort_values('_dkey')
                trend['تاریخ'] = trend[date_col].astype(str)

                long_df = trend.melt(id_vars=['تاریخ', '_dkey'], value_vars=vib_cols,
                                     var_name='نقطه/جهت', value_name='ارتعاش')
                long_df['ارتعاش'] = to_num(long_df['ارتعاش'])
                long_df = long_df.dropna(subset=['ارتعاش'])

                if not long_df.empty:
                    fig = px.line(long_df, x='تاریخ', y='ارتعاش', color='نقطه/جهت',
                                  markers=True, title='روند ارتعاش (mm/s)')
                    fig.add_hline(y=4.5, line_dash='dash', line_color='orange',
                                  annotation_text='حد هشدار')
                    fig.add_hline(y=7.1, line_dash='dash', line_color='red',
                                  annotation_text='حد بحرانی')
                    fig.update_layout(font=dict(family='Tahoma', size=13))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info('داده عددی برای رسم نمودار وجود ندارد.')

        # --- نمودار دایره‌ای سلامت ---
        st.markdown('---')
        st.markdown('### 📈 تحلیل وضعیت سلامت تجهیزات')
        with st.expander('نمایش نمودار دایره‌ای وضعیت سلامت', expanded=False):
            if vib_cols:
                v_max = fdf[vib_cols].apply(to_num, axis=0).max(axis=1)

                def cat(v):
                    if pd.isna(v): return 'نامشخص'
                    if v > 7.1: return 'بحرانی'
                    if v > 4.5: return 'هشدار'
                    return 'سالم'

                status = v_max.map(cat).value_counts()
                if not status.empty:
                    fig_pie = px.pie(
                        values=status.values, names=status.index, color=status.index,
                        color_discrete_map={'سالم': '#2e7d32', 'هشدار': '#ffa500',
                                            'بحرانی': '#ff4b4b', 'نامشخص': '#9e9e9e'},
                        hole=0.35)
                    fig_pie.update_traces(textinfo='percent+label')
                    fig_pie.update_layout(font=dict(family='Tahoma', size=13))
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info('داده‌ای برای تحلیل سلامت یافت نشد.')
            else:
                st.info('ستون‌های ارتعاشات یافت نشد.')
    else:
        st.warning('⚠️ هیچ داده‌ای با این فیلترها پیدا نشد.')

    st.markdown(
        '<div style="text-align:center; margin-top:50px; color:#555; font-family:Tahoma;">'
        'طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>',
        unsafe_allow_html=True
    )
else:
    st.error('❌ خطا در دریافت داده‌ها از گوگل‌شیت.')
