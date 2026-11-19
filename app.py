import datetime
import base64

import pandas as pd
import plotly.express as px
import streamlit as st

# ==============================================================================
# 0. تنظیمات صفحه
# ==============================================================================
st.set_page_config(page_title='داشبورد فنی ارتعاشات سیمان تهران', layout='wide')

# ==============================================================================
# 1. ورود (Authentication)
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
            unsafe_allow_html=True,
        )
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
# 2. توابع کمکی
# ==============================================================================
def norm(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return ''
    s = str(x).strip()
    farsi = '۰۱۲۳۴۵۶۷۸۹'
    arabic = '٠١٢٣٤٥٦٧٨٩'
    english = '0123456789'
    for f, e in zip(farsi, english):
        s = s.replace(f, e)
    for a, e in zip(arabic, english):
        s = s.replace(a, e)
    s = (s.replace('ي', 'ی').replace('ى', 'ی').replace('ك', 'ک')
          .replace('ۀ', 'ه').replace('ة', 'ه'))
    s = s.replace('\u200c', ' ').replace('\xa0', ' ')
    s = ' '.join(s.split()).lower()
    return s


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
    for k in keywords:
        for c in cols:
            if norm(c) == norm(k):
                return c
    for k in keywords:
        for c in cols:
            if norm(k) in norm(c):
                return c
    return None


def to_num(series):
    s = (series.astype(str)
         .str.replace('٫', '.', regex=False)
         .str.replace('،', '.', regex=False)
         .str.replace(',', '.', regex=False)
         .str.strip())
    s = s.replace({'': None, 'nan': None, 'None': None, '---': None})
    return pd.to_numeric(s, errors='coerce')


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
    return 'راهنمای نقاط تعریف نشده است.'


# ==============================================================================
# 3. سیستم اعلامیه‌ها (Announcement System)
# ==============================================================================
# برای هر اعلامیه ۴ سطح اهمیت داریم و رنگ هر کدام خودکار تعیین می‌شود:
#   warning = زرد (هشدار عملیاتی)
#   info    = آبی (اطلاع‌رسانی عمومی)
#   danger  = قرمز (خطر / توقف اضطراری)
#   success = سبز (دستور انجام‌شده / تأییدیه)
#
# نکات:
#   - expiry: تاریخ میلادی انقضا (datetime.date). بعد از این تاریخ، اعلامیه خودکار حذف می‌شود.
#   - None   : یعنی بدون تاریخ انقضا (همیشه نمایش داده می‌شود).
#   - enabled: با False می‌توانی اعلامیه را بدون حذف کردن، موقتاً خاموش کنی.
#   - expires_label: متنی که زیر اعلامیه نشان داده می‌شود (مثلاً اعتبار تا پایان آذر ۱۴۰۵).
ANNOUNCEMENT_STYLES = {
    'warning': {'bg': '#fff8e1', 'border': '#ffb300', 'title': '#8d6e00', 'icon': '⚠️'},
    'info':    {'bg': '#e3f2fd', 'border': '#1e88e5', 'title': '#0d47a1', 'icon': 'ℹ️'},
    'danger':  {'bg': '#ffebee', 'border': '#e53935', 'title': '#b71c1c', 'icon': '🚨'},
    'success': {'bg': '#e8f5e9', 'border': '#43a047', 'title': '#1b5e20', 'icon': '✅'},
}

ANNOUNCEMENTS = [
    {
        'enabled': True,
        'type': 'warning',
        'title': 'اطلاعیه عملیاتی و ایمنی',
        'text': ('با توجه به خنک شدن هوا، لطفاً در صورت عدم لزوم، برق فن‌های خنک‌کننده '
                 'نصب‌شده بر روی تجهیزات را قطع نمایید.<br>'
                 '<b>فن خنک‌کننده یاتاقان آزاد (EP فن الکتروفیلتر کوره ۹) نیازی به ادامه کارکرد ندارد.</b>'),
        'expiry': datetime.date(2026, 12, 20),
        'expires_label': 'اعتبار تا پایان آذر ۱۴۰۵',
    },
    {
        'enabled': True,
        'type': 'info',
        'title': 'اطلاع‌رسانی عمومی',
        'text': ('برنامه ارتعاش‌سنجی دوره‌ای واحدهای سنگ‌شکن و آسیاب سیمان طبق تقویم '
                 'پیش‌بینی‌شده انجام می‌شود. همکاری واحد بهره‌برداری در فراهم‌سازی شرایط '
                 'ایمن و توقف کوتاه‌مدت تجهیز، الزامی است.'),
        'expiry': datetime.date(2026, 12, 31),
        'expires_label': 'اعتبار تا پایان آذر ۱۴۰۵',
    },
    {
        'enabled': True,
        'type': 'danger',
        'title': 'هشدار بحرانی',
        'text': ('در صورت مشاهده ارتعاش بالاتر از <b>۷/۱ mm/s</b> در هر یک از نقاط اندازه‌گیری، '
                 'موضوع بلافاصله به دفتر فنی گزارش شود و تجهیز تا بررسی کارشناسی '
                 'در وضعیت پایش لحظه‌ای قرار گیرد.'),
        'expiry': None,
        'expires_label': 'دائمی',
    },
    {
        'enabled': False,
        'type': 'success',
        'title': 'نمونه اعلامیه خاموش‌شده',
        'text': 'این اعلامیه به‌صورت موقت غیرفعال شده است. برای نمایش، مقدار enabled را True کن.',
        'expiry': datetime.date(2026, 12, 31),
        'expires_label': 'نمونه آموزشی',
    },
]


def render_announcements(announcements):
    today = datetime.date.today()
    shown = 0
    for ann in announcements:
        if not ann.get('enabled', True):
            continue
        expiry = ann.get('expiry')
        if expiry is not None and today > expiry:
            continue

        style = ANNOUNCEMENT_STYLES.get(ann.get('type', 'info'), ANNOUNCEMENT_STYLES['info'])
        icon = style['icon']
        label = ann.get('expires_label', '')
        footer = (
            f"<div style='margin-top:10px; font-size:13px; color:{style['title']}; opacity:0.85;'>"
            f"🗓️ {label}</div>"
        ) if label else ''

        st.markdown(f'''
<div style="background-color:{style['bg']}; border-right:8px solid {style['border']};
            padding:16px 24px; border-radius:12px; margin-bottom:14px; direction:rtl;
            text-align:right; font-family:Tahoma; box-shadow:0 4px 12px rgba(0,0,0,0.06);">
    <h3 style="color:{style['title']}; margin:0 0 10px 0; font-size:20px;">{icon} {ann['title']}</h3>
    <div style="color:#333; font-size:17px; line-height:1.7;">{ann['text']}</div>
    {footer}
</div>
''', unsafe_allow_html=True)
        shown += 1
    return shown


# ==============================================================================
# 4. هدر و اعلامیه‌ها
# ==============================================================================
logo_siman = get_image_base64('client_logo.png')
logo_faz = get_image_base64('my_logo.png')

st.markdown(f'''
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;
            background:white; padding:15px 30px; border-radius:15px; box-shadow:0 4px 8px rgba(0,0,0,0.1);">
    <img src="data:image/png;base64,{logo_faz}" style="width:110px; height:auto;">
    <div style="text-align:center; color:#1E3A8D; font-size:26px; font-weight:bold; font-family:Tahoma;">
        🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران
    </div>
    <img src="data:image/png;base64,{logo_siman}" style="width:110px; height:auto;">
</div>
''', unsafe_allow_html=True)

render_announcements(ANNOUNCEMENTS)

# ==============================================================================
# 5. بارگذاری داده‌ها
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
        st.error(f'❌ خطا در بارگذاری شیت ارتعاشات: {e}')
    try:
        df_assets = pd.read_csv(ASSETS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception as e:
        st.warning(f'⚠️ خطا در بارگذاری شیت Assets: {e}')
    return df_vib, df_assets


df, df_assets = load_all_data()

# ==============================================================================
# 6. فیلترها
# ==============================================================================
st.sidebar.header('🔍 فیلترهای پیشرفته')

if not df.empty:
    col_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
    col_unit = smart_find_column(df.columns, ['واحد'])
    equip_col = smart_find_column(df.columns, ['نام تجهیز', 'تجهیز', 'Equipment', 'Asset', 'عنوان تجهیز'])
    date_col = smart_find_column(df.columns, ['تاریخ', 'Date'])

    df['_k_line'] = df[col_line].apply(norm) if col_line else ''
    df['_k_unit'] = df[col_unit].apply(norm) if col_unit else ''
    df['_k_eq'] = df[equip_col].apply(norm) if equip_col else ''
    df['_k_date'] = df[date_col].apply(norm) if date_col else ''

    def display_map(key_col, original_col):
        if original_col is None:
            return {}
        tmp = df[df[key_col] != '']
        if tmp.empty:
            return {}
        return tmp.groupby(key_col)[original_col].agg(
            lambda s: s.str.strip().value_counts().idxmax()
        ).to_dict()

    line_map = display_map('_k_line', col_line)
    unit_map = display_map('_k_unit', col_unit)
    eq_map = display_map('_k_eq', equip_col)

    sel_line_k = st.sidebar.selectbox(
        '📍 خط تولید:', ['همه'] + sorted(line_map.keys()),
        format_func=lambda k: 'همه' if k == 'همه' else line_map.get(k, k))

    tmp = df.copy()
    if sel_line_k != 'همه':
        tmp = tmp[tmp['_k_line'] == sel_line_k]
    unit_keys = sorted([u for u in tmp['_k_unit'].unique() if u != ''])
    sel_unit_k = st.sidebar.selectbox(
        '🏢 واحد:', ['همه'] + unit_keys,
        format_func=lambda k: 'همه' if k == 'همه' else unit_map.get(k, k))

    if sel_unit_k != 'همه':
        tmp = tmp[tmp['_k_unit'] == sel_unit_k]
    eq_keys = sorted([e for e in tmp['_k_eq'].unique() if e != ''])
    sel_eq_k = st.sidebar.selectbox(
        '⚙️ انتخاب تجهیز:', ['همه تجهیزات'] + eq_keys,
        format_func=lambda k: 'همه تجهیزات' if k == 'همه تجهیزات' else eq_map.get(k, k))

    search_eq = st.sidebar.text_input('🔎 جستجوی سریع:')
    date_search = st.sidebar.text_input('جستجوی تاریخ (مثلاً ۱۴۰۵/۰۸):')

    date_map = {}
    if date_col:
        tmp_d = df[df['_k_date'] != '']
        if not tmp_d.empty:
            date_map = tmp_d.groupby('_k_date')[date_col].agg(
                lambda s: s.str.strip().value_counts().idxmax()).to_dict()
    sel_date_k = st.sidebar.selectbox(
        '🌙 انتخاب تاریخ:', ['همه تاریخ‌ها'] + sorted(list(date_map.keys()), reverse=True),
        format_func=lambda k: 'همه تاریخ‌ها' if k == 'همه تاریخ‌ها' else date_map.get(k, k))

    fdf = df.copy()
    if sel_line_k != 'همه':
        fdf = fdf[fdf['_k_line'] == sel_line_k]
    if sel_unit_k != 'همه':
        fdf = fdf[fdf['_k_unit'] == sel_unit_k]
    if sel_eq_k != 'همه تجهیزات':
        fdf = fdf[fdf['_k_eq'] == sel_eq_k]
    if search_eq.strip():
        q = norm(search_eq)
        fdf = fdf[fdf['_k_eq'].apply(lambda x: all(t in x for t in q.split() if t))]
    if date_search.strip():
        fdf = fdf[fdf['_k_date'].str.contains(norm(date_search), na=False)]
    if sel_date_k != 'همه تاریخ‌ها':
        fdf = fdf[fdf['_k_date'] == sel_date_k]
    if date_col:
        fdf = fdf.sort_values(by=date_col, ascending=False)

    # ==========================================================================
    # 7. نمایش محتوا
    # ==========================================================================
    st.title('📊 تحلیل روند ارتعاشات تجهیزات')

    # --- 7-1 کارت مشخصات فنی -------------------------------------------------
    if sel_eq_k != 'همه تجهیزات':
        eq_display = eq_map.get(sel_eq_k, sel_eq_k)
        matched = False

        if not df_assets.empty:
            a_name = smart_find_column(df_assets.columns, ['نام تجهیز', 'نام', 'تجهیز', 'Asset'])
            if a_name:
                norm_assets = df_assets[a_name].apply(norm)
                rows = df_assets[norm_assets == sel_eq_k]
                if rows.empty:
                    rows = df_assets[norm_assets.apply(
                        lambda x: x != '' and (sel_eq_k in x or x in sel_eq_k))]

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
                    e_rpm = gv(['دور', 'RPM', 'سرعت'])
                    e_unit = gv(['واحد'])
                    e_line = gv(['خط تولید', 'خط'])
                    e_drive = gv(['نوع انتقال', 'انتقال قدرت', 'سیستم انتقال',
                                  'کوپلینگ', 'کوپل', 'اتصال', 'درایو'])
                    e_brg = gv(['شماره بیرینگ', 'بیرینگ', 'برینگ', 'Bearing'])
                    e_bush = gv(['شماره بوش', 'بوش', 'Bush'])

                    st.markdown(f'''
<div style="background:#f0f7ff; padding:20px 24px; border-radius:15px;
            border-right:10px solid #1E3A8D; margin-bottom:18px; text-align:right;
            direction:rtl; box-shadow:2px 2px 8px rgba(0,0,0,0.06);">
    <h3 style="color:#1E3A8D; margin:0 0 14px 0; font-family:Tahoma;">🛠️ مشخصات فنی: {eq_display}</h3>
    <div style="display:flex; flex-wrap:wrap; gap:10px 26px; font-size:16px; color:#333; font-family:Tahoma;">
        <span><b style="color:#1E3A8D;">🔹 نوع تجهیز:</b> {e_type}</span>
        <span><b style="color:#1E3A8D;">🔹 دور:</b> {e_rpm} RPM</span>
        <span><b style="color:#1E3A8D;">🔹 خط تولید:</b> {e_line}</span>
        <span><b style="color:#1E3A8D;">🔹 واحد:</b> {e_unit}</span>
        <span><b style="color:#1E3A8D;">🔹 نوع انتقال قدرت:</b> {e_drive}</span>
    </div>
    <div style="display:flex; flex-wrap:wrap; gap:10px 26px; font-size:16px; color:#333;
                margin-top:10px; font-family:Tahoma;">
        <span><b style="color:#1E3A8D;">🧩 شماره بیرینگ:</b> {e_brg}</span>
        <span><b style="color:#1E3A8D;">🧩 شماره بوش:</b> {e_bush}</span>
    </div>
    <div style="margin-top:14px; font-size:15px; color:#1E3A8D; background:#e6efff;
                padding:8px 15px; border-radius:8px; display:inline-block; font-family:Tahoma;">
        <b>📍 راهنمای نقاط (P-Map):</b> {get_point_guide(eq_display, e_type)}
    </div>
</div>
''', unsafe_allow_html=True)

                    pts = smart_find_column(df_assets.columns, ['نقطه', 'پوینت', 'Point'])
                    brg = smart_find_column(df_assets.columns, ['بیرینگ', 'برینگ', 'Bearing'])
                    bsh = smart_find_column(df_assets.columns, ['بوش', 'Bush'])
                    log_cols = [c for c in [pts, brg, bsh] if c]
                    if log_cols:
                        rename = {}
                        if pts:
                            rename[pts] = 'نقطه اندازه‌گیری'
                        if brg:
                            rename[brg] = 'شماره بیرینگ'
                        if bsh:
                            rename[bsh] = 'شماره بوش'
                        logistics = rows[log_cols].rename(columns=rename)
                        logistics = logistics.replace({'': '---', 'nan': '---', 'None': '---'})
                        with st.expander('📦 اطلاعات قطعات و لجستیک (بیرینگ / بوش)', expanded=True):
                            st.dataframe(logistics, hide_index=True, use_container_width=True)

                    with st.expander('📋 مشاهده تمام مشخصات ثبت‌شده این تجهیز', expanded=False):
                        full = pd.DataFrame({
                            'عنوان': df_assets.columns,
                            'مقدار': [str(x).strip() for x in r0.values],
                        })
                        full = full[~full['مقدار'].isin(['', 'nan', 'None', 'NaN'])]
                        st.dataframe(full, hide_index=True, use_container_width=True)

        if not matched:
            st.info('ℹ️ برای این تجهیز، ردیفی در شیت Assets پیدا نشد. (نام تجهیز در دو شیت باید یکسان باشد.)')

    # --- 7-2 جدول ارتعاشات ---------------------------------------------------
    if not fdf.empty:
        vis_cols = [c for c in fdf.columns if not str(c).startswith('_k_')]
        v_cols = [c for c in vis_cols if any(k in str(c) for k in ['عمودی', 'افقی', 'محوری'])]

        st.markdown(f'### 📋 داده‌های ارتعاشات ({len(fdf)} مورد)')

        def color_v(v):
            try:
                val = float(str(v).replace('٫', '.').replace('،', '.').replace(',', '.').strip())
            except Exception:
                return ''
            if val > 7.1:
                return 'background-color:#ff4b4b; color:white'
            if val > 4.5:
                return 'background-color:#ffa500; color:white'
            return 'background-color:#2e7d32; color:white'

        table = fdf[vis_cols].copy()
        if v_cols:
            try:
                styled = table.style.map(color_v, subset=v_cols)
            except AttributeError:
                styled = table.style.applymap(color_v, subset=v_cols)
            st.dataframe(styled, use_container_width=True, hide_index=True)
        else:
            st.dataframe(table, use_container_width=True, hide_index=True)

        # --- 7-3 نمودار دایره‌ای (انتهای صفحه) --------------------------------
        st.markdown('---')
        with st.expander('📈 تحلیل وضعیت سلامت (نمودار دایره‌ای)', expanded=False):
            if v_cols:
                v_max = fdf[v_cols].apply(to_num, axis=0).max(axis=1)

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
                    fig = px.pie(
                        values=status.values, names=status.index, color=status.index,
                        color_discrete_map={'سالم': '#2e7d32', 'هشدار': '#ffa500',
                                            'بحرانی': '#ff4b4b', 'نامشخص': '#9e9e9e'},
                        hole=0.35)
                    fig.update_traces(textinfo='percent+label')
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption('معیار: بیشینه ارتعاش هر ردیف — سالم ≤ ۴/۵ | هشدار ۴/۵ تا ۷/۱ | بحرانی > ۷/۱ (mm/s)')
                else:
                    st.info('داده عددی معتبری برای تحلیل وجود ندارد.')
            else:
                st.info('ستون‌های ارتعاشات (عمودی/افقی/محوری) پیدا نشد.')
    else:
        st.warning('⚠️ هیچ داده‌ای با این فیلترها پیدا نشد.')

    st.markdown(
        '<div style="text-align:center; margin-top:50px; color:#555; font-family:Tahoma;">'
        'طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>',
        unsafe_allow_html=True)
else:
    st.error('❌ خطا در دریافت داده‌ها.')
