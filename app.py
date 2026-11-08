import pandas as pd
import streamlit as st
import base64

st.set_page_config(page_title="داشبورد فنی ارتعاشات سیمان تهران", layout="wide")

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

def clean_text(text):
    if pd.isna(text): return ""
    text = str(text).strip()
    farsi_nums = "۰۱۲۳۴۵۶۷۸۹"
    arabic_nums = "٠١٢٣٤٥٦٧٨٩"
    english_nums = "0123456789"
    for f, e in zip(farsi_nums, english_nums): text = text.replace(f, e)
    for a, e in zip(arabic_nums, english_nums): text = text.replace(a, e)
    return " ".join(text.split()).lower()

def find_col(cols, *keywords):
    for k in keywords:
        for c in cols:
            if k in str(c): return c
    return None

def get_image_base64(path):
    try:
        with open(path, "rb") as image_file: return base64.b64encode(image_file.read()).decode()
    except: return ""

logo_siman_base64 = get_image_base64("client_logo.png")
logo_faz_fidar_base64 = get_image_base64("my_logo.png")

st.markdown(f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; background-color: white; padding: 15px 30px; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);">
        <img src="data:image/png;base64,{logo_faz_fidar_base64}" style="width: 110px; height: auto;">
        <div style="text-align: center; color: #1E3A8D; font-size: 26px; font-weight: bold; font-family: Tahoma;">🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران</div>
        <img src="data:image/png;base64,{logo_siman_base64}" style="width: 110px; height: auto;">
    </div>
    """, unsafe_allow_html=True)

VIB_URL = "https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0"
ASSETS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTI4vONsowudctVbskGkkSyQNqkkGZ8AuiykO9UKeE-8FSBZemWkR4q5DSAhpXEqwQkgsCUQy44Vvqx/pub?gid=1276803564&single=true&output=csv"

@st.cache_data(ttl=60)
def load_all_data():
    try:
        df_vib = pd.read_csv(VIB_URL)
        df_vib.columns = df_vib.columns.str.strip()

        tcol = find_col(df_vib.columns, "عنوان تجهیز", "نام تجهیز")
        if tcol:
            df_vib[tcol] = df_vib[tcol].replace(r"^\s*$", pd.NA, regex=True).ffill()

        df_vib = df_vib.astype(str).apply(lambda x: x.str.strip())
        df_vib = df_vib.replace({"nan": "", "None": "", "none": ""})

        df_assets = None
        try:
            df_assets = pd.read_csv(ASSETS_URL)
            df_assets.columns = df_assets.columns.str.strip()
            df_assets = df_assets.astype(str).apply(lambda x: x.str.strip())
        except Exception:
            df_assets = None

        return df_vib, df_assets
    except Exception as e:
        st.error(f"❌ خطا در دریافت داده‌ها: {e}")
        return None, None

df, df_assets = load_all_data()

def get_point_guide(eq_name, eq_type):
    name = str(eq_name).lower()
    etype = str(eq_type).lower() if eq_type else ""
    if "گیربکس" in name or "گیربکس" in etype:
        return "P1: انتهای موتور | P2: سر موتور | P3: محور ورودی گیربکس | P4: سمت آزاد محور ورودی | P5: فیکس محور دوم | P6: آزاد محور دوم | P7: فیکس محور سوم | P8: آزاد محور سوم | P9: بابیت اول | P10: بابیت دوم | P11: بابیت پینیون"
    if "کراشر" in name or "کراشر" in etype:
        return "P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس (پولی کوچک) | P4: یاتاقان آزاد (پولی کوچک) | P5: یاتاقان فیکس روتور | P6: یاتاقان آزاد روتور"
    if "فن" in name or "فن" in etype:
        return "P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس | P4: یاتاقان آزاد"
    return "راهنمای نقاط تعریف نشده است."

if df is not None:
    col_line = find_col(df.columns, "خط تولید", "خط")
    col_unit = find_col(df.columns, "واحد")
    col_title = find_col(df.columns, "عنوان تجهیز", "نام تجهیز")
    col_date = find_col(df.columns, "تاریخ")
    point_col = find_col(df.columns, "نقطه", "point")

    with st.expander("🩺 عیب‌یابی داده‌ها (موقت)", expanded=False):
        st.write("ستون‌های ارتعاشات:", df.columns.tolist())
        st.write("تعداد کل رکوردها:", len(df))
        if col_date:
            st.write("تعداد تاریخ‌های یکتا:", df[col_date].nunique())
            st.write("تاریخ‌ها:", sorted(df[col_date].unique().tolist()))
        if col_title:
            st.write("تجهیزات:", sorted([x for x in df[col_title].unique().tolist() if x]))
        if df_assets is not None:
            st.write("ستون‌های Assets:", df_assets.columns.tolist())

    with st.expander("🔍 سیستم جستجو و فیلتر پیشرفته", expanded=True):
        f1, f2, f3, f4, f5 = st.columns(5)
        with f1:
            selected_line = st.selectbox("📍 خط تولید:", ["همه"] + (sorted(df[col_line].unique().tolist()) if col_line else []))
        with f2:
            selected_unit = st.selectbox("🏢 واحد:", ["همه"] + (sorted(df[col_unit].unique().tolist()) if col_unit else []))
        with f3:
            search_eq = st.text_input("🔍 نام تجهیز:", "")
        with f4:
            selected_point = st.selectbox("📍 نقطه:", ["همه"] + [f"P{i}" for i in range(1, 13)])
        with f5:
            selected_date = st.selectbox("📅 تاریخ:", ["همه تاریخ‌ها"] + (sorted(df[col_date].unique().tolist(), reverse=True) if col_date else []))

    filtered_df = df.copy()
    if col_line and selected_line != "همه":
        filtered_df = filtered_df[filtered_df[col_line].apply(clean_text) == clean_text(selected_line)]
    if col_unit and selected_unit != "همه":
        filtered_df = filtered_df[filtered_df[col_unit].apply(clean_text) == clean_text(selected_unit)]
    if col_title and search_eq:
        filtered_df = filtered_df[filtered_df[col_title].apply(clean_text).str.contains(clean_text(search_eq), na=False)]
    if point_col and selected_point != "همه":
        filtered_df = filtered_df[filtered_df[point_col].astype(str).str.upper().str.strip() == selected_point.upper()]
    if col_date and selected_date != "همه تاریخ‌ها":
        filtered_df = filtered_df[filtered_df[col_date].apply(clean_text) == clean_text(selected_date)]

    if not filtered_df.empty:
        eq_name_val = filtered_df[col_title].iloc[0] if col_title else ""

        if df_assets is not None:
            asset_name_col = find_col(df_assets.columns, "نام تجهیز", "نام", "تجهیز")
            target_clean = clean_text(eq_name_val)

            asset_rows = df_assets[df_assets[asset_name_col].apply(
                lambda x: bool(clean_text(x)) and (target_clean in clean_text(x) or clean_text(x) in target_clean)
            )].copy()

            asset_pts = find_col(df_assets.columns, "نقطه")
            if asset_pts:
                asset_rows = asset_rows[asset_rows[asset_pts].astype(str).str.upper().str.startswith("P")]

            if not asset_rows.empty:
                first_row = asset_rows.iloc[0]
                def get_val(k):
                    c = find_col(df_assets.columns, k)
                    if c is None: return "---"
                    v = str(first_row[c]).strip()
                    return v if v.lower() not in ['', 'nan', 'none'] else "---"

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

                brg = find_col(df_assets.columns, "بیرینگ")
                bsh = find_col(df_assets.columns, "بوش")
                show_cols = [asset_pts] + ([brg] if brg else []) + ([bsh] if bsh else [])
                st.dataframe(asset_rows[show_cols].rename(columns={asset_pts: "نقطه", brg: "بیرینگ", bsh: "بوش"}),
                             hide_index=True, use_container_width=True)
            else:
                st.warning(f"⚠️ مشخصات فنی برای تجهیز '{eq_name_val}' در شیت Assets یافت نشد.")

        m1, m2, m3 = st.columns(3)
        with m1: st.metric("تعداد رکوردها", len(filtered_df))
        with m2:
            bal_col = find_col(filtered_df.columns, "بالانس")
            st.metric("تعداد بالانس شده", len(filtered_df[filtered_df[bal_col].astype(str) != "0"]) if bal_col else "0")
        with m3:
            cost_col = find_col(filtered_df.columns, "هزینه")
            cost = pd.to_numeric(filtered_df[cost_col].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce').fillna(0).sum() if cost_col else 0
            st.metric("جمع هزینه‌ها", f"{cost:,.0f} تومان")

        st.markdown("### 📋 جزئیات پایش و مقایسه (تمام سوابق)")

        def color_v(val):
            try:
                n = float(str(val).replace(",", ".").replace("٫", "."))
                if n > 7.2: return 'background-color: #ffcccc; color: #9b0000; font-weight: bold'
                if n > 4.7: return 'background-color: #fff2b2; color: #856404; font-weight: bold'
                return 'background-color: #e6ffed; color: #2e7d32'
            except: return ''

        vib_cols = [c for c in filtered_df.columns if any(k in str(c) for k in ["افقی", "عمودی", "محوری", "mm/s"])]
        st.dataframe(filtered_df.style.map(color_v, subset=vib_cols) if vib_cols else filtered_df,
                     use_container_width=True, hide_index=True)
    else:
        st.info("🔎 داده‌ای با این مشخصات یافت نشد.")

    st.markdown('<div style="text-align:center; margin-top:20px; font-weight:bold;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>', unsafe_allow_html=True)
else:
    st.error("❌ خطا در دریافت داده‌ها. لطفاً اتصال اینترنت و لینک گوگل‌شیت را بررسی کنید
