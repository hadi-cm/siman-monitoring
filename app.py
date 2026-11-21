# -*- coding: utf-8 -*-
"""
=============================================================================
سامانه پایش وضعیت تجهیزات سیمان تهران  |  نسخه ۱۲
ساختار شیت: افقی (Wide)  ->  هر ردیف یک تجهیز در یک تاریخ،
ستون‌ها همان ستون‌های خودِ شیت (P1 | افقی ، P1 | عمودی ، ... ) دست‌نخورده می‌مانند.
توسعه: مهندس هادی زندیه  |  فاز فیدار پارسیان
=============================================================================
"""

# ==========================================================================
# بخش ۱ : تنظیمات صفحه و ورود کاربران
# ==========================================================================
import re
import base64
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title='داشبورد پایش وضعیت سیمان تهران',
                   page_icon='🛠️', layout='wide')

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
        st.markdown('<h2 style="text-align:center;">🔐 ورود به سامانه پایش وضعیت سیمان تهران</h2>',
                    unsafe_allow_html=True)
        with st.form('login_form'):
            email = st.text_input('ایمیل کاربری:')
            password = st.text_input('رمز عبور:', type='password')
            submitted = st.form_submit_button('ورود به داشبورد')
            if submitted:
                email_clean = email.strip().lower()
                found = None
                for k in USER_CREDENTIALS:
                    if k.strip().lower() == email_clean:
                        found = k
                        break
                if found and USER_CREDENTIALS[found].strip() == password.strip():
                    st.session_state['authenticated'] = True
                    st.rerun()
                else:
                    st.error('❌ ایمیل یا رمز عبور اشتباه است.')
        return False
    return True


if not check_password():
    st.stop()


# ==========================================================================
# بخش ۲ : توابع کمکی (پاکسازی متن فارسی، تبدیل عدد، کلید تاریخ)
# ==========================================================================
FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'
EN_DIGITS = '0123456789'


def norm(x):
    """نرمال‌سازی برای مقایسه: اعداد فارسی، ی/ک عربی، فاصله‌ها"""
    if x is None:
        return ''
    s = str(x).strip()
    if s == '':
        return ''
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = s.replace('ي', 'ی').replace('ى', 'ی').replace('ك', 'ک')
    s = s.replace('ۀ', 'ه').replace('ة', 'ه')
    s = s.replace('\u200c', ' ').replace('\xa0', ' ')
    s = s.replace('-', ' ').replace('_', ' ').replace('.', ' ')
    return ' '.join(s.split()).lower()


def clean_num_text(x):
    """پاکسازی رشته برای تبدیل به عدد"""
    s = str(x).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = s.replace('٫', '.').replace('،', '.').replace(',', '.')
    s = s.replace('%', '').replace(' ', '').replace('\u200c', '')
    return s


def to_num(x):
    """تبدیل امن به عدد؛ در صورت شکست None"""
    if x is None:
        return None
    s = clean_num_text(x)
    if s == '':
        return None
    try:
        return float(s)
    except Exception:
        m = re.search(r'[-+]?\d*\.?\d+', s)
        if m:
            try:
                return float(m.group())
            except Exception:
                return None
        return None


def date_sort_key(val):
    """کلید مرتب‌سازی تاریخ شمسی به صورت 14050829"""
    s = norm(val)
    m = re.search(r'(\d{2,4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})', s)
    if m:
        try:
            y = int(m.group(1))
            mo = int(m.group(2))
            d = int(m.group(3))
            if y < 100:
                y += 1400
            return int('{}{:02d}{:02d}'.format(y, mo, d))
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
    """یافتن ستون بر اساس چند کلیدواژه (اول تطابق کامل، بعد شامل بودن)"""
    if columns is None:
        return None
    cols = list(columns)
    normed = {}
    for c in cols:
        normed[c] = norm(c)
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if normed[c] == nk:
                return c
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if nk != '' and nk in normed[c]:
                return c
    return None


def is_vib_col(col):
    """آیا این ستون، ستون مقدار ارتعاش یک نقطه است؟"""
    n = norm(col)
    if re.search(r'(^|[^a-z])p\s*\d+', n):
        return True
    for k in ['عمودی', 'افقی', 'محوری', 'بالانس']:
        if k in n:
            return True
    return False


def direction_of(col):
    n = norm(col)
    for k in ['عمودی', 'افقی', 'محوری', 'بالانس']:
        if k in n:
            return k
    return 'سایر'


def make_styled(df_show, sub_cols):

    def color_vib(val):
        v = to_num(val)
        if v is None:
            return ''
        if v > 7.1:
            return 'background-color:#ff4b4b; color:white; font-weight:bold'
        if v > 4.5:
            return 'background-color:#ffa500; color:white'
        return 'background-color:#2e7d32; color:white'

    if not sub_cols:
        return df_show
    try:
        return df_show.style.map(color_vib, subset=sub_cols)
    except Exception:
        return df_show.style.applymap(color_vib, subset=sub_cols)


# ==========================================================================
# بخش ۳ : بارگذاری داده‌ها از گوگل‌شیت
# ==========================================================================
SHEET_ID = '1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs'
VIB_URL = 'https://docs.google.com/spreadsheets/d/' + SHEET_ID + '/export?format=csv&gid=0'
ASSETS_URL = 'https://docs.google.com/spreadsheets/d/' + SHEET_ID + '/export?format=csv&gid=1276803564'
ANN_URL = 'https://docs.google.com/spreadsheets/d/' + SHEET_ID + '/export?format=csv&gid=2057447521'


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

c_date = smart_find_column(df_raw.columns, ['تاریخ', 'date'])
c_line = smart_find_column(df_raw.columns, ['خط تولید', 'خط'])
c_unit = smart_find_column(df_raw.columns, ['واحد'])
c_equip = smart_find_column(df_raw.columns, ['عنوان تجهیز', 'نام تجهیز', 'تجهیز', 'asset'])

vib_cols = [c for c in df_raw.columns if is_vib_col(c)]

if not df_raw.empty:
    df_raw['_k_line'] = df_raw[c_line].map(norm) if c_line else ''
    df_raw['_k_unit'] = df_raw[c_unit].map(norm) if c_unit else ''
    df_raw['_k_eq'] = df_raw[c_equip].map(norm) if c_equip else ''
    if c_date:
        df_raw['_k_date'] = df_raw[c_date].map(norm)
        df_raw['_dkey'] = df_raw[c_date].map(date_sort_key)
    else:
        df_raw['_k_date'] = ''
        df_raw['_dkey'] = 0


# ==========================================================================
# بخش ۴ : هدر برنامه و اعلانیه‌ها
# ==========================================================================
logo_siman = get_image_base64('client_logo.png')
logo_faz = get_image_base64('my_logo.png')

st.markdown(
    '''
    <div style="display:flex; justify-content:space-between; align-items:center;
                margin-bottom:18px; background:#ffffff; padding:14px 28px;
                border-radius:14px; box-shadow:0 4px 10px rgba(0,0,0,0.08);">
        <img src="data:image/png;base64,''' + logo_faz + '''" style="width:105px; height:auto;">
        <div style="text-align:center; color:#1E3A8D; font-size:24px; font-weight:bold;
                    font-family:Tahoma;">🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران</div>
        <img src="data:image/png;base64,''' + logo_siman + '''" style="width:105px; height:auto;">
    </div>
    ''',
    unsafe_allow_html=True,
)

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
            typ = str(row[c_typ]) if c_typ else ''
            if typ == '':
                color, icon = '#1E3A8D', 'ℹ️'
            elif any(w in typ for w in ['خطر', 'بحرانی', 'هشدار']):
                color, icon = '#ff4b4b', '🚨'
            elif 'موفق' in typ:
                color, icon = '#2e7d32', '✅'
            else:
                color, icon = '#1E3A8D', 'ℹ️'
            st.markdown(
                '<div style="background:' + color + '; padding:12px 14px; border-radius:10px;'
                ' margin-bottom:8px; color:#fff; direction:rtl; text-align:right;'
                ' font-family:Tahoma; line-height:1.9;">'
                '<b>' + icon + ' ' + t + '</b><br><span style="font-size:13px;">' + txt + '</span></div>',
                unsafe_allow_html=True,
            )


# ==========================================================================
# بخش ۵ : فیلترها (سایدبار) + پنل عیب‌یابی
# ==========================================================================
st.sidebar.header('🔍 فیلترها')

with st.sidebar.expander('🩺 عیب‌یابی داده'):
    st.write('ستون تاریخ: ' + str(c_date))
    st.write('ستون تجهیز: ' + str(c_equip))
    st.write('ستون خط: ' + str(c_line))
    st.write('ستون واحد: ' + str(c_unit))
    st.write('تعداد ستون‌های ارتعاش: ' + str(len(vib_cols)))
    st.write('نمونه ستون‌های ارتعاش:')
    st.code(' , '.join(vib_cols[:12]) if vib_cols else 'یافت نشد')
    st.write('تعداد ردیف خام: ' + str(len(df_raw)))

if df_raw.empty:
    st.error('❌ داده‌ای بارگذاری نشد. اتصال اینترنت یا لینک گوگل‌شیت را بررسی کنید.')
    st.stop()

lines = sorted([x for x in df_raw['_k_line'].unique() if x != ''])
units = sorted([x for x in df_raw['_k_unit'].unique() if x != ''])
equips = sorted([x for x in df_raw['_k_eq'].unique() if x != ''])
dates = sorted([x for x in df_raw['_k_date'].unique() if x != ''], reverse=True)

sel_line = st.sidebar.selectbox('📍 خط تولید:', ['همه'] + lines)
sel_unit = st.sidebar.selectbox('🏢 واحد:', ['همه'] + units)
sel_eq = st.sidebar.selectbox('⚙️ تجهیز:', ['همه تجهیزات'] + equips)
search_txt = st.sidebar.text_input('🔎 جستجوی سریع تجهیز:')
sel_date = st.sidebar.selectbox('🌙 تاریخ:', ['همه تاریخ‌ها'] + dates)

fdf = df_raw.copy()
if sel_line != 'همه':
    fdf = fdf[fdf['_k_line'] == norm(sel_line)]
if sel_unit != 'همه':
    fdf = fdf[fdf['_k_unit'] == norm(sel_unit)]
if sel_eq != 'همه تجهیزات':
    fdf = fdf[fdf['_k_eq'] == norm(sel_eq)]
if search_txt.strip() != '':
    q = norm(search_txt)
    fdf = fdf[fdf['_k_eq'].map(lambda x: q in x)]
if sel_date != 'همه تاریخ‌ها':
    fdf = fdf[fdf['_k_date'] == norm(sel_date)]
if c_date:
    fdf = fdf.sort_values('_dkey', ascending=False)


# ==========================================================================
# بخش ۶ : کارت‌های خلاصه + جدول اصلی (بدون تغییر ساختار افقی)
# ==========================================================================
st.title('📊 جدول ارتعاشات تجهیزات')

# --- کارت‌های خلاصه ---
all_vals = []
for col in vib_cols:
    if col in fdf.columns:
        for v in fdf[col].tolist():
            n = to_num(v)
            if n is not None:
                all_vals.append(n)

n_crit = len([v for v in all_vals if v > 7.1])
n_warn = len([v for v in all_vals if 4.5 < v <= 7.1])
n_ok = len([v for v in all_vals if v <= 4.5])
n_eq = fdf['_k_eq'].nunique() if '_k_eq' in fdf.columns else 0

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric('تعداد تجهیزات', n_eq)
k2.metric('کل قرائت‌ها', len(all_vals))
k3.metric('🟢 نرمال', n_ok)
k4.metric('🟠 هشدار', n_warn)
k5.metric('🔴 بحرانی', n_crit)

st.divider()

# --- جدول: همان ستون‌های شیت، همان چیدمان ---
st.subheader('📋 تعداد ردیف نمایش داده شده: ' + str(len(fdf)))

vis_cols = [c for c in fdf.columns if not c.startswith('_')]
sub_cols = [c for c in vib_cols if c in vis_cols]

if vis_cols:
    styled = make_styled(fdf[vis_cols], sub_cols)
    st.dataframe(styled, use_container_width=True, hide_index=True, height=520)
else:
    st.warning('ستونی برای نمایش وجود ندارد.')


# ==========================================================================
# بخش ۷ : مشخصات فنی تجهیز + نمودار روند
# ==========================================================================
if sel_eq != 'همه تجهیزات':

    # --- ۷-۱ : مشخصات فنی از شیت Assets ---
    if not df_assets.empty:
        a_name = smart_find_column(df_assets.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'asset'])
        if a_name:
            mask = df_assets[a_name].map(lambda x: norm(x) == norm(sel_eq))
            a_rows = df_assets[mask]
            if a_rows.empty:
                mask = df_assets[a_name].map(lambda x: norm(sel_eq) in norm(x))
                a_rows = df_assets[mask]

            if not a_rows.empty:

                def gv(keys):
                    col = smart_find_column(df_assets.columns, keys)
                    if col is None:
                        return '---'
                    val = str(a_rows.iloc[0][col]).strip()
                    return val if val != '' else '---'

                st.info(
                    '🛠️ نوع: ' + gv(['نوع تجهیز', 'نوع']) +
                    '  |  دور: ' + gv(['دور', 'RPM', 'rpm']) + ' RPM' +
                    '  |  خط: ' + gv(['خط تولید', 'خط']) +
                    '  |  واحد: ' + gv(['واحد'])
                )

                # راهنمای نقاط (اگر چند ردیف تکراری باشد، یکتا می‌شود)
                g_col = smart_find_column(df_assets.columns, ['راهنمای نقاط', 'راهنما', 'نقطه', 'point'])
                if g_col is not None:
                    guides = []
                    for g in a_rows[g_col].tolist():
                        g = str(g).strip()
                        if g != '' and g not in guides:
                            guides.append(g)
                    if guides:
                        with st.expander('📍 راهنمای نقاط اندازه‌گیری', expanded=False):
                            for g in guides:
                                st.write('• ' + g)

    # --- ۷-۲ : نمودار روند ---
    if c_date and sub_cols:
        st.markdown('### 📈 نمودار روند ارتعاشات')

        d_options = ['همه جهت‌ها', 'عمودی', 'افقی', 'محوری', 'بالانس']
        sel_dir = st.selectbox('جهت اندازه‌گیری:', d_options)

        if sel_dir == 'همه جهت‌ها':
            chart_cols = sub_cols
        else:
            chart_cols = [c for c in sub_cols if direction_of(c) == sel_dir]

        if not chart_cols:
            st.info('برای این جهت، ستونی در داده‌های این تجهیز وجود ندارد.')
        else:
            cdf = fdf.copy()
            cdf['_sort'] = cdf['_dkey']
            cdf = cdf.sort_values('_sort')
            x_vals = cdf[c_date].astype(str).tolist()

            fig = go.Figure()
            has_point = False
            for c in chart_cols:
                y_vals = [to_num(v) for v in cdf[c].tolist()]
                if any(v is not None for v in y_vals):
                    has_point = True
                    fig.add_trace(go.Scatter(
                        x=x_vals, y=y_vals, mode='lines+markers',
                        name=str(c), connectgaps=True,
                    ))

            if has_point:
                fig.add_hline(y=4.5, line_dash='dash', line_color='orange',
                              annotation_text='هشدار 4.5')
                fig.add_hline(y=7.1, line_dash='dash', line_color='red',
                              annotation_text='بحرانی 7.1')
                fig.update_layout(
                    height=470,
                    xaxis_title='تاریخ',
                    yaxis_title='mm/s',
                    legend_title='نقطه / جهت',
                    hovermode='x unified',
                    margin=dict(l=10, r=10, t=40, b=10),
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info('در ردیف‌های انتخاب‌شده، مقدار عددی برای رسم نمودار وجود ندارد.')
    else:
        st.info('برای رسم نمودار روند، حداقل یک تاریخ و یک ستون مقدار لازم است.')

st.markdown(
    '<div style="text-align:center; margin-top:45px; color:#555; font-family:Tahoma;'
    ' font-size:13px;">طراحی و توسعه: مهندس هادی زندیه  |  شرکت فاز فیدار پارسیان</div>',
    unsafe_allow_html=True,
)
