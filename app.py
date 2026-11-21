import re
import pandas as pd
import streamlit as st
import base64
import plotly.express as px

# ==============================================================================
# بخش ۱ — تنظیمات صفحه و ورود کاربران
# ==============================================================================
st.set_page_config(page_title='داشبورد فنی ارتعاشات سیمان تهران', layout='wide')

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
            unsafe_allow_html=True,
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
# بخش ۲ — توابع کمکی
# ==============================================================================
FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'
EN_DIGITS = '0123456789'


def norm(x):
    if x is None or str(x).strip() == '':
        return ''
    s = str(x).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = (s.replace('ي', 'ی').replace('ى', 'ی')
          .replace('ك', 'ک').replace('ۀ', 'ه').replace('ة', 'ه'))
    s = s.replace('\u200c', ' ').replace('\xa0', ' ')
    s = re.sub(r'[-_.\\/]', ' ', s)
    return ' '.join(s.split()).lower()


def clean_num_text(x):
    s = str(x).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = s.replace('٫', '.').replace('،', '.').replace(',', '.')
    return s.replace(' ', '')


def to_num(x):
    try:
        return float(clean_num_text(x))
    except Exception:
        return None


def date_sort_key(val):
    s = norm(val)
    m = re.search(r'(\d{2,4})\s*(\d{1,2})\s*(\d{1,2})', s)
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 1400
            return int(f"{y}{mo:02d}{d:02d}")
        except Exception:
            return 0
    return 0


def point_number(val):
    """شماره نقطه را از هر شکلی استخراج می‌کند: P1 , p 10 , پی۲ , P3-عمودی ..."""
    s = clean_num_text(val).lower()
    s = s.replace('پی', 'p')
    m = re.search(r'p\s*0*(\d+)', s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return 999
    m2 = re.search(r'(\d+)', s)
    if m2:
        return int(m2.group(1))
    return 999


def get_image_base64(path):
    try:
        with open(path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ''


def smart_find_column(columns, keywords):
    if columns is None:
        return None
    cols = list(columns)
    normed = {c: norm(c) for c in cols}
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if normed[c] == nk or (nk != '' and nk in normed[c]):
                return c
    return None


# ==============================================================================
# بخش ۳ — بارگذاری داده از سه شیت (مستقیماً و بدون تغییر چیدمان)
# ==============================================================================
VIB_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0'
ASSETS_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=1276803564'
ANN_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=2057447521'


@st.cache_data(ttl=600)
def load_data():
    def _read(url):
        try:
            return pd.read_csv(url, dtype=str, keep_default_na=False, encoding='utf-8-sig')
        except Exception:
            return pd.DataFrame()
    return _read(VIB_URL), _read(ASSETS_URL), _read(ANN_URL)


df_raw, df_assets, df_ann = load_data()

c_date = smart_find_column(df_raw.columns, ['تاریخ', 'date'])
c_line = smart_find_column(df_raw.columns, ['خط تولید', 'خط'])
c_unit = smart_find_column(df_raw.columns, ['واحد'])
c_equip = smart_find_column(df_raw.columns, ['عنوان تجهیز', 'نام تجهیز', 'تجهیز', 'asset'])
c_point = smart_find_column(df_raw.columns, ['محل اندازه گیری', 'محل اندازه‌گیری', 'نقطه', 'point'])

# ستون‌های مقدار ارتعاش (عمودی / افقی / محوری / mm/s)
VIB_KEYS = ['عمودی', 'افقی', 'محوری', 'محور', 'mm/s', 'mm s', 'velocity']
vib_cols = [c for c in df_raw.columns if any(k in norm(c) for k in [norm(k) for k in VIB_KEYS])]

if not df_raw.empty:
    df_raw['_k_line'] = df_raw[c_line].map(norm) if c_line else ''
    df_raw['_k_unit'] = df_raw[c_unit].map(norm) if c_unit else ''
    df_raw['_k_eq'] = df_raw[c_equip].map(norm) if c_equip else ''
    df_raw['_k_date'] = df_raw[c_date].map(norm) if c_date else ''
    df_raw['_dkey'] = df_raw[c_date].map(date_sort_key) if c_date else 0
    df_raw['_pnum'] = df_raw[c_point].map(point_number) if c_point else 999

    # نگاشت نام زیبا برای فیلترها
    df_raw['_d_line'] = df_raw[c_line] if c_line else ''
    df_raw['_d_unit'] = df_raw[c_unit] if c_unit else ''
    df_raw['_d_eq'] = df_raw[c_equip] if c_equip else ''

# ==============================================================================
# بخش ۴ — هدر و اعلانیه‌ها
# ==============================================================================
logo_siman = get_image_base64('client_logo.png')
logo_faz = get_image_base64('my_logo.png')

st.markdown(f'''
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;
            background:white; padding:15px 30px; border-radius:15px; box-shadow:0 4px 8px rgba(0,0,0,0.1);">
    <img src="data:image/png;base64,{logo_faz}" style="width:110px; height:auto;">
    <div style="text-align:center; color:#1E3A8D; font-size:24px; font-weight:bold; font-family:Tahoma;">
        🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران
    </div>
    <img src="data:image/png;base64,{logo_siman}" style="width:110px; height:auto;">
</div>
''', unsafe_allow_html=True)

if not df_ann.empty:
    c_tit = smart_find_column(df_ann.columns, ['عنوان', 'title'])
    c_txt = smart_find_column(df_ann.columns, ['متن', 'text'])
    c_typ = smart_find_column(df_ann.columns, ['نوع', 'type'])
    c_act = smart_find_column(df_ann.columns, ['فعال', 'active'])
    if c_tit and c_txt:
        for _, row in df_ann.iterrows():
            if c_act and norm(row[c_act]) not in ['بله', 'yes', 'true', '1']:
                continue
            t = str(row[c_tit])
            txt = str(row[c_txt])
            typ = str(row[c_typ]) if c_typ else ''
            if any(x in typ for x in ['خطر', 'بحرانی']):
                color, icon = '#ff4b4b', '🚨'
            elif 'موفق' in typ:
                color, icon = '#2e7d32', '✅'
            else:
                color, icon = '#1E3A8D', 'ℹ️'
            st.markdown(
                f'<div style="background:{color}; padding:12px; border-radius:10px; margin-bottom:8px; '
                f'color:white; direction:rtl; text-align:right; font-family:Tahoma;">'
                f'<b>{icon} {t}</b><br><small>{txt}</small></div>',
                unsafe_allow_html=True,
            )

# ==============================================================================
# بخش ۵ — سایدبار: فیلترها، حدود هشدار، عیب‌یابی
# ==============================================================================
st.sidebar.header('🔍 فیلترها')

WARN = st.sidebar.number_input('حد هشدار (mm/s)', value=4.5, step=0.1, format='%.1f')
CRIT = st.sidebar.number_input('حد بحرانی (mm/s)', value=7.1, step=0.1, format='%.1f')

order_mode = st.sidebar.radio(
    'ترتیب نمایش',
    ['گروه‌بندی بر اساس تجهیز', 'بر اساس تاریخ'],
    index=0,
    help='در حالت اول، نقاط هر تجهیز پشت سر هم و از P1 به بالا مرتب می‌شوند.',
)

if not df_raw.empty:
    lines = sorted({v for v in df_raw['_d_line'] if str(v).strip() != ''})
    units = sorted({v for v in df_raw['_d_unit'] if str(v).strip() != ''})
    equips = sorted({v for v in df_raw['_d_eq'] if str(v).strip() != ''})
    dates = sorted({v for v in df_raw['_k_date'] if v != ''}, reverse=True)

    sel_line = st.sidebar.selectbox('📍 خط تولید:', ['همه'] + lines)
    sel_unit = st.sidebar.selectbox('🏢 واحد:', ['همه'] + units)
    sel_eq = st.sidebar.selectbox('⚙️ تجهیز:', ['همه تجهیزات'] + equips)
    search_txt = st.sidebar.text_input('🔎 جستجوی تجهیز:')
    sel_date = st.sidebar.selectbox('🌙 تاریخ:', ['همه تاریخ‌ها'] + dates)

    with st.sidebar.expander('🩺 عیب‌یابی داده'):
        st.write('ستون تاریخ:', c_date)
        st.write('ستون تجهیز:', c_equip)
        st.write('ستون نقطه:', c_point)
        st.write('تعداد ستون‌های ارتعاش:', len(vib_cols))
        st.write('نمونه ستون‌ها:', vib_cols[:8])
        st.write('تعداد رکورد خام:', len(df_raw))

    # -------------------- اعمال فیلترها --------------------
    fdf = df_raw.copy()
    if sel_line != 'همه':
        fdf = fdf[fdf['_k_line'] == norm(sel_line)]
    if sel_unit != 'همه':
        fdf = fdf[fdf['_k_unit'] == norm(sel_unit)]
    if sel_eq != 'همه تجهیزات':
        fdf = fdf[fdf['_k_eq'] == norm(sel_eq)]
    if search_txt.strip():
        q = norm(search_txt)
        fdf = fdf[fdf['_k_eq'].str.contains(q, na=False)]
    if sel_date != 'همه تاریخ‌ها':
        fdf = fdf[fdf['_k_date'] == norm(sel_date)]

    # -------------------- 🔑 ترتیب نمایش (رفع به‌هم‌ریختگی) --------------------
    if order_mode == 'گروه‌بندی بر اساس تجهیز':
        fdf = fdf.sort_values(
            by=['_k_eq', '_dkey', '_pnum'],
            ascending=[True, False, True],
            kind='mergesort',
        )
    else:
        fdf = fdf.sort_values(
            by=['_dkey', '_k_eq', '_pnum'],
            ascending=[False, True, True],
            kind='mergesort',
        )
    fdf = fdf.reset_index(drop=True)

    st.title('📊 تحلیل ارتعاشات تجهیزات')

    # ==========================================================================
    # بخش ۶ — کارت‌های خلاصه + جدول اصلی
    # ==========================================================================
    all_vals = []
    for c in vib_cols:
        if c in fdf.columns:
            all_vals.extend([v for v in fdf[c].map(to_num) if v is not None])

    k1, k2, k3, k4 = st.columns(4)
    k1.metric('تعداد تجهیزات', fdf['_k_eq'].nunique())
    k2.metric('رکورد نمایش‌داده‌شده', len(fdf))
    k3.metric('وضعیت هشدار', sum(1 for v in all_vals if WARN < v <= CRIT))
    k4.metric('وضعیت بحرانی', sum(1 for v in all_vals if v > CRIT))

    if fdf.empty:
        st.warning('با این فیلترها رکوردی پیدا نشد.')
    else:
        st.subheader(f'📋 جدول ارتعاشات — {len(fdf)} ردیف')

        vis_cols = [c for c in fdf.columns if not c.startswith('_')]
        color_subset = [c for c in vib_cols if c in vis_cols]

        def color_vib(val):
            v = to_num(val)
            if v is None:
                return ''
            if v > CRIT:
                return 'background-color:#ff4b4b; color:white'
            if v > WARN:
                return 'background-color:#ffa500; color:white'
            return 'background-color:#2e7d32; color:white'

        styled = fdf[vis_cols].style
        if color_subset:
            styled = styled.map(color_vib, subset=color_subset)
        st.dataframe(styled, use_container_width=True, hide_index=True, height=620)

        # نام تجهیز در سطر اول هر گروه پررنگ دیده شود
        st.caption(
            'ترتیب فعلی: ' + order_mode +
            ' — نقاط هر تجهیز پیوسته و به ترتیب شماره نقطه (P1 → Pn) نمایش داده می‌شوند.'
        )

        # شمارنده شماره نقاط
        with st.expander('🔢 نقاط شناسایی‌شده در این جدول'):
            tmp = fdf[['_d_eq', '_pnum']].copy()
            tmp['نقطه'] = tmp['_pnum'].map(lambda n: f'P{n}' if n != 999 else 'نامشخص')
            st.dataframe(
                tmp.groupby('_d_eq')['نقطه'].apply(lambda s: ' , '.join(sorted(set(s), key=lambda x: point_number(x))))
                .reset_index().rename(columns={'_d_eq': 'تجهیز', 'نقطه': 'نقاط'}),
                use_container_width=True,
                hide_index=True,
            )

        # -------------------- نمای افقی اختیاری --------------------
        with st.expander('↔️ نمای افقی (نقاط روی ستون) — اختیاری'):
            if c_equip and c_date and c_point and vib_cols:
                base_cols = [c for c in [c_date, c_line, c_unit, c_equip] if c]
                piv = fdf.copy()
                piv['_pt'] = piv['_pnum'].map(lambda n: f'P{n}' if n != 999 else '؟')
                for c in vib_cols:
                    piv[c] = piv[c].map(to_num)
                wide = piv.pivot_table(
                    index=base_cols + ['_dkey'], columns='_pt', values=vib_cols[0], aggfunc='first'
                ).reset_index().drop(columns=['_dkey'])
                st.dataframe(wide, use_container_width=True, hide_index=True)
            else:
                st.info('برای این نما نیاز به ستون تجهیز، تاریخ، نقطه و مقدار است.')

        # -------------------- دانلود CSV --------------------
        st.download_button(
            '⬇️ دانلود جدول فیلترشده (CSV)',
            data=fdf[vis_cols].to_csv(index=False).encode('utf-8-sig'),
            file_name='vibration_report.csv',
            mime='text/csv',
        )

    # ==========================================================================
    # بخش ۷ — مشخصات تجهیز، راهنمای نقاط، نمودار روند
    # ==========================================================================
    if sel_eq != 'همه تجهیزات' and not df_assets.empty:
        a_name = smart_find_column(df_assets.columns, ['نام تجهیز', 'عنوان تجهیز', 'Asset'])
        if a_name:
            rows = df_assets[df_assets[a_name].map(norm) == norm(sel_eq)]
            if not rows.empty:
                r = rows.iloc[0]

                def gv(keys):
                    c = smart_find_column(df_assets.columns, keys)
                    if c and str(r[c]).strip() != '':
                        return str(r[c])
                    return '---'

                st.info(
                    f"🛠️ نوع: {gv(['نوع تجهیز', 'نوع'])} | "
                    f"دور: {gv(['دور', 'RPM'])} RPM | "
                    f"خط: {gv(['خط'])} | واحد: {gv(['واحد'])}"
                )

    if sel_eq != 'همه تجهیزات' and len(fdf) > 1 and c_date and vib_cols:
        st.subheader('📈 نمودار روند ارتعاش')
        dirs = st.multiselect('جهت اندازه‌گیری:', vib_cols, default=vib_cols[:3])
        if dirs:
            long_df = fdf[[c_date] + dirs].copy()
            long_df['_dkey'] = long_df[c_date].map(date_sort_key)
            long_df = long_df.sort_values('_dkey')
            melted = long_df.melt(id_vars=[c_date, '_dkey'], value_vars=dirs,
                                  var_name='جهت', value_name='مقدار')
            melted['مقدار'] = melted['مقدار'].map(to_num)
            melted = melted.dropna(subset=['مقدار'])
            if not melted.empty:
                fig = px.line(melted, x=c_date, y='مقدار', color='جهت', markers=True,
                              title='روند تغییرات ارتعاش (mm/s)')
                fig.add_hline(y=WARN, line_dash='dash', line_color='orange',
                              annotation_text='هشدار')
                fig.add_hline(y=CRIT, line_dash='dash', line_color='red',
                              annotation_text='بحرانی')
                st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div style="text-align:center; margin-top:50px; color:#555; font-family:Tahoma;">'
        'طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>',
        unsafe_allow_html=True,
    )
else:
    st.error('❌ داده‌ای بارگذاری نشد. لینک شیت و دسترسی انتشار را بررسی کنید.')
