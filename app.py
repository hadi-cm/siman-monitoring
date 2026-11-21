import re
import base64
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title='پایش وضعیت ارتعاشات سیمان تهران', layout='wide')

# ============================================================
# 1) ورود کاربران
# ============================================================
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
    st.session_state.setdefault('authenticated', False)
    if st.session_state['authenticated']:
        return True
    st.markdown('<h2 style="text-align:center">🔐 ورود به سامانه پایش وضعیت سیمان تهران</h2>',
                unsafe_allow_html=True)
    with st.form('login_form'):
        email = st.text_input('ایمیل کاربری:')
        password = st.text_input('رمز عبور:', type='password')
        submitted = st.form_submit_button('ورود به داشبورد')
    if submitted:
        key = email.strip().lower()
        if USER_CREDENTIALS.get(key) and USER_CREDENTIALS[key] == password.strip():
            st.session_state['authenticated'] = True
            st.rerun()
        else:
            st.error('❌ ایمیل یا رمز عبور اشتباه است.')
    return False


if not check_password():
    st.stop()

# ============================================================
# 2) توابع کمکی
# ============================================================
FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'
EN_DIGITS = '0123456789'


def norm(x):
    if x is None:
        return ''
    s = str(x).strip()
    if not s:
        return ''
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = (s.replace('ي', 'ی').replace('ى', 'ی')
          .replace('ك', 'ک').replace('ۀ', 'ه').replace('ة', 'ه'))
    s = (s.replace('\u200c', ' ').replace('\xa0', ' ')
          .replace('-', ' ').replace('_', ' ').replace('.', ' ')
          .replace('،', ' ').replace('/', ' '))
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
    m = re.search(r'(\d{2,4})\s*(\d{1,2})\s*(\d{1,2})', s)
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 1400
            return int('{:04d}{:02d}{:02d}'.format(y, mo, d))
        except Exception:
            return 0
    return 0


def get_image_base64(path):
    try:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ''


def smart_find_column(columns, keywords):
    """پیدا کردن نام ستون بر اساس کلیدواژه‌ها با تطبیق نرمال‌شده."""
    if columns is None:
        return None
    cols = list(columns)
    normed = {c: norm(c) for c in cols}
    for k in keywords:
        nk = norm(k)
        if not nk:
            continue
        for c in cols:
            if normed[c] == nk:
                return c
        for c in cols:
            if nk in normed[c]:
                return c
    return None


def norm_point(x):
    """نرمال‌سازی نام نقطه: 'پی ۲' یا 'P2' یا '2' همه به 'p2' تبدیل می‌شوند."""
    s = norm(x)
    if not s:
        return ''
    m = re.search(r'(?:p|پی)\s*[-_ ]?\s*(\d{1,2})', s)
    if m:
        return 'p{}'.format(int(m.group(1)))
    m = re.search(r'^(\d{1,2})$', s)
    if m:
        return 'p{}'.format(int(m.group(1)))
    return s


# ============================================================
# 3) بارگذاری داده‌ها
# ============================================================
VIB_URL = ('https://docs.google.com/spreadsheets/d/'
           '1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0')
ASSETS_URL = ('https://docs.google.com/spreadsheets/d/'
              '1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=1276803564')
ANN_URL = ('https://docs.google.com/spreadsheets/d/'
           '1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=2057447521')


@st.cache_data(ttl=600)
def load_data():
    def rd(url):
        try:
            return pd.read_csv(url, dtype=str, keep_default_na=False, encoding='utf-8-sig')
        except Exception:
            return pd.DataFrame()

    return rd(VIB_URL), rd(ASSETS_URL), rd(ANN_URL)


df_raw, df_assets, df_ann = load_data()

# --- ستون‌های شیت ارتعاشات ---
c_date = smart_find_column(df_raw.columns, ['تاریخ', 'date'])
c_line = smart_find_column(df_raw.columns, ['خط تولید', 'خط'])
c_unit = smart_find_column(df_raw.columns, ['واحد'])
c_equip = smart_find_column(df_raw.columns, ['عنوان تجهیز', 'نام تجهیز', 'تجهیز', 'asset'])
c_point = smart_find_column(df_raw.columns, ['محل اندازه گیری', 'نقطه', 'point'])

vib_cols = [c for c in df_raw.columns
            if any(k in norm(c) for k in ['عمودی', 'افقی', 'محوری', 'mm s', 'arc'])]

if not df_raw.empty:
    df_raw['_k_line'] = df_raw[c_line].map(norm) if c_line else ''
    df_raw['_k_unit'] = df_raw[c_unit].map(norm) if c_unit else ''
    df_raw['_k_eq'] = df_raw[c_equip].map(norm) if c_equip else ''
    df_raw['_k_date'] = df_raw[c_date].map(norm) if c_date else ''
    df_raw['_dkey'] = df_raw[c_date].map(date_sort_key) if c_date else 0
    df_raw['_k_point'] = df_raw[c_point].map(norm_point) if c_point else ''

# ============================================================
# 3-ب) ساخت ایندکس مشخصات تجهیز (Assets) به تفکیک نقطه
# ============================================================
@st.cache_data(ttl=600)
def build_asset_index(df):
    """ایندکس: (نام تجهیز نرمال‌شده، نقطه) -> دیکشنری همه ستون‌های Assets"""
    idx, cols = {}, []
    if df is None or df.empty:
        return idx, cols, None, None, None

    a_eq = smart_find_column(df.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'نام دستگاه', 'asset'])
    a_pt = smart_find_column(df.columns, ['راهنمای نقاط', 'نقطه', 'point', 'محل اندازه گیری', 'محل نصب'])
    a_bearing = smart_find_column(df.columns, ['شماره بیرینگ', 'بیرینگ', 'bearing'])

    skip = {a_eq, a_pt}
    cols = [c for c in df.columns if c not in skip]

    for _, r in df.iterrows():
        eq = norm(r[a_eq]) if a_eq else ''
        pt = norm_point(r[a_pt]) if a_pt else ''
        rec = {}
        for c in cols:
            v = str(r[c]).strip()
            if v and v.lower() not in ('nan', 'none'):
                rec[c] = v
        if not rec:
            continue
        idx[(eq, pt)] = rec
        if (eq, '') not in idx:
            idx[(eq, '')] = rec
    return idx, cols, a_eq, a_pt, a_bearing


ASSET_IDX, ASSET_COLS, A_EQ, A_PT, A_BEARING = build_asset_index(df_assets)


def asset_lookup(k_eq, k_point):
    rec = ASSET_IDX.get((k_eq, k_point))
    if rec is None:
        rec = ASSET_IDX.get((k_eq, ''))
    return rec or {}


# ============================================================
# 4) هدر و اعلانیه‌ها
# ============================================================
logo_client = get_image_base64('client_logo.png')
logo_me = get_image_base64('my_logo.png')

st.markdown(
    """
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;
                background:white; padding:14px 26px; border-radius:16px;
                box-shadow:0 4px 10px rgba(0,0,0,.08);">
        <img src="data:image/png;base64,{a}" style="width:100px;height:auto;">
        <div style="text-align:center;color:#1E3A8D;font-size:24px;font-weight:bold;font-family:Tahoma;">
            🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران
        </div>
        <img src="data:image/png;base64,{b}" style="width:100px;height:auto;">
    </div>
    """.format(a=logo_me, b=logo_client),
    unsafe_allow_html=True,
)

if not df_ann.empty:
    c_tit = smart_find_column(df_ann.columns, ['عنوان', 'title'])
    c_txt = smart_find_column(df_ann.columns, ['متن', 'text'])
    c_typ = smart_find_column(df_ann.columns, ['نوع', 'type'])
    c_act = smart_find_column(df_ann.columns, ['فعال', 'active'])
    if c_tit and c_txt:
        for _, row in df_ann.iterrows():
            if c_act and norm(row[c_act]) not in ('بله', 'yes', 'true', '1'):
                continue
            t = str(row[c_tit])
            txt = str(row[c_txt])
            typ = norm(row[c_typ]) if c_typ else ''
            if any(k in typ for k in ['خطر', 'بحرانی', 'critical']):
                color, icon = '#d32f2f', '🚨'
            elif any(k in typ for k in ['هشدار', 'warning']):
                color, icon = '#ef6c00', '⚠️'
            elif any(k in typ for k in ['موفق', 'ok']):
                color, icon = '#2e7d32', '✅'
            else:
                color, icon = '#1E3A8D', 'ℹ️'
            st.markdown(
                '<div style="background:{c};padding:11px 14px;border-radius:10px;margin-bottom:8px;'
                'color:white;direction:rtl;text-align:right;font-family:Tahoma;">'
                '<b>{i} {t}</b><br><small>{x}</small></div>'.format(c=color, i=icon, t=t, x=txt),
                unsafe_allow_html=True,
            )

# ============================================================
# 5) سایدبار: فیلتر آبشاری + تنظیمات
# ============================================================
st.sidebar.header('🔍 فیلترها')
if df_raw.empty:
    st.error('❌ خطا در بارگذاری داده‌های شیت ارتعاشات.')
    st.stop()

f_line = df_raw
lines = sorted({v for v in f_line['_k_line'] if v})
sel_line = st.sidebar.selectbox('📍 خط تولید:', ['همه'] + lines)
if sel_line != 'همه':
    f_line = f_line[f_line['_k_line'] == norm(sel_line)]

units = sorted({v for v in f_line['_k_unit'] if v})
sel_unit = st.sidebar.selectbox('🏢 واحد:', ['همه'] + units)
if sel_unit != 'همه':
    f_line = f_line[f_line['_k_unit'] == norm(sel_unit)]

equips = sorted({v for v in f_line['_k_eq'] if v})
sel_eq = st.sidebar.selectbox('⚙️ تجهیز:', ['همه تجهیزات'] + equips)
if sel_eq != 'همه تجهیزات':
    f_line = f_line[f_line['_k_eq'] == norm(sel_eq)]

search_txt = st.sidebar.text_input('🔎 جستجوی تجهیز در همین محدوده:')

dates = sorted({v for v in f_line['_k_date'] if v}, reverse=True)
sel_date = st.sidebar.selectbox('📅 تاریخ:', ['همه تاریخ‌ها'] + dates)
if sel_date != 'همه تاریخ‌ها':
    f_line = f_line[f_line['_k_date'] == norm(sel_date)]

fdf = f_line.copy()
if search_txt:
    q = norm(search_txt)
    fdf = fdf[fdf['_k_eq'].map(lambda x: q in x)]
if c_date:
    fdf = fdf.sort_values('_dkey', ascending=False)

st.sidebar.markdown('---')
st.sidebar.header('⚠️ حدود هشدار')
warn_limit = st.sidebar.slider('حد هشدار (نارنجی)', 0.0, 20.0, 4.5, 0.1)
crit_limit = st.sidebar.slider('حد بحرانی (قرمز)', 0.0, 30.0, 7.1, 0.1)

st.sidebar.markdown('---')
st.sidebar.header('📈 نمودار روند')
show_chart = st.sidebar.checkbox('نمایش نمودار', value=False)
chart_cols = st.sidebar.multiselect('ستون‌های نمودار:', vib_cols, default=vib_cols)

st.sidebar.markdown('---')
st.sidebar.header('📑 گزارش')
st.sidebar.caption('گزارش HTML شامل مشخصات تجهیز و جدول است؛ با Ctrl+P به PDF تبدیل کن.')

# ============================================================
# 6) پنل مشخصات فنی + نقشه نقاط و بیرینگ‌ها
# ============================================================
if sel_eq != 'همه تجهیزات':
    k_eq = norm(sel_eq)
    eq_rows = df_assets[df_assets[A_EQ].map(norm) == k_eq] if (A_EQ and not df_assets.empty) else pd.DataFrame()

    st.subheader('🛠️ مشخصات فنی تجهیز: {}'.format(sel_eq))

    if eq_rows.empty:
        st.info('برای این تجهیز ردیفی در شیت Assets پیدا نشد. اگر نام تجهیز بین دو شیت متفاوت است، همان‌طور که در شیت نوشته شده در فیلتر بنویس.')
    else:
        # الف) مشخصات مشترک تجهیز (کارت‌ها)
        common = {}
        for c in eq_rows.columns:
            if c in (A_PT,):
                continue
            vals = sorted({str(v).strip() for v in eq_rows[c] if str(v).strip()})
            if len(vals) == 1:
                common[c] = vals[0]

        cols_ui = st.columns(3)
        for i, (k, v) in enumerate(common.items()):
            with cols_ui[i % 3]:
                st.metric(label=k, value=v)

        # ب) نقشه نقاط: هر نقطه و بیرینگ مخصوص خودش
        st.markdown('**📌 نقشه نقاط اندازه‌گیری و شماره بیرینگ هر نقطه**')
        map_cols = []
        if A_PT:
            map_cols.append(A_PT)
        if A_BEARING:
            map_cols.append(A_BEARING)
        for c in ASSET_COLS:
            if c not in map_cols:
                map_cols.append(c)

        map_df = eq_rows[map_cols].copy()
        map_df = map_df[map_df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]

        if A_PT:
            map_df['_order'] = map_df[A_PT].map(norm_point)
            map_df['_onum'] = map_df['_order'].map(
                lambda p: int(re.sub(r'\D', '', p) or 0)
            )
            map_df = map_df.sort_values('_onum')
            map_df = map_df.drop(columns=['_order', '_onum'])

        st.dataframe(map_df, use_container_width=True, hide_index=True)
        st.caption('تعداد نقاط ثبت‌شده برای این تجهیز: {} نقطه'.format(len(map_df)))

# ============================================================
# 7) جدول اصلی + ادغام ستون‌های Assets در هر ردیف
# ============================================================
st.markdown('---')
st.subheader('📋 جدول ارتعاشات — {} ردیف'.format(len(fdf)))

if fdf.empty:
    st.warning('با این فیلترها ردیفی پیدا نشد.')
    st.stop()

# --- ادغام مشخصات نقطه در هر ردیف ---
out = fdf.copy()
added_names = []

if ASSET_IDX and ASSET_COLS:
    # ستون بیرینگ اول نمایش داده شود
    ordered_asset_cols = ([A_BEARING] if A_BEARING else []) + [c for c in ASSET_COLS if c != A_BEARING]
    for ac in ordered_asset_cols:
        new_name = '🔧 {}'.format(ac)
        vals = []
        for _, r in out.iterrows():
            rec = asset_lookup(r['_k_eq'], r['_k_point'])
            vals.append(rec.get(ac, ''))
        if any(str(v).strip() for v in vals):
            out[new_name] = vals
            added_names.append(new_name)

vis_cols = [c for c in out.columns if not c.startswith('_')]

# چیدن ستون‌های جدید درست بعد از ستون «محل اندازه‌گیری»
if c_point in vis_cols and added_names:
    base_cols = [c for c in vis_cols if c not in added_names]
    i = base_cols.index(c_point) + 1
    vis_cols = base_cols[:i] + added_names + base_cols[i:]

table = out[vis_cols]


def color_vib(val):
    v = to_num(val)
    if v is None:
        return ''
    if v >= crit_limit:
        return 'background-color:#e53935;color:white;font-weight:bold'
    if v >= warn_limit:
        return 'background-color:#fb8c00;color:white;font-weight:bold'
    return 'background-color:#2e7d32;color:white'


num_cols = [c for c in vis_cols if c in vib_cols]

try:
    styled = table.style.map(color_vib, subset=num_cols)
except AttributeError:
    styled = table.style.applymap(color_vib, subset=num_cols)

st.dataframe(styled, use_container_width=True, hide_index=True)

if added_names:
    st.caption('✅ ستون‌های 🔧 از شیت Assets خوانده شده‌اند و برای هر نقطه همان بیرینگ و مشخصات مخصوص خودش نمایش داده می‌شود.')
else:
    st.caption('ℹ️ مشخصات نقطه‌ای برای ادغام پیدا نشد؛ نام تجهیز و نام نقطه را در دو شیت یکسان کن.')

# ============================================================
# 8) نمودار روند
# ============================================================
if show_chart and chart_cols and c_date:
    with st.expander('📈 نمودار روند', expanded=True):
        plot_df = out[[c_date] + chart_cols].copy()
        plot_df['_dkey'] = plot_df[c_date].map(date_sort_key)
        plot_df = plot_df.sort_values('_dkey')

        long_df = plot_df.melt(id_vars=[c_date, '_dkey'], value_vars=chart_cols,
                               var_name='ستون', value_name='مقدار')
        long_df['مقدار'] = long_df['مقدار'].map(to_num)
        long_df = long_df.dropna(subset=['مقدار'])

        if long_df.empty:
            st.info('داده عددی برای رسم نمودار نیست.')
        else:
            fig = px.line(long_df, x=c_date, y='مقدار', color='ستون',
                          markers=True, title='روند ارتعاشات')
            fig.add_hline(y=warn_limit, line_dash='dash', line_color='orange',
                          annotation_text='هشدار')
            fig.add_hline(y=crit_limit, line_dash='dash', line_color='red',
                          annotation_text='بحرانی')
            fig.update_layout(height=520)
            st.plotly_chart(fig, use_container_width=True)

# ============================================================
# 9) دانلودها
# ============================================================
c1, c2 = st.columns(2)

with c1:
    csv_bytes = table.to_csv(index=False).encode('utf-8-sig')
    st.download_button('📥 دانلود CSV جدول', csv_bytes,
                       file_name='vibration_table.csv', mime='text/csv')

with c2:
    specs_html = ''
    if sel_eq != 'همه تجهیزات':
        rows_html = ''
        for k, v in common.items() if 'common' in dir() else []:
            rows_html += '<tr><th style="text-align:right;padding:6px;background:#f1f5f9;">{}</th><td style="padding:6px;">{}</td></tr>'.format(k, v)
        specs_html = '<h3>مشخصات تجهیز: {}</h3><table style="width:100%;border-collapse:collapse;">{}</table>'.format(sel_eq, rows_html)

    html_report = """
    <html lang="fa" dir="rtl"><head><meta charset="utf-8">
    <style>
      body{{font-family:Tahoma,sans-serif;padding:24px;}}
      table{{width:100%;border-collapse:collapse;font-size:11px;}}
      th,td{{border:1px solid #cbd5e1;padding:5px;text-align:center;}}
      th{{background:#1E3A8D;color:#fff;}}
    </style></head><body>
    <h2>گزارش پایش وضعیت ارتعاشات</h2>
    <p>تعداد ردیف: {n} | حد هشدار: {w} | حد بحرانی: {c}</p>
    {specs}
    {tbl}
    </body></html>
    """.format(n=len(table), w=warn_limit, c=crit_limit, specs=specs_html,
               tbl=table.to_html(index=False, escape=True))

    st.download_button('📄 دانلود گزارش HTML', html_report.encode('utf-8'),
                       file_name='vibration_report.html', mime='text/html')

st.markdown(
    '<div style="text-align:center;margin-top:46px;color:#666;font-family:Tahoma;">'
    'طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>',
    unsafe_allow_html=True,
)
