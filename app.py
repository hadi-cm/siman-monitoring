import pandas as pd
import streamlit as st
import base64
# ==============================================================================
# 0. تنظیمات صفحه
# ==============================================================================
st.set_page_config(page_title='داشبورد فنی ارتعاشات سیمان تهران', layout='wide')
# ==============================================================================
# 1. تنظیمات امنیتی و ورود
# ==============================================================================
USER_CREDENTIALS = {
    'alireza76ir@gmail.com': 'siman123',
    'vah.rezaei@gmail.com': 'siman123',
    'cm.zandiyeh@gmail.com': 'siman123',
    'tehrancement@gmail.com': 'siman123',
    'masoud.sa.1989823@gmail.com': 'siman123',
}
def check_password():
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    if not st.session_state['authenticated']:
        st.markdown('<h2 style="text-align: center;">🔐 ورود به سامانه هوشمند پایش وضعیت سیمان تهران</h2>', unsafe_allow_html=True)
        with st.form('login_form'):
            email = st.text_input('ایمیل کاربری:')
            password = st.text_input('رمز عبور:', type='password')
            if st.form_submit_button('ورود به داشبورد'):
                email_clean = email.strip().lower()
                found_email = next((k for k in USER_CREDENTIALS if k.strip().lower() == email_clean), None)
                if found_email and USER_CREDENTIALS[found_email].strip() == password.strip():
                    st.session_state['authenticated'] = True
                    st.rerun()
                else:
                    st.error('❌ ایمیل یا رمز عبور اشتباه است.')
        return False
    return True
if not check_password():
    st.stop()
# ==============================================================================
# 2. توابع کمکی (اصلاح شده)
# ==============================================================================
def clean_text(text):
    if pd.isna(text): return ''
    text = str(text).strip()
    farsi_nums = '۰۱۲۳۴۵۶۷۸۹'
    arabic_nums = '٠١٢٣٤٥٦٧٨٩'
    english_nums = '0123456789'
    for f, e in zip(farsi_nums, english_nums): text = text.replace(f, e)
    for a, e in zip(arabic_nums, english_nums): text = text.replace(a, e)
    return ' '.join(text.split()).lower()
def get_image_base64(path):
    try:
        with open(path, 'rb') as image_file: 
            return base64.b64encode(image_file.read()).decode()
    except: 
        return ''
# --- اصلاح اصلی: تابع find_col منعطف برای پذیرش هر تعداد ورودی ---
def find_col(cols, keywords):
    """پیدا کردن نام دقیق ستون بر اساس کلمات کلیدی (هر تعداد ورودی)"""
    if cols is None: return None
    for k in keywords:
        for c in cols:
            if k.lower() in str(c).strip().lower(): 
                return c
    return None

def color_vibration(val):
    """رنگ‌بندی مقادیر ارتعاشات (نمونه - مقادیر را بر اساس استاندارد خود تغییر دهید)"""
    try:
        num = float(val)
        if num > 7.1: return 'background-color: #ff4b4b; color: white' # قرمز
        if num > 4.5: return 'background-color: #ffa500; color: white' # نارنجی
        return 'background-color: #2e7d32; color: white' # سبز
    except:
        return ''

# ==============================================================================
# 3. هدر و لوگوها
# ==============================================================================
logo_siman_base64 = get_image_base64('client_logo.png')
logo_faz_fidar_base64 = get_image_base64('my_logo.png')

st.markdown(f'''
    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; background-color: white; padding: 15px 30px; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'>
        <img src='data:image/png;base64,{logo_faz_fidar_base64}' style='width: 110px; height: auto;'>
        <div style='text-align: center; color: #1E3A8D; font-size: 26px; font-weight: bold; font-family: Tahoma;'>🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران</div>
        <img src='data:image/png;base64,{logo_siman_base64}' style='width: 110px; height: auto;'>
    </div>
    ''', unsafe_allow_html=True)

# ==============================================================================
# 4. بارگذاری داده‌ها (بازنویسی شده برای پایداری)
# ==============================================================================
VIB_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0'
ASSETS_URL = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vTI4vONsowudctVbskGkkSyQNqkkGZ8AuiykO9UKeE-8FSBZemWkR4q5DSAhpXEqwQkgsCUQy44Vvqx/pub?gid=1276803564&single=true&output=csv'

@st.cache_data(ttl=60)
def load_all_data():
    try:
        # بارگذاری لرزش‌ها
        df_vib = pd.read_csv(VIB_URL)
        df_vib.columns = df_vib.columns.str.strip()

        # شناسایی ستون عنوان تجهیز با استفاده از تابع اصلاح شده
        title_col = find_col(df_vib.columns, 'عنوان تجهیز', 'نام تجهیز')
        if title_col:
            df_vib[title_col] = df_vib[title_col].replace(r'^\s$', pd.NA, regex=True).ffill()
        df_vib = df_vib.astype(str).apply(lambda x: x.str.strip()).replace({'nan': '', 'None': ''})
        # بارگذاری دارایی‌ها
        try:
            df_assets = pd.read_csv(ASSETS_URL)
            df_assets.columns = df_assets.columns.str.strip()
            df_assets = df_assets.astype(str).apply(lambda x: x.str.strip()).replace({'nan': '', 'None': ''})
        except: 
            df_assets = None
        return df_vib, df_assets
    except Exception as e:
        st.error(f'❌ خطا در دریافت داده‌ها: {e}')
        return None, None
df, df_assets = load_all_data()
# ==============================================================================
# 5. راهنمای نقاط
# ==============================================================================
def get_point_guide(eq_name, eq_type):
    name = str(eq_name).lower()
    etype = str(eq_type).lower() if eq_type else ''
    if 'گیربکس' in name or 'گیربکس' in etype:
        return 'P1: انتهای موتور | P2: جلوی موتور | P3: محور ورودی گیربکس | P4: سمت آزاد محور ورودی | P5: سمت فیکس محور دوم | P6: سمت آزاد محور دوم | P7: سمت فیکس محور سوم | P8: سمت آزاد محور سوم | P9: بابیت اول سمت گیربکس | P10: بابیت دوم | P11: بابیت نزدیک پینیون آسیاب'
    if 'کراشر' in name or 'کراشر' in etype:
        return 'P1: انتهای موتور | P2: سر موتور | P3: یاتاقان سمت فیکس (پولی کوچک) | P4: یاتاقان سمت آزاد (پولی کوچک) | P5: یاتاقان فیکس (روتور) | P6: یاتاقان سمت آزاد (روتور)'
    if 'فن' in name or 'فن' in etype:
        return 'P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس | P4: یاتاقان آزاد'
    return 'راهنمای نقاط تعریف نشده است.'
# ==============================================================================
# 6. رابط کاربری و فیلترها
# ==============================================================================
if df is not None:
    # شناسایی ستون‌ها با تابع منعطف
    col_line = find_col(df.columns, 'خط تولید', 'خط')
    col_unit = find_col(df.columns, 'واحد')
    col_title = find_col(df.columns, 'عنوان تجهیز', 'نام تجهیز')
    col_date = find_col(df.columns, 'تاریخ')
    point_col = find_col(df.columns, 'نقطه', 'point')
    with st.expander('🔍 سیستم جستجو و فیلتر پیشرفته', expanded=True):
        f1, f2, f3, f4, f5 = st.columns(5)
        with f1:
            sel_line = st.selectbox('📍 خط تولید:', ['همه'] + sorted([str(v) for v in df[col_line].unique() if pd.notna(v)]) if col_line else ['همه'])
        with f2:
            sel_unit = st.selectbox('🏢 واحد:', ['همه'] + sorted([str(v) for v in df[col_unit].unique() if pd.notna(v)]) if col_unit else ['همه'])
        with f3:
            search_eq = st.text_input('🔍 نام تجهیز:', '')
        with f4:
            selected_point = st.selectbox('📍 نقطه:', ['همه'] + [f'P{i}' for i in range(1, 13)])
        with f5:
            sel_date = st.selectbox('📅 تاریخ:', ['همه تاریخ‌ها'] + sorted([str(v) for v in df[col_date].unique() if pd.notna(v)], reverse=True) if col_date else ['همه تاریخ‌ها'])
    # فیلترینگ هوشمند
    filtered_df = df.copy()
    if col_line and sel_line != 'همه':
        filtered_df = filtered_df[filtered_df[col_line].apply(clean_text) == clean_text(sel_line)]
    if col_unit and sel_unit != 'همه':
        filtered_df = filtered_df[filtered_df[col_unit].apply(clean_text) == clean_text(sel_unit)]
    if col_title and search_eq:
        filtered_df = filtered_df[filtered_df[col_title].str.contains(search_eq, case=False, na=False)]
    if point_col and selected_point != 'همه':
        filtered_df = filtered_df[filtered_df[point_col].astype(str).str.upper().str.strip() == selected_point.upper()]
    if col_date and sel_date != 'همه تاریخ‌ها':
        filtered_df = filtered_df[filtered_df[col_date].apply(clean_text) == clean_text(sel_date)]
    if not filtered_df.empty:
        # نمایش داده‌ها با رنگ‌بندی
        vib_keywords = ['افقی', 'عمودی', 'محوری', 'mm/s']
        vib_cols = [c for c in filtered_df.columns if any(k in str(c) for k in vib_keywords)]
        styled_df = filtered_df.style
        if vib_cols:
            styled_df = styled_df.map(color_vibration, subset=vib_cols)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info('🔎 هیچ داده‌ای با این فیلترها یافت نشد.')
    st.markdown('<div style="text-align:center; margin-top:20px; font-weight:bold;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>', unsafe_allow_html=True)
else:
    st.error('❌ خطا در دریافت داده‌ها. لطفاً اتصال اینترنت و لینک گوگل‌شیت را بررسی کنید.')
