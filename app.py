mport re
import pandas as pd
import streamlit as st
import base64
import plotly.express as px

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
        st.markdown('<h2 style="text-align:center;">🔐 ورود به سامانه هوشمند پایش وضعیت سیمان تهران</h2>', unsafe_allow_html=True)
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
    if x is None or str(x).strip() == '': return ''
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
    s = s.replace('٫', '.').replace('،', '.').replace(',', '.')
    s = s.replace(' ', '')
    return s

def to_num(x):
    try:
        return float(clean_num_text(x))
    except:
        return None

def date_sort_key(val):
    s = norm(val)
    m = re.search(r'(\d{2,4})\s/\s*(\d{1,2})\s*/\s*(\d{1,2})', s)
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100: y += 1400
            return int(f"{y}{mo:02d}{d:02d}")
        except: return 0
    return 0
def get_image_base64(path):
    try:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    except: return ''
def smart_find_column(columns, keywords):
    if columns is None: return None
    cols = list(columns)
    normed = {c: norm(c) for c in cols}
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if normed[c] == nk or (nk != '' and nk in normed[c]): return c
    return None
# ==============================================================================
# 3. بارگذاری داده‌ها (ساختار کاملاً افقی و حفظ ستون‌های P1 تا P11)
# ==============================================================================
VIB_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0'
ASSETS_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=1276803564'
ANN_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=2057447521'
@st.cache_data(ttl=600)
def load_data():
    try: df_v = pd.read_csv(VIB_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except: df_v = pd.DataFrame()
    try: df_a = pd.read_csv(ASSETS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except: df_a = pd.DataFrame()
    try: df_ann = pd.read_csv(ANN_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except: df_ann = pd.DataFrame()
    return df_v, df_a, df_ann
df_raw, df_assets, df_ann = load_data()
c_date = smart_find_column(df_raw.columns, ['تاریخ', 'date'])
c_line = smart_find_column(df_raw.columns, ['خط تولید', 'خط'])
c_unit = smart_find_column(df_raw.columns, ['واحد'])
c_equip = smart_find_column(df_raw.columns, ['عنوان تجهیز', 'نام تجهیز', 'تجهیز', 'asset'])
if not df_raw.empty:
    if c_line: df_raw['_k_line'] = df_raw[c_line].map(norm)
    else: df_raw['_k_line'] = ''
    if c_unit: df_raw['_k_unit'] = df_raw[c_unit].map(norm)
    else: df_raw['_k_unit'] = ''
    if c_equip: df_raw['_k_eq'] = df_raw[c_equip].map(norm)
    else: df_raw['_k_eq'] = ''
    if c_date: 
        df_raw['_k_date'] = df_raw[c_date].map(norm)
        df_raw['_dkey'] = df_raw[c_date].map(date_sort_key)
    else:
        df_raw['_k_date'] = ''
        df_raw['_dkey'] = 0
# ==============================================================================
# 4. ظاهر برنامه و فیلترها
# ==============================================================================
logo_siman = get_image_base64('client_logo.png')
logo_faz = get_image_base64('my_logo.png')
st.markdown(f'''
<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;
            background:white; padding:15px 30px; border-radius:15px; box-shadow:0 4px 8px rgba(0,0,0,0.1);'>
    <img src='data:image/png;base64,{logo_faz}' style='width:110px; height:auto;'>
    <div style='text-align:center; color:#1E3A8D; font-size:26px; font-weight:bold; font-family:Tahoma;'>
        🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران
    </div >
    <img src='data:image/png;base64,{logo_siman}' style='width:110px; height:auto;'>
</div>
''', unsafe_allow_html=True)
# اعلان‌ها
if not df_ann.empty:
    c_tit = smart_find_column(df_ann.columns, ['عنوان', 'title'])
    c_txt = smart_find_column(df_ann.columns, ['متن', 'text'])
    c_typ = smart_find_column(df_ann.columns, ['نوع', 'type'])
    c_act = smart_find_column(df_ann.columns, ['فعال', 'active'])
    if c_tit and c_txt:
        for _, row in df_ann.iterrows():
            if c_act and str(row[c_act]).strip() != 'بله': continue
            t, txt, typ = str(row[c_tit]), str(row[c_txt]), str(row[c_typ]) if c_typ else ''
            color, icon = ("#ff4b4b", "🚨") if any(x in typ for x in ["خطر", "بحرانی"]) else ("#2e7d32", "✅") if "موفق" in typ else ("#1E3A8D", "ℹ️")
            st.markdown(f'<div style="background:{color}; padding:12px; border-radius:10px; margin-bottom:8px; color:white; direction:rtl; text-align:right; font-family:Tahoma;"><b>{icon} {t}</b><br><small>{txt}</small></div>', unsafe_allow_html=True)
st.sidebar.header('🔍 فیلترها')
if not df_raw.empty:
    lines = sorted([l for l in df_raw['_k_line'].unique() if l != ''])
    units = sorted([u for u in df_raw['_k_unit'].unique() if u != ''])
    equips = sorted([e for e in df_raw['_k_eq'].unique() if e != ''])
    dates = sorted([d for d in df_raw['_k_date'].unique() if d != ''], reverse=True)
    sel_line = st.sidebar.selectbox('📍 خط:', ['همه'] + lines)
    sel_unit = st.sidebar.selectbox('🏢 واحد:', ['همه'] + units)
    sel_eq = st.sidebar.selectbox('⚙️ تجهیز:', ['همه تجهیزات'] + equips)
    search_txt = st.sidebar.text_input('🔎 جستجوی سریع تجهیز:')
    sel_date = st.sidebar.selectbox('🌙 تاریخ:', ['همه تاریخ‌ها'] + dates)
    # فیلتر داده‌ها بدون تغییر ساختار افقی
    fdf = df_raw.copy()
    if sel_line != 'همه': fdf = fdf[fdf['_k_line'] == norm(sel_line)]
    if sel_unit != 'همه': fdf = fdf[fdf['_k_unit'] == norm(sel_unit)]
    if sel_eq != 'همه تجهیزات': fdf = fdf[fdf['_k_eq'] == norm(sel_eq)]
    if search_txt:
        q = norm(search_txt)
        fdf = fdf[fdf['_k_eq'].map(lambda x: q in x)]
    if sel_date != 'همه تاریخ‌ها': fdf = fdf[fdf['_k_date'] == norm(sel_date)]
    if c_date: fdf = fdf.sort_values('_dkey', ascending=False)
    st.title('📊 جدول افقی ارتعاشات تجهیزات')
    # نمایش جدول دقیقاً به شکل افقی اصلی شیت
    if not fdf.empty:
        st.subheader(f"📋 تعداد ردیف: {len(fdf)}")
        vis_cols = [c for c in fdf.columns if not c.startswith('_')]
        def color_vib(val):
            v = to_num(val)
            if v is not None:
                if v > 7.1: return 'background-color:#ff4b4b; color:white'
                if v > 4.5: return 'background-color:#ffa500; color:white'
                return 'background-color:#2e7d32; color:white'
            return ''
        # شناسایی ستون‌های مقادیر عددی برای رنگ‌بندی
        num_cols = [c for c in vis_cols if any(p in c.lower() for p in ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8', 'p9', 'p10', 'p11', 'mm/s', 'عمودی', 'افقی', 'محوری'])]
        st.dataframe(fdf[vis_cols].style.map(color_vib, subset=[c for c in num_cols if c in vis_cols]), use_container_width=True, hide_index=True)
    st.markdown('<div style="text-align:center; margin-top:50px; color:#555; font-family:Tahoma;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>', unsafe_allow_html=True)
else:
    st.error("❌ خطا در بارگذاری داده‌ها.")
