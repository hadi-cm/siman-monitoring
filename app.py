import pandas as pd
import streamlit as st
import base64

# ==============================================================================
# 1. تنظیمات امنیتی و دسترسی
# ==============================================================================
USER_CREDENTIALS = {
    "alireza76ir@gmail.com": "siman123",
    "vah.rezaei@gmail.com": "siman123",
    "cm.zandiyeh@gmail.com": "siman123",
    "tehrancement@gmail.com": "siman123",
    "masoud.sa.1989823@gmail.com": "siman123",
}

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if not st.session_state["authenticated"]:
        st.markdown("<h2 style='text-align: center;'>🔐 ورود به سامانه هوشمند پایش وضعیت سیمان تهران</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            email = st.text_input("ایمیل کاربری:")
            password = st.text_input("رمز عبور:", type="password")
            if st.form_submit_button("ورود به داشبورد"):
                email_clean = email.strip().lower()
                found_email = next((k for k in USER_CREDENTIALS if k.strip().lower() == email_clean), None)
                if found_email and USER_CREDENTIALS[found_email].strip() == password.strip():
                    st.session_state["authenticated"] = True
                    st.rerun()
                else:
                    st.error("❌ ایمیل یا رمز عبور اشتباه است.")
        return False
    return True

if not check_password():
    st.stop()

# ==============================================================================
# 2. پیکربندی صفحه و استایل‌های CSS
# ==============================================================================
st.set_page_config(page_title="داشبورد فنی ارتعاشات سیمان تهران", layout="wide")

def get_image_base64(path):
    try:
        with open(path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except: return ""

logo_siman_base64 = get_image_base64("client_logo.png")
logo_faz_fidar_base64 = get_image_base64("my_logo.png")

st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; background-color: white; padding: 15px 30px; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
        <img src="data:image/png;base64,{logo_faz_fidar_base64}" style="width: 110px; height: auto;">
        <div style="text-align: center; color: #1E3A8D; font-size: 26px; font-weight: bold; font-family: 'Tahoma';">🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران</div>
        <img src="data:image/png;base64,{logo_siman_base64}" style="width: 110px; height: auto;">
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 3. مدیریت داده‌ها و اتصال به گوگل‌شیت
# ==============================================================================
VIB_URL = "https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0"

@st.cache_data(ttl=60)
def load_and_process_data():
    try:
        df = pd.read_csv(VIB_URL)
        df.columns = df.columns.str.strip()
        df = df.astype(str).apply(lambda x: x.str.strip())
        if "سیستم درایور" in df.columns:
            df = df.rename(columns={"سیستم درایور": "نوع اتصال"})
        numeric_cols = ["بالانس", "هزینه"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col].str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"❌ خطا در دریافت داده‌ها: {e}")
        return None

df = load_and_process_data()

if df is not None:
    # --- بخش فیلترها ---
    with st.expander("🔍 سیستم جستجو و فیلتر پیشرفته", expanded=True):
        # استفاده از 5 ستون برای نمایش بهتر
        f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns([1, 1, 1, 1, 1])
        
        with f_col1:
            all_lines = sorted([str(x) for x in df["خط تولید"].unique() if str(x) not in ['nan', 'None', '']]) if "خط تولید" in df.columns else []
            selected_line = st.selectbox("📍 خط تولید:", ["همه"] + all_lines)
        with f_col2:
            all_units = sorted([str(x) for x in df["واحد"].unique() if str(x) not in ['nan', 'None', '']]) if "واحد" in df.columns else []
            selected_unit = st.selectbox("🏢 واحد:", ["همه"] + all_units)
        with f_col3:
            search_eq = st.text_input("🔍 نام تجهیز:", "")
        with f_col4:
            point_list = ["همه"] + [f"P{i}" for i in range(1, 12)]
            selected_point = st.selectbox("📍 نقطه:", point_list)
        with f_col5:
            date_col_name = next((col for col in df.columns if "تاریخ" in col), None)
            selected_date = "همه تاریخ‌ها"
            if date_col_name and not df.empty:
                available_dates = sorted(df[date_col_name].unique(), reverse=True)
                selected_date = st.selectbox("📅 تاریخ:", ["همه تاریخ‌ها"] + list(available_dates))

    # اعمال فیلترها
    filtered_df = df.copy()
    if selected_line != "همه": filtered_df = filtered_df[filtered_df["خط تولید"] == selected_line]
    if selected_unit != "همه": filtered_df = filtered_df[filtered_df["واحد"] == selected_unit]
    if search_eq: filtered_df = filtered_df[filtered_df["عنوان تجهیز"].str.contains(search_eq, case=False, na=False)]
    
    # --- هوشمندسازی شناسایی ستون نقاط ---
    point_col_name = None
    for col in df.columns:
        if df[col].astype(str).str.contains('P\d+', na=False).any():
            point_col_name = col
            break
    
    if point_col_name and selected_point != "همه":
        filtered_df = filtered_df[filtered_df[point_col_name] == selected_point]

    if selected_date != "همه تاریخ‌ها" and date_col_name:
        filtered_df = filtered_df[filtered_df[date_col_name] == selected_date]

    # نمایش تحلیل فنی
    st.markdown("### 📈 وضعیت تحلیل فنی")
    m1, m2, m3 = st.columns(3)
    with m1: st.metric("تعداد رکورد یافت شده", len(filtered_df))
    with m2:
        bal_count = filtered_df[filtered_df["بالانس"] != 0].shape[0] if "بالانس" in filtered_df.columns else 0
        st.metric("تعداد بالانس شده", bal_count)
    with m3:
        total_cost = filtered_df["هزینه"].sum() if "هزینه" in filtered_df.columns else 0
        st.metric("جمع کل هزینه‌ها", f"{total_cost:,.0f} تومان")

    # نمایش جدول
    st.markdown("### 📋 جدول جزئیات پایش و مقایسه")
    vib_cols = [col for col in filtered_df.columns if any(name in str(col) for name in ["افقی", "عمودی", "محوری", "mm/s"])]

    def color_vibration(val):
        try:
            num = float(str(val).replace(",", ".").replace("٫", "."))
            if num > 7.2: return 'background-color: #ffcccc; color: #9b0000; font-weight: bold'
            if num > 4.7: return 'background-color: #fff2b2; color: #856404; font-weight: bold'
            return 'background-color: #e6ffed; color: #2e7d32'
        except: return ''

    if vib_cols:
        styled_df = filtered_df.style.map(color_vibration, subset=vib_cols)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        st.info("💡 راهنمای رنگی: سبز (عادی) | زرد (هشدار ۴.۷-۷.۲) | قرمز (خطر بالای ۷.۲)")
    else:
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    st.markdown('<div style="text-align:center; margin-top:20px; font-weight:bold;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>', unsafe_allow_html=True)
else:
    st.error("❌ خطا در دریافت داده‌ها.")
