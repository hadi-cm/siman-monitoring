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
# 2. توابع نرمال‌سازی (قلب حل مشکل تطبیق نام‌ها)
# ==============================================================================
TRANS_TABLE = str.maketrans(
    '۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩يكىۀةأإآ',
    '01234567890123456789یکیههههااا'
)
def norm(x):
    """نرمال‌سازی کامل: اعداد فارسی→انگلیسی، یکدست‌سازی ی/ک، حذف نیم‌فاصله و فاصله اضافی"""
    if x is None:
        return ''
    s = str(x)
    s = s.replace('\u200c', ' ').replace('\xa0', ' ')
    s = s.translate(TRANS_TABLE)
    s = s.replace('-', ' ').replace('_', ' ').replace('.', ' ')
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s
def clean_text(text):
    return norm(text)
def get_image_base64(path):
    try:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ''
def smart_find_column(columns, keywords):
    if columns is None:
        return None
    for k in keywords:
        for c in columns:
            if k.lower() in str(c).strip().lower():
                return c
    return None
def to_num(series):
    """تبدیل امن به عدد (ممیز فارسی/عربی، کاما)"""
    s = (series.astype(str)
         .str.replace('٫', '.', regex=False)
         .str.replace(',', '.', regex=False)
         .str.replace('،', '.', regex=False)
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
        # dtype=str + keep_default_na=False → هیچ عددی به float تبدیل نمی‌شود
        df_vib = pd.read_csv(VIB_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception as e:
        st.error(f"❌ خطا در خواندن شیت ارتعاشات: {e}")
    try:
        df_assets = pd.read_csv(ASSETS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception as e:
        st.warning(f"⚠️ شیت مشخصات فنی (Assets) خوانده نشد — gid این شیت را چک کنید. ({e})")
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
    # --- ساخت کلیدهای نرمال‌شده (راه‌حل اصلی مشکل تطبیق) ---
    df['_k_line'] = df[col_line].map(norm) if col_line else ''
    df['_k_unit'] = df[col_unit].map(norm) if col_unit else ''
    df['_k_eq'] = df[equip_col].map(norm) if equip_col else ''
    df['_k_date'] = df[date_col].map(norm) if date_col else ''
    def display_map(key_col, original_col):
        """کلید نرمال → نام نمایشی (پرتکرارترین شکل اصلی)"""
        tmp = df[df[key_col] != '']
        if tmp.empty or original_col is None:
            return {}
        best = (tmp.groupby(key_col)[original_col]
                   .agg(lambda s: s.str.strip().value_counts().idxmax()))
        return best.to_dict()
    line_map = display_map('_k_line', col_line)
    unit_map = display_map('_k_unit', col_unit)
    eq_map = display_map('_k_eq', equip_col)
    # ---------- خط تولید ----------
    lines = sorted(line_map.keys())
    sel_line_key = st.sidebar.selectbox(
        "📍 خط تولید:", ["همه"] + lines,
        format_func=lambda k: "همه" if k == "همه" else line_map.get(k, k)
    )
    # ---------- واحد (وابسته به خط) ----------
    base = df.copy()
    if sel_line_key != "همه":
        base = base[base['_k_line'] == sel_line_key]
    unit_map_f = display_map('_k_unit', col_unit) if False else None
    units_available = sorted([u for u in base['_k_unit'].unique() if u != ''])
    sel_unit_key = st.sidebar.selectbox(
        "🏢 واحد:", ["همه"] + units_available,
        format_func=lambda k: "همه" if k == "همه" else unit_map.get(k, k)
    )
    # ---------- تجهیز (وابسته به خط و واحد) ----------
    if sel_unit_key != "همه":
        base = base[base['_k_unit'] == sel_unit_key]
    eq_available = sorted([e for e in base['_k_eq'].unique() if e != ''])
    sel_eq_key = st.sidebar.selectbox(
        "⚙️ انتخاب تجهیز:", ["همه تجهیزات"] + eq_available,
        format_func=lambda k: "همه تجهیزات" if k == "همه تجهیزات" else eq_map.get(k, k)
    )
    # ---------- جستجوی آزاد نام تجهیز ----------
    search_text = st.sidebar.text_input(
        "🔎 جستجوی نام تجهیز (اختیاری):",
        placeholder="مثلاً: میل فن مواد 8"
    )
    # ---------- تاریخ ----------
    st.sidebar.markdown("**📅 فیلتر تاریخ**")
    date_search = st.sidebar.text_input("جستجوی تاریخ:", placeholder="مثلاً 1405/08").strip()
    date_display_map = {}
    if date_col:
        tmp_dates = df[df[col].notna()] if False else df[df['_k_date'] != '']
        date_display_map = (tmp_dates.groupby('_k_date')[date_col]
                            .agg(lambda s: s.str.strip().value_counts().idxmax()).to_dict())
    date_keys = list(date_display_map.keys())
    date_keys.sort(reverse=True)
    sel_date_key = st.sidebar.selectbox(
        "🌙 انتخاب تاریخ:", ["همه تاریخ‌ها"] + date_keys,
        format_func=lambda k: "همه تاریخ‌ها" if k == "همه تاریخ‌ها" else date_display_map.get(k, k)
    )
    # ==============================================================================
    # 6. منطق فیلتر کردن
    # ==============================================================================
    fdf = df.copy()
    if sel_line_key != "همه":
        fdf = fdf[fdf['_k_line'] == sel_line_key]
    if sel_unit_key != "همه":
        fdf = fdf[fdf['_k_unit'] == sel_unit_key]
    if sel_eq_key != "همه تجهیزات":
        fdf = fdf[fdf['_k_eq'] == sel_eq_key]
    # جستجوی آزاد (نرمال‌شده → تفاوت فاصله/عدد فارسی اثری ندارد)
    if search_text.strip():
        q = norm(search_text)
        tokens = [t for t in q.split() if t]
        if tokens:
            mask = fdf['_k_eq'].apply(lambda v: all(t in v for t in tokens))
            if mask.any():
                fdf = fdf[mask]
            else:
                st.info(f"ℹ️ تجهیزی با عبارت «{search_text}» پیدا نشد؛ همه نتایج نمایش داده می‌شود.")
    if date_search:
        fdf = fdf[fdf['_k_date'].str.contains(norm(date_search), na=False)]
    if sel_date_key != "همه تاریخ‌ها":
        fdf = fdf[fdf['_k_date'] == sel_date_key]
    # مرتب‌سازی: جدیدترین بالا (تلاش برای تاریخ، در غیر این صورت متن نزولی)
    if date_col:
        tmp_date = pd.to_datetime(fdf[date_col], errors='coerce')
        if tmp_date.notna().any():
            fdf = fdf.assign(_sortd=tmp_date).sort_values('_sortd', ascending=False).drop(columns=['_sortd'])
        else:
            fdf = fdf.sort_values('_k_date', ascending=False)
    # ==============================================================================
    # 7. نمایش
    # ==============================================================================
    st.markdown('<style>.main .block-container { padding-right:1rem; padding-left:1rem; }</style>', unsafe_allow_html=True)
    st.title("📊 تحلیل روند ارتعاشات تجهیزات")
    vib_cols = [c for c in df.columns if any(k in str(c) for k in ['عمودی', 'افقی', 'محوری'])]
    visible_cols = [c for c in df.columns if not c.startswith('_k_')]
    if not fdf.empty:
        # ---------- کارت مشخصات فنی ----------
        if sel_eq_key != "همه تجهیزات" and not df_assets.empty:
            a_name = smart_find_column(df_assets.columns, ['نام تجهیز', 'نام', 'تجهیز'])
            if a_name:
                target = sel_eq_key
                rows = df_assets[df_assets[a_name].map(norm) == target]
                if rows.empty:
                    # جستجوی نرم (زیرمجموعه نام)
                    rows = df_assets[df_assets[a_name].map(lambda x: target in norm(x) or norm(x) in target)]
                if not rows.empty:
                    r0 = rows.iloc[0]
                    def gv(keys):
                        c = smart_find_column(df_assets.columns, keys)
                        if not c:
                            return '---'
                        v = str(r0[c]).strip()
                        return v if v not in ('', 'nan', 'None') else '---'
                    e_type = gv(['نوع'])
                    eq_display = eq_map.get(sel_eq_key, sel_eq_key)
                    st.markdown(f'''
                    <div style='background:#f0f7ff; padding:20px; border-radius:15px; border-right:10px solid #1E3A8D; margin-bottom:15px; text-align:right; direction:rtl; box-shadow:2px 2px 5px rgba(0,0,0,0.05);'>
                        <h3 style='color:#1E3A8D; margin-top:0; font-family:Tahoma;'>🛠️ مشخصات فنی: {eq_display}</h3>
                        <div style='display:flex; justify-content:flex-start; font-size:16px; color:#333; flex-wrap:wrap; gap:20px;'>
                            <span><b style='color:#1E3A8D;'>🔹 نوع:</b> {e_type}</span>
                            <span><b style='color:#1E3A8D;'>🔹 دور:</b> {gv(['دور'])} RPM</span>
                            <span><b style='color:#1E3A8D;'>🔹 واحد:</b> {gv(['واحد'])}</span>
                        </div>
                        <div style='margin-top:12px; font-size:15px; color:#1E3A8D; background:#e6efff; padding:8px 15px; border-radius:8px; display:inline-block;'>
                            <b>📍 راهنمای نقاط (P-Map):</b> {get_point_guide(eq_display, e_type)}
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
        # ---------- نمودار سلامت ----------
        if vib_cols:
            vals = fdf[vib_cols].apply(to_num, axis=0).max(axis=1)
            def cat(v):
                if pd.isna(v): return 'نامشخص'
                return 'بحرانی' if v > 7.1 else 'هشدار' if v > 4.5 else 'سالم'
            status = vals.map(cat).value_counts()
            if not status.empty:
                st.markdown("### 📈 تحلیل وضعیت سلامت")
                fig = px.pie(values=status.values, names=status.index,
                             color=status.index,
                             color_discrete_map={'سالم': '#2e7d32', 'هشدار': '#ffa500', 'بحرانی': '#ff4b4b', 'نامشخص': '#9e9e9e'})
                st.plotly_chart(fig, use_container_width=True)
        # ---------- جدول ----------
        st.markdown(f"### 📋 نتایج یافت شده ({len(fdf)} مورد)")
        def color_vib(val):
            try:
                v = float(str(val).replace('٫', '.').replace(',', '.').strip())
            except Exception:
                return ''
            if v > 7.1: return 'background-color:#ff4b4b; color:white'
            if v > 4.5: return 'background-color:#ffa500; color:white'
            return 'background-color:#2e7d32; color:white'
        table = fdf[visible_cols].copy()
        if vib_cols:
            styled = table.style.map(color_vib, subset=vib_cols)
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.dataframe(table, use_container_width=True, hide_index=True)
    else:
        st.warning("⚠️ هیچ داده‌ای با این فیلترها پیدا نشد.")
    st.markdown('<div style="text-align:center; margin-top:60px; font-weight:bold; color:#555; font-family:Tahoma;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>', unsafe_allow_html=True)
else:
    st.error("❌ داده‌ای دریافت نشد. لینک گوگل‌شیت و دسترسی «Anyone with the link» را بررسی کنید.")
