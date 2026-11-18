import pandas as pd
import streamlit as st
import base64
import datetime
import plotly.express as px
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
    'm.babahasan@gmail.com': 'siman123',
    'freedocs.ir@gmail.com': 'siman123',
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
# 2. توابع کمکی (بهبود یافته برای پاک‌سازی داده‌ها)
# ==============================================================================
def clean_text(text):
    if pd.isna(text): return ''
    text = str(text).strip()
    # تبدیل اعداد فارسی و عربی به انگلیسی برای یکدستی
    farsi_nums = '۰۱۲۳۴۵۶۷۸۹'
    arabic_nums = '٠١٢٣٤٥٦٧٨٩'
    english_nums = '0123456789'
    for f, e in zip(farsi_nums, english_nums): text = text.replace(f, e)
    for a, e in zip(arabic_nums, english_nums): text = text.replace(a, e)
    # حذف فاصله‌های اضافی در ابتدا، انتها و وسط
    return ' '.join(text.split()).lower()
def get_image_base64(path):
    try:
        with open(path, 'rb') as image_file: return base64.b64encode(image_file.read()).decode()
    except: return ''
def smart_find_column(columns, keywords):
    if columns is None: return None
    for k in keywords:
        for c in columns:
            if k.lower() in str(c).strip().lower(): return c
    return None
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
# 4. بارگذاری داده‌ها
# ==============================================================================
VIB_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0'
ASSETS_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=1'
@st.cache_data(ttl=600)
def load_all_data():
    try:
        df_vib = pd.read_csv(VIB_URL)
        date_col = smart_find_column(df_vib.columns, ['تاریخ', 'Date'])
        if date_col:
            df_vib[date_col] = df_vib[date_col].astype(str)
        try:
            df_assets = pd.read_csv(ASSETS_URL)
        except:
            df_assets = pd.DataFrame()
        return df_vib, df_assets
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری داده‌ها: {e}")
        return pd.DataFrame(), pd.DataFrame()
df, df_assets = load_all_data()
# ==============================================================================
# 5. فیلترهای پیشرفته
# ==============================================================================
st.sidebar.header("🔍 فیلترهای پیشرفته")
if not df.empty:
    col_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
    col_unit = smart_find_column(df.columns, ['واحد'])
    equip_col = smart_find_column(df.columns, ['تجهیز', 'Equipment', 'Asset', 'عنوان تجهیز', 'نام تجهیز'])
    date_col = smart_find_column(df.columns, ['تاریخ', 'Date'])
    if col_line:
        lines = sorted([str(v) for v in df[col_line].unique() if pd.notna(v)])
        sel_line = st.sidebar.selectbox("📍 خط تولید:", ["همه"] + lines)
    else: sel_line = "همه"
    if col_unit:
        unit_df = df.copy()
        if sel_line != "همه" and col_line: unit_df = unit_df[unit_df[col_line].astype(str) == sel_line]
        units = sorted([str(v) for v in unit_df[col_unit].unique() if pd.notna(v)])
        sel_unit = st.sidebar.selectbox("🏢 واحد:", ["همه"] + units)
    else: sel_unit = "همه"
    if equip_col:
        eq_df = df.copy()
        if sel_line != "همه" and col_line: eq_df = eq_df[eq_df[col_line].astype(str) == sel_line]
        if sel_unit != "همه" and col_unit: eq_df = eq_df[eq_df[col_unit].astype(str) == sel_unit]
        equipment_list = sorted([str(v) for v in eq_df[equip_col].unique() if pd.notna(v)])
        selected_equipment = st.sidebar.selectbox("⚙️ انتخاب تجهیز:", ["همه تجهیزات"] + equipment_list)
    else: selected_equipment = "همه تجهیزات"
    st.sidebar.markdown("**📅 فیلتر تاریخ**")
    date_filter = st.sidebar.text_input("جستجوی تاریخ (مثلاً ۱۴۰۵/۰۸):", placeholder="مثلاً ۱۴۰۵/۰۸")
    if date_col:
        all_dates = sorted([str(v) for v in df[date_col].unique() if pd.notna(v)])
        selected_date_dropdown = st.sidebar.selectbox("🌙 انتخاب تاریخ دقیق:", ["همه تاریخ‌ها"] + all_dates)
    else: selected_date_dropdown = "همه تاریخ‌ها"
    # ==============================================================================
    # 6. منطق فیلتر کردن (با پاک‌سازی هوشمند متنی)
    # ==============================================================================
    filtered_df = df.copy()
    if sel_line != "همه" and col_line:
        filtered_df = filtered_df[filtered_df[col_line].astype(str).str.strip() == sel_line.strip()]
    if sel_unit != "همه" and col_unit:
        filtered_df = filtered_df[filtered_df[col_unit].astype(str).str.strip() == sel_unit.strip()]
    if selected_equipment != "همه تجهیزات" and equip_col:
        # --- نکته طلایی: پاک‌سازی هر دو طرف برای جلوگیری از مشکل فاصله و حروف ---
        selected_clean = clean_text(selected_equipment)
        filtered_df = filtered_df[filtered_df[equip_col].apply(lambda x: clean_text(x) == selected_clean)]
    if date_filter and date_col:
        filtered_df = filtered_df[filtered_df[date_col].astype(str).str.contains(date_filter)]
    if selected_date_dropdown != "همه تاریخ‌ها" and date_col:
        filtered_df = filtered_df[filtered_df[date_col].astype(str) == selected_date_dropdown]
    # ==============================================================================
    # 7. نمایش محتوا
    # ==============================================================================
    st.markdown('<style>.main .block-container { padding-right: 1rem; padding-left: 1rem; }</style>', unsafe_allow_html=True)
    st.title("📊 تحلیل روند ارتعاشات تجهیزات")
    if not filtered_df.empty:
        if selected_equipment != "همه تجهیزات" and not df_assets.empty:
            asset_name_col = smart_find_column(df_assets.columns, ['نام تجهیز', 'نام', 'تجهیز'])
            if asset_name_col:
                target_clean = clean_text(selected_equipment)
                asset_rows = df_assets[df_assets[asset_name_col].apply(lambda x: target_clean in clean_text(x) or clean_text(x) in target_clean)].copy()
                if not asset_rows.empty:
                    first_row = asset_rows.iloc[0]
                    def get_val_safe(k_list):
                        c = smart_find_column(df_assets.columns, k_list)
                        return str(first_row[c]).strip() if c and pd.notna(first_row[c]) else '---'
                    e_type = get_val_safe(['نوع'])
                    st.markdown(f'''
                    <div style='background-color: #f0f7ff; padding: 20px; border-radius: 15px; border-right: 10px solid #1E3A8D; margin-bottom: 15px; text-align: right; direction: rtl;'>
                        <h3 style='color: #1E3A8D; margin-top: 0; font-family: Tahoma;'>🛠️ مشخصات فنی: {selected_equipment}</h3>
                        <div style='display: flex; justify-content: flex-start; font-size: 16px; color: #333; flex-wrap: wrap; gap: 20px;'>
                            <span><b style='color: #1E3A8D;'>🔹 نوع:</b> {e_type}</span>
                            <span><b style='color: #1E3A8D;'>🔹 دور:</b> {get_val_safe(['دور'])} RPM</span>
                            <span><b style='color: #1E3A8D;'>🔹 واحد:</b> {get_val_safe(['واحد'])}</span>
                        </div>
                        <div style='margin-top: 12px; font-size: 15px; color: #1E3A8D; background: #e6efff; padding: 8px 15px; border-radius: 8px; display: inline-block;'>
                            <b style='color: #1E3A8D;'>📍 راهنمای نقاط (P-Map):</b> {get_point_guide(selected_equipment, e_type)}
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
        # تحلیل سلامت
        vib_cols = [c for c in filtered_df.columns if any(k in str(c) for k in ['عمودی', 'افقی', 'محوری'])]
        if vib_cols:
            chart_df = filtered_df.copy()
            chart_df['Max_Vib'] = chart_df[vib_cols].apply(pd.to_numeric, errors='coerce').max(axis=1)
            def categorize(val):
                if pd.isna(val): return 'نامشخص'
                return 'بحرانی' if val > 7.1 else 'هشدار' if val > 4.5 else 'سالم'
            chart_df['Status'] = chart_df['Max_Vib'].apply(categorize)
            status_counts = chart_df['Status'].value_counts()
            if not status_counts.empty:
                st.markdown("### 📈 تحلیل وضعیت سلامت")
                fig_pie = px.pie(values=status_counts.values, names=status_counts.index, 
                                 color=status_counts.index, color_discrete_map={'سالم': '#2e7d32', 'هشدار': '#ffa500', 'بحرانی': '#ff4b4b', 'نامشخص': '#9e9e9e'})
                st.plotly_chart(fig_pie, use_container_width=True)
        st.markdown(f"### 📋 نتایج یافت شده ({len(filtered_df)} مورد)")
        def color_vib(val):
            try:
                v = float(str(val).replace(',', '.'))
                return 'background-color: #ff4b4b; color: white' if v > 7.1 else 'background-color: #ffa500; color: white' if v > 4.5 else 'background-color: #2e7d32; color: white'
            except: return ''
        if vib_cols:
            st.dataframe(filtered_df.style.map(color_vib, subset=vib_cols), use_container_width=True)
        else:
            st.dataframe(filtered_df, use_container_width=True)
    else:
        st.warning("⚠️ هیچ داده‌ای با این فیلترها پیدا نشد.")
    st.markdown('<div style="text-align:center; margin-top:60px; font-weight:bold; color: #555; font-family: Tahoma;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>', unsafe_allow_html=True)
else:
    st.error("❌ خطا در دریافت داده‌ها.")
