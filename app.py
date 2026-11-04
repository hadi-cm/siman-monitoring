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
        <div style="text-align: center; color: #1E3A8D; font-size: 26px; font-weight: bold; font-family: 'Tahoma';">🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران</div >
        <img src="data:image/png;base64,{logo_siman_base64}" style="width: 110px; height: auto;">
    </div >
    """, unsafe_allow_html=True)
# ==============================================================================
# 3. مدیریت داده‌ها و اتصال به گوگل‌شیت
# ==============================================================================
# لینک شیت اصلی (ارتعاشات)
VIB_URL = "https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0"
# لینک شیت مشخصات فنی (Assets) - حتماً باید gid مربوط به آن تب را در اینجا جایگزین کنید
https://docs.google.com/spreadsheets/d/e/2PACX-1vTI4vONsowudctVbskGkkSyQNqkkGZ8AuiykO9UKeE-8FSBZemWkR4q5DSAhpXEqwQkgsCUQy44Vvqx/pub?gid=1276803564&single=true&output=csvdef load_all_data():
    try:
        df_vib = pd.read_csv(VIB_URL)
        df_vib.columns = df_vib.columns.str.strip()
        df_vib = df_vib.astype(str).apply(lambda x: x.str.strip())
        try:
            df_assets = pd.read_csv(ASSETS_URL)
            df_assets.columns = df_assets.columns.str.strip()
            df_assets = df_assets.astype(str).apply(lambda x: x.str.strip())
        except:
            df_assets = None
        return df_vib, df_assets
    except Exception as e:
        st.error(f"❌ خطا در دریافت داده‌ها: {e}")
        return None, None
df, df_assets = load_all_data()
# ==============================================================================
# 4. منطق هوشمند راهنمای نقاط (Point Map)
# ==============================================================================
def get_point_guide(eq_name, eq_type):
    name = eq_name.lower()
    etype = eq_type.lower() if eq_type else ""
    if "فن" in name or "فن" in etype:
        if "ایر اسلاید" in name:
            return "P1: انتهای موتور | P2: سر موتور"
        return "P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس | P4: یاتاقان آزاد"
    if any(x in name or x in etype for x in ["کمپرسور", "پمپ", "موتور", "بلوئر"]):
        return "P1: انتهای موتور | P2: سر موتور | P3: محور ورودی/سر تجهیز | P4: انتهای تجهیز/سمت آزاد"
    if "کراشر" in name or "کراشر" in etype:
        return "P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس (صغیر) | P4: یاتاقان آزاد (صغیر) | P5: یاتاقان فیکس (کبیر) | P6: یاتاقان آزاد (کبیر)"
    if "گیربکس" in name or "گیربکس" in etype:
        return "P1: انتهای موتور | P2: سر موتور | P3: محور ورودی | P4: محور خروجی | ... (مطابق نقشه فنی)"
    return "راهنمای نقاط برای این تجهیز تعریف نشده است."
# ==============================================================================
# 5. رابط کاربری و فیلترها
# ==============================================================================
if df is not None:
    with st.expander("🔍 سیستم جستجو و فیلتر پیشرفته", expanded=True):
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
            point_list = ["همه"] + [f"P{i}" for i in range(1, 13)]
            selected_point = st.selectbox("📍 نقطه:", point_list)
        with f_col5:
            date_col_name = next((col for col in df.columns if "تاریخ" in col), None)
            selected_date = "همه تاریخ‌ها"
            if date_col_name:
                available_dates = sorted(df[date_col_name].unique(), reverse=True)
                selected_date = st.selectbox("📅 تاریخ:", ["همه تاریخ‌ها"] + list(available_dates))
    # اعمال فیلترها
    filtered_df = df.copy()
    if selected_line != "همه": filtered_df = filtered_df[filtered_df["خط تولید"] == selected_line]
    if selected_unit != "همه": filtered_df = filtered_df[filtered_df["واحد"] == selected_unit]
    if search_eq: filtered_df = filtered_df[filtered_df["عنوان تجهیز"].str.contains(search_eq, case=False, na=False)]
    # فیلتر نقطه (هوشمند)
    point_col_name = next((col for col in df.columns if df[col].astype(str).str.contains('P\d+', na=False).any()), None)
    if point_col_name and selected_point != "همه":
        filtered_df = filtered_df[filtered_df[point_col_name] == selected_point]
    if selected_date != "همه تاریخ‌ها" and date_col_name:
        filtered_df = filtered_df[filtered_df[date_col_name] == selected_date]
    # ==============================================================================
    # 6. بخش نمایش اطلاعات فنی (The Asset Intelligence)
    # ==============================================================================
    if not filtered_df.empty:
        sample_eq_name = filtered_df["عنوان تجهیز"].iloc[0]
        if df_assets is not None:
            asset_info = df_assets[df_assets["نام تجهیز"] == sample_eq_name]
            if not asset_info.empty:
                row = asset_info.iloc[0]
                eq_type = row.get("نوع تجهیز", "نامشخص")
                st.markdown(f"""
                <div style="background-color: #f0f7ff; padding: 20px; border-radius: 15px; border-right: 10px solid #1E3A8D; margin-bottom: 20px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                    <h3 style="color: #1E3A8D; margin-top: 0; font-family: 'Tahoma';">🛠️ مشخصات فنی تجهیز: {sample_eq_name}</h3>
                    <div style="display: flex; justify-content: space-between; font-size: 16px; color: #333;">
                        <span><b>🔹 نوع:</b> {eq_type}</span>
                        <span><b>🔹 دور:</b> {row.get('دور نامی', 'نامشخص')} RPM</span>
                        <span><b>🔹 واحد:</b> {row.get('واحد', 'نامشخص')}</span>
                    </div>
                    <hr style="border: 0.5px solid #ddd; margin: 15px 0;">
                    <div style="background-color: white; padding: 12px; border-radius: 10px; border: 1px solid #dceefb; font-size: 15px; color: #1E3A8D;">
                        <b>📌 راهنمای نقاط (P-Map):</b> {get_point_guide(sample_eq_name, eq_type)}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                # نمایش اطلاعات بیرینگ و سایر موارد در یک باکس جداگانه برای واحد خرید
                with st.expander("📦 اطلاعات لجستیکی و قطعات (برای واحد خرید/تعمیرات)"):
                    st.write(f"**📌 شماره بیرینگ:** {row.get('شماره بیرینگ', 'ثبت نشده')}")
                    st.write(f"**📌 سیستم درایو:** {row.get('سیستم درایو', 'نامشخص')}")
            else:
                st.warning(f"⚠️ مشخصات فنی برای تجهیز {sample_eq_name} در شیت Assets یافت نشد.")
        # نمایش تحلیل فنی سریع
        m1, m2, m3 = st.columns(3)
        with m1: st.metric("تعداد رکورد یافت شده", len(filtered_df))
        with m2:
            bal_count = filtered_df[filtered_df["بالانس"] != '0'].shape[0] if "بالانس" in filtered_df.columns else 0
            st.metric("تعداد بالانس شده", bal_count)
        with m3:
            try:
                total_cost = pd.to_numeric(filtered_df["هزینه"].str.replace(r'[^\d.]', '', regex=True), errors='coerce').sum()
                st.metric("جمع کل هزینه‌ها", f"{total_cost:,.0f} تومان")
            except: st.metric("جمع کل هزینه‌ها", "نامشخص")
        # نمایش جدول با رنگ‌بندی ارتعاشات
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
    else:
        st.info("🔎 هیچ داده‌ای با این فیلترها یافت نشد.")
    st.markdown('<div style="text-align:center; margin-top:20px; font-weight:bold;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div >', unsafe_allow_html=True)
else:
    st.error("❌ خطا در دریافت داده‌ها. لطفاً اتصال اینترنت و لینک گوگل‌شیت را بررسی کنید.")
