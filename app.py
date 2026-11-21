import re
import pandas as pd
import streamlit as st
import base64
import plotly.express as px
from datetime import datetime
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
# 2. توابع کمکی
# ==============================================================================
FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'
EN_DIGITS = '0123456789'
def norm(x):
    if x is None: return ''
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
            if normed[c] == nk: return c
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if nk and nk in normed[c]: return c
    return None
def date_sort_key(val):
    s = norm(val)
    m = re.search(r'(\d{2,4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})', s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100: y += 1400
        return y  10000 + mo  100 + d
    m = re.search(r'(\d{6,8})', s)
    if m: return int(m.group(1))
    return 0
def get_point_guide(eq_name, eq_type=''):
    name = norm(eq_name) + ' ' + norm(eq_type)
    if 'گیربکس' in name:
        return ('P1: انتهای موتور | P2: جلوی موتور | P3: محور ورودی گیربکس | '
                'P4: سمت آزاد محور ورودی | P5: سمت فیکس محور دوم | P6: سمت آزاد محور دوم | '
                'P7: سمت فیکس محور سوم | P8: سمت آزاد محور سوم | P9: بابیت اول سمت گیربکس | '
                'P10: بابیت دوم | P11: بابیت نزدیک پینیون آسیاب')
    if 'کراشر' in name or 'سنگ شکن' in name:
        return ('P1: انتهای موتور | P2: سر موتور | P3: یاتاقان سمت فیکس | P4: یاتاقان سمت آزاد | P5: یاتاقان فیکس | P6: یاتاقان آزاد')
    if 'فن' in name:
        return 'P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس | P4: یاتاقان آزاد'
    if 'بلوئر' in name:
        return 'P1: انتهای موتور | P2: سر موتور | P3: محور ورود بلوئر | P4: انتهای بلوئر'
    if 'کمپرسور' in name:
        return 'P1: انتهای موتور | P2: سر موتور | P3: سر ایرند | P4: انتهای ایرند'
    return 'راهنمای نقاط تعریف نشده است.'
# ==============================================================================
# 3. بارگذاری و پردازش اصلی (Pivot Strategy)
# ==============================================================================
VIB_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0'
ASSETS_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=1276803564'
ANN_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=2057447521'
@st.cache_data(ttl=600)
def load_and_pivot_data():
    try: df_vib_raw = pd.read_csv(VIB_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except: df_vib_raw = pd.DataFrame()
    try: df_assets = pd.read_csv(ASSETS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except: df_assets = pd.DataFrame()
    try: df_ann = pd.read_csv(ANN_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except: df_ann = pd.DataFrame()
    if df_vib_raw.empty:
        return df_vib_raw, df_assets, df_ann
    # شناسایی ستون‌های کلیدی
    c_date = smart_find_column(df_vib_raw.columns, ['تاریخ', 'Date'])
    c_line = smart_find_column(df_vib_raw.columns, ['خط تولید', 'خط'])
    c_unit = smart_find_column(df_vib_raw.columns, ['واحد'])
    c_equip = smart_find_column(df_vib_raw.columns, ['عنوان تجهیز', 'نام تجهیز', 'تجهیز', 'Asset'])
    c_point = smart_find_column(df_vib_raw.columns, ['p', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8', 'p9', 'p10', 'p11'])
    # ستون‌های مقداری (مثل عمودی، افقی، محوری)
    val_cols = [c for c in df_vib_raw.columns if any(k in c.lower() for k in ['عمودی', 'افقی', 'محوری', 'v', 'h', 'a'])]
    # تمام ستون‌های غیر مقداری که باید در ردیف اول پر باشند (برای انتشار در تمام ردیف‌ها)
    info_cols = [c for c in df_vib_raw.columns if c not in val_cols and c != c_point and c != c_date and c != c_line and c != c_unit and c != c_equip]
    # ۱. تمیز کردن داده‌ها (Fill info cols forward)
    # چون در شیت شما فقط ردیف اول پر است، از ffill استفاده می‌کنیم تا به ردیف‌های p1, p2... برسد
    df_vib_raw[c_line] = df_vib_raw[c_line].replace('', None).ffill()
    df_vib_raw[c_unit] = df_vib_raw[c_unit].replace('', None).ffill()
    df_vib_raw[c_equip] = df_vib_raw[c_equip].replace('', None).ffill()
    if c_date: df_vib_raw[c_date] = df_vib_raw[c_date].replace('', None).ffill()
    for col in info_cols:
        df_vib_raw[col] = df_vib_raw[col].replace('', None).ffill()
    # ۲. ساخت کلید اصلی برای ادغام (تجهیز + تاریخ)
    df_vib_raw['_grp_key'] = df_vib_raw[c_equip].map(norm) + "|" + df_vib_raw[c_date].map(norm)
    # ۳. پیوت کردن: تبدیل از Long به Wide
    # ما می‌خواهیم هر تجهیز در یک تاریخ، یک ردیف باشد و ستون‌های P1, P2... داشته باشد
    # ابتدا ستون‌های مقداری را هم باید مدیریت کنیم. اگر در شیت شما هر ردیف فقط یک P دارد،
    # یعنی مقادیر در ستون‌های عمودی/افقی قرار دارند.
    # ایجاد یک لیست از تمام ستون‌های مقداری که می‌خواهیم در Wide حالت داشته باشیم
    # برای سادگی، فرض می‌کنیم در هر ردیف فقط یک نقطه (p) پر است.
    # استراتژی: Groupby بر اساس تجهیز و تاریخ، و سپس Pivot کردن ستون p
    pivot_df = df_vib_raw.pivot_table(
        index=['_grp_key', c_line, c_unit, c_equip, c_date],
        columns=c_point,
        values=val_cols if val_cols else [c_point], # اگر ستون مقداری نبود، همان p را بگیرد
        aggfunc='first'
    ).reset_index()
    # پاکسازی نام ستون‌ها بعد از Pivot (نام ستون‌ها تبدیل به Tuple شده)
    pivot_df.columns = [c[0] if isinstance(c, tuple) else c for c in pivot_df.columns]
    # رفع مشکل ستون‌های خالی و نام‌های عجیب
    pivot_df = pivot_df.replace('', None).fillna('')
    # مرتب سازی ستون‌های P به ترتیب عددی
    def get_p_order(col_name):
        m = re.search(r'p(\d+)', str(col_name).lower())
        return int(m.group(1)) if m else 999
    p_cols_found = [c for c in pivot_df.columns if re.search(r'p\d+', str(c).lower())]
    other_cols = [c for c in pivot_df.columns if c not in p_cols_found and not c.startswith('_')]
    sorted_p_cols = sorted(p_cols_found, key=get_p_order)
    final_cols = other_cols + sorted_p_cols
    # بازگرداندن دیتافریم نهایی
    df_final = pivot_df[final_cols]
    # اضافه کردن کلیدهای کمکی برای فیلتر
    df_final['_k_line'] = df_final[c_line].map(norm)
    df_final['_k_unit'] = df_final[c_unit].map(norm)
    df_final['_k_eq'] = df_final[c_equip].map(norm)
    df_final['_k_date'] = df_final[c_date].map(norm)
    if c_date: df_final['_dkey'] = df_final[c_date].map(date_sort_key)
    return df_final, df_assets, df_ann
df, df_assets, df_ann = load_and_pivot_data()
# ==============================================================================
# 4. هدر و اعلان‌ها
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
    </div>
    <img src='data:image/png;base64,{logo_siman}' style='width:110px; height:auto;'>
</div>
''', unsafe_allow_html=True)
if not df_ann.empty:
    col_title = smart_find_column(df_ann.columns, ['عنوان'])
    col_text = smart_find_column(df_ann.columns, ['متن'])
    col_type = smart_find_column(df_ann.columns, ['نوع'])
    col_active = smart_find_column(df_ann.columns, ['فعال'])
    col_label = smart_find_column(df_ann.columns, ['برچسب'])
    if col_title and col_text and col_type:
        if col_active:
            df_ann = df_ann[df_ann[col_active].astype(str).str.strip() == 'بله']
        for _, row in df_ann.iterrows():
            ann_type, ann_title, ann_msg = str(row[col_type]), str(row[col_title]), str(row[col_text])
            ann_label = str(row[col_label]) if col_label else ""
            if "خطر" in ann_type or "بحرانی" in ann_type: color, icon = "#ff4b4b", "🚨"
            elif "هشدار" in ann_type: color, icon = "#ffaa00", "⚠️"
            elif any(x in ann_type for x in ["اطلاعیه", "موفق", "گزارش"]): color, icon = "#2e7d32", "✅"
            else: color, icon = "#1E3A8D", "ℹ️"
            st.markdown(f'''
            <div style='background:{color}; padding:15px; border-radius:10px; margin-bottom:10px; color:white; direction:rtl; text-align:right; font-family:Tahoma;'>
                <div style='display:flex; justify-content:space-between; align-items:center;'>
                    <b style='font-size:18px;'>{icon} {ann_title}</b>
                    <span style='background:rgba(255,255,255,0.2); padding:2px 8px; border-radius:5px; font-size:12px;'>{ann_label}</span>
                </div>
                <div style='margin-top:5px; font-size:15px; opacity:0.9;'>{ann_msg}</div>
            </div>
            ''', unsafe_allow_html=True)
# ==============================================================================
# 5. فیلترها و بدنه اصلی
# ==============================================================================
st.sidebar.header('🔍 فیلترهای پیشرفته')
if not df.empty:
    c_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
    c_unit = smart_find_column(df.columns, ['واحد'])
    c_equip = smart_find_column(df.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'Asset'])
    c_date = smart_find_column(df.columns, ['تاریخ', 'Date'])
    def _mode(series):
        v = series.astype(str).str.strip()
        v = v[v != '']
        return v.value_counts().idxmax() if not v.empty else ''
    def display_map(k_col, o_col):
        if o_col is None: return {}
        tmp = df[df[k_col] != '']
        return tmp.groupby(k_col)[o_col].agg(_mode).to_dict() if not tmp.empty else {}
    line_map = display_map('_k_line', c_line)
    unit_map = display_map('_k_unit', c_unit)
    eq_map = display_map('_k_eq', c_equip)
    sel_line = st.sidebar.selectbox('📍 خط تولید:', ['همه'] + sorted(line_map.keys()), format_func=lambda k: 'همه' if k == 'همه' else line_map.get(k, k))
    tmp_u = df.copy()
    if sel_line != 'همه': tmp_u = tmp_u[tmp_u['_k_line'] == sel_line]
    unit_keys = sorted([u for u in tmp_u['_k_unit'].unique() if u != ''])
    sel_unit = st.sidebar.selectbox('🏢 واحد:', ['همه'] + unit_keys, format_func=lambda k: 'همه' if k == 'همه' else unit_map.get(k, k))
    if sel_unit != 'همه': tmp_u = tmp_u[tmp_u['_k_unit'] == sel_unit]
    eq_keys = sorted([e for e in tmp_u['_k_eq'].unique() if e != ''])
    sel_eq = st.sidebar.selectbox('⚙️ انتخاب تجهیز:', ['همه تجهیزات'] + eq_keys, format_func=lambda k: 'همه تجهیزات' if k == 'همه تجهیزات' else eq_map.get(k, k))
    search_eq = st.sidebar.text_input('🔎 جستجوی سریع تجهیز:', placeholder='مثلاً: میل فن')
    date_map = {}
    if c_date:
        tmp_d = df[df['_k_date'] != '']
        date_map = tmp_d.groupby('_k_date')[c_date].agg(_mode).to_dict()
    date_keys = sorted(list(date_map.keys()), reverse=True)
    sel_date = st.sidebar.selectbox('🌙 انتخاب تاریخ:', ['همه تاریخ‌ها'] + date_keys, format_func=lambda k: 'همه تاریخ‌ها' if k == 'همه تاریخ‌ها' else date_map.get(k, k))
    fdf = df.copy()
    if sel_line != 'همه': fdf = fdf[fdf['_k_line'] == sel_line]
    if sel_unit != 'همه': fdf = fdf[fdf['_k_unit'] == sel_unit]
    if sel_eq != 'همه تجهیزات': fdf = fdf[fdf['_k_eq'] == sel_eq]
    if search_eq.strip():
        q = norm(search_eq)
        fdf = fdf[fdf['_k_eq'].map(lambda v: q in v)]
    if sel_date != 'همه تاریخ‌ها': fdf = fdf[fdf['_k_date'] == sel_date]
    if c_date: fdf = fdf.sort_values(by='_dkey', ascending=False)
    # --- نمایش اصلی ---
    st.title('📊 تحلیل روند ارتعاشات تجهیزات')
    # شناسایی ستون‌های ارتعاش (P1, P2...)
    p_cols = [c for c in fdf.columns if re.search(r'p\d+', str(c).lower())]
    other_vis_cols = [c for c in fdf.columns if c not in p_cols and not c.startswith('_')]
    if sel_eq != 'همه تجهیزات':
        # مشخصات فنی از Assets
        eq_display = eq_map.get(sel_eq, sel_eq)
        matched = False
        if not df_assets.empty:
            a_name = smart_find_column(df_assets.columns, ['نام تجهیز', 'عنوان تجهیز', 'Asset'])
            if a_name:
                n_assets = df_assets[a_name].map(norm)
                rows = df_assets[n_assets == sel_eq]
                if rows.empty: rows = df_assets[n_assets.map(lambda x: sel_eq in x if x else '')]
                if not rows.empty:
                    matched = True
                    r0 = rows.iloc[0]
                    def gv(keys, default='---'):
                        c = smart_find_column(df_assets.columns, keys)
                        return str(r0[c]).strip() if c and str(r0[c]).strip() not in ('', 'nan', 'None') else default
                    e_type, e_rpm, e_line, e_unit = gv(['نوع تجهیز', 'نوع']), gv(['دور', 'RPM']), gv(['خط']), gv(['واحد'])
                    e_drive, e_brg, e_bush = gv(['نوع انتقال', 'کوپلینگ']), gv(['بیرینگ', 'Bearing']), gv(['بوش', 'Bush'])
                    st.markdown(f'''
                    <div style='background:#f0f7ff; padding:20px; border-radius:15px; border-right:10px solid #1E3A8D; margin-bottom:18px; text-align:right; direction:rtl; box-shadow:2px 2px 8px rgba(0,0,0,0.06);'>
                        <h3 style='color:#1E3A8D; margin:0 0 14px 0; font-family:Tahoma;'>🛠️ مشخصات فنی: {eq_display}</h3>
                        <div style='display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:10px; font-size:16px; color:#333; font-family:Tahoma;'>
                            <span><b style='color:#1E3A8D;'>🔹 نوع:</b> {e_type}</span>
                            <span><b style='color:#1E3A8D;'>🔹 دور:</b> {e_rpm} RPM</span>
                            <span><b style='color:#1E3A8D;'>🔹 خط:</b> {e_line}</span>
                            <span><b style='color:#1E3A8D;'>🔹 واحد:</b> {e_unit}</span>
                            <span><b style='color:#1E3A8D;'>🔹 انتقال:</b> {e_drive}</span>
                            <span><b style='color:#1E3A8D;'>🧩 بیرینگ:</b> {e_brg}</span>
                            <span><b style='color:#1E3A8D;'>🧩 بوش:</b> {e_bush}</span>
                        </div>
                        <div style='margin-top:14px; font-size:15px; color:#1E3A8D; background:#e6efff; padding:8px 15px; border-radius:8px; display:inline-block; font-family:Tahoma;'>
                            <b style='font-family:Tahoma;'>📍 راهنمای نقاط (P-Map):</b> {get_point_guide(eq_display, e_type)}
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
                    with st.expander('📦 اطلاعات قطعات و لجستیک', expanded=True):
                        pts = smart_find_column(df_assets.columns, ['نقطه', 'Point'])
                        brg = smart_find_column(df_assets.columns, ['بیرینگ', 'Bearing'])
                        bsh = smart_find_column(df_assets.columns, ['بوش', 'Bush'])
                        log_cols = [c for c in [pts, brg, bsh] if c]
                        if log_cols:
                            st.dataframe(rows[log_cols], hide_index=True, use_container_width=True)
    if not matched: st.info('ℹ️ مشخصات فنی یافت نشد.')
    if not fdf.empty:
        st.markdown(f'### 📋 داده‌های ارتعاشات ({len(fdf)} مورد)')
        def color_vib(val):
            try:
                v = float(clean_num_text(val))
                if v > 7.1: return 'background-color:#ff4b4b; color:white'
                if v > 4.5: return 'background-color:#ffa500; color:white'
                return 'background-color:#2e7d32; color:white'
            except: return ''
        if p_cols:
            st.dataframe(fdf[other_vis_cols + p_cols].style.map(color_vib, subset=p_cols), use_container_width=True, hide_index=True)
        else:
            st.dataframe(fdf[other_vis_cols], use_container_width=True, hide_index=True)
        if p_cols and sel_eq != 'همه تجهیزات' and c_date and len(fdf) > 1:
            with st.expander('📈 نمودار روند ارتعاشات', expanded=False):
                trend = fdf[[c_date] + p_cols].copy()
                trend['_dkey'] = trend[c_date].map(date_sort_key)
                trend = trend.sort_values('_dkey')
                trend[c_date] = trend[c_date].astype(str)
                long_df = trend.melt(id_vars=[c_date, '_dkey'], value_vars=p_cols, var_name='نقطه', value_name='ارتعاش')
                long_df['ارتعاش'] = to_num(long_df['ارتعاش'])
                long_df = long_df.dropna(subset=['ارتعاش'])
                if not long_df.empty:
                    fig = px.line(long_df, x=c_date, y='ارتعاش', color='نقطه', markers=True, title='روند ارتعاش (mm/s)')
                    fig.add_hline(y=4.5, line_dash='dash', line_color='orange')
                    fig.add_hline(y=7.1, line_dash='dash', line_color='red')
                    st.plotly_chart(fig, use_container_width=True)
    st.markdown('<div style="text-align:center; margin-top:50px; color:#555; font-family:Tahoma;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>', unsafe_allow_html=True)
else:
    st.error('❌ خطا در اتصال به منبع داده.')
