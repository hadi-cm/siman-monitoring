import re
import datetime
import pandas as pd
import streamlit as st
import base64
import plotly.express as px

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
# 2. توابع کمکی
# ==============================================================================
FA_DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')


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
    s = s.replace('ي', 'ی').replace('ى', 'ی').replace('ك', 'ک').replace('ۀ', 'ه').replace('ة', 'ه')
    s = s.replace('\u200c', ' ').replace('\xa0', ' ')
    s = s.replace('-', ' ').replace('_', ' ')
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


def jalali_to_gregorian(jy, jm, jd):
    """تبدیل تاریخ شمسی به میلادی (الگوریتم استاندارد jalaali)"""
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    sal_a = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    return gy, gm, gd


def parse_date(value):
    """تاریخ شمسی یا میلادی را به آبجکت date تبدیل می‌کند. خالی بودن ⇒ None"""
    if value is None:
        return None
    s = str(value).strip().translate(FA_DIGITS)
    if s in ('', 'nan', 'None', 'NaN', '-', '---'):
        return None
    nums = re.findall(r'\d+', s)
    if len(nums) < 3:
        return None
    try:
        y, m, d = int(nums[0]), int(nums[1]), int(nums[2])
    except Exception:
        return None
    if y > 1500:  # میلادی
        try:
            return datetime.date(y, m, d)
        except Exception:
            return None
    try:
        gy, gm, gd = jalali_to_gregorian(y, m, d)
        return datetime.date(gy, gm, gd)
    except Exception:
        return None


def get_point_guide(eq_name, eq_type=''):
    name = norm(eq_name) + ' ' + norm(eq_type)
    if 'گیربکس' in name:
        return 'P1: انتهای موتور | P2: جلوی موتور | P3: محور ورودی گیربکس | P4: سمت آزاد محور ورودی | P5: سمت فیکس محور دوم | P6: سمت آزاد محور دوم | P7: سمت فیکس محور سوم | P8: سمت آزاد محور سوم | P9: بابیت اول سمت گیربکس | P10: بابیت دوم | P11: بابیت نزدیک پینیون آسیاب'
    if 'کراشر' in name or 'سنگ شکن' in name:
        return 'P1: انتهای موتور | P2: سر موتور | P3: یاتاقان سمت فیکس (پولی کوچک) | P4: یاتاقان سمت آزاد (پولی کوچک) | P5: یاتاقان فیکس (روتور) | P6: یاتاقان سمت آزاد (روتور)'
    if 'فن' in name:
        return 'P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس | P4: یاتاقان آزاد'
    return 'راهنمای نقاط تعریف نشده است.'

# ==============================================================================
# 3. سیستم اعلامیه‌ها بر پایه گوگل شیت (مرکز کنترل)
# ==============================================================================
SHEET_ID = '1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs'
BASE_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid='

VIB_GID = '0'
ASSETS_GID = '1276803564'
ANNOUNCEMENTS_GID = '2057447521'   # تب اعلانیه‌ها

VIB_URL = BASE_URL + VIB_GID
ASSETS_URL = BASE_URL + ASSETS_GID
ANNOUNCEMENTS_URL = BASE_URL + ANNOUNCEMENTS_GID

# استایل و آیکون هر نوع اعلامیه
ANNOUNCEMENT_STYLES = {
    'warning': {'icon': '⚠️', 'bg': '#fff3cd', 'border': '#ffc107', 'head': '#856404', 'body': '#6b5200'},
    'info':    {'icon': 'ℹ️', 'bg': '#e1f5fe', 'border': '#03a9f4', 'head': '#01579b', 'body': '#0d3c5c'},
    'danger':  {'icon': '🚨', 'bg': '#ffebee', 'border': '#e53935', 'head': '#b71c1c', 'body': '#7f1010'},
    'success': {'icon': '✅', 'bg': '#e8f5e9', 'border': '#43a047', 'head': '#1b5e20', 'body': '#14471a'},
}

TYPE_ALIASES = {
    'هشدار': 'warning', 'اخطار': 'warning', 'warning': 'warning', 'warn': 'warning',
    'اطلاعیه': 'info', 'اطلاع': 'info', 'اطلاع رسانی': 'info', 'info': 'info', 'notice': 'info',
    'خطر': 'danger', 'بحرانی': 'danger', 'critical': 'danger', 'danger': 'danger',
    'موفق': 'success', 'انجام شده': 'success', 'تایید': 'success', 'success': 'success',
}


def resolve_type(value):
    k = norm(value)
    for alias, real in TYPE_ALIASES.items():
        if norm(alias) == k:
            return real
    for alias, real in TYPE_ALIASES.items():
        if norm(alias) and norm(alias) in k:
            return real
    return 'info'


def is_active(value):
    k = norm(value)
    if k == '':
        return True
    return k not in ('خیر', 'نه', 'غیر فعال', 'غیرفعال', 'no', 'false', '0', 'off')


@st.cache_data(ttl=600)
def load_all_data():
    df_vib, df_assets, df_ann = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        df_vib = pd.read_csv(VIB_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception as e:
        st.error(f"❌ خطا در خواندن شیت ارتعاشات: {e}")
    try:
        df_assets = pd.read_csv(ASSETS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception as e:
        st.warning(f"⚠️ شیت مشخصات فنی (Assets) بارگذاری نشد. ({e})")
    try:
        df_ann = pd.read_csv(ANNOUNCEMENTS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception as e:
        st.warning(f"⚠️ شیت اعلانیه‌ها بارگذاری نشد. ({e})")
    return df_vib, df_assets, df_ann


def build_announcements(df_ann):
    items = []
    if df_ann is None or df_ann.empty:
        return items

    c_title = smart_find_column(df_ann.columns, ['عنوان', 'تیتر', 'موضوع', 'title'])
    c_text = smart_find_column(df_ann.columns, ['متن', 'توضیح', 'شرح', 'محتوا', 'text'])
    c_type = smart_find_column(df_ann.columns, ['نوع', 'دسته', 'type'])
    c_act = smart_find_column(df_ann.columns, ['فعال', 'وضعیت', 'نمایش', 'enabled'])
    c_start = smart_find_column(df_ann.columns, ['تاریخ شروع', 'شروع', 'از تاریخ', 'start'])
    c_end = smart_find_column(df_ann.columns, ['تاریخ انقضا', 'انقضا', 'پایان', 'تا تاریخ', 'expiry'])
    c_label = smart_find_column(df_ann.columns, ['برچسب', 'یادداشت', 'label'])

    today = datetime.date.today()

    for _, row in df_ann.iterrows():
        title = str(row[c_title]).strip() if c_title else ''
        text = str(row[c_text]).strip() if c_text else ''
        if title == '' and text == '':
            continue
        if c_act and not is_active(row[c_act]):
            continue

        start = parse_date(row[c_start]) if c_start else None
        end = parse_date(row[c_end]) if c_end else None
        if start and today < start:
            continue
        if end and today > end:
            continue

        atype = resolve_type(row[c_type]) if c_type else 'info'
        label = str(row[c_label]).strip() if c_label else ''
        if label in ('nan', 'None', '-'):
            label = ''

        items.append({'title': title or 'اطلاعیه', 'text': text, 'type': atype, 'label': label})

    return items


df, df_assets, df_ann = load_all_data()
announcements = build_announcements(df_ann)

# ==============================================================================
# 4. هدر
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
# 5. نمایش اعلانیه‌ها (بالای صفحه، قبل از هر چیز دیگر)
# ==============================================================================
if announcements:
    for ann in announcements:
        sty = ANNOUNCEMENT_STYLES.get(ann['type'], ANNOUNCEMENT_STYLES['info'])
        label_html = f"<div style='margin-top:12px; font-size:13px; background:rgba(255,255,255,0.75); padding:5px 12px; border-radius:8px; display:inline-block;'>🗓️ {ann['label']}</div>" if ann['label'] else ''
        st.markdown(f'''
        <div style="background-color:{sty['bg']}; border-right:8px solid {sty['border']}; padding:16px 26px; border-radius:12px; margin-bottom:15px; direction:rtl; text-align:right; font-family:Tahoma; box-shadow:0 4px 12px rgba(0,0,0,0.06);">
            <h3 style="color:{sty['head']}; margin:0 0 8px 0; font-size:20px;">{sty['icon']} {ann['title']}</h3>
            <div style="color:{sty['body']}; font-size:17px; line-height:1.8;">{ann['text']}</div>
            {label_html}
        </div>
        ''', unsafe_allow_html=True)

# ==============================================================================
# 6. فیلترها (سایدبار)
# ==============================================================================
st.sidebar.header("🔍 فیلترهای پیشرفته")

if st.sidebar.button("🔄 بروزرسانی داده‌ها"):
    st.cache_data.clear()
    st.rerun()

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
        return tmp.groupby(key_col)[original_col].agg(lambda s: s.str.strip().value_counts().idxmax()).to_dict()

    line_map = display_map('_k_line', col_line)
    unit_map = display_map('_k_unit', col_unit)
    eq_map = display_map('_k_eq', equip_col)

    lines = sorted(line_map.keys())
    sel_line_k = st.sidebar.selectbox("📍 خط تولید:", ["همه"] + lines,
                                      format_func=lambda k: "همه" if k == "همه" else line_map.get(k, k))

    tmp = df.copy()
    if sel_line_k != "همه":
        tmp = tmp[tmp['_k_line'] == sel_line_k]
    unit_keys = sorted([u for u in tmp['_k_unit'].unique() if u != ''])
    sel_unit_k = st.sidebar.selectbox("🏢 واحد:", ["همه"] + unit_keys,
                                      format_func=lambda k: "همه" if k == "همه" else unit_map.get(k, k))

    if sel_unit_k != "همه":
        tmp = tmp[tmp['_k_unit'] == sel_unit_k]
    eq_keys = sorted([e for e in tmp['_k_eq'].unique() if e != ''])
    sel_eq_k = st.sidebar.selectbox("⚙️ انتخاب تجهیز:", ["همه تجهیزات"] + eq_keys,
                                    format_func=lambda k: "همه تجهیزات" if k == "همه تجهیزات" else eq_map.get(k, k))

    search_eq = st.sidebar.text_input("🔎 جستجوی سریع تجهیز:", placeholder="مثلاً: میل فن")
    st.sidebar.markdown("**📅 فیلتر تاریخ**")
    date_search = st.sidebar.text_input("جستجوی تاریخ (مثلاً ۱۴۰۵/۰۸):")

    date_map = {}
    if date_col:
        tmp_d = df[df['_k_date'] != '']
        date_map = tmp_d.groupby('_k_date')[date_col].agg(lambda s: s.str.strip().value_counts().idxmax()).to_dict()
    date_keys = sorted(list(date_map.keys()), reverse=True)
    sel_date_k = st.sidebar.selectbox("🌙 انتخاب تاریخ:", ["همه تاریخ‌ها"] + date_keys,
                                      format_func=lambda k: "همه تاریخ‌ها" if k == "همه تاریخ‌ها" else date_map.get(k, k))

    fdf = df.copy()
    if sel_line_k != "همه":
        fdf = fdf[fdf['_k_line'] == sel_line_k]
    if sel_unit_k != "همه":
        fdf = fdf[fdf['_k_unit'] == sel_unit_k]
    if sel_eq_k != "همه تجهیزات":
        fdf = fdf[fdf['_k_eq'] == sel_eq_k]
    if search_eq.strip():
        q = norm(search_eq)
        mask = fdf['_k_eq'].apply(lambda x: all(t in x for t in q.split() if t))
        if mask.any():
            fdf = fdf[mask]
    if date_search.strip():
        fdf = fdf[fdf['_k_date'].str.contains(norm(date_search), na=False)]
    if sel_date_k != "همه تاریخ‌ها":
        fdf = fdf[fdf['_k_date'] == sel_date_k]

    if date_col:
        fdf = fdf.sort_values(by=date_col, ascending=False)

    # ==============================================================================
    # 7. نمایش محتوا
    # ==============================================================================
    st.markdown('<style>.main .block-container { padding-right:1rem; padding-left:1rem; }</style>', unsafe_allow_html=True)
    st.title("📊 تحلیل روند ارتعاشات تجهیزات")

    if sel_eq_k != "همه تجهیزات":
        eq_display = eq_map.get(sel_eq_k, sel_eq_k)
        matched = False
        if not df_assets.empty:
            a_name = smart_find_column(df_assets.columns, ['نام تجهیز', 'نام', 'تجهیز', 'Asset'])
            if a_name:
                norm_assets = df_assets[a_name].apply(norm)
                rows = df_assets[norm_assets == sel_eq_k]
                if rows.empty:
                    rows = df_assets[norm_assets.apply(lambda x: x != '' and (sel_eq_k in x or x in sel_eq_k))]
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
                    e_drive = gv(['نوع انتقال', 'انتقال قدرت', 'سیستم انتقال', 'کوپلینگ', 'کوپل', 'اتصال', 'درایو'])
                    e_brg = gv(['شماره بیرینگ', 'بیرینگ', 'برینگ', 'Bearing'])
                    e_bush = gv(['شماره بوش', 'بوش', 'Bush'])

                    st.markdown(f'''
                    <div style='background:#f0f7ff; padding:20px 24px; border-radius:15px; border-right:10px solid #1E3A8D; margin-bottom:18px; text-align:right; direction:rtl; box-shadow:2px 2px 8px rgba(0,0,0,0.06);'>
                        <h3 style='color:#1E3A8D; margin:0 0 14px 0; font-family:Tahoma;'>🛠️ مشخصات فنی: {eq_display}</h3>
                        <div style='display:flex; flex-wrap:wrap; gap:10px 28px; font-size:16px; color:#333; font-family:Tahoma;'>
                            <span><b style='color:#1E3A8D;'>🔹 نوع تجهیز:</b> {e_type}</span>
                            <span><b style='color:#1E3A8D;'>🔹 دور:</b> {e_rpm} RPM</span>
                            <span><b style='color:#1E3A8D;'>🔹 خط تولید:</b> {e_line}</span>
                            <span><b style='color:#1E3A8D;'>🔹 واحد:</b> {e_unit}</span>
                            <span><b style='color:#1E3A8D;'>🔹 نوع انتقال قدرت:</b> {e_drive}</span>
                        </div>
                        <div style='display:flex; flex-wrap:wrap; gap:10px 28px; font-size:16px; color:#333; margin-top:10px; font-family:Tahoma;'>
                            <span><b style='color:#1E3A8D;'>🧩 شماره بیرینگ:</b> {e_brg}</span>
                            <span><b style='color:#1E3A8D;'>🧩 شماره بوش:</b> {e_bush}</span>
                        </div>
                        <div style='margin-top:14px; font-size:15px; color:#1E3A8D; background:#e6efff; padding:8px 15px; border-radius:8px; display:inline-block; font-family:Tahoma;'>
                            <b style='font-family:Tahoma;'>📍 راهنمای نقاط (P-Map):</b> {get_point_guide(eq_display, e_type)}
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)

                    pts = smart_find_column(df_assets.columns, ['نقطه', 'پوینت', 'Point'])
                    brg = smart_find_column(df_assets.columns, ['بیرینگ', 'برینگ', 'Bearing'])
                    bsh = smart_find_column(df_assets.columns, ['بوش', 'Bush'])
                    log_cols = [c for c in [pts, brg, bsh] if c]
                    if log_cols:
                        with st.expander('📦 اطلاعات قطعات و لجستیک (بیرینگ / بوش)', expanded=True):
                            st.dataframe(rows[log_cols], hide_index=True, use_container_width=True)

                    with st.expander('📋 مشاهده تمام مشخصات ثبت‌شده این تجهیز', expanded=False):
                        full = pd.DataFrame({'عنوان': df_assets.columns, 'مقدار': [str(x).strip() for x in r0.values]})
                        full = full[~full['مقدار'].isin(['', 'nan', 'None', 'NaN'])]
                        st.dataframe(full, hide_index=True, use_container_width=True)

        if not matched:
            st.info("ℹ️ برای این تجهیز، ردیف مشخصاتی در شیت Assets پیدا نشد.")

    if not fdf.empty:
        visible_cols = [c for c in fdf.columns if not str(c).startswith('_k_')]
        vib_cols = [c for c in visible_cols if any(k in str(c) for k in ['عمودی', 'افقی', 'محوری'])]
        st.markdown(f"### 📋 داده‌های ارتعاشات ({len(fdf)} مورد)")

        def color_vib(val):
            try:
                v = float(str(val).replace('٫', '.').replace('،', '.').replace(',', '.').strip())
                if v > 7.1:
                    return 'background-color:#ff4b4b; color:white'
                elif v > 4.5:
                    return 'background-color:#ffa500; color:white'
                else:
                    return 'background-color:#2e7d32; color:white'
            except Exception:
                return ''

        if vib_cols:
            st.dataframe(fdf[visible_cols].style.map(color_vib, subset=vib_cols), use_container_width=True, hide_index=True)
        else:
            st.dataframe(fdf[visible_cols], use_container_width=True, hide_index=True)

        st.markdown("---")
        with st.expander('📈 نمایش تحلیل وضعیت سلامت (نمودار دایره‌ای)', expanded=False):
            if vib_cols:
                v_max = fdf[vib_cols].apply(to_num, axis=0).max(axis=1)

                def cat(v):
                    if pd.isna(v):
                        return 'نامشخص'
                    return 'بحرانی' if v > 7.1 else 'هشدار' if v > 4.5 else 'سالم'

                status = v_max.map(cat).value_counts()
                if not status.empty:
                    fig = px.pie(values=status.values, names=status.index, color=status.index,
                                 color_discrete_map={'سالم': '#2e7d32', 'هشدار': '#ffa500', 'بحرانی': '#ff4b4b', 'نامشخص': '#9e9e9e'},
                                 hole=0.35)
                    st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("⚠️ هیچ داده‌ای با این فیلترها پیدا نشد.")

    st.markdown('<div style="text-align:center; margin-top:50px; color:#555; font-family:Tahoma;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>', unsafe_allow_html=True)
else:
    st.error("❌ خطا در دریافت داده‌ها.")
