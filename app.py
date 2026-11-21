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
# 2. توابع کمکی
# ==============================================================================
FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'
EN_DIGITS = '0123456789'


def norm(x):
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
    s = (s.replace('\u200c', ' ').replace('\xa0', ' ')
          .replace('-', ' ').replace('_', ' ').replace('.', ' '))
    return ' '.join(s.split()).lower()


def clean_num_text(x):
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
    s = s.replace({'': None, 'nan': None, 'None': None, '---': None,
                   'NaN': None, 'null': None})
    return pd.to_numeric(s, errors='coerce')


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
            if normed[c] == nk:
                return c
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if nk and nk in normed[c]:
                return c
    return None


def date_sort_key(val):
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


# ------------------------------------------------------------------------------
# تشخیص نوع تجهیز و نقشه نقاط
# ------------------------------------------------------------------------------
def detect_equipment_family(eq_name, eq_type=''):
    name = norm(eq_name) + ' ' + norm(eq_type)
    # ترتیب مهم است: خاص‌ترها اول
    if 'کراشر' in name or 'سنگ شکن' in name or 'crusher' in name:
        return 'crusher'
    if 'گیربکس' in name or 'gearbox' in name or 'gear box' in name:
        # گیربکس سمت کوه (آسیاب) نقاط بیشتری دارد
        if ('کوه' in name) or ('اسیاب' in name) or ('آسیاب' in name) or ('mill' in name):
            return 'gearbox_mill'
        return 'gearbox'
    if 'بلوئر' in name or 'blower' in name:
        return 'blower'
    if 'کمپرسور' in name or 'compressor' in name:
        return 'compressor'
    if 'فن' in name or 'fan' in name:
        return 'fan'
    return 'generic'


POINT_MAPS = {
    'fan': [
        ('P1', 'انتهای موتور'),
        ('P2', 'سر موتور'),
        ('P3', 'یاتاقان فیکس'),
        ('P4', 'یاتاقان آزاد'),
    ],
    'blower': [
        ('P1', 'انتهای موتور'),
        ('P2', 'سر موتور'),
        ('P3', 'محور ورود بلوئر'),
        ('P4', 'انتهای بلوئر'),
    ],
    'compressor': [
        ('P1', 'انتهای موتور'),
        ('P2', 'سر موتور'),
        ('P3', 'سر ایرند'),
        ('P4', 'انتهای ایرند'),
    ],
    'gearbox': [
        ('P1', 'انتهای موتور'),
        ('P2', 'سر موتور'),
        ('P3', 'محور ورود گیربکس'),
        ('P4', 'محور خروج گیربکس'),
    ],
    'gearbox_mill': [
        ('P1', 'انتهای موتور'),
        ('P2', 'سر موتور'),
        ('P3', 'محور ورودی (سمت فیکس پینیون)'),
        ('P4', 'انتهای سمت آزاد پینیون'),
        ('P5', 'محور دوم سمت فیکس'),
        ('P6', 'سمت آزاد محور دوم'),
        ('P7', 'سمت فیکس محور سوم'),
        ('P8', 'سمت آزاد محور سوم'),
        ('P9', 'بابیت سمت گیربکس'),
        ('P10', 'بابیت وسط'),
        ('P11', 'بابیت سمت پینیون آسیاب'),
    ],
    'crusher': [
        ('P1', 'انتهای موتور'),
        ('P2', 'سر موتور'),
        ('P3', 'یاتاقان سمت فیکس (پولی کوچک)'),
        ('P4', 'یاتاقان سمت آزاد (پولی کوچک)'),
        ('P5', 'یاتاقان فیکس (روتور)'),
        ('P6', 'یاتاقان سمت آزاد (روتور)'),
    ],
    'generic': [
        ('P1', 'نقطه ۱'),
        ('P2', 'نقطه ۲'),
        ('P3', 'نقطه ۳'),
        ('P4', 'نقطه ۴'),
    ],
}


def get_point_map(eq_name, eq_type=''):
    return POINT_MAPS.get(detect_equipment_family(eq_name, eq_type), POINT_MAPS['generic'])


# ------------------------------------------------------------------------------
# ترتیب عددی نقاط P1..P11
# ------------------------------------------------------------------------------
def point_index(col_name):
    """شماره نقطه را از نام ستون بیرون می‌کشد. اگر ستون نقطه نباشد None."""
    if col_name is None:
        return None
    raw = str(col_name).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        raw = raw.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        raw = raw.replace(a, e)
    raw_up = raw.upper()
    m = re.search(r'\bP\s*[-_]?\s*(\d{1,2})\b', raw_up)
    if m:
        return int(m.group(1))
    n = norm(raw)
    m = re.search(r'(?:^|\s)(?:پی|نقطه|point|p)\s*(\d{1,2})(?:\s|$)', n)
    if m:
        return int(m.group(1))
    return None


def order_points(cols):
    """ستون‌های نقطه را بر اساس شماره عددی مرتب می‌کند."""
    indexed, others = [], []
    for i, c in enumerate(cols):
        idx = point_index(c)
        if idx is None:
            others.append((i, c))
        else:
            indexed.append((idx, i, c))
    indexed.sort(key=lambda t: (t[0], t[1]))
    return [c for _, _, c in indexed] + [c for _, c in others]


def natural_key(s):
    return [int(t) if t.isdigit() else norm(t)
            for t in re.split(r'(\d+)', str(s))]


# ==============================================================================
# 3. بارگذاری داده‌ها
# ==============================================================================
VIB_URL = ('https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/'
           'export?format=csv&gid=0')
ASSETS_URL = ('https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/'
              'export?format=csv&gid=1276803564')
ANN_URL = ('https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/'
           'export?format=csv&gid=2057447521')


@st.cache_data(ttl=600)
def load_all_data():
    df_vib, df_assets, df_ann = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        df_vib = pd.read_csv(VIB_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception:
        pass
    try:
        df_assets = pd.read_csv(ASSETS_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception:
        pass
    try:
        df_ann = pd.read_csv(ANN_URL, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    except Exception:
        pass
    return df_vib, df_assets, df_ann


df_raw, df_assets, df_ann = load_all_data()

# ==============================================================================
# 4. هدر
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
# 5. اعلانیه‌ها (از شیت جداگانه gid=2057447521)
# ==============================================================================
ANN_STYLES = {
    'error': ('#d32f2f', '🚨'),
    'warning': ('#f9a825', '⚠️'),
    'success': ('#2e7d32', '✅'),
    'info': ('#1565c0', 'ℹ️'),
}


def classify_announcement(t):
    t = norm(t)
    if any(k in t for k in ['خطر', 'بحرانی', 'اضطراری', 'فوری']):
        return 'error'
    if any(k in t for k in ['هشدار', 'اخطار']):
        return 'warning'
    if any(k in t for k in ['موفق', 'گزارش', 'اطلاعیه', 'اطلاع رسانی']):
        return 'success'
    return 'info'


if not df_ann.empty:
    a_title = smart_find_column(df_ann.columns, ['عنوان'])
    a_text = smart_find_column(df_ann.columns, ['متن'])
    a_type = smart_find_column(df_ann.columns, ['نوع'])
    a_active = smart_find_column(df_ann.columns, ['فعال'])
    a_label = smart_find_column(df_ann.columns, ['برچسب'])
    a_start = smart_find_column(df_ann.columns, ['تاریخ شروع'])
    a_end = smart_find_column(df_ann.columns, ['تاریخ انقضا', 'تاریخ پایان'])

    if a_title and a_text:
        adf = df_ann.copy()
        if a_active:
            adf = adf[adf[a_active].astype(str).map(norm) == 'بله']

        # فیلتر بر اساس ستون تاریخ شروع/انقضا (اگر وجود داشت)
        if a_start:
            s_keys = adf[a_start].map(date_sort_key)
            ak_valid = (s_keys == 0) | (s_keys <= 99999999)  # همیشه true نگه‌داشتن برای امنیت
        if a_start and a_end:
            start_keys = adf[a_start].map(date_sort_key)
            end_keys = adf[a_end].map(date_sort_key)
            today = min(max(start_keys.max() if len(start_keys) else 0, 1), 99999999)

        for _, row in adf.iterrows():
            atype = str(row[a_type]).strip() if a_type else 'اطلاعیه'
            title = str(row[a_title]).strip()
            msg = str(row[a_text]).strip()
            label = str(row[a_label]).strip() if a_label else ''
            kind = classify_announcement(atype)
            color, icon = ANN_STYLES[kind]

            span = ''
            if a_start and a_end:
                s_val = str(row[a_start]).strip()
                e_val = str(row[a_end]).strip()
                if s_val or e_val:
                    span = f'{s_val} → {e_val}'

            badge = (f"<span style='background:rgba(255,255,255,0.25); padding:3px 10px; "
                     f"border-radius:20px; font-size:12px; margin-inline-start:8px; "
                     f"unicode-bidi:isolate;'>{label}</span>") if label else ''

            dates = (f"<div style='font-size:12px; opacity:0.85; margin-top:6px; "
                     f"unicode-bidi:isolate;'>{span}</div>") if span else ''

            st.markdown(f'''
            <div style='background:{color}; padding:14px 18px; border-radius:12px; margin-bottom:10px;
                        color:white; direction:rtl; text-align:right; font-family:Tahoma;
                        box-shadow:0 2px 6px rgba(0,0,0,0.15);'>
                <div style='display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap;'>
                    <b style='font-size:17px;'>{icon} {title}</b>
                    {badge}
                </div>
                <div style='margin-top:6px; font-size:14px; line-height:1.9; opacity:0.95;'>{msg}</div>
                {dates}
            </div>
            ''', unsafe_allow_html=True)

# ==============================================================================
# 6. ادغام هوشمند ردیف‌ها
# ==============================================================================
def first_filled(values):
    """اولین مقدار غیرخالی و غیرصفرمتنی گروه را برمی‌گرداند (بدون خطا روی گروه خالی)."""
    for v in values:
        s = str(v).strip()
        if s and s.lower() not in ('nan', 'none', 'null', '---'):
            return s
    return ''


def consolidate_vib_data(df, mode='full'):
    if df.empty:
        return df

    col_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
    col_unit = smart_find_column(df.columns, ['واحد'])
    equip_col = smart_find_column(df.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'Asset'])
    date_col = smart_find_column(df.columns, ['تاریخ', 'Date'])

    if not all([col_line, col_unit, equip_col, date_col]):
        return df

    df = df.copy()
    df['_k_line'] = df[col_line].map(norm)
    df['_k_unit'] = df[col_unit].map(norm)
    df['_k_eq'] = df[equip_col].map(norm)
    df['_k_date'] = df[date_col].map(norm)
    df['_dkey'] = df[date_col].map(date_sort_key)

    group_cols = ['_k_line', '_k_unit', '_k_eq', '_k_date', '_dkey']

    value_cols = [c for c in df.columns
                  if c not in group_cols and not str(c).startswith('_')]

    if mode == 'full':
        agg_dict = {c: first_filled for c in value_cols}
        new_df = df.groupby(group_cols, as_index=False, dropna=False).agg(agg_dict)
    else:
        # محافظه‌کارانه: فقط اگر در همه ستون‌های نقطه تضاد وجود نداشت ادغام کن
        rows = []
        for keys, grp in df.groupby(group_cols, sort=False, dropna=False):
            if len(grp) == 1:
                rows.append(grp.iloc[0])
                continue
            conflict = False
            for c in value_cols:
                vals = {str(v).strip() for v in grp[c] if str(v).strip()}
                if len(vals) > 1:
                    conflict = True
                    break
            if conflict:
                rows.extend([grp.iloc[i] for i in range(len(grp))])
            else:
                merged = grp.iloc[0].copy()
                for c in value_cols:
                    merged[c] = first_filled(grp[c])
                for gc in group_cols:
                    merged[gc] = keys[group_cols.index(gc)]
                rows.append(merged)
        new_df = pd.DataFrame(rows).reset_index(drop=True) if rows else df.copy()

    return new_df


# ==============================================================================
# 7. سایدبار
# ==============================================================================
st.sidebar.header('🔍 فیلترهای پیشرفته')

merge_mode = st.sidebar.radio(
    '⚙️ روش ادغام ردیف‌های هم‌نام',
    options=['full', 'safe'],
    format_func=lambda v: 'ادغام کامل (توصیه‌شده)' if v == 'full' else 'ادغام محافظه‌کارانه',
    index=0,
)

df = consolidate_vib_data(df_raw, merge_mode)

if not df.empty:
    col_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
    col_unit = smart_find_column(df.columns, ['واحد'])
    equip_col = smart_find_column(df.columns, ['نام تجهیز', 'عنوان تجهیز', 'تجهیز', 'Asset'])
    date_col = smart_find_column(df.columns, ['تاریخ', 'Date'])

    def _mode(series):
        v = series.astype(str).str.strip()
        v = v[v != '']
        return v.value_counts().idxmax() if not v.empty else ''

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

    sel_line_k = st.sidebar.selectbox(
        '📍 خط تولید:',
        ['همه'] + sorted(line_map.keys(), key=lambda k: natural_key(line_map.get(k, k))),
        format_func=lambda k: 'همه' if k == 'همه' else line_map.get(k, k),
    )

    tmp_u = df.copy()
    if sel_line_k != 'همه':
        tmp_u = tmp_u[tmp_u['_k_line'] == sel_line_k]
    unit_keys = sorted([u for u in tmp_u['_k_unit'].unique() if u != ''],
                       key=lambda k: natural_key(unit_map.get(k, k)))
    sel_unit_k = st.sidebar.selectbox(
        '🏢 واحد:',
        ['همه'] + unit_keys,
        format_func=lambda k: 'همه' if k == 'همه' else unit_map.get(k, k),
    )

    if sel_unit_k != 'همه':
        tmp_u = tmp_u[tmp_u['_k_unit'] == sel_unit_k]
    eq_keys = sorted([e for e in tmp_u['_k_eq'].unique() if e != ''],
                     key=lambda k: natural_key(eq_map.get(k, k)))
    sel_eq_k = st.sidebar.selectbox(
        '⚙️ انتخاب تجهیز:',
        ['همه تجهیزات'] + eq_keys,
        format_func=lambda k: 'همه تجهیزات' if k == 'همه تجهیزات' else eq_map.get(k, k),
    )

    search_eq = st.sidebar.text_input('🔎 جستجوی سریع تجهیز:', placeholder='مثلاً: میل فن')

    date_map = {}
    if date_col:
        tmp_d = df[df['_k_date'] != '']
        if not tmp_d.empty:
            date_map = tmp_d.groupby('_k_date')[date_col].agg(_mode).to_dict()
    date_keys = sorted(date_map.keys(), key=lambda k: date_sort_key(date_map.get(k, k)),
                       reverse=True)
    sel_date_k = st.sidebar.selectbox(
        '🌙 انتخاب تاریخ:',
        ['همه تاریخ‌ها'] + date_keys,
        format_func=lambda k: 'همه تاریخ‌ها' if k == 'همه تاریخ‌ها' else date_map.get(k, k),
    )

    # ---- اعمال فیلترها ----
    fdf = df.copy()
    if sel_line_k != 'همه':
        fdf = fdf[fdf['_k_line'] == sel_line_k]
    if sel_unit_k != 'همه':
        fdf = fdf[fdf['_k_unit'] == sel_unit_k]
    if sel_eq_k != 'همه تجهیزات':
        fdf = fdf[fdf['_k_eq'] == sel_eq_k]
    if search_eq.strip():
        tokens = [t for t in norm(search_eq).split() if t]
        if tokens:
            fdf = fdf[fdf['_k_eq'].map(lambda v: all(t in v for t in tokens))]
    if sel_date_k != 'همه تاریخ‌ها':
        fdf = fdf[fdf['_k_date'] == sel_date_k]
    if date_col:
        fdf = fdf.sort_values(by='_dkey', ascending=False)

    # ---- پنل عیب‌یابی ----
    with st.sidebar.expander('🩺 عیب‌یابی داده'):
        st.write('**ستون‌های شناسایی‌شده:**')
        st.write({
            'خط': col_line, 'واحد': col_unit,
            'تجهیز': equip_col, 'تاریخ': date_col,
        })
        all_visible = [c for c in df.columns if not str(c).startswith('_')]
        pts = [c for c in all_visible if point_index(c) is not None]
        st.write(f'**ردیف خام:** {len(df_raw)} | **پس از ادغام:** {len(df)}')
        st.write(f'**ستون‌های نقطه ({len(pts)}):**')
        st.write(order_points(pts))

    # ==========================================================================
    # 8. نمایش اصلی
    # ==========================================================================
    st.title('📊 تحلیل روند ارتعاشات تجهیزات')

    visible_cols = [c for c in df.columns if not str(c).startswith('_')]
    point_cols = [c for c in visible_cols if point_index(c) is not None]
    extra_vib = [c for c in visible_cols
                 if c not in point_cols and any(k in str(c) for k in ['عمودی', 'افقی', 'محوری'])]
    vib_cols = order_points(point_cols) + extra_vib

    # ترتیب نهایی ستون‌های جدول
    base_order = [c for c in [col_line, col_unit, equip_col, date_col] if c]
    ordered_cols = base_order + [c for c in order_points(point_cols) if c not in base_order]
    ordered_cols += [c for c in visible_cols if c not in ordered_cols]

    matched = False
    if sel_eq_k != 'همه تجهیزات':
        eq_display = eq_map.get(sel_eq_k, sel_eq_k)
        if not df_assets.empty:
            a_name = smart_find_column(df_assets.columns,
                                       ['نام تجهیز', 'عنوان تجهیز', 'نام', 'تجهیز', 'Asset'])
            if a_name:
                n_assets = df_assets[a_name].map(norm)
                rows = df_assets[n_assets == sel_eq_k]
                if rows.empty:
                    rows = df_assets[n_assets.map(
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
                    e_rpm = gv(['دور', 'RPM'])
                    e_line_v = gv(['خط'])
                    e_unit_v = gv(['واحد'])
                    e_drive = gv(['نوع انتقال', 'کوپلینگ', 'اتصال', 'درایو'])
                    e_brg = gv(['بیرینگ', 'Bearing'])
                    e_bush = gv(['بوش', 'Bush'])

                    i_style = 'unicode-bidi:isolate;'
                    st.markdown(f'''
                    <div style='background:#f0f7ff; padding:20px; border-radius:15px;
                                border-right:10px solid #1E3A8D; margin-bottom:18px; text-align:right;
                                direction:rtl; box-shadow:2px 2px 8px rgba(0,0,0,0.06);'>
                        <h3 style='color:#1E3A8D; margin:0 0 14px 0; font-family:Tahoma;'>
                            🛠️ مشخصات فنی: <span style='{i_style}'>{eq_display}</span>
                        </h3>
                        <div style='display:grid; grid-template-columns:repeat(auto-fit, minmax(210px, 1fr));
                                    gap:10px; font-size:16px; color:#333; font-family:Tahoma;'>
                            <span style='{i_style}'><b style='color:#1E3A8D;'>🔹 نوع:</b> {e_type}</span>
                            <span style='{i_style}'><b style='color:#1E3A8D;'>🔹 دور:</b> {e_rpm} RPM</span>
                            <span style='{i_style}'><b style='color:#1E3A8D;'>🔹 خط:</b> {e_line_v}</span>
                            <span style='{i_style}'><b style='color:#1E3A8D;'>🔹 واحد:</b> {e_unit_v}</span>
                            <span style='{i_style}'><b style='color:#1E3A8D;'>🔹 انتقال:</b> {e_drive}</span>
                            <span style='{i_style}'><b style='color:#1E3A8D;'>🧩 بیرینگ:</b> {e_brg}</span>
                            <span style='{i_style}'><b style='color:#1E3A8D;'>🧩 بوش:</b> {e_bush}</span>
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)

                    # ---- نقشه نقاط (بالای جدول داده‌ها) ----
                    pmap = get_point_map(eq_display, e_type)
                    existing = {}
                    if not fdf.empty:
                        for c in point_cols:
                            idx = point_index(c)
                            if idx is None:
                                continue
                            vals = to_num(fdf[c]).dropna()
                            if not vals.empty:
                                existing[idx] = str(c)

                    chips = []
                    for code, desc in pmap:
                        idx = int(re.sub(r'\D', '', code) or 0)
                        has_data = idx in existing
                        bg = '#1E3A8D' if has_data else '#e3ecf7'
                        fg = '#ffffff' if has_data else '#5a6b7c'
                        mark = ' ●' if has_data else ''
                        chips.append(
                            f"<span style='display:inline-block; background:{bg}; color:{fg}; "
                            f"padding:6px 12px; border-radius:20px; margin:4px; font-size:13px; "
                            f"font-family:Tahoma; unicode-bidi:isolate; white-space:nowrap;'>"
                            f"<b>{code}</b>{mark} — {desc}</span>"
                        )

                    legend = ('<span style="font-size:12px; color:#5a6b7c;">'
                              '(نقاط پررنگ دارای داده ثبت‌شده هستند)</span>')
                    st.markdown(f'''
                    <div style='background:#fbfdff; border:1px solid #d8e4f0; border-radius:12px;
                                padding:14px 16px; margin-bottom:18px; direction:rtl; text-align:right;'>
                        <div style='color:#1E3A8D; font-weight:bold; font-family:Tahoma; margin-bottom:8px;'>
                            📍 راهنمای نقاط اندازه‌گیری (P-Map) — {legend}
                        </div>
                        <div style='line-height:2;'>{''.join(chips)}</div>
                    </div>
                    ''', unsafe_allow_html=True)

                    pts_c = smart_find_column(df_assets.columns, ['نقطه', 'Point'])
                    brg_c = smart_find_column(df_assets.columns, ['بیرینگ', 'Bearing'])
                    bsh_c = smart_find_column(df_assets.columns, ['بوش', 'Bush'])
                    if any([pts_c, brg_c, bsh_c]):
                        log_cols = [c for c in [pts_c, brg_c, bsh_c] if c]
                        logistics = rows[log_cols].copy().replace(
                            {'': '---', 'nan': '---', 'None': '---', 'NaN': '---'})
                        logistics = logistics.rename(
                            columns={k: v for k, v in
                                     {pts_c: 'نقطه', brg_c: 'بیرینگ', bsh_c: 'بوش'}.items()
                                     if k in logistics.columns})
                        with st.expander('📦 اطلاعات قطعات و لجستیک', expanded=True):
                            st.dataframe(logistics, hide_index=True, use_container_width=True)

    if sel_eq_k == 'همه تجهیزات':
        matched = True
    if not matched:
        st.info('ℹ️ مشخصات فنی برای این تجهیز در شیت Assets یافت نشد.')

    # ---- جدول داده‌ها ----
    if not fdf.empty:
        st.markdown(f'### 📋 داده‌های ارتعاشات ({len(fdf)} مورد)')

        def color_vib(val):
            try:
                v = float(clean_num_text(val))
                if v > 7.1:
                    return 'background-color:#ff4b4b; color:white'
                if v > 4.5:
                    return 'background-color:#ffa500; color:white'
                return 'background-color:#2e7d32; color:white'
            except Exception:
                return ''

        table = fdf[ordered_cols].copy()
        styled = table.style
        if vib_cols:
            try:
                styled = styled.map(color_vib, subset=[c for c in vib_cols if c in table.columns])
            except Exception:
                styled = styled.applymap(color_vib, subset=[c for c in vib_cols if c in table.columns])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # ---- نمودار روند ----
        if vib_cols and sel_eq_k != 'همه تجهیزات' and date_col and len(fdf) > 1:
            with st.expander('📈 نمودار روند ارتعاشات', expanded=False):
                trend = fdf[[date_col] + vib_cols].copy()
                trend['_dkey'] = trend[date_col].map(date_sort_key)
                trend = trend.sort_values('_dkey')
                trend['تاریخ'] = trend[date_col].astype(str)
                long_df = trend.melt(id_vars=['تاریخ', '_dkey'], value_vars=vib_cols,
                                     var_name='نقطه/جهت', value_name='ارتعاش')
                long_df['_order'] = long_df['نقطه/جهت'].map(
                    lambda c: point_index(c) if point_index(c) is not None else 99)
                long_df = long_df.sort_values('_order')
                long_df['ارتعاش'] = to_num(long_df['ارتعاش'])
                long_df = long_df.dropna(subset=['ارتعاش'])
                if not long_df.empty:
                    fig_line = px.line(long_df, x='تاریخ', y='ارتعاش', color='نقطه/جهت',
                                       markers=True, title='روند ارتعاش (mm/s)')
                    fig_line.add_hline(y=4.5, line_dash='dash', line_color='orange',
                                       annotation_text='هشدار')
                    fig_line.add_hline(y=7.1, line_dash='dash', line_color='red',
                                       annotation_text='بحرانی')
                    st.plotly_chart(fig_line, use_container_width=True)

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
                        values=status.values, names=status.index, color=status.index,
                        color_discrete_map={'سالم': '#2e7d32', 'هشدار': '#ffa500',
                                            'بحرانی': '#ff4b4b', 'نامشخص': '#9e9e9e'},
                        hole=0.35,
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.warning('⚠️ هیچ داده‌ای با این فیلترها پیدا نشد.')

    st.markdown(
        '<div style="text-align:center; margin-top:50px; color:#555; font-family:Tahoma;">'
        'طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>',
        unsafe_allow_html=True,
    )
else:
    st.error('❌ خطا در اتصال به منبع داده.')
