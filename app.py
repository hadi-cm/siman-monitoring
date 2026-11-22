# -*- coding: utf-8 -*-
"""
سیستم هوشمند پایش وضعیت - سیمان تهران
نسخه یکپارچه: اتصال مستقیم به گوگل شیت، فیلتر خط ← واحد ← تجهیز ← تاریخ
"""

import re
import html as html_lib
from datetime import datetime, timedelta, date
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ==========================================================
# 1) پیکربندی
# ==========================================================
st.set_page_config(
    page_title='سیستم هوشمند پایش وضعیت - سیمان تهران',
    page_icon='📊',
    layout='wide',
)

APP_TITLE = 'سیستم هوشمند پایش وضعیت - سیمان تهران'

USER_DB = {
    'cm.zandiyeh@gmail.com':          {'name': 'هادی زندیه',      'role': 'پیمانکار / مالک سیستم', 'password': 'siman123'},
    'vah.rezaei@gmail.com':           {'name': 'وحید رضایی',      'role': 'مدیر مکانیک',           'password': 'siman123'},
    'me.vibration.shokri@gmail.com':  {'name': 'مهدی شکری',       'role': 'مدیر دفتر فنی',         'password': 'siman123'},
    'tehrancment@gmail.com':          {'name': 'سید مهدی حسینی',  'role': 'معاونت فنی',            'password': 'siman123'},
    'alireza76ir@gmail.com':          {'name': 'علیرضا',          'role': 'کارشناس',               'password': 'siman123'},
    'masoud.sa.1989823@gmail.com':    {'name': 'مسعود صمیمی',     'role': 'کارشناس',               'password': 'siman123'},
    'operator2@tehrancment.ir':       {'name': 'اپراتور خط ۲',    'role': 'کاربر',                 'password': 'siman123'},
}
OWNER_EMAIL = 'cm.zandiyeh@gmail.com'
SEND_ROLES = ('مدیر', 'معاونت', 'مالک')

# --- منابع داده (لینک‌های گوگل شیت) ---
BASE_CSV = ('https://docs.google.com/spreadsheets/d/e/2PACX-1vTI4vONsowudctVbskGkkSyQNqkkGZ8Aui'
            'ykO9UKeE-8FSBZemWkR4q5DSAhpXEqwQkgsCUQy44Vvqx/pub?output=csv')
VIB_CSV_URL = BASE_CSV
EQUIP_CSV_URL = BASE_CSV + '&gid=1728784730'

# --- نام ستون‌های استاندارد ---
COL_DATE = 'تاریخ'
COL_LINE = 'خط تولید'
COL_UNIT = 'واحد'
COL_EQUIP = 'عنوان تجهیز'
COL_H = 'افقی'
COL_V = 'عمودی'
COL_A = 'محوری'
COL_T = 'دما'
COL_TXT_DATE = 'تاریخ شمسی'
COL_S = 'وضعیت'

FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'

LINE_PRIORITY = ['خط تولید ۳', 'خط تولید ۴', 'خط تولید ۶',
                 'خط تولید ۷', 'خط تولید ۸', 'خط تولید ۹']
UNIT_PRIORITY = ['آسیاب سنگ', 'آسیاب مواد', 'کوره', 'آسیاب سیمان',
                 'بارگیرخانه تهران', 'بارگیرخانه ۶', 'بارگیرخانه ۹']

STATUS_EMOJI = {'نرمال': '🟢', 'هشدار': '🟡', 'بحرانی': '🔴'}


# ==========================================================
# 2) توابع کمکی متنی
# ==========================================================
def to_latin(v):
    """ارقام فارسی/عربی را به لاتین تبدیل می‌کند."""
    s = str(v)
    out = ''
    for ch in s:
        if ch in FA_DIGITS:
            out += str(FA_DIGITS.index(ch))
        elif ch in '٠١٢٣٤٥٦٧٨٩':
            out += str('٠١٢٣٤٥٦٧٨٩'.index(ch))
        else:
            out += ch
    return out


def fa_num(v):
    out = ''
    for ch in str(v):
        out += FA_DIGITS[int(ch)] if ch.isdigit() else ch
    return out


def norm_text(v):
    """حذف کشیده، نیم‌فاصله‌های اضافه و فاصله‌های تکراری."""
    if v is None:
        return ''
    s = str(v).replace('ـ', '').replace('\u200c', ' ').strip()
    return ' '.join(s.split())


def norm_key(v):
    """کلید مقایسه: بدون فاصله، فقط حروف و ارقام لاتین."""
    s = to_latin(norm_text(v)).lower()
    return re.sub(r'[^0-9a-zآ-ی]', '', s)


def clean_line_name(v):
    """
    نام خط تولید را استاندارد می‌کند:
    - صفرهای ابتدایی حذف می‌شوند  (۰۶ → ۶)
    - اگر مقدار ۶۰ / ۷۰ / ۸۰ ثبت شده باشد به ۶ / ۷ / ۸ برمی‌گردد
    """
    s = to_latin(v).strip()
    digits = ''.join(filter(str.isdigit, s))
    if not digits:
        return norm_text(v)
    val = int(digits)
    while val > 9 and val % 10 == 0:
        val //= 10
    return 'خط تولید ' + fa_num(val)


def norm_unit(v):
    return norm_text(v)


def to_num(v):
    """تبدیل امن به عدد: ممیز / ، ارقام فارسی، و مقادیر متنی غیرعددی."""
    if v is None:
        return np.nan
    s = to_latin(str(v)).replace('ـ', '').strip()
    if s in ('', 'nan', 'None', 'N/A', '-', 'عدم دسترسی', 'دکوپل',
             'قطع', 'نامشخص', 'خارج از سرویس'):
        return np.nan
    s = s.replace('٫', '.').replace('/', '.').replace('،', '')
    m = re.search(r'-?\d+(?:\.\d+)?', s)
    return float(m.group()) if m else np.nan


# ==========================================================
# 3) تبدیل تاریخ شمسی ↔ میلادی
# ==========================================================
def j2g(jy, jm, jd):
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
    sal = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    while gm <= 12 and gd > sal[gm]:
        gd -= sal[gm]
        gm += 1
    return gy, gm, gd


def g2j(gy, gm, gd):
    g_dm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2, gm2, gd2 = gy - 1600, gm - 1, gd - 1
    g_day = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    g_day += g_dm[gm2] + gd2
    if gm > 2 and ((gy % 4 == 0 and gy % 100 != 0) or gy % 400 == 0):
        g_day += 1
    j_day = g_day - 79
    j_np = j_day // 12053
    j_day %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day // 1461)
    j_day %= 1461
    if j_day >= 366:
        jy += (j_day - 1) // 365
        j_day = (j_day - 1) % 365
    if j_day < 186:
        jm = 1 + j_day // 31
        jd = 1 + j_day % 31
    else:
        jm = 7 + (j_day - 186) // 30
        jd = 1 + (j_day - 186) % 30
    return jy, jm, jd


def parse_jalali(v):
    """رشته تاریخ شمسی → تاریخ میلادی (datetime.date)."""
    if isinstance(v, (datetime, date)) and not isinstance(v, bool):
        return v if isinstance(v, date) else v.date()
    s = to_latin(norm_text(v)).replace('-', '/').replace('.', '/').replace('_', '/')
    s = re.sub(r'\s+', '', s)
    parts = s.split('/')
    if len(parts) < 3:
        m = re.match(r'^(\d{4})(\d{2})(\d{2})$', s)
        if not m:
            return None
        parts = [m.group(1), m.group(2), m.group(3)]
    try:
        jy, jm, jd = int(parts[0]), int(parts[1]), int(parts[2])
        if jy < 100:
            jy += 1400
        if not (1 <= jm <= 12 and 1 <= jd <= 31):
            return None
        gy, gm, gd = j2g(jy, jm, jd)
        return date(gy, gm, gd)
    except Exception:
        return None


def jalali_label(d):
    """تاریخ میلادی → برچسب شمسی ۱۴۰۴/۰۹/۰۱"""
    jy, jm, jd = g2j(d.year, d.month, d.day)
    return '{:04d}/{:02d}/{:02d}'.format(jy, jm, jd)


# ==========================================================
# 4) بارگذاری و آماده‌سازی داده
# ==========================================================
@st.cache_data(ttl=300, show_spinner='در حال دریافت داده از گوگل شیت...')
def load_raw():
    """خواندن شیت ارتعاشات و شیت لیست تجهیزات."""
    vib = None
    equip = None
    try:
        vib = pd.read_csv(VIB_CSV_URL)
        vib.columns = [norm_text(c) for c in vib.columns]
    except Exception as exc:
        return None, None, 'خطا در خواندن شیت ارتعاشات: {}'.format(exc)

    try:
        equip = pd.read_csv(EQUIP_CSV_URL)
        equip.columns = [norm_text(c) for c in equip.columns]
    except Exception:
        equip = None

    return vib, equip, 'اتصال به گوگل شیت برقرار است'


def map_columns(df):
    """نگاشت هوشمند نام ستون‌های شیت به نام‌های استاندارد."""
    ren = {}
    for c in df.columns:
        cs = to_latin(norm_text(c)).lower()
        if 'تاریخ' in cs:
            ren[c] = COL_DATE
        elif 'خط' in cs and 'تولید' in cs:
            ren[c] = COL_LINE
        elif cs.startswith('خط'):
            ren[c] = COL_LINE
        elif 'واحد' in cs:
            ren[c] = COL_UNIT
        elif 'تجهیز' in cs or 'دستگاه' in cs or 'ماشین' in cs:
            ren[c] = COL_EQUIP
        elif 'افقی' in cs or 'h' == cs:
            ren[c] = COL_H
        elif 'عمودی' in cs or 'v' == cs:
            ren[c] = COL_V
        elif 'محوری' in cs or 'a' == cs:
            ren[c] = COL_A
        elif 'دما' in cs or 'حرارت' in cs:
            ren[c] = COL_T
    return df.rename(columns=ren)


def pick_col(df, keys):
    for c in df.columns:
        cs = to_latin(norm_text(c)).lower()
        for k in keys:
            if k in cs:
                return c
    return None


def build_asset_order(equip_raw):
    """چیدمان تجهیزات بر اساس شیت لیست تجهیزات (برای مرتب‌سازی فیلتر)."""
    order = {}
    if equip_raw is None or equip_raw.empty:
        return order
    df = equip_raw.copy()
    c_line = pick_col(df, ['خط'])
    c_unit = pick_col(df, ['واحد'])
    c_eq = pick_col(df, ['تجهیز', 'دستگاه', 'نام'])
    if not (c_line and c_unit and c_eq):
        return order
    df = df[[c_line, c_unit, c_eq]].dropna()
    for i, (_, r) in enumerate(df.iterrows()):
        key = (clean_line_name(r[c_line]), norm_unit(r[c_unit]), norm_key(r[c_eq]))
        order.setdefault(key, i)
    return order


def prepare(vib):
    """پاکسازی، تجمیع نقاط p1..p11 و محاسبه وضعیت."""
    df = vib.copy()
    df = map_columns(df)

    needed = [COL_DATE, COL_LINE, COL_UNIT, COL_EQUIP]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        return pd.DataFrame(), missing

    for c in (COL_H, COL_V, COL_A, COL_T):
        if c in df.columns:
            df[c] = df[c].map(to_num)
        else:
            df[c] = np.nan

    df[COL_DATE] = df[COL_DATE].map(parse_jalali)
    df = df.dropna(subset=[COL_DATE])

    df[COL_LINE] = df[COL_LINE].map(clean_line_name)
    df[COL_UNIT] = df[COL_UNIT].map(norm_unit)
    df[COL_EQUIP] = df[COL_EQUIP].map(norm_text)
    df = df[(df[COL_EQUIP] != '') & (df[COL_LINE] != '')]

    keys = [COL_DATE, COL_LINE, COL_UNIT, COL_EQUIP]
    agg = df.groupby(keys, as_index=False).agg(
        {COL_H: 'max', COL_V: 'max', COL_A: 'max', COL_T: 'max'}
    )

    agg['حداکثر'] = agg[[COL_H, COL_V, COL_A]].max(axis=1).round(2)
    agg[COL_S] = np.select(
        [agg['حداکثر'] < 4.5, agg['حداکثر'] < 7.0],
        ['نرمال', 'هشدار'], default='بحرانی'
    )
    agg.loc[agg['حداکثر'].isna(), COL_S] = 'بدون داده'
    agg[COL_TXT_DATE] = agg[COL_DATE].map(jalali_label)
    return agg.sort_values(COL_DATE), []


# ==========================================================
# 5) گزارش HTML
# ==========================================================
REPORT_CSS = (
    '<style>'
    '@page{size:A4 landscape;margin:12mm}'
    'body{font-family:Tahoma,sans-serif;direction:rtl;text-align:right;color:#1f2d3d;padding:10px}'
    'h1{font-size:20px;color:#0b3c6b;margin:0 0 4px 0}'
    '.sub{font-size:12px;color:#6b7c8f;margin-bottom:14px}'
    '.box{border:1px solid #d9e2ec;border-radius:8px;padding:10px 14px;margin-bottom:12px;'
    'background:#f7fafc;font-size:13px;line-height:1.9}'
    '.kpis{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}'
    '.kpi{flex:1 1 150px;border:1px solid #d9e2ec;border-radius:8px;padding:10px;text-align:center}'
    '.kpi .v{font-size:18px;font-weight:bold;color:#0b3c6b}'
    '.kpi .l{font-size:11px;color:#6b7c8f;margin-top:4px}'
    'table{border-collapse:collapse;width:100%;font-size:11px}'
    'th{background:#0b3c6b;color:#fff;padding:6px;border:1px solid #0b3c6b}'
    'td{padding:5px 6px;border:1px solid #dfe7ef}'
    'tbody tr:nth-child(even){background:#f4f7fa}'
    '.foot{margin-top:14px;font-size:11px;color:#6b7c8f;text-align:center}'
    '.crit{color:#b3261e;font-weight:bold}'
    '.warn{color:#a2621b;font-weight:bold}'
    '</style>'
)


def build_report_html(df_report, meta):
    esc = html_lib.escape
    cols = [COL_TXT_DATE, COL_LINE, COL_UNIT, COL_EQUIP, COL_H, COL_V, COL_A, COL_T, COL_S]
    cols = [c for c in cols if c in df_report.columns]

    if df_report.empty:
        kpis = [('تعداد رکورد', '0'), ('میانگین افقی', '-'),
                ('میانگین دما', '-'), ('موارد بحرانی', '-')]
        table_html = '<p>برای این ترکیب فیلترها رکوردی یافت نشد.</p>'
    else:
        kpis = [
            ('تعداد رکورد', '{:,}'.format(len(df_report))),
            ('میانگین افقی', '{:.2f} mm/s'.format(df_report[COL_H].mean())),
            ('میانگین دما', '{:.1f} °C'.format(df_report[COL_T].mean())),
            ('موارد بحرانی', '{:,}'.format(int((df_report[COL_S] == 'بحرانی').sum()))),
        ]
        head = ''.join('<th>' + esc(str(c)) + '</th>' for c in cols)
        body = ''
        for _, row in df_report.iterrows():
            cells = ''
            for c in cols:
                val = row[c]
                cell = esc(str(val))
                if c == COL_S and str(val) == 'بحرانی':
                    cell = '<span class="crit">' + cell + '</span>'
                elif c == COL_S and str(val) == 'هشدار':
                    cell = '<span class="warn">' + cell + '</span>'
                cells += '<td>' + cell + '</td>'
            body += '<tr>' + cells + '</tr>'
        table_html = ('<table><thead><tr>' + head + '</tr></thead><tbody>'
                      + body + '</tbody></table>')

    kpi_html = ''
    for label, value in kpis:
        kpi_html += ('<div class="kpi"><div class="v">' + esc(str(value)) +
                     '</div><div class="l">' + esc(label) + '</div></div>')

    info_html = ''
    for key, value in meta.items():
        info_html += '<div><b>' + esc(str(key)) + ':</b> ' + esc(str(value)) + '</div>'

    return (
        "<!DOCTYPE html><html lang='fa' dir='rtl'><head><meta charset='utf-8'>"
        '<title>گزارش پایش وضعیت - سیمان تهران</title>' + REPORT_CSS + '</head><body>'
        '<h1>گزارش پایش وضعیت ارتعاش - سیمان تهران</h1>'
        '<div class="sub">تاریخ گزارش: ' + esc(datetime.now().strftime('%Y-%m-%d %H:%M')) + '</div>'
        '<div class="box">' + info_html + '</div>'
        '<div class="kpis">' + kpi_html + '</div>'
        + table_html +
        '<div class="foot">این گزارش به‌صورت خودکار توسط سامانه پایش وضعیت تولید شده است.</div>'
        '</body></html>'
    )


# ==========================================================
# 6) دسترسی‌ها
# ==========================================================
def can_send(email):
    return any(k in USER_DB.get(email, {}).get('role', '') for k in SEND_ROLES)


def can_edit(email):
    return email == OWNER_EMAIL


def ordered(items, priority):
    clean = []
    for i in items:
        s = str(i)
        if s not in ('', 'nan', 'None') and s not in clean:
            clean.append(s)
    head = [p for p in priority if p in clean]
    return head + sorted([i for i in clean if i not in priority])


# ==========================================================
# 7) رابط کاربری
# ==========================================================
def render_header(user_email=None):
    c1, c2, c3 = st.columns([1, 4, 1])
    with c1:
        try:
            st.image('my_logo.png', use_container_width=True)
        except Exception:
            st.markdown("<div style='border:1px dashed #d9e2ec;border-radius:8px;"
                        "padding:12px;text-align:center;font-size:12px;color:#7a8794'>"
                        "لوگوی شما<br>(my_logo.png)</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(
            "<h2 style='text-align:center;margin-bottom:2px;color:#0b3c6b'>" + APP_TITLE + "</h2>"
            "<p style='text-align:center;color:#7a8794;font-size:13px;margin-top:0'>"
            "پایش برخط ارتعاش و دمای تجهیزات</p>", unsafe_allow_html=True)
    with c3:
        try:
            st.image('client_logo.png', use_container_width=True)
        except Exception:
            st.markdown("<div style='border:1px dashed #d9e2ec;border-radius:8px;"
                        "padding:12px;text-align:center;font-size:12px;color:#7a8794'>"
                        "سیمان تهران<br>(client_logo.png)</div>", unsafe_allow_html=True)


def login_screen():
    render_header()
    st.divider()
    st.markdown('### 🔐 ورود به سامانه')
    with st.form('login_form'):
        email = st.text_input('ایمیل سازمانی', placeholder='name@example.com')
        password = st.text_input('رمز عبور', type='password')
        ok = st.form_submit_button('ورود به داشبورد', use_container_width=True)
    if ok:
        email = (email or '').strip().lower()
        if email in USER_DB and USER_DB[email]['password'] == password:
            st.session_state.user = email
            st.rerun()
        elif email and email not in USER_DB:
            st.error('این ایمیل در سامانه ثبت نشده است.')
        else:
            st.error('رمز عبور نادرست است.')
    st.caption('رمز پیش‌فرض کاربران: siman123')


def main():
    if 'user' not in st.session_state:
        st.session_state.user = None

    if st.session_state.user is None:
        login_screen()
        return

    user_email = st.session_state.user
    user_info = USER_DB[user_email]
    is_sender = can_send(user_email)
    is_editor = can_edit(user_email)

    render_header(user_email)
    st.divider()

    u1, u2, u3 = st.columns([3, 2, 1])
    with u1:
        st.markdown('👤 **' + user_info['name'] + '** — `' + user_email +
                    '` | نقش: ' + user_info['role'])
    with u2:
        st.caption('📨 ارسال اعلان: ' + ('✅' if is_sender else '⛔') +
                   ' | ✏️ مدیریت: ' + ('✅' if is_editor else '⛔'))
    with u3:
        if st.button('خروج', use_container_width=True):
            st.session_state.user = None
            st.rerun()

    # --- بارگذاری داده ---
    vib_raw, equip_raw, source_msg = load_raw()
    if vib_raw is None:
        st.error(source_msg)
        st.stop()

    df_all, missing = prepare(vib_raw)
    if missing:
        st.error('این ستون‌ها در شیت پیدا نشد: ' + '، '.join(missing) +
                 ' — نام ستون‌ها را در بالای کد اصلاح کنید.')
        st.stop()
    if df_all.empty:
        st.error('شیت ارتعاشات خوانده شد ولی هیچ رکورد معتبری ندارد.')
        st.stop()

    asset_order = build_asset_order(equip_raw)

    with st.sidebar:
        st.markdown('### ⚙️ وضعیت سامانه')
        st.caption(source_msg)
        st.caption('رکوردهای شیت: {:,}'.format(len(vib_raw)))
        st.caption('رکوردهای معتبر: {:,}'.format(len(df_all)))
        st.caption('از تاریخ ' + df_all[COL_TXT_DATE].min() +
                   ' تا ' + df_all[COL_TXT_DATE].max())
        if st.button('🔄 بروزرسانی داده', use_container_width=True):
            load_raw.clear()
            st.rerun()

    # ============ فیلترها: خط ← واحد ← تجهیز ============
    st.markdown('#### 🔎 فیلترها')
    f1, f2, f3 = st.columns([2, 2, 3])

    lines_avail = ordered(df_all[COL_LINE].unique().tolist(), LINE_PRIORITY)
    with f1:
        sel_line = st.selectbox('۱) خط تولید', ['همه خطوط'] + lines_avail)

    unit_src = df_all if sel_line == 'همه خطوط' else df_all[df_all[COL_LINE] == sel_line]
    units_avail = ordered(unit_src[COL_UNIT].unique().tolist(), UNIT_PRIORITY)
    with f2:
        sel_unit = st.selectbox('۲) واحد', ['همه واحدها'] + units_avail,
                                key='unit_of_' + sel_line)

    eq_src = unit_src if sel_unit == 'همه واحدها' else unit_src[unit_src[COL_UNIT] == sel_unit]

    # فهرست تجهیزات فقط از داده‌های واقعی ساخته می‌شود تا هر گزینه‌ای که
    # انتخاب می‌شود، حتماً داده داشته باشد (حل مشکل تجهیز بدون داده).
    raw_equips = eq_src[COL_EQUIP].dropna().astype(str).unique().tolist()
    if asset_order:
        def sort_key(name):
            k = (sel_line if sel_line != 'همه خطوط' else '',
                 sel_unit if sel_unit != 'همه واحدها' else '',
                 norm_key(name))
            return (asset_order.get(k, 10 ** 6), name)
        equips_avail = sorted(raw_equips, key=sort_key)
    else:
        equips_avail = sorted(raw_equips)

    with f3:
        if not equips_avail:
            sel_equip = []
            st.selectbox('۳) عنوان تجهیز', ['-'], disabled=True)
        elif len(equips_avail) == 1:
            sel_equip = [st.selectbox('۳) عنوان تجهیز', equips_avail,
                                      key='eq1_' + sel_line + '_' + sel_unit)]
        else:
            sel_equip = st.multiselect(
                '۳) عنوان تجهیز',
                ['همه تجهیزات'] + equips_avail,
                default=['همه تجهیزات'],
                key='eqm_' + sel_line + '_' + sel_unit,
            )

    # ============ اعمال فیلتر خط/واحد/تجهیز ============
    df = df_all.copy()
    if sel_line != 'همه خطوط':
        df = df[df[COL_LINE] == sel_line]
    if sel_unit != 'همه واحدها':
        df = df[df[COL_UNIT] == sel_unit]

    if sel_equip and 'همه تجهیزات' not in sel_equip:
        keys = [norm_key(e) for e in sel_equip]
        mask = df[COL_EQUIP].map(
            lambda x: norm_key(x) in keys
            or any(k and (k in norm_key(x) or norm_key(x) in k) for k in keys)
        )
        df = df[mask]

    # ============ فیلتر تاریخ (بعد از تجهیز) ============
    st.markdown('#### 🗓 فیلتر تاریخ')
    dates_avail = sorted(df[COL_DATE].unique())
    date_labels = [jalali_label(d) for d in dates_avail]
    label_to_date = dict(zip(date_labels, dates_avail))

    d1, d2 = st.columns([2, 4])
    with d1:
        date_mode = st.selectbox(
            'حالت انتخاب تاریخ',
            ['همه تاریخ‌ها', 'بازه تاریخی', 'تاریخ‌های خاص'],
            key='date_mode',
        )

    if not date_labels:
        st.warning('برای این تجهیز هیچ تاریخی ثبت نشده است.')
        df = df.iloc[0:0]
    elif date_mode == 'همه تاریخ‌ها':
        with d2:
            st.caption('نمایش تمام تاریخ‌های موجود: از ' +
                       date_labels[0] + ' تا ' + date_labels[-1])
    elif date_mode == 'بازه تاریخی':
        with d2:
            if len(date_labels) == 1:
                st.caption('فقط یک تاریخ موجود است: ' + date_labels[0])
                df = df[df[COL_DATE] == label_to_date[date_labels[0]]]
            else:
                a, b = st.select_slider(
                    'انتخاب بازه (روی تاریخ‌های موجود)',
                    options=date_labels, value=(date_labels[0], date_labels[-1]),
                    key='date_range',
                )
                st.caption('از ' + a + ' تا ' + b)
                df = df[(df[COL_DATE] >= label_to_date[a]) &
                        (df[COL_DATE] <= label_to_date[b])]
    else:
        with d2:
            picked = st.multiselect('تاریخ‌های مورد نظر را انتخاب کنید',
                                    date_labels, key='date_pick')
            if picked:
                df = df[df[COL_DATE].isin([label_to_date[p] for p in picked])]
            else:
                st.caption('تا انتخاب نشدن تاریخ، همه تاریخ‌ها نمایش داده می‌شود.')

    path = [sel_line]
    if sel_unit != 'همه واحدها':
        path.append(sel_unit)
    if sel_equip and 'همه تجهیزات' not in sel_equip:
        path.append('، '.join(sel_equip))
    path.append('تاریخ: ' + date_mode)
    filter_path_text = ' ➔ '.join(path)
    st.caption('مسیر فیلتر: ' + filter_path_text)

    df = df.sort_values([COL_DATE, COL_LINE, COL_UNIT, COL_EQUIP], ascending=[False, True, True, True])
    st.divider()

    # ============ تب‌ها ============
    tab1, tab2, tab3, tab4 = st.tabs(
        ['📋 جدول داده‌ها', '📈 نمودارها', '📨 ارسال اعلان', '👥 کاربران']
    )

    # ---------- جدول ----------
    with tab1:
        st.markdown('تعداد رکوردها: **{:,}**'.format(len(df)))
        if df.empty:
            st.info('با این فیلترها رکوردی یافت نشد.')
        else:
            show_cols = [COL_TXT_DATE, COL_LINE, COL_UNIT, COL_EQUIP,
                         COL_H, COL_V, COL_A, COL_T, 'حداکثر', COL_S]
            show_cols = [c for c in show_cols if c in df.columns]
            styled = df[show_cols].copy()
            styled[COL_S] = styled[COL_S].map(lambda s: STATUS_EMOJI.get(s, '') + ' ' + str(s))
            st.dataframe(styled, use_container_width=True, height=460)

            b1, b2 = st.columns(2)
            with b1:
                st.download_button(
                    '⬇️ دانلود CSV',
                    data=df.to_csv(index=False).encode('utf-8-sig'),
                    file_name='vibration_data.csv', mime='text/csv',
                    use_container_width=True,
                )
            with b2:
                meta = {
                    'مسیر فیلتر': filter_path_text,
                    'حالت تاریخ': date_mode,
                    'تعداد رکورد': len(df),
                    'تهیه‌کننده': user_info['name'] + ' - ' + user_info['role'],
                }
                st.download_button(
                    '🧾 دانلود گزارش (HTML قابل چاپ به PDF)',
                    data=build_report_html(df, meta).encode('utf-8'),
                    file_name='vibration_report_' + datetime.now().strftime('%Y%m%d_%H%M') + '.html',
                    mime='text/html', use_container_width=True,
                )
            st.caption('برای PDF: فایل گزارش را در مرورگر باز کنید و Ctrl+P → Save as PDF.')

    # ---------- نمودارها ----------
    with tab2:
        if df.empty:
            st.info('داده‌ای برای نمودار نیست.')
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric('میانگین افقی', '{:.2f} mm/s'.format(df[COL_H].mean()))
            m2.metric('میانگین عمودی', '{:.2f} mm/s'.format(df[COL_V].mean()))
            m3.metric('میانگین دما', '{:.1f} °C'.format(df[COL_T].mean()))
            m4.metric('موارد بحرانی', int((df[COL_S] == 'بحرانی').sum()))

            daily = df.groupby(COL_TXT_DATE)[[COL_H, COL_V, COL_A]].mean().reset_index()
            fig = px.line(daily, x=COL_TXT_DATE, y=[COL_H, COL_V, COL_A],
                          markers=True, title='روند میانگین ارتعاش روزانه (mm/s)')
            fig.add_hline(y=4.5, line_dash='dash', line_color='orange',
                          annotation_text='هشدار 4.5')
            fig.add_hline(y=7.0, line_dash='dash', line_color='red',
                          annotation_text='بحرانی 7.0')
            st.plotly_chart(fig, use_container_width=True)

            g1, g2 = st.columns(2)
            with g1:
                worst = (df.groupby(COL_EQUIP)['حداکثر'].max()
                         .sort_values(ascending=False).head(12).reset_index())
                st.plotly_chart(
                    px.bar(worst, x='حداکثر', y=COL_EQUIP, orientation='h',
                           title='۱۲ تجهیز با بیشترین ارتعاش', color='حداکثر',
                           color_continuous_scale='Reds'),
                    use_container_width=True)
            with g2:
                share = df[COL_S].value_counts().reset_index()
                share.columns = ['وضعیت', 'تعداد']
                st.plotly_chart(
                    px.pie(share, names='وضعیت', values='تعداد', hole=0.5,
                           title='سهم وضعیت‌ها',
                           color='وضعیت',
                           color_discrete_map={'نرمال': '#2e7d32', 'هشدار': '#f9a825',
                                               'بحرانی': '#c62828', 'بدون داده': '#90a4ae'}),
                    use_container_width=True)

            temp = df.groupby(COL_TXT_DATE)[COL_T].mean().reset_index()
            st.plotly_chart(
                px.line(temp, x=COL_TXT_DATE, y=COL_T, markers=True,
                        title='روند میانگین دما (°C)'),
                use_container_width=True)

    # ---------- اعلان ----------
    with tab3:
        crit = df[df[COL_S] == 'بحرانی'].sort_values('حداکثر', ascending=False)
        st.markdown('#### 🚨 تجهیزات نیازمند توجه (بحرانی)')
        if crit.empty:
            st.success('در این بازه تجهیز بحرانی وجود ندارد.')
        else:
            cols = [COL_TXT_DATE, COL_LINE, COL_UNIT, COL_EQUIP,
                    COL_H, COL_V, COL_A, COL_T, 'حداکثر']
            st.dataframe(crit[[c for c in cols if c in crit.columns]],
                         use_container_width=True, height=240)

        st.divider()
        st.markdown('#### 📨 پیش‌نویس اعلان')
        all_emails = list(USER_DB.keys())
        recipients = st.multiselect(
            'گیرندگان', all_emails, default=all_emails,
            format_func=lambda e: USER_DB[e]['name'] + ' - ' + e,
        )
        subject = st.text_input(
            'موضوع',
            'هشدار ارتعاش - سیمان تهران - ' + jalali_label(datetime.now().date()),
        )

        if crit.empty:
            body = 'در بازه انتخاب‌شده تجهیز بحرانی گزارش نشده است.'
        else:
            lines_txt = [
                'گزارش وضعیت تجهیزات بحرانی - ' + jalali_label(datetime.now().date()),
                'فیلتر: ' + filter_path_text + ' | تعداد بحرانی: ' + str(len(crit)),
                '',
                'بدترین تجهیزات نیازمند توجه:',
            ]
            for i, (_, r) in enumerate(crit.head(10).iterrows(), 1):
                lines_txt.append(
                    '{}. {} ({} / {}) - تاریخ {} | افقی {} | عمودی {} | دما {}°C'.format(
                        i, r[COL_EQUIP], r[COL_LINE], r[COL_UNIT], r[COL_TXT_DATE],
                        r[COL_H], r[COL_V], r[COL_T]))
            lines_txt += ['', 'ارسال‌کننده: ' + user_info['name'] + ' - ' + user_info['role']]
            body = chr(10).join(lines_txt)

        body = st.text_area('متن پیام', body, height=240)

        if is_sender:
            if st.button('📨 ثبت اعلان', type='primary', use_container_width=True):
                st.session_state.setdefault('sent_log', []).append({
                    'زمان': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'فرستنده': user_info['name'],
                    'موضوع': subject,
                    'گیرندگان': '، '.join(USER_DB[e]['name'] for e in recipients),
                    'تعداد بحرانی': len(crit),
                })
                st.success('اعلان برای {} گیرنده ثبت شد.'.format(len(recipients)))
        else:
            st.button('📨 ارسال اعلان', disabled=True, use_container_width=True)
            st.caption('⛔ شما مجوز ارسال اعلان ندارید.')

        if recipients:
            mailto = 'mailto:' + ','.join(recipients) + \
                     '?subject=' + quote(subject) + '&body=' + quote(body)
            st.markdown('[✉️ باز کردن در برنامه ایمیل]({})'.format(mailto))
            st.download_button(
                '⬇️ دانلود متن پیام',
                data=body.encode('utf-8'),
                file_name='notification.txt', mime='text/plain',
            )

        st.divider()
        st.markdown('#### 📜 تاریخچه اعلان‌ها')
        log = st.session_state.get('sent_log', [])
        if log:
            log_df = pd.DataFrame(log)
            st.dataframe(log_df, use_container_width=True)
            st.download_button(
                '⬇️ دانلود تاریخچه CSV',
                data=log_df.to_csv(index=False).encode('utf-8-sig'),
                file_name='notification_history.csv', mime='text/csv',
            )
        else:
            st.caption('هنوز اعلانی ثبت نشده است.')

    # ---------- کاربران ----------
    with tab4:
        st.markdown('#### 👥 کاربران سامانه')
        rows = [{
            'نام': v['name'],
            'ایمیل': k,
            'نقش': v['role'],
            'رمز': v['password'] if is_editor else '••••••••',
            'ارسال اعلان': '✅' if can_send(k) else '⛔',
            'مدیریت': '✅' if can_edit(k) else '⛔',
        } for k, v in USER_DB.items()]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, height=320)

        if is_editor:
            st.divider()
            target = st.selectbox('انتخاب کاربر', list(USER_DB.keys()),
                                  format_func=lambda e: USER_DB[e]['name'] + ' - ' + e)
            new_pass = st.text_input('رمز جدید', type='password')
            if st.button('💾 ذخیره تغییرات', type='primary'):
                if new_pass.strip():
                    USER_DB[target]['password'] = new_pass.strip()
                    st.success('رمز کاربر به‌روزرسانی شد (تا پایان نشست فعال است).')
                else:
                    st.warning('رمز جدید را وارد کنید.')
        else:
            st.caption('✏️ تغییرات فقط توسط مالک سیستم امکان‌پذیر است.')

    st.divider()
    st.caption('آخرین به‌روزرسانی: ' + datetime.now().strftime('%Y-%m-%d %H:%M') +
               ' - سیمان تهران')


if __name__ == '__main__':
    main()
