import re
import html
import pandas as pd
import streamlit as st
import base64
import plotly.express as px

# ==============================================================================
# 0. تنظیمات صفحه
# ==============================================================================
st.set_page_config(page_title='داشبورد فنی ارتعاشات سیمان تهران',
                   page_icon='📊', layout='wide')

# ==============================================================================
# 1. ورود کاربران
# ==============================================================================
USER_CREDENTIALS = {
    'alireza76ir@gmail.com': 'siman123',
    'vah.rezaei@gmail.com': 'siman123',
    'cm.zandiyeh@gmail.com': 'siman123',
    'me.vibration.shokri@gmail.com': 'siman123',
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
    s = str(x).strip()
    if s == '':
        return ''
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = (s.replace('ي', 'ی').replace('ى', 'ی').replace('ك', 'ک')
          .replace('ۀ', 'ه').replace('ة', 'ه').replace('أ', 'ا').replace('إ', 'ا'))
    s = (s.replace('\u200c', ' ').replace('\xa0', ' ')
          .replace('-', ' ').replace('_', ' ').replace('.', ' ').replace('ـ', ' '))
    return ' '.join(s.split()).lower()

def clean_num_text(x):
    s = str(x).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = s.replace('٫', '.').replace('،', '.').replace(',', '.').replace(' ', '')
    return s

def to_num(x):
    try:
        return float(clean_num_text(x))
    except Exception:
        return None

def date_sort_key(val):
    s = norm(val)
    m = re.search(r'(\d{2,4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})', s)
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 1400
            return int(f"{y}{mo:02d}{d:02d}")
        except Exception:
            return 0
    return 0

def point_num(val):
    m = re.search(r'(\d+)', norm(val))
    return int(m.group(1)) if m else 999

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
        if nk == '':
            continue
        for c in cols:
            if normed[c] == nk:
                return c
    for k in keywords:
        nk = norm(k)
        if nk == '':
            continue
        for c in cols:
            if nk in normed[c]:
                return c
    return None

def build_display_map(df, key_col, orig_col):
    """نگاشت کلید نرمال‌شده به نام اصلی برای نمایش در فیلترها"""
    m = {}
    if df.empty or key_col not in df.columns:
        return m
    src = orig_col if (orig_col and orig_col in df.columns) else key_col
    for k, o in zip(df[key_col], df[src]):
        o = str(o).strip()
        if k and k not in m and o:
            m[k] = o
    return m

def find_asset_row(df_assets, name_key):
    if df_assets.empty or not name_key:
        return None
    a_name = smart_find_column(df_assets.columns,
                               ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'asset', 'equipment', 'نام دستگاه'])
    if not a_name:
        return None
    keys = df_assets[a_name].map(norm)
    exact = df_assets[keys == name_key]
    if not exact.empty:
        return exact.iloc[0]
    mask = keys.map(lambda k: k != '' and (name_key in k or k in name_key))
    cont = df_assets[mask]
    if not cont.empty:
        tmp = cont.copy()
        tmp['_dist'] = tmp[a_name].map(lambda x: abs(len(norm(x)) - len(name_key)))
        return tmp.sort_values('_dist').iloc[0]
    return None

def asset_items(row, df_assets):
    items = []
    if row is None:
        return items
    for c in df_assets.columns:
        try:
            v = str(row[c]).strip()
        except Exception:
            v = ''
        if v == '' or v.lower() in ('nan', 'none', 'nat'):
            continue
        items.append((str(c).strip(), v))
    return items

def colorize(df_show, cols, fn):
    sty = df_show.style
    cols = [c for c in cols if c in df_show.columns]
    try:
        return sty.map(fn, subset=cols)
    except Exception:
        return sty.applymap(fn, subset=cols)

def cell_html(value, is_numeric, warn, crit):
    v = to_num(value) if is_numeric else None
    style = 'padding:6px 8px;border:1px solid #d9d9d9;text-align:center;font-size:12px;'
    if v is not None:
        if v >= crit:
            style += 'background:#ff4b4b;color:#fff;font-weight:bold;'
        elif v >= warn:
            style += 'background:#ffa500;color:#fff;font-weight:bold;'
        else:
            style += 'background:#2e7d32;color:#fff;'
    return f'<td style="{style}">{html.escape(str(value))}</td>'

def build_report_html(eq_title, asset_items_list, df_show, cols, numeric_cols, warn, crit, extra_meta=''):
    head = ''.join(
        f'<th style="padding:8px;border:1px solid #bbb;background:#1E3A8D;color:#fff;font-size:12px;">'
        f'{html.escape(str(c))}</th>' for c in cols
    )
    rows_html = []
    for _, r in df_show.iterrows():
        tds = ''.join(cell_html(r[c], c in numeric_cols, warn, crit) for c in cols)
        rows_html.append(f'<tr>{tds}</tr>')

    asset_html = ''
    if asset_items_list:
        rows_a = ''.join(
            f'<tr><td style="padding:6px 8px;border:1px solid #d9d9d9;background:#f2f5fa;'
            f'font-weight:bold;width:32%;font-size:12px;">{html.escape(str(k))}</td>'
            f'<td style="padding:6px 8px;border:1px solid #d9d9d9;font-size:12px;">{html.escape(str(v))}</td></tr>'
            for k, v in asset_items_list
        )
        asset_html = f'''
        <h2 style="color:#1E3A8D;font-size:16px;margin-top:24px;">مشخصات فنی تجهیز</h2>
        <table style="border-collapse:collapse;width:100%;">{rows_a}</table>
        '''

    return f'''<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<title>گزارش پایش وضعیت - {html.escape(eq_title)}</title>
<style>
  body {{ font-family: Tahoma, Arial, sans-serif; padding: 22px; background:#fff; color:#222; }}
  h1 {{ font-size: 18px; color:#1E3A8D; margin: 0 0 4px 0; }}
  .sub {{ font-size: 12px; color:#555; margin-bottom: 14px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  @media print {{ body {{ padding: 8px; }} }}
</style>
</head>
<body>
  <h1>🛠️ گزارش پایش وضعیت تجهیزات — سیمان تهران</h1>
  <div class="sub">{html.escape(eq_title)} &nbsp;|&nbsp; {html.escape(extra_meta)} &nbsp;|&nbsp;
     حد هشدار: {warn} &nbsp; حد بحرانی: {crit} &nbsp;|&nbsp; تعداد ردیف: {len(df_show)}</div>
  {asset_html}
  <h2 style="color:#1E3A8D;font-size:16px;margin-top:24px;">داده‌های ارتعاشات</h2>
  <table>
    <thead><tr>{head}</tr></thead>
    <tbody>{''.join(rows_html)}</tbody>
  </table>
  <p style="margin-top:22px;font-size:11px;color:#777;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</p>
</body>
</html>'''

# ==============================================================================
# 3. بارگذاری داده‌ها
# ==============================================================================
VIB_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0'
ASSETS_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=1276803564'
ANN_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=2057447521'

@st.cache_data(ttl=600)
def load_data():
    try:
        df_v = pd.read_csv(VIB_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception:
        df_v = pd.DataFrame()
    try:
        df_a = pd.read_csv(ASSETS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception:
        df_a = pd.DataFrame()
    try:
        df_ann = pd.read_csv(ANN_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception:
        df_ann = pd.DataFrame()
    return df_v, df_a, df_ann

df_raw, df_assets, df_ann = load_data()

# --- شناسایی ستون‌های شیت ارتعاشات ---
c_date  = smart_find_column(df_raw.columns, ['تاریخ', 'date'])
c_line  = smart_find_column(df_raw.columns, ['خط تولید', 'خط'])
c_unit  = smart_find_column(df_raw.columns, ['واحد'])
c_equip = smart_find_column(df_raw.columns, ['عنوان تجهیز', 'نام تجهیز', 'تجهیز', 'asset'])
c_point = smart_find_column(df_raw.columns, ['محل اندازه گیری', 'محل اندازه‌گیری', 'نقطه', 'point'])
c_rpm   = smart_find_column(df_raw.columns, ['دور', 'rpm'])

DIRECTION_COLS = [c for c in df_raw.columns if any(k in norm(c) for k in ['عمودی', 'افقی', 'محوری', 'mm s', 'mm/s'])]
P_COLS = [c for c in df_raw.columns if re.search(r'p\s*\d+', norm(c))]
vib_cols = []
for c in DIRECTION_COLS + P_COLS:
    if c not in vib_cols:
        vib_cols.append(c)

if not df_raw.empty:
    df_raw['_k_line'] = df_raw[c_line].map(norm) if c_line else ''
    df_raw['_k_unit'] = df_raw[c_unit].map(norm) if c_unit else ''
    df_raw['_k_eq']   = df_raw[c_equip].map(norm) if c_equip else ''
    df_raw['_k_date'] = df_raw[c_date].map(norm) if c_date else ''
    df_raw['_dkey']   = df_raw[c_date].map(date_sort_key) if c_date else 0
    df_raw['_pnum']   = df_raw[c_point].map(point_num) if c_point else 999

# --- نگاشت نام‌های نمایشی ---
line_map = build_display_map(df_raw, '_k_line', c_line)
unit_map = build_display_map(df_raw, '_k_unit', c_unit)
eq_map   = build_display_map(df_raw, '_k_eq', c_equip)
date_map = build_display_map(df_raw, '_k_date', c_date)

def label(mapping, k, empty_label):
    if k == '':
        return empty_label
    return mapping.get(k, k)

# ==============================================================================
# 4. هدر
# ==============================================================================
logo_siman = get_image_base64('client_logo.png')
logo_faz = get_image_base64('my_logo.png')

st.markdown(f'''
<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;
            background:white; padding:14px 26px; border-radius:15px;
            box-shadow:0 4px 8px rgba(0,0,0,0.08);'>
    <img src='data:image/png;base64,{logo_faz}' style='width:105px; height:auto;'>
    <div style='text-align:center; color:#1E3A8D; font-size:24px; font-weight:bold; font-family:Tahoma;'>
        🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران
    </div>
    <img src='data:image/png;base64,{logo_siman}' style='width:105px; height:auto;'>
</div>
''', unsafe_allow_html=True)

# ==============================================================================
# 5. اعلانیه‌ها
# ==============================================================================
if not df_ann.empty:
    c_tit = smart_find_column(df_ann.columns, ['عنوان', 'title'])
    c_txt = smart_find_column(df_ann.columns, ['متن', 'text'])
    c_typ = smart_find_column(df_ann.columns, ['نوع', 'type'])
    c_act = smart_find_column(df_ann.columns, ['فعال', 'active'])
    if c_tit and c_txt:
        for _, row in df_ann.iterrows():
            if c_act and str(row[c_act]).strip() != 'بله':
                continue
            t = str(row[c_tit]).strip()
            txt = str(row[c_txt]).strip()
            if t == '' and txt == '':
                continue
            typ = str(row[c_typ]) if c_typ else ''
            if any(x in typ for x in ['خطر', 'بحرانی']):
                color, icon = '#ff4b4b', '🚨'
            elif 'موفق' in typ:
                color, icon = '#2e7d32', '✅'
            else:
                color, icon = '#1E3A8D', 'ℹ️'
            st.markdown(
                f'<div style="background:{color}; padding:11px 14px; border-radius:10px; margin-bottom:8px;'
                f'color:white; direction:rtl; text-align:right; font-family:Tahoma;">'
                f'<b>{icon} {html.escape(t)}</b><br><small>{html.escape(txt)}</small></div>',
                unsafe_allow_html=True)

# ==============================================================================
# 6. سایدبار — فیلترهای آبشاری (خط ← واحد ← تجهیز)
# ==============================================================================
st.sidebar.header('🔍 فیلترها')

sel_line = ''
sel_unit = ''
sel_eq = ''
search_txt = ''
sel_date = ''

if not df_raw.empty:
    # --- خط تولید ---
    line_keys = sorted([k for k in df_raw['_k_line'].unique() if k != ''])
    sel_line = st.sidebar.selectbox(
        '📍 خط تولید:', [''] + line_keys,
        format_func=lambda k: label(line_map, k, 'همه خطوط'))

    base_line = df_raw if sel_line == '' else df_raw[df_raw['_k_line'] == sel_line]

    # --- واحد (فقط واحدهای همان خط) ---
    unit_keys = sorted([k for k in base_line['_k_unit'].unique() if k != ''])
    if unit_keys:
        sel_unit = st.sidebar.selectbox(
            '🏢 واحد:', [''] + unit_keys,
            format_func=lambda k: label(unit_map, k, 'همه واحدها'))
    base_unit = base_line if sel_unit == '' else base_line[base_line['_k_unit'] == sel_unit]

    # --- تجهیز (فقط تجهیزات همان واحد؛ اگر واحد انتخاب نشد، همان خط) ---
    eq_keys = sorted([k for k in base_unit['_k_eq'].unique() if k != ''])
    if eq_keys:
        sel_eq = st.sidebar.selectbox(
            '⚙️ تجهیز:', [''] + eq_keys,
            format_func=lambda k: label(eq_map, k, 'همه تجهیزات'))
    base_eq = base_unit if sel_eq == '' else base_unit[base_unit['_k_eq'] == sel_eq]

    # --- جستجوی سریع داخل همان محدوده ---
    search_txt = st.sidebar.text_input('🔎 جستجوی سریع تجهیز (داخل محدوده انتخاب‌شده):')
    if search_txt:
        q = norm(search_txt)
        found_keys = [k for k in base_eq['_k_eq'].unique() if q in k]
        base_eq = base_eq[base_eq['_k_eq'].isin(found_keys)]

    # --- تاریخ (فقط تاریخ‌های همین محدوده) ---
    date_keys = sorted([k for k in base_eq['_k_date'].unique() if k != ''], reverse=True)
    if date_keys:
        sel_date = st.sidebar.selectbox(
            '🌙 تاریخ:', [''] + date_keys,
            format_func=lambda k: label(date_map, k, 'همه تاریخ‌ها'))

    fdf = base_eq.copy()
    if sel_date != '':
        fdf = fdf[fdf['_k_date'] == sel_date]

    # --- ترتیب نمایش ---
    st.sidebar.markdown('---')
    st.sidebar.header('🗂️ ترتیب نمایش')
    sort_mode = st.sidebar.radio(
        'مرتب‌سازی بر اساس:',
        ['گروه‌بندی تجهیز (نقاط پشت سر هم)', 'تاریخ (جدیدترین اول)'],
        index=0)

    if sort_mode.startswith('گروه‌بندی'):
        fdf = fdf.sort_values(['_k_eq', '_pnum', '_dkey'], ascending=[True, True, False])
    else:
        fdf = fdf.sort_values(['_dkey', '_k_eq', '_pnum'], ascending=[False, True, True])

    # --- حدود هشدار ---
    st.sidebar.markdown('---')
    st.sidebar.header('⚠️ حدود هشدار')
    warn_limit = st.sidebar.number_input('حد هشدار (نارنجی)', 0.0, 50.0, 4.5, 0.1)
    crit_limit = st.sidebar.number_input('حد بحرانی (قرمز)', 0.0, 50.0, 7.1, 0.1)

    # --- تنظیمات نمودار ---
    st.sidebar.markdown('---')
    st.sidebar.header('📈 نمودار روند')
    show_chart = st.sidebar.checkbox('نمایش نمودار', value=False)
    chart_modes = st.sidebar.multiselect('جهت‌های نمایش:', ['عمودی', 'افقی', 'محوری'],
                                         default=['عمودی', 'افقی', 'محوری'])
    # --- پنل عیب‌یابی ---
    with st.sidebar.expander('🩺 عیب‌یابی داده'):
        st.write('ستون تاریخ:', c_date)
        st.write('ستون خط:', c_line)
        st.write('ستون واحد:', c_unit)
        st.write('ستون تجهیز:', c_equip)
        st.write('ستون نقطه:', c_point)
        st.write('ستون‌های ارتعاش:', len(vib_cols))
        st.write(vib_cols[:8])
        st.write('تعداد ردیف خام:', len(df_raw))

# ==============================================================================
# 7. بدنه اصلی
# ==============================================================================
if df_raw.empty:
    st.error('❌ داده‌ای از شیت ارتعاشات خوانده نشد.')
    st.stop()

st.title('📊 تحلیل ارتعاشات تجهیزات')

# --- کارت‌های خلاصه ---
num_checked = 0
num_warn = 0
num_crit = 0
for _, r in fdf.iterrows():
    for c in vib_cols:
        if c not in fdf.columns:
            continue
        v = to_num(r[c])
        if v is None:
            continue
        num_checked += 1
        if v >= crit_limit:
            num_crit += 1
        elif v >= warn_limit:
            num_warn += 1

k1, k2, k3, k4 = st.columns(4)
k1.metric('تعداد ردیف', len(fdf))
k2.metric('قرائت‌های نرمال', max(num_checked - num_warn - num_crit, 0))
k3.metric('هشدار (نارنجی)', num_warn)
k4.metric('بحرانی (قرمز)', num_crit)

# --- پنل مشخصات فنی تجهیز (بالای جدول، زیر اعلانیه‌ها) ---
asset_show = []
if sel_eq != '':
    eq_title = eq_map.get(sel_eq, sel_eq)
    asset_row = find_asset_row(df_assets, sel_eq)
    asset_show = asset_items(asset_row, df_assets)

    if not df_assets.empty and not asset_show:
        asset_row = find_asset_row(df_assets, norm(search_txt)) if search_txt else None
        asset_show = asset_items(asset_row, df_assets)

    if asset_show:
        with st.expander(f'🛠️ مشخصات فنی تجهیز — {eq_title}', expanded=True):
            cols_grid = st.columns(3)
            for i, (k, v) in enumerate(asset_show):
                with cols_grid[i % 3]:
                    st.markdown(
                        f'<div style="background:#f4f7fc; border-right:4px solid #1E3A8D;'
                        f'padding:7px 10px; border-radius:7px; margin-bottom:7px;'
                        f'font-family:Tahoma; direction:rtl;">'
                        f'<div style="font-size:11px; color:#5a6b8c;">{html.escape(k)}</div>'
                        f'<div style="font-size:13px; color:#12224a; font-weight:bold;">{html.escape(v)}</div>'
                        f'</div>', unsafe_allow_html=True)
    else:
        st.info(f'ℹ️ برای «{eq_title}» ردیفی در شیت Assets پیدا نشد. '
                'نام تجهیز را در شیت Assets کمی نزدیک‌تر به نام شیت ارتعاشات بنویسد تا تطبیق انجام شود.')

# --- جدول اصلی ---
if fdf.empty:
    st.warning('برای فیلترهای انتخاب‌شده ردیفی وجود ندارد.')
else:
    vis_cols = [c for c in fdf.columns if not c.startswith('_')]
    numeric_cols = [c for c in vis_cols if c in vib_cols]

    def color_vib(val):
        v = to_num(val)
        if v is not None:
            if v >= crit_limit:
                return 'background-color:#ff4b4b; color:white'
            if v >= warn_limit:
                return 'background-color:#ffa500; color:white'
            return 'background-color:#2e7d32; color:white'
        return ''

    st.subheader(f'📋 جدول ارتعاشات — {len(fdf)} ردیف')
    st.dataframe(colorize(fdf[vis_cols], numeric_cols, color_vib),
                 use_container_width=True, hide_index=True)

    # --- نمودار ---
    if show_chart and c_date and len(fdf) > 0:
        with st.expander('📈 نمودار روند ارتعاشات', expanded=True):
            target = [c for c in vib_cols if any(m in norm(c) for m in [norm(x) for x in chart_modes])]
            target = [c for c in target if c in fdf.columns]
            if not target:
                st.warning('جهتی برای رسم نمودار انتخاب نشده است.')
            else:
                p_df = fdf[[c_date] + target + ['_dkey']].copy()
                p_df = p_df.sort_values('_dkey')
                long_df = p_df.melt(id_vars=[c_date, '_dkey'], value_vars=target,
                                    var_name='جهت / نقطه', value_name='مقدار')
                long_df['مقدار'] = long_df['مقدار'].apply(to_num)
                long_df = long_df.dropna(subset=['مقدار'])
                if long_df.empty:
                    st.warning('مقدار عددی برای رسم نمودار موجود نیست.')
                else:
                    fig = px.line(long_df, x=c_date, y='مقدار', color='جهت / نقطه',
                                  markers=True, title='روند ارتعاشات (mm/s)')
                    fig.add_hline(y=warn_limit, line_dash='dash', line_color='orange',
                                  annotation_text='هشدار')
                    fig.add_hline(y=crit_limit, line_dash='dash', line_color='red',
                                  annotation_text='بحرانی')
                    fig.update_layout(height=430, legend_title_text='')
                    st.plotly_chart(fig, use_container_width=True)

    # --- گزارش‌ها ---
    st.markdown('---')
    st.subheader('📑 گزارش‌گیری')
    eq_title = eq_map.get(sel_eq, sel_eq) if sel_eq else 'همه تجهیزات'
    meta = ''
    if sel_line:
        meta += f'خط: {line_map.get(sel_line, sel_line)}  '
    if sel_unit:
        meta += f'واحد: {unit_map.get(sel_unit, sel_unit)}  '
    if sel_date:
        meta += f'تاریخ: {date_map.get(sel_date, sel_date)}'

    rep_cols = [c for c in vis_cols]
    html_report = build_report_html(eq_title, asset_show, fdf, rep_cols,
                                    numeric_cols, warn_limit, crit_limit, meta)

    cA, cB = st.columns(2)
    cA.download_button('📄 دانلود گزارش چاپی (HTML)', data=html_report.encode('utf-8-sig'),
                       file_name='gozaresh_erteash.pdf.html' if False else 'gozaresh_erteashat.html',
                       mime='text/html', use_container_width=True)
    csv_bytes = fdf[vis_cols].to_csv(index=False).encode('utf-8-sig')
    cB.download_button('📥 دانلود داده‌ها (CSV)', data=csv_bytes,
                       file_name='erteashat.csv', mime='text/csv', use_container_width=True)
    st.caption('گزارش HTML را باز کن و با Ctrl+P به‌صورت PDF ذخیره کن؛ مشخصات فنی تجهیز '
               'و جدول رنگ‌بندی‌شده داخل همان گزارش هست.')

st.markdown(
    '<div style="text-align:center; margin-top:40px; color:#666; font-family:Tahoma;">'
    'طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>',
    unsafe_allow_html=True)
