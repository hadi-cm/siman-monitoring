import pandas as pd
import streamlit as st
import base64
# ==============================================================================
# 0. تنظیمات صفحه
# ==============================================================================
st.set_page_config(page_title="داشبورد فنی ارتعاشات سیمان تهران", layout="wide")
# ==============================================================================
# 1. تنظیمات امنیتی و ورود
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
# 2. توابع کمکی
# ==============================================================================
def clean_text(text):
    if pd.isna(text): return ""
    text = str(text).strip()
    farsi_nums = "۰۱۲۳۴۵۶۷۸۹"
    arabic_nums = "٠١٢٣٤٥٦٧٨٩"
    english_nums = "0123456789"
    for f, e in zip(farsi_nums, english_nums): text = text.replace(f, e)
    for a, e in zip(arabic_nums, english_nums): text = text.replace(a, e)
    return " ".join(text.split()).lower()
def get_image_base64(path):
    try:
        with open(path, "rb") as image_file: return base64.b64encode(image_file.read()).decode()
    except: return ""
# ==============================================================================
# 3. هدر و لوگوها
# ==============================================================================
logo_siman_base64 = get_image_base64("client_logo.png")
logo_faz_fidar_base64 = get_image_base64("my_logo.png")
st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; background-color: white; padding: 15px 30px; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
        <img src="data:image/png;base64,{logo_faz_fidar_base64}" style="width: 110px; height: auto;">
        <div style="text-align: center; color: #1E3A8D; font-size: 26px; font-weight: bold; font-family: Tahoma;">🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران</div>
        <img src="data:image/png;base64,{logo_siman_base64}" style="width: 110px; height: auto;">
    </div>
    """, unsafe_allow_html=True)
# ==============================================================================
# 4. بارگذاری داده‌ها
# ==============================================================================
VIB_URL = "https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0"
ASSETS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTI4vONsowudctVbskGkkSyQNqkkGZ8AuiykO9UKeE-8FSBZemWkR4q5DSAhpXEqwQkgsCUQy44Vvqx/pub?gid=1276803564&single=true&output=csv"
@st.cache_data(ttl=60)
def load_all_data():
    try:
        df_vib = pd.read_csv(VIB_URL)
        df_vib.columns = df_vib.columns.str.strip()
        title_col = next((c for c in df_vib.columns if "عنوان تجهیز" in c or "نام تجهیز" in c), None)
        if title_col: df_vib[title_col] = df_vib[title_col].replace(r"^\s*$", pd.NA, regex=True).ffill()
        df_vib = df_vib.astype(str).apply(lambda x: x.str.strip())
        df_assets = None
        try:
            df_assets = pd.read_csv(ASSETS_URL)
            df_assets.columns = df_assets.columns.str.strip()
            df_assets = df_assets.astype(str).apply(lambda x: x.str.strip())
        except: df_assets = None
        return df_vib, df_assets
    except Exception as e:
        st.error(f"❌ خطا در دریافت داده‌ها: {e}")
        return None, None
df, df_assets = load_all_data()
# ==============================================================================
# 5. راهنمای نقاط
# ==============================================================================
def get_point_guide(eq_name, eq_type):
    name = str(eq_name).lower()
    etype = str(eq_type).lower() if eq_type else ""
    if "گیربکس" in name or "گیربکس" in etype: return "P1: انتهای موتور | P2: جلوی موتور | P3: محور ورودی گیربکس | P4: سمت آزاد محور ورودی | P5: سمت فیکس محور دوم | P6: سمت آزاد محور دوم | P7: سمت فیکس محور سوم | P8: سمت آزاد محور سوم | P9: بابیت اول سمت گیربکس | P10: بابیت دوم | P11: بابیت نزدیک پینیون آسیاب"
    if "کراشر" in name or "کراشر" in etype: return "P1: انتهای موتور | P2: سر موتور | P3: یاتاقان سمت فیکس (پولی کوچک) | P4: یاتاقان سمت آزاد (پولی کوچک) | P5: یاتاقان فیکس (روتور) | P6: یاتاقان سمت آزاد (روتور)"
    if "فن" in name or "فن" in etype: return "P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس | P4: یاتاقان آزاد"
    return "راهنمای نقاط تعریف نشده است."
# ==============================================================================
# 6. رابط کاربری و فیلترها
# ==============================================================================
if df is not None:
    col_line = next((c for c in df.columns if "خط تولید" in c), None)
    col_unit = next((c for c in df.columns if "واحد" in c), None)
    col_title = next((c for c in df.columns if "عنوان تجهیز" in c or "نام تجهیز" in c), None)
    col_date = next((c for c in df.columns if "تاریخ" in c), None)
    point_col = next((c for c in df.columns if "نقطه" in str(c).lower() or "point" in str(c).lower()), None)
    with st.expander("🔍 سیستم جستجو و فیلتر پیشرفته", expanded=True):
        f1, f2, f3, f4, f5 = st.columns(5)
        with f1: 
            if col_line:
                all_lines = sorted([str(v) for v in df[col_line].unique() if pd.notna(v)])
                selected_line = st.selectbox("📍 خط تولید:", ["همه"] + all_lines)
            else: selected_line = "همه"
        with f2: 
            if col_unit:
                all_units = sorted([str(v) for v in df[col_unit].unique() if pd.notna(v)])
                selected_unit = st.selectbox("🏢 واحد:", ["همه"] + all_units)
            else: selected_unit = "همه"
        with f3: search_eq = st.text_input("🔍 نام تجهیز:", "")
        with f4: selected_point = st.selectbox("📍 نقطه:", ["همه"] + [f"P{i}" for i in range(1, 13)])
        with f5: 
            if col_date:
                all_dates = sorted([str(v) for v in df[col_date].unique() if pd.notna(v)], reverse=True)
                selected_date = st.selectbox("📅 تاریخ:", ["همه تاریخ‌ها"] + all_dates)
            else: selected_date = "همه تاریخ‌ها"
    # فیلتر کردن داده‌ها (بدون محدود کردن تعداد ردیف‌ها)
    filtered_df = df.copy()
    if col_line and selected_line != "همه":
        filtered_df = filtered_df[filtered_df[col_line].apply(clean_text) == clean_text(selected_line)]
    if col_unit and selected_unit != "همه":
        filtered_df = filtered_df[filtered_df[col_unit].apply(clean_text) == clean_text(selected_unit)]
    if col_title and search_eq:
        filtered_df = filtered_df[filtered_df[col_title].str.contains(search_eq, case=False, na=False)]
    if point_col and selected_point != "همه":
        filtered_df = filtered_df[filtered_df[point_col].astype(str).str.upper() == selected_point.upper()]
    if col_date and selected_date != "همه تاریخ‌ها":
        filtered_df = filtered_df[filtered_df[col_date].apply(clean_text) == clean_text(selected_date)]
    if not filtered_df.empty:
        eq_name_val = filtered_df[col_title].iloc[0] if col_title else ""
        if df_assets is not None:
            asset_name_col = next((c for c in df_assets.columns if "نام" in c or "تجهیز" in c), df_assets.columns[0])
            # جستجوی منعطف: اگر نام تجهیز ارتعاشات شامل نام تجهیز Assets باشد یا برعکس
            target_clean = clean_text(eq_name_val)
            asset_rows = df_assets[df_assets[asset_name_col].apply(lambda x: target_clean in clean_text(x) or clean_text(x) in target_clean)].copy()
            if not asset_rows.empty:
                first_row = asset_rows.iloc[0]
                def get_val(k):
                    c = next((c for c in df_assets.columns if k in c), None)
                    return str(first_row[c]).strip() if c and str(first_row[c]).strip().lower() not in ['nan', 'none', ''] else "---"
                eq_type = get_val("نوع")
                st.markdown(f"""
                <div style="background-color: #f0f7ff; padding: 20px; border-radius: 15px; border-right: 10px solid #1E3A8D; margin-bottom: 15px;">
                    <h3 style="color: #1E3A8D; margin-top: 0;">🛠️ مشخصات فنی: {eq_name_val}</h3>
                    <div style="display: flex; gap: 20px; font-size: 16px;">
                        <span><b style="color: #1E3A8D;">🔹 نوع:</b> {eq_type}</span> | <span><b style="color: #1E3A8D;">🔹 دور:</b> {get_val("دور")} RPM</span> | <span><b style="color: #1E3A8D;">🔹 واحد:</b> {get_val("واحد")}</span>
                    </div>
                    <div style="margin-top: 12px; font-size: 15px; color: #1E3A8D; background: #e6efff; padding: 8px 15px; border-radius: 8px; display: inline-block;">
                        <b style="color: #1E3A8D;">📍 راهنمای نقاط:</b> {get_point_guide(eq_name_val, eq_type)}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                pts = next((c for c in df_assets.columns if "نقطه" in c), df_assets.columns[4] if len(df_assets.columns)>4 else df_assets.columns[0])
                brg = next((c for c in df_assets.columns if "بیرینگ" in c), None)
                bsh = next((c for c in df_assets.columns if "بوش" in c), None)
                cols = [pts] + ([brg] if brg else []) + ([bsh] if bsh else [])
                st.dataframe(asset_rows[cols].rename(columns={pts:"نقطه", brg:"بیرینگ", bsh:"بوش"}), hide_index=True, use_container_width=True)
            else:
                st.warning(f"⚠️ مشخصات فنی برای تجهیز '{eq_name_val}' در شیت Assets یافت نشد.")
        m1, m2, m3 = st.columns(3)
        with m1: st.metric("تعداد رکوردها", len(filtered_df))
        with m2: 
            bal_col = next((c for c in filtered_df.columns if "بالانس" in c), None)
            st.metric("تعداد بالانس شده", len(filtered_df[filtered_df[bal_col] != "0"]) if bal_col else "0")
        with m3:
            cost_col = next((c for c in filtered_df.columns if "هزینه" in c), None)
            cost = pd.to_numeric(filtered_df[cost_col].str.replace(r'[^\d.]', '', regex=True), errors='coerce').sum() if cost_col else 0
            st.metric("جمع هزینه‌ها", f"{cost:,.0f} تومان")
        st.markdown("### 📋 جزئیات پایش و مقایسه (تمام سوابق)")
        def color_v(val):
            try:
                n = float(str(val).replace(",", ".").replace("٫", "."))
                if n > 7.2: return 'background-color: #ffcccc; color: #9b0000; font-weight: bold'
                if n > 4.7: return 'background-color: #fff2b2; color: #856404; font-weight: bold'
                return 'background-color: #e6ffed; color: #2e7d32'
            except: return ''
        vib_cols = [c for c in filtered_df.columns if any(k in c for k in ["افقی", "عمودی", "محوری", "mm/s"])]
        st.dataframe(filtered_df.style.map(color_v, subset=vib_cols), use_container_width=True, hide_index=True)
    else:
        st.info("🔎 داده‌ای با این مشخصات یافت نشد.")
    st.markdown('<div style="text-align:center; margin-top:20px; font-weight:bold;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>', unsafe_allow_html=True)
else:
    st.error("❌ خطا در دریافت داده‌ها. لطفاً اتصال اینترنت و لینک گوگل‌شیت را بررسی کنید.")
