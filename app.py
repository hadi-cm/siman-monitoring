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
# 2. پیکربندی صفحه و استایل‌ها
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
# 3. مدیریت داده‌ها (با قابلیت Fill Down خودکار)
# ==============================================================================
VIB_URL = "https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0"
ASSETS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTI4vONsowudctVbskGkkSyQNqkkGZ8AuiykO9UKeE-8FSBZemWkR4q5DSAhpXEqwQkgsCUQy44Vvqx/pub?gid=1276803564&single=true&output=csv"
@st.cache_data(ttl=60)
def load_all_data():
    try:
        df_vib = pd.read_csv(VIB_URL)
        df_vib.columns = df_vib.columns.str.strip()
        # --- بخش جادویی: پر کردن خودکار سلول‌های خالی در ستون عنوان تجهیز ---
        title_col = next((c for c in df_vib.columns if "عنوان تجهیز" in c or "نام تجهیز" in c), None)
        if title_col:
            # ابتدا سلول‌های خالی را پیدا می‌کنیم و مقدار ردیف قبلی را در آن‌ها قرار می‌دهیم
df_vib[title_col] = df_vib[title_col].replace('', None).replace('nan', None).fillna(method='ffill')        df_vib = df_vib.astype(str).apply(lambda x: x.str.strip())
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
# 4. راهنمای نقاط
# ==============================================================================
def get_point_guide(eq_name, eq_type):
    name = str(eq_name).lower()
    etype = str(eq_type).lower() if eq_type else ""
    if "گیربکس" in name or "گیربکس" in etype:
        return "P1: انتهای موتور | P2: جلوی موتور | P3: محور ورودی گیربکس | P4: سمت آزاد محور ورودی | P5: سمت فیکس محور دوم | P6: سمت آزاد محور دوم | P7: سمت فیکس محور سوم | P8: سمت آزاد محور سوم | P9: بابیت اول سمت گیربکس | P10: بابیت دوم | P11: بابیت نزدیک پینیون آسیاب"
    if "کراشر" in name or "کراشر" in etype:
        return "P1: انتهای موتور | P2: سر موتور | P3: یاتاقان سمت فیکس (پولی کوچک) | P4: یاتاقان سمت آزاد (پولی کوچک) | P5: یاتاقان فیکس (روتور) | P6: یاتاقان سمت آزاد (روتور)"
    if "فن" in name or "فن" in etype:
        if "ایر اسلاید" in name: return "P1: انتهای موتور | P2: سر موتور"
        return "P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس | P4: یاتاقان آزاد"
    if any(x in name or x in etype for x in ["کمپرسور", "پمپ", "موتور", "بلوئر"]):
        return "P1: انتهای موتور | P2: سر موتور | P3: محور ورودی | P4: محور خروجی"
    return "راهنمای نقاط تعریف نشده است."
# ==============================================================================
# 5. رابط کاربری و فیلترها
# ==============================================================================
if df is not None:
    with st.expander("🔍 سیستم جستجو و فیلتر پیشرفته", expanded=True):
        f_col1, f_col2, f_col3, f_col4, f_col5 = st.columns([1, 1, 1, 1, 1])
        col_line = next((c for c in df.columns if "خط تولید" in c), None)
        with f_col1:
            if col_line:
                all_lines = sorted({str(v).strip() for v in df[col_line].dropna().tolist() if str(v).strip() and str(v).strip().lower() != "nan"})
                selected_line = st.selectbox("📍 خط تولید:", ["همه"] + list(all_lines))
            else: selected_line = "همه"
        col_unit = next((c for c in df.columns if "واحد" in c), None)
        with f_col2:
            if col_unit:
                all_units = sorted({str(v).strip() for v in df[col_unit].dropna().tolist() if str(v).strip() and str(v).strip().lower() != "nan"})
                selected_unit = st.selectbox("🏢 واحد:", ["همه"] + list(all_units))
            else: selected_unit = "همه"
        col_title = next((c for c in df.columns if "عنوان تجهیز" in c or "نام تجهیز" in c), None)
        with f_col3:
            search_eq = st.text_input("🔍 نام تجهیز:", "")
        with f_col4:
            selected_point = st.selectbox("📍 نقطه:", ["همه"] + [f"P{i}" for i in range(1, 13)])
        col_date = next((c for c in df.columns if "تاریخ" in c), None)
        with f_col5:
            if col_date:
                all_dates = sorted({str(v).strip() for v in df[col_date].dropna().tolist() if str(v).strip() and str(v).strip().lower() != "nan"}, reverse=True)
                selected_date = st.selectbox("📅 تاریخ:", ["همه تاریخ‌ها"] + list(all_dates))
            else: selected_date = "همه تاریخ‌ها"
    filtered_df = df.copy()
    if col_line and selected_line != "همه": filtered_df = filtered_df[filtered_df[col_line] == selected_line]
    if col_unit and selected_unit != "همه": filtered_df = filtered_df[filtered_df[col_unit] == selected_unit]
    if col_title and search_eq: filtered_df = filtered_df[filtered_df[col_title].str.contains(search_eq, case=False, na=False)]
    point_col = next((c for c in df.columns if df[c].astype(str).str.contains('P\d+', na=False).any()), None)
    if point_col and selected_point != "همه": 
        filtered_df = filtered_df[filtered_df[point_col] == selected_point]
    if col_date and selected_date != "همه تاریخ‌ها": filtered_df = filtered_df[filtered_df[col_date] == selected_date]
    # ==============================================================================
    # 6. نمایش مشخصات فنی (با قابلیت جستجوی هوشمند)
    # ==============================================================================
    if not filtered_df.empty:
        eq_name_val = filtered_df[col_title].iloc[0] if col_title else "نامشخص"
        asset_row = None
        if df_assets is not None:
            asset_name_col = next((c for c in df_assets.columns if "نام" in c or "تجهیز" in c), None)
            if asset_name_col:
                # تطابق دقیق
                match = df_assets[df_assets[asset_name_col] == eq_name_val]
                if not match.empty:
                    asset_row = match.iloc[0]
                else:
                    # تطابق تقریبی (اگر فقط بخشی از نام مشترک بود)
                    parts = eq_name_val.split()
                    if len(parts) > 1:
                        fuzzy_match = df_assets[df_assets[asset_name_col].str.contains(parts[0], na=False)]
                        if not fuzzy_match.empty: asset_row = fuzzy_match.iloc[0]
        if asset_row is not None:
            eq_type = next((asset_row[c] for c in df_assets.columns if "نوع" in c), "نامشخص")
            bearing = next((asset_row[c] for c in df_assets.columns if "بیرینگ" in c), "ثبت نشده")
            bush = next((asset_row[c] for c in df_assets.columns if "بوش" in c), "---")
            rpm = next((asset_row[c] for c in df_assets.columns if "دور" in c), "نامشخص")
            unit_val = next((asset_row[c] for c in df_assets.columns if "واحد" in c), "نامشخص")
            if bush.lower() in ['nan', 'none', '']: bush = "---"
            st.markdown(f"""
            <div style="background-color: #f0f7ff; padding: 20px; border-radius: 15px; border-right: 10px solid #1E3A8D; margin-bottom: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);">
                <h3 style="color: #1E3A8D; margin-top: 0; font-family: 'Tahoma';">🛠️ مشخصات فنی تجهیز: {eq_name_val}</h3>
                <div style="display: flex; justify-content: space-between; font-size: 16px; color: #333; flex-wrap: wrap; gap: 10px;">
                    <span><b style="color: #1E3A8D;">🔹 نوع:</b> {eq_type}</span>
                    <span><b style="color: #1E3A8D;">🔹 دور:</b> {rpm} RPM</span>
                    <span><b style="color: #1E3A8D;">🔹 واحد:</b> {unit_val}</span>
                </div >
                <div style="margin-top: 12px; font-size: 15px; color: #1E3A8D; background: #e6efff; padding: 8px 15px; border-radius: 8px; display: inline-block;">
                    <b style="color: #1E3A8D;">📍 راهنمای نقاط (P-Map):</b> {get_point_guide(eq_name_val, eq_type)}
                </div >
            </div >
            """, unsafe_allow_html=True)
            with st.expander("📦 اطلاعات لجستیکی و قطعات (بیرینگ و بوش)", expanded=True):
                c1, c2 = st.columns(2)
                with c1: st.markdown(f"**🛢️ شماره بیرینگ:*\n`{bearing}`")
                with c2: st.markdown(f"⚙️ شماره بوش:*\n`{bush}`")
        else:
            st.warning(f"⚠️ مشخصات فنی برای تجهیز '{eq_name_val}' یافت نشد.")
        # متریک‌ها و جدول
        m1, m2, m3 = st.columns(3)
        with m1: st.metric("تعداد رکورد یافت شده", len(filtered_df))
        with m2:
            bal_col = next((c for c in filtered_df.columns if "بالانس" in c), None)
            bal_count = filtered_df[filtered_df[bal_col] != '0'].shape[0] if bal_col else 0
            st.metric("تعداد بالانس شده", bal_count)
        with m3:
            cost_col = next((c for c in filtered_df.columns if "هزینه" in c), None)
            try:
                total_cost = pd.to_numeric(filtered_df[cost_col].str.replace(r'[^\d.]', '', regex=True), errors='coerce').sum() if cost_col else 0
                st.metric("جمع کل هزینه‌ها", f"{total_cost:,.0f} تومان")
            except: st.metric("جمع کل هزینه‌ها", "نامشخص")
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
            st.dataframe(filtered_df.style.map(color_vibration, subset=vib_cols), use_container_width=True, hide_index=True)
        else:
            st.dataframe(filtered_df, use_container_width=True, hide_index=True)
    else:
        st.info("🔎 هیچ داده‌ای با این فیلترها یافت نشد.")
    st.markdown('<div style="text-align:center; margin-top:20px; font-weight:bold;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div >', unsafe_allow_html=True)
else:
    st.error("❌ خطا در دریافت داده‌ها. لطفلط اتصال اینترنت و لینک گوگل‌شیت را بررسی کنید.")
