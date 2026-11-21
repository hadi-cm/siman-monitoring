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
# 2. توابع کمکی و منطق تاریخ
# ==============================================================================
FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'
EN_DIGITS = '0123456789'

def norm(x):
    if x is None: return ''
    try:
        if isinstance(x, float) and pd.isna(x): return ''
    except: pass
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
    m = re.search(r'(\d{2,4})\s/\s*(\d{1,2})\s*/\s*(\d{1,2})', s)
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
        return ('P1: انتهای موتور | P2: سر موتور | P3: یاتاقان سمت فیکس (پولی کوچک) | '
                'P4: یاتاقان سمت آزاد (پولی کوچک) | P5: یاتاقان فیکس (روتور) | '
                'P6: یاتاقان سمت آزاد (روتور)')
    if 'فن' in name:
        return 'P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس | P4: یاتاقان آزاد'
    if 'بلوئر' in name:
        return 'P1: انتهای موتور | P2: سر موتور | P3: محور ورود بلوئر | P4: انتهای بلوئر'
    if 'کمپرسور' in name:
        return 'P1: انتهای موتور | P2: سر موتور | P3: سر ایرند | P4: انتهای ایرند'
    return 'راهنمای نقاط برای این نوع تجهیز تعریف نشده است.'
# ==============================================================================
# 3. بارگذاری داده‌ها و مدیریت اعلان‌ها
# ==============================================================================
VIB_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0'
ASSETS_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=1276803564'
ANN_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=2057447521'
@st.cache_data(ttl=600)
def load_all_data():
    df_vib, df_assets, df_ann = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try: df_vib = pd.read_csv(VIB_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except: pass
    try: df_assets = pd.read_csv(ASSETS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except: pass
    try: df_ann = pd.read_csv(ANN_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except: pass
    return df_vib, df_assets, df_ann
df_raw, df_assets, df_ann = load_all_data()
# ==============================================================================
# 4. هدر و نمایش اعلان‌ها (Announcements)
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
            ann_type = str(row[col_type]).strip()
            ann_title = str(row[col_title]).strip()
            ann_msg = str(row[col_text]).strip()
            ann_label = str(row[col_label]).strip() if col_label else ""
            if "خطر" in ann_type or "بحرانی" in ann_type:
                color, icon = "#ff4b4b", "🚨"
            elif "هشدار" in ann_type:
                color, icon = "#ffaa00", "⚠️"
            elif "اطلاعیه" in ann_type or "موفق" in ann_type or "گزارش" in ann_type:
                color, icon = "#2e7d32", "✅"
            else:
                color, icon = "#1E3A8D", "ℹ️"
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
# 5. ادغام هوشمند داده‌ها (Consolidation)
# ==============================================================================
def consolidate_vib_data(df, mode='full'):
    if df.empty: return df
    col_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
    col_unit = smart_find_column(df.columns, ['واحد'])
    equip_col = smart_find_column(df.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'Asset'])
    date_col = smart_find_column(df.columns, ['تاریخ', 'Date'])
    if not all([col_line, col_unit, equip_col, date_col]):
        return df
    # ایجاد کلید اصلی برای ادغام
    df['_k_line'] = df[col_line].map(norm)
    df['_k_unit'] = df[col_unit].map(norm)
    df['_k_eq'] = df[equip_col].map(norm)
    df['_k_date'] = df[date_col].map(norm)
    df['_dkey'] = df[date_col].map(date_sort_key)
    group_cols = ['_k_line', '_k_unit', '_k_eq', '_k_date', '_dkey']
    if mode == 'full':
        # در حالت ادغام کامل، اولین مقدار غیر-خالی را برای هر ستون برمی‌داریم
        # برای جلوگیری از IndexError، از first() استفاده می‌کنیم که بسیار امن است
        agg_dict = {}
        for col in df.columns:
            if col in group_cols or col.startswith('_'):
                continue
            agg_dict[col] = 'first'
        new_df = df.groupby(group_cols, as_index=False).agg(agg_dict)
    else:
        new_df = df.copy()
    return new_df
df = consolidate_vib_data(df_raw)
# ==============================================================================
# 6. فیلترهای سایدبار
# ==============================================================================
st.sidebar.header('🔍 فیلترهای پیشرفته')
if not df.empty:
    col_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
    col_unit = smart_find_column(df.columns, ['واحد'])
    equip_col = smart_find_column(df.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'Asset'])
    date_col = smart_find_column(df.columns, ['تاریخ', 'Date'])
    # نقشه‌ها برای فیلتر
    def _mode(series):
        v = series.astype(str).str.strip()
        v = v[v != '']
        return v.value_counts().idxmax() if not v.empty else ''
    def display_map(key_col, original_col):
        if original_col is None: return {}
        tmp = df[df[key_col] != '']
        return tmp.groupby(key_col)[original_col].agg(_mode).to_dict() if not tmp.empty else {}
    line_map = display_map('_k_line', col_line)
    unit_map = display_map('_k_unit', col_unit)
    eq_map = display_map('_k_eq', equip_col)
    sel_line_k = st.sidebar.selectbox('📍 خط تولید:', ['همه'] + sorted(line_map.keys()), 
                                   format_func=lambda k: 'همه' if k == 'همه' else line_map.get(k, k))
    tmp_u = df.copy()
    if sel_line_k != 'همه': tmp_u = tmp_u[tmp_u['_k_line'] == sel_line_k]
    unit_keys = sorted([u for u in tmp_u['_k_unit'].unique() if u != ''])
    sel_unit_k = st.sidebar.selectbox('🏢 واحد:', ['همه'] + unit_keys, 
                                   format_func=lambda k: 'همه' if k == 'همه' else unit_map.get(k, k))
    if sel_unit_k != 'همه': tmp_u = tmp_u[tmp_u['_k_unit'] == sel_unit_k]
    eq_keys = sorted([e for e in tmp_u['_k_eq'].unique() if e != ''])
    sel_eq_k = st.sidebar.selectbox('⚙️ انتخاب تجهیز:', ['همه تجهیزات'] + eq_keys,
                                   format_func=lambda k: 'همه تجهیزات' if k == 'همه تجهیزات' else eq_map.get(k, k))
    search_eq = st.sidebar.text_input('🔎 جستجوی سریع تجهیز:', placeholder='مثلاً: میل فن')
    date_map = {}
    if date_col:
        tmp_d = df[df['_k_date'] != '']
        date_map = tmp_d.groupby('_k_date')[date_col].agg(_mode).to_dict()
    date_keys = sorted(list(date_map.keys()), reverse=True)
    sel_date_k = st.sidebar.selectbox('🌙 انتخاب تاریخ:', ['همه تاریخ‌ها'] + date_keys,
                                   format_func=lambda k: 'همه تاریخ‌ها' if k == 'همه تاریخ‌ها' else date_map.get(k, k))
    # اعمال فیلترها
    fdf = df.copy()
    if sel_line_k != 'همه': fdf = fdf[fdf['_k_line'] == sel_line_k]
    if sel_unit_k != 'همه': fdf = fdf[fdf['_k_unit'] == sel_unit_k]
    if sel_eq_k != 'همه تجهیزات': fdf = fdf[fdf['_k_eq'] == sel_eq_k]
    if search_eq.strip():
        q = norm(search_eq)
        tokens = [t for t in q.split() if t]
        if tokens: fdf = fdf[fdf['_k_eq'].map(lambda v: all(t in v for t in tokens))]
    if sel_date_k != 'همه تاریخ‌ها': fdf = fdf[fdf['_k_date'] == sel_date_k]
    if date_col: fdf = fdf.sort_values(by='_dkey', ascending=False)
    # ==========================================================================
    # 7. نمایش اصلی
    # ==========================================================================
    st.title('📊 تحلیل روند ارتعاشات تجهیزات')
    visible_cols = [c for c in df.columns if not str(c).startswith('_')]
    vib_cols = [c for c in visible_cols if any(k in str(c) for k in ['عمودی', 'افقی', 'محوری']) or str(c).startswith('P')]
    if sel_eq_k != 'همه تجهیزات':
        eq_display = eq_map.get(sel_eq_k, sel_eq_k)
        matched = False
        if not df_assets.empty:
            a_name = smart_find_column(df_assets.columns, ['نام تجهیز', 'عنوان تجهیز', 'نام', 'تجهیز', 'Asset'])
            if a_name:
                n_assets = df_assets[a_name].map(norm)
                rows = df_assets[n_assets == sel_eq_k]
                if rows.empty:
                    rows = df_assets[n_assets.map(lambda x: x != '' and (sel_eq_k in x or x in sel_eq_k))]
                if not rows.empty:
                    matched = True
                    r0 = rows.iloc[0]
                    def gv(keys, default='---'):
                        c = smart_find_column(df_assets.columns, keys)
                        if not c: return default
                        v = str(r0[c]).strip()
                        return v if v not in ('', 'nan', 'None', 'NaN') else default
                    e_type, e_rpm, e_line, e_unit = gv(['نوع تجهیز', 'نوع']), gv(['دور', 'RPM']), gv(['خط']), gv(['واحد'])
                    e_drive = gv(['نوع انتقال', 'کوپلینگ', 'اتصال', 'درایو'])
                    e_brg, e_bush = gv(['بیرینگ', 'Bearing']), gv(['بوش', 'Bush'])
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
                    pts, brg, bsh = smart_find_column(df_assets.columns, ['نقطه', 'Point']), smart_find_column(df_assets.columns, ['بیرینگ', 'Bearing']), smart_find_column(df_assets.columns, ['بوش', 'Bush'])
                    if any([pts, brg, bsh]):
                        log_cols = [c for c in [pts, brg, bsh] if c]
                        logistics = rows[log_cols].copy().replace({'': '---', 'nan': '---', 'None': '---', 'NaN': '---'})
                        rename = {pts: 'نقطه', brg: 'بیرینگ', bsh: 'بوش'}
                        logistics = logistics.rename(columns={k: v for k, v in rename.items() if k in logistics.columns})
                        with st.expander('📦 اطلاعات قطعات و لجستیک', expanded=True):
                            st.dataframe(logistics, hide_index=True, use_container_width=True)
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
        table = fdf[visible_cols].copy()
        if vib_cols:
            st.dataframe(table.style.map(color_vib, subset=vib_cols), use_container_width=True, hide_index=True)
        else:
            st.dataframe(table, use_container_width=True, hide_index=True)
        if vib_cols and sel_eq_k != 'همه تجهیزات' and date_col and len(fdf) > 1:
            with st.expander('📈 نمودار روند ارتعاشات', expanded=False):
                trend = fdf[[date_col] + vib_cols].copy()
                trend['_dkey'] = trend[date_col].map(date_sort_key)
                trend = trend.sort_values('_dkey')
                trend['تاریخ'] = trend[date_col].astype(str)
                long_df = trend.melt(id_vars=['تاریخ', '_dkey'], value_vars=vib_cols, var_name='نقطه/جهت', value_name='ارتعاش')
                long_df['ارتعاش'] = to_num(long_df['ارتعاش'])
                long_df = long_df.dropna(subset=['ارتعاش'])
                if not long_df.empty:
                    fig_line = px.line(long_df, x='تاریخ', y='ارتعاش', color='نقطه/جهت', markers=True, title='روند ارتعاش (mm/s)')
                    fig_line.add_hline(y=4.5, line_dash='dash', line_color='orange', annotation_text='هشدار')
                    fig_line.add_hline(y=7.1, line_dash='dash', line_color='red', annotation_text='بحرانی')
                    st.plotly_chart(fig_line, use_container_width=True)
        st.markdown('---')
        st.markdown('### 📈 تحلیل وضعیت سلامت تجهیزات')
        with st.expander('نمایش نمودار دایره‌ای وضعیت سلامت', expanded=False):
            if vib_cols:
                v_max = fdf[vib_cols].apply(to_num, axis=0).max(axis=1)
                def cat(v):
                    if pd.isna(v): return 'نامشخص'
                    if v > 7.1: return 'بحرانی'
                    if v > 4.5: return 'هشدار'
                    return 'سالم'
                status = v_max.map(cat).value_counts()
                if not status.empty:
                    fig_pie = px.pie(values=status.values, names=status.index, color=status.index,
                                   color_discrete_map={'سالم': '#2e7d32', 'هشدار': '#ffa500', 'بحرانی': '#ff4b4b', 'نامشخص': '#9e9e9e'}, hole=0.35)
                    st.plotly_chart(fig_pie, use_container_width=True)
    st.markdown('<div style="text-align:center; margin-top:50px; color:#555; font-family:Tahoma;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>', unsafe_allow_html=True)
else:
    st.error('❌ خطا در اتصال به منبع داده.')
