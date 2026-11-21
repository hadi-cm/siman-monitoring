python
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
# 2. توابع کمکی و اصلاح شده (Fixing Syntax Error)
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
def to_num(series):
    s = series.map(clean_num_text)
    s = s.replace({'': None, 'nan': None, 'None': None, '---': None, 'NaN': None})
    return pd.to_numeric(s, errors='coerce')
def date_sort_key(val):
    s = norm(val)
    m = re.search(r'(\d{2,4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})', s)
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100: y += 1400
            return (y  10000) + (mo  100) + d
        except: return 0
    m = re.search(r'(\d{6,8})', s)
    if m: return int(m.group(1))
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
def get_point_guide(eq_name, eq_type=''):
    name = norm(eq_name) + ' ' + norm(eq_type)
    if 'گیربکس' in name:
        return ('P1: انتهای موتور | P2: جلوی موتور | P3: محور ورودی گیربکس | '
                'P4: سمت آزاد محور ورودی | P5: سمت فیکس محور دوم | P6: سمت آزاد محور دوم | '
                'P7: سمت فیکس محور سوم | P8: سمت آزاد محور سوم | P9: بابیت اول سمت گیربکس | '
                'P10: بابیت دوم | P11: بابیت نزدیک پینیون آسیاب')
    if 'کراشر' in name or 'سنگ شکن' in name:
        return ('P1: انتهای موتور | P2: سر موتور | P3: یاتاقان سمت فیکس | '
                'P4: یاتاقان سمت آزاد | P5: یاتاقان فیکس | P6: یاتاقان آزاد')
    if 'فن' in name:
        return 'P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس | P4: یاتاقان آزاد'
    if 'بلوئر' in name:
        return 'P1: انتهای موتور | P2: سر موتور | P3: محور ورود بلوئر | P4: انتهای بلوئر'
    return 'راهنمای نقاط تعریف نشده است.'
# ==============================================================================
# 3. بارگذاری و پردازش Pivot (اصلی‌ترین بخش برای حل مشکل تو)
# ==============================================================================
VIB_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0'
ASSETS_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=1276803564'
ANN_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=2057447521'
@st.cache_data(ttl=600)
def load_processed_data():
    try: df_vib = pd.read_csv(VIB_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except: df_vib = pd.DataFrame()
    try: df_assets = pd.read_csv(ASSETS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except: df_assets = pd.DataFrame()
    try: df_ann = pd.read_csv(ANN_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except: df_ann = pd.DataFrame()
    if df_vib.empty: return df_vib, df_assets, df_ann
    # شناسایی ستون‌ها بر اساس عکس تو
    c_date = smart_find_column(df_vib.columns, ['تاریخ', 'Date'])
    c_line = smart_find_column(df_vib.columns, ['خط تولید', 'خط'])
    c_unit = smart_find_column(df_vib.columns, ['واحد'])
    c_equip = smart_find_column(df_vib.columns, ['عنوان تجهیز', 'نام تجهیز', 'تجهیز', 'Asset'])
    c_point = smart_find_column(df_vib.columns, ['p', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8', 'p9', 'p10', 'p11'])
    # ستون‌های مقداری (بعد از ستون نقطه)
    val_cols = [c for c in df_vib.columns if any(k in c.lower() for k in ['عمودی', 'افقی', 'محوری', 'v', 'h', 'a', 'mm/s'])]
    # ۱. پر کردن ستون‌های خالی (Forward Fill) برای اینکه اطلاعات تجهیز به تمام نقاط برسد
    cols_to_ffill = [c_date, c_line, c_unit, c_equip]
    for col in cols_to_ffill:
        if col:
            df_vib[col] = df_vib[col].replace('', None).ffill()
    # ۲. ایجاد ستون‌های کمکی برای گروه‌بندی
    df_vib['_k_equip'] = df_vib[c_equip].map(norm)
    df_vib['_k_date'] = df_vib[c_date].map(norm)
    df_vib['_dkey'] = df_vib[c_date].map(date_sort_key)
    # ۳. اجرای عملیات Pivot (تبدیل Long به Wide)
    # این کار باعث می‌شود P1 تا P11 در یک ردیف کنار هم قرار بگیرند
    pivot_idx = [c for c in [c_date, c_line, c_unit, c_equip] if c]
    pivot_idx.append('_dkey')
    # اگر ستون مقداری پیدا نشد، از خود ستون نقطه استفاده کن
    vals = val_cols if val_cols else [c_point]
    try:
        df_pivoted = df_vib.pivot_table(
            index=pivot_idx,
            columns=c_point,
            values=vals,
            aggfunc='first'
        ).reset_index()
        # تمیز کردن نام ستون‌ها (در حالت Pivot ستون‌ها Tuple می‌شوند)
        new_cols = []
        for col in df_pivoted.columns:
            if isinstance(col, tuple):
                new_cols.append(col[0])
            else:
                new_cols.append(col)
        df_pivoted.columns = new_cols
        # حذف ستون‌های اضافی
        cols_to_keep = [c for c in df_pivoted.columns if not c.startswith('_')]
        df_pivoted = df_pivoted[cols_to_keep]
        # اضافه کردن مجدد کلیدهای کمکی برای فیلترها
        if c_line: df_pivoted['_k_line'] = df_pivoted[c_line].map(norm)
        if c_unit: df_pivoted['_k_unit'] = df_pivoted[c_unit].map(norm)
        if c_equip: df_pivoted['_k_eq'] = df_pivoted[c_equip].map(norm)
        if c_date: df_pivoted['_k_date'] = df_pivoted[c_date].map(norm)
        if c_date: df_pivoted['_dkey'] = df_pivoted['_dkey'] # حفظ ترتیب زمانی
        # مرتب‌سازی ستون‌های P به ترتیب عددی (P1, P2, ... P11)
        p_cols_found = [c for c in df_pivoted.columns if re.search(r'p\d+', str(c).lower())]
        def get_p_num(name):
            m = re.search(r'p(\d+)', str(name).lower())
            return int(m.group(1)) if m else 999
        other_cols = [c for c in df_pivoted.columns if c not in p_cols_found and not str(c).startswith('_')]
        sorted_p_cols = sorted(p_cols_found, key=get_p_num)
        df_pivoted = df_pivoted[other_cols + sorted_p_cols]
    except Exception as e:
        st.error(f"خطا در پردازش Pivot: {e}")
        df_pivoted = df_vib
    return df_pivoted, df_assets, df_ann
df, df_assets, df_ann = load_processed_data()
# ==============================================================================
# 4. نمایش اعلان‌ها (Announcements)
# ==============================================================================
logo_siman = get_image_base64('client_logo.png')
logo_faz = get_image_base64('my_logo.png')
st.markdown(f'''
<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;
            background:white; padding:15px 30px; border-radius:15px;
            box-shadow:0 4px 8px rgba(0,0,0,0.1);'>
    <img src='data:image/png;base64,{logo_faz}' style='width:110px; height:auto;'>
    <div style='text-align:center; color:#1E3A8D; font-size:26px; font-weight:bold; font-family:Tahoma;'>
        🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران
    </div >
    <img src='data:image/png;base64,{logo_siman}' style='width:110px; height:auto;'>
</div >
''', unsafe_allow_html=True)
if not df_ann.empty:
    c_tit = smart_find_column(df_ann.columns, ['عنوان'])
    c_txt = smart_find_column(df_ann.columns, ['متن'])
    c_typ = smart_find_column(df_ann.columns, ['نوع'])
    c_act = smart_find_column(df_ann.columns, ['فعال'])
    if c_tit and c_txt and c_typ:
        if c_act:
            df_ann = df_ann[df_ann[c_act].astype(str).str.strip() == 'بله']
        for _, row in df_ann.iterrows():
            t, txt, typ = str(row[c_tit]), str(row[c_txt]), str(row[c_typ])
            if any(x in typ for x in ["خطر", "بحرانی"]): color, icon = "#ff4b4b", "🚨"
            elif "هشدار" in typ: color, icon = "#ffaa00", "⚠️"
            else: color, icon = "#2e7d32", "✅"
            st.markdown(f'''
            <div style='background:{color}; padding:12px; border-radius:10px; margin-bottom:8px; color:white; direction:rtl; text-align:right; font-family:Tahoma;'>
                <b>{icon} {t}</b><br><small>{txt}</small>
            </div>
            ''', unsafe_allow_html=True)
# ==============================================================================
# 5. سایدبار و فیلترها
# ==============================================================================
st.sidebar.header('🔍 فیلترها')
if not df.empty:
    c_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
    c_unit = smart_find_column(df.columns, ['واحد'])
    c_equip = smart_find_column(df.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'Asset'])
    c_date = smart_find_column(df.columns, ['تاریخ', 'Date'])
    def get_map(k_col, o_col):
        if not o_col: return {}
        tmp = df[df[k_col] != ''].copy()
        return tmp.groupby(k_col)[o_col].apply(lambda x: x.value_counts().index[0]).to_dict()
    l_map = get_map('_k_line', c_line)
    u_map = get_map('_k_unit', c_unit)
    e_map = get_map('_k_eq', c_equip)
    sel_line = st.sidebar.selectbox('📍 خط:', ['همه'] + sorted(l_map.keys()), format_func=lambda x: 'همه' if x=='همه' else l_map.get(x, x))
    tmp_u = df.copy()
    if sel_line != 'همه': tmp_u = tmp_u[tmp_u['_k_line'] == sel_line]
    u_keys = sorted([u for u in tmp_u['_k_unit'].unique() if u != ''])
    sel_unit = st.sidebar.selectbox('🏢 واحد:', ['همه'] + u_keys, format_func=lambda x: 'همه' if x=='همه' else u_map.get(x, x))
    if sel_unit != 'همه': tmp_u = tmp_u[tmp_u['_k_unit'] == sel_unit]
    e_keys = sorted([e for e in tmp_u['_k_eq'].unique() if e != ''])
    sel_eq = st.sidebar.selectbox('⚙️ تجهیز:', ['همه تجهیزات'] + e_keys, format_func=lambda x: 'همه تجهیزات' if x=='همه تجهیزات' else e_map.get(x, x))
    search_eq = st.sidebar.text_input('🔎 جستجو:')
    date_map = {}
    if c_date:
        date_map = df.groupby('_k_date')[c_date].apply(lambda x: x.value_counts().index[0]).to_dict()
    sel_date = st.sidebar.selectbox('🌙 تاریخ:', ['همه تاریخ‌ها'] + sorted(list(date_map.keys()), reverse=True), format_func=lambda x: 'همه تاریخ‌ها' if x=='همه تاریخ‌ها' else date_map.get(x, x))
    # اعمال فیلترها
    fdf = df.copy()
    if sel_line != 'همه': fdf = fdf[fdf['_k_line'] == sel_line]
    if sel_unit != 'همه': fdf = fdf[fdf['_k_unit'] == sel_unit]
    if sel_eq != 'همه تجهیزات': fdf = fdf[fdf['_k_eq'] == sel_eq]
    if search_eq: fdf = fdf[fdf['_k_eq'].str.contains(norm(search_eq))]
    if sel_date != 'همه تاریخ‌ها': fdf = fdf[fdf['_k_date'] == sel_date]
    if c_date: fdf = fdf.sort_values('_dkey', ascending=False)
    # ==========================================================================
    # 6. نمایش نتایج
    # ==========================================================================
    st.title('📊 تحلیل روند ارتعاشات')
    if sel_eq != 'همه تجهیزات':
        # نمایش مشخصات فنی از Assets
        if not df_assets.empty:
            a_name = smart_find_column(df_assets.columns, ['نام تجهیز', 'عنوان تجهیز', 'Asset'])
            if a_name:
                # پیدا کردن ردیف تجهیز در Assets
                asset_rows = df_assets[df_assets[a_name].map(norm) == sel_eq]
                if not asset_rows.empty:
                    r = asset_rows.iloc[0]
                    def get_v(k):
                        col = smart_find_column(df_assets.columns, k)
                        return str(r[col]) if col and str(r[col]) != '' else '---'
                    st.info(f"🛠️ مشخصات: {get_v(['نوع تجهیز', 'نوع'])} | {get_v(['دور', 'RPM'])} RPM | {get_v(['خط'])} | {get_v(['واحد'])}")
                    st.caption(f"📍 راهنما: {get_point_guide(sel_eq, get_v(['نوع تجهیز', 'نوع']))}")
    if not fdf.empty:
        # تشخیص ستون‌های P
        p_cols = [c for c in fdf.columns if re.search(r'p\d+', str(c).lower())]
        disp_cols = [c for c in fdf.columns if c not in p_cols and not c.startswith('_')]
        st.markdown(f"### 📋 داده‌های شناسایی شده ({len(fdf)} ردیف)")
        def color_cells(val):
            try:
                v = float(clean_num_text(val))
                if v > 7.1: return 'background-color:#ff4b4b; color:white'
                if v > 4.5: return 'background-color:#ffa500; color:white'
                return 'background-color:#2e7d32; color:white'
            except: return ''
        if p_cols:
            st.dataframe(fdf[disp_cols + p_cols].style.map(color_cells, subset=p_cols), use_container_width=True, hide_index=True)
        else:
            st.dataframe(fdf[disp_cols], use_container_width=True, hide_index=True)
        # نمودار روند
        if p_cols and len(fdf) > 1:
            with st.expander("📈 نمودار روند نقاط", expanded=False):
                trend_df = fdf[[c_date if c_date else fdf.columns[0]] + p_cols].copy()
                # تبدیل به حالت Long برای Plotly
                trend_df = trend_df.melt(id_vars=[trend_df.columns[0]], var_name='نقطه', value_name='مقدار')
                trend_df['مقدار'] = to_num(trend_df['مقدار'])
                trend_df = trend_df.dropna(subset=['مقدار'])
                if not trend_df.empty:
                    fig = px.line(trend_df, x=trend_df.columns[0], y='مقدار', color='نقطه', markers=True)
                    fig.add_hline(y=4.5, line_dash="dash", line_color="orange")
                    fig.add_hline(y=7.1, line_dash="dash", line_color="red")
                    st.plotly_chart(fig, use_container_width=True)
    st.markdown('<div style="text-align:center; margin-top:50px; color:#555; font-family:Tahoma;">طراحی و توسعه: مهندس هادی زندیه</div>', unsafe_allow_html=True)
else:
    st.error("داده‌ای یافت نشد.")
