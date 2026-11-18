import re
import pandas as pd
import streamlit as st
import base64
import plotly.express as px

# ==============================================================================
# 0. تنظیمات صفحه
# ==============================================================================
st.set_page_config(page_title='داشبورد فنی ارتعاشات سیمان تهران', layout='wide')

# ==============================================================================
# 1. ورود
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
            if st.form_submit_button('ورود به داشبورد'):
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
# 2. توابع کمکی (اصلاح شده)
# ==============================================================================
def norm(x):
    """نرمال‌سازی کامل: اعداد فارسی/عربی -> انگلیسی، یکدست‌سازی ی/ک، حذف فاصله‌های اضافی"""
    if x is None or pd.isna(x):
        return ''
    s = str(x).strip()
    # جایگزینی اعداد فارسی و عربی با انگلیسی
    farsi_nums = '۰۱۲۳۴۵۶۷۸۹'
    arabic_nums = '٠١٢٣٤٥٦٧٨٩'
    english_nums = '0123456789'
    for f, e in zip(farsi_nums, english_nums): s = s.replace(f, e)
    for a, e in zip(arabic_nums, english_nums): s = s.replace(a, e)
    # یکدست‌سازی حروف ی و ک
    s = s.replace('ي', 'ی').replace('ى', 'ی').replace('ك', 'ک')
    # حذف نیم‌فاصله و کاراکترهای کنترلی
    s = s.replace('\u200c', ' ').replace('\xa0', ' ')
    # حذف فاصله‌های اضافه و تبدیل به حروف کوچک
    s = ' '.join(s.split()).lower()
    return s

def clean_text(text):
    return norm(text)

def get_image_base64(path):
    try:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    except:
        return ''

def smart_find_column(columns, keywords):
    if columns is None: return None
    for k in keywords:
        for c in columns:
            if k.lower() in str(c).strip().lower(): return c
    return None

def to_num(series):
    """تبدیل امن به عدد برای محاسبات و نمودار"""
    s = (series.astype(str)
         .str.replace('٫', '.', regex=False)
         .str.replace(',', '.', regex=False)
         .str.strip())
    s = s.replace({'': None, 'nan': None, 'None': None, '---': None})
    return pd.to_numeric(s, errors='coerce')

def get_point_guide(eq_name, eq_type):
    name = norm(eq_name)
    etype = norm(eq_type)
    if 'گیربکس' in name or 'گیربکس' in etype:
        return 'P1: انتهای موتور | P2: جلوی موتور | P3: محور ورودی گیربکس | P4: سمت آزاد محور ورودی | P5: سمت فیکس محور دوم | P6: سمت آزاد محور دوم | P7: سمت فیکس محور سوم | P8: سمت آزاد محور سوم | P9: بابیت اول سمت گیربکس | P10: بابیت دوم | P11: بابیت نزدیک پینیون آسیاب'
    if 'کراشر' in name or 'کراشر' in etype:
        return 'P1: انتهای موتور | P2: سر موتور | P3: یاتاقان سمت فیکس (پولی کوچک) | P4: یاتاقان سمت آزاد (پولی کوچک) | P5: یاتاقان فیکس (روتور) | P6: یاتاقان سمت آزاد (روتور)'
    if 'فن' in name or 'فن' in etype:
        return 'P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس | P4: یاتاقان آزاد'
    return 'راهنمای نقاط تعریف نشده است.'

# ==============================================================================
# 3. هدر
# ==============================================================================
logo_siman = get_image_base64('client_logo.png')
logo_faz = get_image_base64('my_logo.png')
st.markdown(f'''
<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; background:white; padding:15px 30px; border-radius:15px; box-shadow:0 4px 8px rgba(0,0,0,0.1);'>
    <img src='data:image/png;base64,{logo_faz}' style='width:110px; height:auto;'>
    <div style='text-align:center; color:#1E3A8D; font-size:26px; font-weight:bold; font-family:Tahoma;'>🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران</div>
    <img src='data:image/png;base64,{logo_siman}' style='width:110px; height:auto;'>
</div>
''', unsafe_allow_html=True)

# ==============================================================================
# 4. بارگذاری داده (همه چیز به صورت متن خام → بدون صفر اضافه)
# ==============================================================================
VIB_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0'
ASSETS_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=1'

@st.cache_data(ttl=600)
def load_all_data():
    df_vib = pd.DataFrame()
    df_assets = pd.DataFrame()
    try:
        # استفاده از dtype=str برای جلوگیری از تبدیل خودکار اعداد به float (رفع مشکل صفر اضافه)
        df_vib = pd.read_csv(VIB_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception as e:
        st.error(f"❌ خطا در خواندن شیت ارتعاشات: {e}")
    try:
        df_assets = pd.read_csv(ASSETS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception as e:
        st.warning(f"⚠️ شیت مشخصات فنی (Assets) بارگذاری نشد. ({e})")
    return df_vib, df_assets

df, df_assets = load_all_data()

# ==============================================================================
# 5. فیلترها
# ==============================================================================
st.sidebar.header("🔍 فیلترهای پیشرفته")

if not df.empty:
    col_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
    col_unit = smart_find_column(df.columns, ['واحد'])
    equip_col = smart_find_column(df.columns, ['نام تجهیز', 'تجهیز', 'Equipment', 'Asset', 'عنوان تجهیز'])
    date_col = smart_find_column(df.columns, ['تاریخ', 'Date'])

    # ساخت ستون‌های کلید نرمال‌شده برای تطبیق دقیق نام‌ها
    df['_k_line'] = df[col_line].apply(norm) if col_line else ''
    df['_k_unit'] = df[col_unit].apply(norm) if col_unit else ''
    df['_k_eq'] = df[equip_col].apply(norm) if equip_col else ''
    df['_k_date'] = df[date_col].apply(norm) if date_col else ''

    def get_display_map(key_col, original_col):
        if original_col is None: return {}
        tmp = df[df[key_col] != ''].copy()
        if tmp.empty: return {}
        # پیدا کردن پر تکرارترین حالت اصلی برای نمایش در منو
        return tmp.groupby(key_col)[original_col].agg(lambda x: x.str.strip().value_counts().idxmax()).to_dict()

    line_map = get_display_map('_k_line', col_line)
    unit_map = get_display_map('_k_unit', col_unit)
    eq_map = get_display_map('_k_eq', equip_col)

    # ۱. خط تولید
    lines = sorted(line_map.keys())
    sel_line_k = st.sidebar.selectbox("📍 خط تولید:", ["همه"] + lines, format_func=lambda k: "همه" if k == "همه" else line_map.get(k, k))

    # ۲. واحد
    unit_keys = []
    if sel_line_k != "همه":
        unit_keys = sorted(df[df['_k_line'] == sel_line_k]['_k_unit'].unique())
        unit_keys = [u for u in unit_keys if u != '']

    sel_unit_k = st.sidebar.selectbox("🏢 واحد:", ["همه"] + unit_keys, format_func=lambda k: "همه" if k == "همه" else unit_map.get(k, k))

    # ۳. تجهیز
    eq_keys = []
    if sel_line_k != "همه":
        temp_df = df[df['_k_line'] == sel_line_k]
        if sel_unit_k != "همه":
            temp_df = temp_df[temp_df['_k_unit'] == sel_unit_k]
        eq_keys = sorted(temp_df['_k_eq'].unique())
        eq_keys = [e for e in eq_keys if e != '']

    sel_eq_k = st.sidebar.selectbox("⚙️ انتخاب تجهیز:", ["همه تجهیزات"] + eq_keys, format_func=lambda k: "همه تجهیزات" if k == "همه تجهیزات" else eq_map.get(k, k))

    # ۴. جستجوی آزاد (برای حل مشکل "میل فن مواد 8")
    search_eq = st.sidebar.text_input("🔎 جستجوی سریع تجهیز:", placeholder="مثلاً: میل فن")

    # ۵. تاریخ
    st.sidebar.markdown("📅 فیلتر تاریخ")
    date_search = st.sidebar.text_input("جستجوی تاریخ (مثلاً ۱۴۰۵/۰۸):")

    date_map = {}
    if date_col:
        tmp_d = df[df['_k_date'] != ''].copy()
        date_map = tmp_d.groupby('_k_date')[date_col].agg(lambda x: x.str.strip().value_counts().idxmax()).to_dict()

    date_keys = sorted(list(date_map.keys()), reverse=True)
    sel_date_k = st.sidebar.selectbox("🌙 انتخاب تاریخ:", ["همه تاریخ‌ها"] + date_keys, format_func=lambda k: "همه تاریخ‌ها" if k == "همه تاریخ‌ها" else date_map.get(k, k))

    # ==============================================================================
    # 6. اعمال فیلترها
    # ==============================================================================
    fdf = df.copy()

    if sel_line_k != "همه": fdf = fdf[fdf['_k_line'] == sel_line_k]
    if sel_unit_k != "همه": fdf = fdf[fdf['_k_unit'] == sel_unit_k]
    if sel_eq_k != "همه تجهیزات": fdf = fdf[fdf['_k_eq'] == sel_eq_k]

    if search_eq:
        q = norm(search_eq)
        fdf = fdf[fdf['_k_eq'].apply(lambda x: q in x if q else False)]

    if date_search:
        fdf = fdf[fdf['_k_date'].str.contains(norm(date_search), na=False)]

    if sel_date_k != "همه تاریخ‌ها":
        fdf = fdf[fdf['_k_date'] == sel_date_k]

    # مرتب‌سازی (جدیدترین در بالا)
    if date_col:
        fdf = fdf.sort_values(by=date_col, ascending=False)

    # ==============================================================================
    # 7. نمایش
    # ==============================================================================
    st.markdown('<style>.main .block-container { padding-right:1rem; padding-left:1rem; }</style>', unsafe_allow_html=True)
    st.title("📊 تحلیل روند ارتعاشات تجهیزات")

    if not fdf.empty:
        # مشخصات فنی
        if sel_eq_k != "همه تجهیزات" and not df_assets.empty:
            a_name = smart_find_column(df_assets.columns, ['نام تجهیز', 'نام', 'تجهیز'])
            if a_name:
                # تطبیق نرم در Assets
                target = sel_eq_k
                rows = df_assets[df_assets[a_name].apply(lambda x: target in norm(x) or norm(x) in target)].copy()
                if not rows.empty:
                    r0 = rows.iloc[0]
                    def gv(ks):
                        c = smart_find_column(df_assets.columns, ks)
                        return str(r0[c]).strip() if c and r0[c] not in ('', 'nan', 'None') else '---'

                    e_type = gv(['نوع'])
                    st.markdown(f'''
                    <div style='background:#f0f7ff; padding:20px; border-radius:15px; border-right:10px solid #1E3A8D; margin-bottom:15px; text-align:right; direction:rtl;'>
                        <h3 style='color:#1E3A8D; margin-top:0; font-family:Tahoma;'>🛠️ مشخصات فنی: {eq_map.get(sel_eq_k, sel_eq_k)}</h3>
                        <div style='display:flex; gap:20px; font-size:16px;'>
                            <span><b>🔹 نوع:</b> {e_type}</span>
                            <span><b>🔹 دور:</b> {gv(['دور'])} RPM</span>
                            <span><b>🔹 واحد:</b> {gv(['واحد'])}</span>
                        </div>
                        <div style='margin-top:12px; background:#e6efff; padding:8px 15px; border-radius:8px; display:inline-block;'>
                            <b>📍 راهنمای نقاط:</b> {get_point_guide(eq_map.get(sel_eq_k, sel_eq_k), e_type)}
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)

                    pts, brg, bsh = smart_find_column(df_assets.columns, ['نقطه']), smart_find_column(df_assets.columns, ['بیرینگ']), smart_find_column(df_assets.columns, ['بوش'])
                    cols = [c for c in [pts, brg, bsh] if c]
                    if cols:
                        with st.expander("📦 قطعات و لجستیک", expanded=True):
                            st.dataframe(rows[cols], hide_index=True, use_container_width=True)

        # نمودار سلامت
        vib_cols = [c for c in df.columns if any(k in str(c) for k in ['عمودی', 'افقی', 'محوری'])]
        if vib_cols:
            chart_df = fdf.copy()
            # تبدیل برای محاسبات نمودار (فقط در اینجا)
            v_data = chart_df[vib_cols].apply(to_num, axis=0).max(axis=1)
            def cat(v):
                if pd.isna(v): return 'نامشخص'
                return 'بحرانی' if v > 7.1 else 'هشدار' if v > 4.5 else 'سالم'
            status = v_data.map(cat).value_counts()
            if not status.empty:
                st.markdown("### 📈 وضعیت سلامت")
                fig = px.pie(values=status.values, names=status.index, color=status.index,
                             color_discrete_map={'سالم':'#2e7d32', 'هشدار':'#ffa500', 'بحرانی':'#ff4b4b', 'نامشخص':'#9e9e9e'})
                st.plotly_chart(fig, use_container_width=True)

        # ------------------ جدول نتایج ------------------
        st.markdown(f"### 📋 نتایج یافت شده ({len(fdf)} مورد)")

        def color_vib(val):
            try:
                v = float(str(val).replace('٫', '.').replace(',', '.').strip())
                if v > 7.1: return 'background-color: #ff4b4b; color: white'
                elif v > 4.5: return 'background-color: #ffa500; color: white'
                else: return 'background-color: #2e7d32; color: white'
            except: return ''

        # --- اصلاح اصلی: حذف ستون‌های مخفی از نمایش ---
        # تمام ستون‌هایی که با '_k_' شروع می‌شوند را از لیست ستون‌های نمایشی حذف می‌کنیم
        visible_cols = [c for c in fdf.columns if not str(c).startswith('_k_')]
        
        vib_cols = [c for c in visible_cols if any(k in str(c) for k in ['عمودی', 'افقی', 'محوری'])]

        if vib_cols:
            # اعمال رنگ فقط روی ستون‌های ارتعاشات
            styled_df = fdf[visible_cols].style.map(color_vib, subset=vib_cols)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.dataframe(fdf[visible_cols], use_container_width=True, hide_index=True)


    else:
        st.warning("⚠️ داده‌ای یافت نشد.")

    st.markdown('<div style="text-align:center; margin-top:50px; color:#555; font-family:Tahoma;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>', unsafe_allow_html=True)
else:
    st.error("❌ خطا در دریافت داده‌ها.")
