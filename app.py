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
        st.markdown(
            '<h2 style="text-align:center;">🔐 ورود به سامانه هوشمند پایش وضعیت سیمان تهران</h2>',
            unsafe_allow_html=True
        )
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
    """نرمال‌سازی کامل متن: اعداد فارسی/عربی، یکدست‌سازی ی/ک، حذف فاصله و نیم‌فاصله"""
    if x is None:
        return ''
    try:
        if isinstance(x, float) and pd.isna(x):
            return ''
    except Exception:
        pass
    s = str(x).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = (s.replace('ي', 'ی').replace('ى', 'ی')
          .replace('ك', 'ک').replace('ۀ', 'ه').replace('ة', 'ه'))
    s = s.replace('\u200c', ' ').replace('\xa0', ' ')
    s = s.replace('-', ' ').replace('_', ' ').replace('.', ' ')
    s = ' '.join(s.split()).lower()
    return s


def clean_num_text(x):
    """پاک‌سازی متن عددی برای تبدیل به عدد"""
    s = str(x).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
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
    except Exception:
        return ''


def smart_find_column(columns, keywords):
    """یافتن ستون بر اساس تطبیق دقیق، سپس کلمه کلیدی"""
    if columns is None:
        return None
    cols = list(columns)
    normed = {c: norm(c) for c in cols}
    # 1) تطبیق کامل
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if normed[c] == nk:
                return c
    # 2) تطبیق کلمه کلیدی
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if nk and nk in normed[c]:
                return c
    return None


def date_sort_key(val):
    """تبدیل تاریخ متنی (شمسی یا میلادی) به عدد قابل مرتب‌سازی: YYYYMMDD"""
    s = norm(val)
    m = re.search(r'(\d{2,4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})', s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 1400
        return y * 10000 + mo * 100 + d
    m = re.search(r'(\d{6,8})', s)
    if m:
        return int(m.group(1))
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
    return 'راهنمای نقاط برای این نوع تجهیز تعریف نشده است.'

# ==============================================================================
# 3. هدر و لوگوها
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

# ==============================================================================
# 4. بارگذاری داده‌ها (متن خام => بدون صفر اضافه)
# ==============================================================================
VIB_URL = ('https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/'
           'export?format=csv&gid=0')
ASSETS_URL = ('https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/'
              'export?format=csv&gid=1276803564')


@st.cache_data(ttl=600)
def load_all_data():
    df_vib = pd.DataFrame()
    df_assets = pd.DataFrame()
    try:
        df_vib = pd.read_csv(VIB_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception as e:
        st.error(f'❌ خطا در خواندن شیت ارتعاشات: {e}')
    try:
        df_assets = pd.read_csv(ASSETS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception as e:
        st.warning(f'⚠️ شیت مشخصات فنی (Assets) بارگذاری نشد. ({e})')
    return df_vib, df_assets


df, df_assets = load_all_data()

# ==============================================================================
# 5. فیلترهای سایدبار
# ==============================================================================
st.sidebar.header('🔍 فیلترهای پیشرفته')

if not df.empty:
    col_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
    col_unit = smart_find_column(df.columns, ['واحد'])
    equip_col = smart_find_column(df.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'Equipment', 'Asset'])
    date_col = smart_find_column(df.columns, ['تاریخ', 'Date'])

    df['_k_line'] = df[col_line].map(norm) if col_line else ''
    df['_k_unit'] = df[col_unit].map(norm) if col_unit else ''
    df['_k_eq'] = df[equip_col].map(norm) if equip_col else ''
    df['_k_date'] = df[date_col].map(norm) if date_col else ''
    df['_dkey'] = df[date_col].map(date_sort_key) if date_col else 0

    def _mode(series):
        v = series.astype(str).str.strip()
        v = v[v != '']
        if v.empty:
            return ''
        return v.value_counts().idxmax()

    def display_map(key_col, original_col):
        if original_col is None:
            return {}
        tmp = df[df[key_col] != '']
        if tmp.empty:
            return {}
        return tmp.groupby(key_col)[original_col].agg(_mode).to_dict()

    line_map = display_map('_k_line', col_line)
    unit_map = display_map('_k_unit', col_unit)
    eq_map = display_map('_k_eq', equip_col)

    # ---------- خط تولید ----------
    lines = sorted(line_map.keys())
    sel_line_k = st.sidebar.selectbox(
        '📍 خط تولید:', ['همه'] + lines,
        format_func=lambda k: 'همه' if k == 'همه' else line_map.get(k, k)
    )

    # ---------- واحد ----------
    tmp = df.copy()
    if sel_line_k != 'همه':
        tmp = tmp[tmp['_k_line'] == sel_line_k]
    unit_keys = sorted([u for u in tmp['_k_unit'].unique() if u != ''])
    sel_unit_k = st.sidebar.selectbox(
        '🏢 واحد:', ['همه'] + unit_keys,
        format_func=lambda k: 'همه' if k == 'همه' else unit_map.get(k, k)
    )

    # ---------- تجهیز ----------
    if sel_unit_k != 'همه':
        tmp = tmp[tmp['_k_unit'] == sel_unit_k]
    eq_keys = sorted([e for e in tmp['_k_eq'].unique() if e != ''])
    sel_eq_k = st.sidebar.selectbox(
        '⚙️ انتخاب تجهیز:', ['همه تجهیزات'] + eq_keys,
        format_func=lambda k: 'همه تجهیزات' if k == 'همه تجهیزات' else eq_map.get(k, k)
    )

    search_eq = st.sidebar.text_input('🔎 جستجوی سریع تجهیز:', placeholder='مثلاً: میل فن')

    # ---------- تاریخ ----------
    st.sidebar.markdown('**📅 فیلتر تاریخ**')
    date_search = st.sidebar.text_input('جستجوی تاریخ (مثلاً 1405/08):')

    date_map = {}
    if date_col:
        tmp_d = df[df['_k_date'] != '']
        date_map = tmp_d.groupby('_k_date')[date_col].agg(_mode).to_dict()
    date_keys = sorted(list(date_map.keys()), reverse=True)
    sel_date_k = st.sidebar.selectbox(
        '🌙 انتخاب تاریخ:', ['همه تاریخ‌ها'] + date_keys,
        format_func=lambda k: 'همه تاریخ‌ها' if k == 'همه تاریخ‌ها' else date_map.get(k, k)
    )

    # ==========================================================================
    # 6. اعمال فیلترها
    # ==========================================================================
    fdf = df.copy()
    if sel_line_k != 'همه':
        fdf = fdf[fdf['_k_line'] == sel_line_k]
    if sel_unit_k != 'همه':
        fdf = fdf[fdf['_k_unit'] == sel_unit_k]
    if sel_eq_k != 'همه تجهیزات':
        fdf = fdf[fdf['_k_eq'] == sel_eq_k]

    if search_eq.strip():
        q = norm(search_eq)
        tokens = [t for t in q.split() if t]
        if tokens:
            mask = fdf['_k_eq'].map(lambda v: all(t in v for t in tokens))
            if mask.any():
                fdf = fdf[mask]

    if date_search.strip():
        fdf = fdf[fdf['_k_date'].str.contains(norm(date_search), na=False, regex=False)]
    if sel_date_k != 'همه تاریخ‌ها':
        fdf = fdf[fdf['_k_date'] == sel_date_k]

    if date_col:
        fdf = fdf.sort_values(by='_dkey', ascending=False)

    # ==========================================================================
    # 7. نمایش
    # ==========================================================================
    st.markdown('<style>.main .block-container { padding-right:1rem; padding-left:1rem; }</style>',
                unsafe_allow_html=True)
    st.title('📊 تحلیل روند ارتعاشات تجهیزات')

    visible_cols = [c for c in df.columns if not str(c).startswith('_')]
    vib_cols = [c for c in visible_cols if any(k in str(c) for k in ['عمودی', 'افقی', 'محوری'])]

    # --------------------------------------------------------------------------
    # 7-1. کارت مشخصات فنی + قطعات (اول صفحه)
    # --------------------------------------------------------------------------
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
                        if not c:
                            return default
                        v = str(r0[c]).strip()
                        return v if v not in ('', 'nan', 'None', 'NaN') else default

                    e_type = gv(['نوع تجهیز', 'نوع'])
                    e_rpm = gv(['دور گردش', 'دور', 'RPM', 'سرعت'])
                    e_line = gv(['خط تولید', 'خط'])
                    e_unit = gv(['واحد'])
                    e_drive = gv(['نوع انتقال', 'انتقال قدرت', 'سیستم انتقال', 'کوپلینگ',
                                  'کوپل', 'اتصال', 'درایو', 'تسمه', 'پولی'])
                    e_brg = gv(['شماره بیرینگ', 'بیرینگ', 'برینگ', 'Bearing'])
                    e_bush = gv(['شماره بوش', 'بوش', 'Bush'])

                    st.markdown(f'''
                    <div style='background:#f0f7ff; padding:20px 24px; border-radius:15px;
                                border-right:10px solid #1E3A8D; margin-bottom:18px; text-align:right;
                                direction:rtl; box-shadow:2px 2px 8px rgba(0,0,0,0.06);'>
                        <h3 style='color:#1E3A8D; margin:0 0 14px 0; font-family:Tahoma;'>
                            🛠️ مشخصات فنی: {eq_display}
                        </h3>
                        <div style='display:flex; flex-wrap:wrap; gap:10px 28px; font-size:16px;
                                    color:#333; font-family:Tahoma;'>
                            <span><b style='color:#1E3A8D;'>🔹 نوع تجهیز:</b> {e_type}</span>
                            <span><b style='color:#1E3A8D;'>🔹 دور:</b> {e_rpm} RPM</span>
                            <span><b style='color:#1E3A8D;'>🔹 خط تولید:</b> {e_line}</span>
                            <span><b style='color:#1E3A8D;'>🔹 واحد:</b> {e_unit}</span>
                            <span><b style='color:#1E3A8D;'>🔹 نوع انتقال قدرت:</b> {e_drive}</span>
                        </div>
                        <div style='display:flex; flex-wrap:wrap; gap:10px 28px; font-size:16px;
                                    color:#333; margin-top:10px; font-family:Tahoma;'>
                            <span><b style='color:#1E3A8D;'>🧩 شماره بیرینگ:</b> {e_brg}</span>
                            <span><b style='color:#1E3A8D;'>🧩 شماره بوش:</b> {e_bush}</span>
                        </div>
                        <div style='margin-top:14px; font-size:15px; color:#1E3A8D; background:#e6efff;
                                    padding:8px 15px; border-radius:8px; display:inline-block;
                                    font-family:Tahoma;'>
                            <b>📍 راهنمای نقاط (P-Map):</b> {get_point_guide(eq_display, e_type)}
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)

                    # جدول قطعات و لجستیک
                    pts = smart_find_column(df_assets.columns, ['نقطه', 'پوینت', 'Point'])
                    brg = smart_find_column(df_assets.columns, ['بیرینگ', 'برینگ', 'Bearing'])
                    bsh = smart_find_column(df_assets.columns, ['بوش', 'Bush'])
                    log_cols = [c for c in [pts, brg, bsh] if c]

                    if log_cols:
                        logistics = rows[log_cols].copy()
                        logistics = logistics.replace({'': '---', 'nan': '---', 'None': '---', 'NaN': '---'})
                        rename = {}
                        if pts:
                            rename[pts] = 'نقطه اندازه‌گیری'
                        if brg:
                            rename[brg] = 'شماره بیرینگ'
                        if bsh:
                            rename[bsh] = 'شماره بوش'
                        logistics = logistics.rename(columns=rename)
                        with st.expander('📦 اطلاعات قطعات و لجستیک (بیرینگ / بوش)', expanded=True):
                            st.dataframe(logistics, hide_index=True, use_container_width=True)

                    # تمام ستون‌های شیت Assets برای این تجهیز
                    with st.expander('📋 مشاهده تمام مشخصات ثبت‌شده این تجهیز', expanded=False):
                        full = pd.DataFrame({
                            'عنوان': list(df_assets.columns),
                            'مقدار': [str(x).strip() for x in r0.values]
                        })
                        full = full[~full['مقدار'].isin(['', 'nan', 'None', 'NaN'])]
                        st.dataframe(full, hide_index=True, use_container_width=True)

        if not matched:
            st.info('ℹ️ برای این تجهیز، ردیف مشخصاتی در شیت Assets پیدا نشد. '
                    '(نام تجهیز در دو شیت باید مشابه باشد.)')

    # --------------------------------------------------------------------------
    # 7-2. جدول داده‌های ارتعاشات
    # --------------------------------------------------------------------------
    if not fdf.empty:
        st.markdown(f'### 📋 داده‌های ارتعاشات ({len(fdf)} مورد)')

        def color_vib(val):
            try:
                v = float(clean_num_text(val))
            except Exception:
                return ''
            if v > 7.1:
                return 'background-color:#ff4b4b; color:white'
            if v > 4.5:
                return 'background-color:#ffa500; color:white'
            return 'background-color:#2e7d32; color:white'

        table = fdf[visible_cols].copy()
        if vib_cols:
            try:
                styled = table.style.map(color_vib, subset=vib_cols)
            except AttributeError:
                styled = table.style.applymap(color_vib, subset=vib_cols)
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.dataframe(table, use_container_width=True, hide_index=True)

        # ----------------------------------------------------------------------
        # 7-3. نمودار روند ارتعاشات (برای تجهیز انتخاب‌شده)
        # ----------------------------------------------------------------------
        if vib_cols and sel_eq_k != 'همه تجهیزات' and date_col and len(fdf) > 1:
            with st.expander('📈 نمودار روند ارتعاشات این تجهیز در طول زمان', expanded=False):
                trend = fdf[[date_col] + vib_cols].copy()
                trend['_dkey'] = trend[date_col].map(date_sort_key)
                trend = trend.sort_values('_dkey')
                trend['تاریخ'] = trend[date_col].astype(str)

                long_df = trend.melt(
                    id_vars=['تاریخ', '_dkey'],
                    value_vars=vib_cols,
                    var_name='نقطه/جهت',
                    value_name='ارتعاش'
                )
                long_df['ارتعاش'] = to_num(long_df['ارتعاش'])
                long_df = long_df.dropna(subset=['ارتعاش'])

                if not long_df.empty:
                    fig_line = px.line(
                        long_df,
                        x='تاریخ',
                        y='ارتعاش',
                        color='نقطه/جهت',
                        markers=True,
                        title='روند ارتعاش بر حسب تاریخ اندازه‌گیری (mm/s)'
                    )
                    fig_line.add_hline(y=4.5, line_dash='dash', line_color='orange',
                                       annotation_text='حد هشدار 4.5')
                    fig_line.add_hline(y=7.1, line_dash='dash', line_color='red',
                                       annotation_text='حد بحرانی 7.1')
                    st.plotly_chart(fig_line, use_container_width=True)
                else:
                    st.info('داده عددی معتبری برای رسم روند وجود ندارد.')

        # ----------------------------------------------------------------------
        # 7-4. نمودار دایره‌ای وضعیت سلامت (انتهای صفحه)
        # ----------------------------------------------------------------------
        st.markdown('---')
        st.markdown('### 📈 تحلیل وضعیت سلامت تجهیزات')
        with st.expander('نمایش نمودار دایره‌ای وضعیت سلامت', expanded=False):
            if vib_cols:
                v_max = fdf[vib_cols].apply(to_num, axis=0).max(axis=1)

                def cat(v):
                    if pd.isna(v):
                        return 'نامشخص'
                    if v > 7.1:
                        return 'بحرانی'
                    if v > 4.5:
                        return 'هشدار'
                    return 'سالم'

                status = v_max.map(cat).value_counts()
                if not status.empty:
                    fig_pie = px.pie(
                        values=status.values,
                        names=status.index,
                        color=status.index,
                        color_discrete_map={
                            'سالم': '#2e7d32',
                            'هشدار': '#ffa500',
                            'بحرانی': '#ff4b4b',
                            'نامشخص': '#9e9e9e'
                        },
                        hole=0.35
                    )
                    fig_pie.update_traces(textinfo='percent+label')
                    st.plotly_chart(fig_pie, use_container_width=True)
                    st.caption('معیار: بیشینه ارتعاش هر ردیف — سالم ≤ 4.5 | هشدار 4.5 تا 7.1 | بحرانی > 7.1 (mm/s)')
                else:
                    st.info('داده عددی معتبری برای تحلیل سلامت وجود ندارد.')
            else:
                st.info('ستون‌های ارتعاشات (عمودی/افقی/محوری) پیدا نشد.')

    else:
        st.warning('⚠️ هیچ داده‌ای با این فیلترها پیدا نشد. فیلترها را بازتر کنید.')

    st.markdown(
        '<div style="text-align:center; margin-top:50px; color:#555; font-family:Tahoma;">'
        'طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>',
        unsafe_allow_html=True
    )

else:
    st.error('❌ خطا در دریافت داده‌ها. لطفاً لینک گوگل‌شیت و دسترسی آن را بررسی کنید.')
