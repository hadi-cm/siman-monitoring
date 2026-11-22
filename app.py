# -*- coding: utf-8 -*-
# =============================================================================
#  سامانه هوشمند پایش وضعیت - سیمان تهران
#  پایش برخط ارتعاش و دمای تجهیزات - نسخه جامع (اتصال به گوگل شیت)
#  اجرا:  streamlit run app.py
# =============================================================================
import os
import re
import urllib.parse
import html as html_lib
from datetime import datetime, timedelta, date

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title='سامانه هوشمند پایش وضعیت - سیمان تهران',
    page_icon='🏭',
    layout='wide',
)

# =============================================================================
# 1) پیکربندی
# =============================================================================
APP_TITLE = 'سامانه هوشمند پایش وضعیت - سیمان تهران'
SUB_TITLE = 'پایش برخط ارتعاش و دمای تجهیزات'
SITE_NAME = 'سیمان تهران'

LOGO_LEFT = 'my_logo.png'        # لوگوی پیمانکار / سازنده سیستم
LOGO_RIGHT = 'client_logo.png'   # لوگوی کارخانه سیمان تهران

# --- دیتابیس کاربران ---
USER_DB = {
    'cm.zandiyeh@gmail.com':         {'name': 'هادی زندیه',     'role': 'پیمانکار / مالک سیستم', 'password': 'siman123'},
    'vah.rezaei@gmail.com':          {'name': 'وحید رضایی',     'role': 'مدیر مکانیک',           'password': 'siman123'},
    'me.vibration.shokri@gmail.com': {'name': 'مهدی شکری',      'role': 'مدیر دفتر فنی',         'password': 'siman123'},
    'tehrancment@gmail.com':         {'name': 'سید مهدی حسینی', 'role': 'معاونت فنی',            'password': 'siman123'},
    'alireza76ir@gmail.com':         {'name': 'علیرضا',         'role': 'کارشناس',               'password': 'siman123'},
    'masoud.sa.1989823@gmail.com':   {'name': 'مسعود صمیمی',    'role': 'کارشناس',               'password': 'siman123'},
    'operator2@tehrancment.ir':      {'name': 'اپراتور خط ۲',   'role': 'کاربر',                 'password': 'siman123'},
}
OWNER_EMAIL = 'cm.zandiyeh@gmail.com'
SEND_ROLES = ('مدیر', 'معاونت', 'مالک')

# --- لینک شیت‌های گوگل (CSV منتشرشده) ---
BASE_CSV = ('https://docs.google.com/spreadsheets/d/e/'
            '2PACX-1vTI4vONsowudctVbskGkkSyQNqkkGZ8AuiykO9UKeE-8FSBZemWkR4q5DSAhpXEqwQkgsCUQy44Vvqx'
            '/pub?output=csv')
VIB_CSV_URL   = BASE_CSV                      # شیت ارتعاشات  (gid=0)
EQUIP_CSV_URL = BASE_CSV + '&gid=1728784730'  # شیت لیست تجهیزات

# --- نام ستون‌های داخلی ---
COL_DATE  = 'تاریخ'
COL_LINE  = 'خط تولید'
COL_UNIT  = 'واحد'
COL_EQUIP = 'عنوان تجهیز'
COL_H     = 'افقی'
COL_V     = 'عمودی'
COL_A     = 'محوری'
COL_T     = 'دما'
COL_S     = 'وضعیت'
COL_MAX   = 'حداکثر'

DISPLAY = {
    COL_DATE:  'تاریخ',
    COL_LINE:  'خط تولید',
    COL_UNIT:  'واحد',
    COL_EQUIP: 'عنوان تجهیز',
    COL_H:     'افقی (mm/s)',
    COL_V:     'عمودی (mm/s)',
    COL_A:     'محوری (mm/s)',
    COL_T:     'دما (°C)',
    COL_MAX:   'حداکثر (mm/s)',
    COL_S:     'وضعیت',
}

STATUS_EMOJI = {'نرمال': '🟢', 'هشدار': '🟡', 'بحرانی': '🔴'}

FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'

LINE_PRIORITY = ['خط تولید ۳', 'خط تولید ۴', 'خط تولید ۶',
                 'خط تولید ۷', 'خط تولید ۸', 'خط تولید ۹']
UNIT_PRIORITY = ['آسیاب سنگ', 'آسیاب مواد', 'کوره', 'آسیاب سیمان',
                 'بارگیرخانه تهران', 'بارگیرخانه ۶', 'بارگیرخانه ۹']

LINE_UNITS = {
    'خط تولید ۳': ['آسیاب سنگ', 'کوره', 'آسیاب سیمان'],
    'خط تولید ۴': ['آسیاب سنگ', 'آسیاب مواد', 'کوره', 'آسیاب سیمان'],
    'خط تولید ۶': ['آسیاب سنگ', 'آسیاب مواد', 'کوره', 'آسیاب سیمان', 'بارگیرخانه ۶'],
    'خط تولید ۷': ['آسیاب سیمان', 'بارگیرخانه تهران'],
    'خط تولید ۸': ['آسیاب سنگ', 'آسیاب مواد', 'کوره', 'آسیاب سیمان'],
    'خط تولید ۹': ['آسیاب سنگ', 'آسیاب مواد', 'کوره', 'آسیاب سیمان', 'بارگیرخانه ۹'],
}

UNIT_COMPONENTS = {
    'آسیاب سنگ': ['گیربکس اصلی', 'موتور اصلی', 'فن روغن‌کاری'],
    'آسیاب مواد': ['گیربکس اصلی', 'موتور اصلی', 'پینیون'],
    'کوره': ['گیربکس سمت کوه', 'گیربکس سمت شهر',
             'گیربکس سمت اور', 'موتور گیربکس باند برگشتی سمت اور'],
    'آسیاب سیمان': ['گیربکس سمت کوه', 'گیربکس سمت شهر',
                    'گیربکس سمت اور', 'موتور گیربکس باند برگشتی سمت اور',
                    'فن بگ‌هاوس'],
    'بارگیرخانه تهران': ['الواتور', 'کمپرسور'],
    'بارگیرخانه ۶': ['الواتور', 'کمپرسور'],
    'بارگیرخانه ۹': ['الواتور', 'کمپرسور'],
}


def can_send(email):
    role = USER_DB.get(email, {}).get('role', '')
    return any(k in role for k in SEND_ROLES)


def can_edit(email):
    return email == OWNER_EMAIL


# =============================================================================
# 2) ابزارهای متنی و عددی
# =============================================================================
def to_latin(v):
    """ارقام فارسی/عربی را به لاتین تبدیل می‌کند."""
    out = []
    for ch in str(v):
        if ch in FA_DIGITS:
            out.append(str(FA_DIGITS.index(ch)))
        elif '٠' <= ch <= '٩':
            out.append(str(ord(ch) - ord('٠')))
        else:
            out.append(ch)
    return ''.join(out)


def fa_num(v):
    """ارقام لاتین را به فارسی تبدیل می‌کند."""
    out = []
    for ch in str(v):
        out.append(FA_DIGITS[int(ch)] if ch.isdigit() else ch)
    return ''.join(out)


def norm_text(v):
    """کشیده، نیم‌فاصله و فاصله‌های اضافه را اصلاح می‌کند."""
    if pd.isna(v):
        return ''
    s = str(v).replace('ـ', '').replace('\u200c', ' ').replace('\xa0', ' ')
    return ' '.join(s.split()).strip()


def norm_line(v):
    s = to_latin(v).strip()
    digits = ''.join(filter(str.isdigit, s))
    if not digits:
        return norm_text(v)
    return 'خط تولید ' + fa_num(int(digits))


def norm_unit(v):
    s = norm_text(v)
    # «بارگیرخانه6» -> «بارگیرخانه 6»
    has_digit = any(ch.isdigit() for ch in s)
    if has_digit:
        s = re.sub(r'(?<=[^\d\s])(\d)', r' \1', s)
    return ' '.join(s.split())


NA_TOKENS = ('عدم دسترسی', 'دکوپل', 'دکوپل‌', 'قطع', 'ندارد', 'خراب',
             'بی‌مورد', 'بیمورد', 'نامشخص', '-', '—', '?', '؟')


def to_num(v):
    """مقدار عددی ایمن: ممیز شمسی، ارقام فارسی و متن‌های غیرعددی را مدیریت می‌کند."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    if isinstance(v, (int, float, np.integer, np.floating)):
        return float(v)
    s = to_latin(v).strip()
    if not s or s.lower() in ('nan', 'none', 'null'):
        return np.nan
    if any(tok in s for tok in NA_TOKENS):
        return np.nan
    s = s.replace('٫', '.').replace('،', '').replace(',', '').replace(' ', '')
    if s.count('/') == 1:
        a, b = s.split('/')
        if a.isdigit() and b.isdigit():
            s = a + '.' + b
    try:
        return float(s)
    except ValueError:
        m = re.search(r'-?\d+(?:\.\d+)?', s)
        return float(m.group()) if m else np.nan


def jalali_to_gregorian(jy, jm, jd):
    """تبدیل تاریخ شمسی به میلادی (الگوریتم jalaali)."""
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    days += (jm - 1) * 31 if jm < 7 else ((jm - 7) * 30) + 186

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


def parse_date(v):
    """تاریخ شمسی یا میلادی را به Timestamp میلادی تبدیل می‌کند."""
    if v is None:
        return pd.NaT
    if isinstance(v, pd.Timestamp):
        return v.normalize()
    if isinstance(v, (datetime, date)):
        return pd.Timestamp(v).normalize()

    s = to_latin(str(v)).strip()
    if not s or s.lower() in ('nan', 'none', 'nat'):
        return pd.NaT
    s = s.split('T')[0].split(' ')[0]
    s = s.replace('\\', '/').replace('-', '/').replace('.', '/')
    parts = [p for p in s.split('/') if p.strip() != '']
    if len(parts) < 3:
        return pd.NaT
    try:
        a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return pd.NaT

    if a > 1700:                       # تاریخ میلادی
        try:
            return pd.Timestamp(year=a, month=b, day=c)
        except ValueError:
            return pd.NaT
    if a < 100:                        # سال دو رقمی شمسی
        a += 1400
    gy, gm, gd = jalali_to_gregorian(a, b, c)
    try:
        return pd.Timestamp(year=gy, month=gm, day=gd)
    except ValueError:
        return pd.NaT


def ordered(items, priority):
    """مرتب‌سازی بر اساس اولویت کارخانه، سپس الفبایی."""
    clean = []
    for i in items:
        s = str(i)
        if s in ('nan', 'None', '', 'NaT') or s in clean:
            continue
        clean.append(s)
    head = [p for p in priority if p in clean]
    tail = sorted([i for i in clean if i not in priority])
    return head + tail


# =============================================================================
# 3) بارگذاری و پاکسازی داده
# =============================================================================
def build_sample_df():
    """داده نمونه فقط برای زمانی که اتصال به شیت برقرار نیست."""
    rng = np.random.default_rng(7)
    rows = []
    today = datetime.now().date()
    for line, units in LINE_UNITS.items():
        for unit in units:
            for eq in UNIT_COMPONENTS.get(unit, []):
                title = eq + ' - ' + unit
                base = rng.uniform(1.5, 8.0)
                for day in range(30):
                    h = base * rng.uniform(0.85, 1.9)
                    v = base * rng.uniform(0.85, 1.9)
                    a = base * rng.uniform(0.85, 1.9)
                    t = rng.uniform(45, 85)
                    rows.append({
                        COL_DATE: today - timedelta(days=29 - day),
                        COL_LINE: line,
                        COL_UNIT: unit,
                        COL_EQUIP: title,
                        COL_H: round(h, 2),
                        COL_V: round(v, 2),
                        COL_A: round(a, 2),
                        COL_T: round(t, 1),
                    })
    return pd.DataFrame(rows)


def map_columns(df):
    """نام ستون‌های شیت را به نام‌های داخلی نگاشت می‌کند."""
    ren = {}
    for c in df.columns:
        cs = norm_text(c)
        if not cs:
            continue
        if 'تاریخ' in cs:
            ren[c] = COL_DATE
        elif 'خط' in cs:
            ren[c] = COL_LINE
        elif 'واحد' in cs or 'بخش' in cs:
            ren[c] = COL_UNIT
        elif any(k in cs for k in ('تجهیز', 'دستگاه', 'ماشین', 'عنوان')):
            ren[c] = COL_EQUIP
        elif 'افقی' in cs or cs.upper().startswith('H'):
            ren[c] = COL_H
        elif 'عمودی' in cs or cs.upper().startswith('V'):
            ren[c] = COL_V
        elif 'محوری' in cs or 'شعاعی' in cs or cs.upper().startswith('A'):
            ren[c] = COL_A
        elif 'دما' in cs or 'حرارت' in cs:
            ren[c] = COL_T
    return df.rename(columns=ren)


@st.cache_data(ttl=300, show_spinner=False)
def load_all_data():
    """خواندن شیت ارتعاشات و شیت لیست تجهیزات از گوگل."""
    vib, assets, source = pd.DataFrame(), pd.DataFrame(), ''

    try:
        vib = pd.read_csv(VIB_CSV_URL)
        vib.columns = [str(c).strip() for c in vib.columns]
        vib = map_columns(vib)
        source = 'گوگل شیت (برخط)'
    except Exception as exc:
        vib = pd.DataFrame()
        source = 'داده نمونه — خطا در اتصال: ' + str(exc)[:90]

    try:
        assets = pd.read_csv(EQUIP_CSV_URL)
        assets.columns = [str(c).strip() for c in assets.columns]
        assets = map_columns(assets)
    except Exception:
        assets = pd.DataFrame()

    if vib.empty:
        vib = map_columns(build_sample_df())
        source = 'داده نمونه (اتصال به شیت برقرار نشد)'

    return vib, assets, source


def prepare(df):
    """پاکسازی، تبدیل تاریخ/عدد و تجمیع نقاط p1..p11 به ردیف روزانه."""
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    for col in (COL_H, COL_V, COL_A, COL_T):
        if col in df.columns:
            df[col] = df[col].map(to_num)
        else:
            df[col] = np.nan

    if COL_DATE not in df.columns:
        return pd.DataFrame()

    df[COL_DATE] = df[COL_DATE].map(parse_date)
    df = df.dropna(subset=[COL_DATE])

    for col in (COL_LINE, COL_UNIT, COL_EQUIP):
        df[col] = df[col].map(norm_text) if col in df.columns else ''

    df[COL_LINE] = df[COL_LINE].map(norm_line)
    df[COL_UNIT] = df[COL_UNIT].map(norm_unit)
    df[COL_EQUIP] = df[COL_EQUIP].map(norm_text)

    df = df[(df[COL_EQUIP] != '') | (df[COL_UNIT] != '')]

    keys = [COL_DATE, COL_LINE, COL_UNIT, COL_EQUIP]
    agg = (df.groupby(keys, as_index=False)[[COL_H, COL_V, COL_A, COL_T]]
             .max())

    agg[COL_MAX] = agg[[COL_H, COL_V, COL_A]].max(axis=1).round(2)
    agg[COL_MAX] = agg[COL_MAX].fillna(0)

    agg[COL_S] = np.select(
        [agg[COL_MAX] < 4.5, agg[COL_MAX] < 7.0],
        ['نرمال', 'هشدار'],
        default='بحرانی',
    )
    agg[COL_DATE] = agg[COL_DATE].dt.date
    return agg.sort_values([COL_DATE, COL_LINE, COL_UNIT],
                           ascending=[False, True, True]).reset_index(drop=True)


# =============================================================================
# 4) گزارش HTML قابل چاپ
# =============================================================================
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
    '.warn{color:#a15c00;font-weight:bold}'
    '</style>'
)


def build_report_html(df_report, meta):
    esc = html_lib.escape

    if df_report is None or df_report.empty:
        kpi_items = [('تعداد رکورد', '0'), ('میانگین ارتعاش افقی', '-'),
                     ('میانگین دما', '-'), ('تجهیزات بحرانی', '-')]
        table_html = '<p>برای این ترکیب فیلترها رکوردی یافت نشد.</p>'
    else:
        h_mean = df_report[COL_H].mean()
        t_mean = df_report[COL_T].mean()
        kpi_items = [
            ('تعداد رکورد', '{:,}'.format(len(df_report))),
            ('میانگین ارتعاش افقی',
             '-' if pd.isna(h_mean) else '{:.2f} mm/s'.format(h_mean)),
            ('میانگین دما',
             '-' if pd.isna(t_mean) else '{:.1f} °C'.format(t_mean)),
            ('تجهیزات بحرانی',
             '{:,}'.format(int((df_report[COL_S] == 'بحرانی').sum()))),
        ]

        show = df_report[[COL_DATE, COL_LINE, COL_UNIT, COL_EQUIP,
                          COL_H, COL_V, COL_A, COL_T, COL_MAX, COL_S]].copy()
        show = show.rename(columns=DISPLAY)
        cols = list(show.columns)

        head = ''.join('<th>' + esc(str(c)) + '</th>' for c in cols)
        body = ''
        for _, row in show.iterrows():
            cells = ''
            for c in cols:
                val = row[c]
                cell = esc(str(val))
                if c == DISPLAY[COL_S]:
                    if str(val) == 'بحرانی':
                        cell = '<span class="crit">' + cell + '</span>'
                    elif str(val) == 'هشدار':
                        cell = '<span class="warn">' + cell + '</span>'
                cells += '<td>' + cell + '</td>'
            body += '<tr>' + cells + '</tr>'
        table_html = ('<table><thead><tr>' + head + '</tr></thead><tbody>'
                      + body + '</tbody></table>')

    kpis = ''
    for label, value in kpi_items:
        kpis += ('<div class="kpi"><div class="v">' + esc(str(value)) + '</div>'
                 '<div class="l">' + esc(str(label)) + '</div></div>')

    info_lines = ''
    for key, value in meta.items():
        info_lines += ('<div><b>' + esc(str(key)) + ':</b> '
                       + esc(str(value)) + '</div>')

    return (
        "<!DOCTYPE html><html lang='fa' dir='rtl'><head><meta charset='utf-8'>"
        '<title>گزارش پایش ارتعاش - ' + SITE_NAME + '</title>'
        + REPORT_CSS + '</head><body>'
        '<h1>گزارش پایش وضعیت ارتعاش - ' + SITE_NAME + '</h1>'
        '<div class="sub">تاریخ گزارش: '
        + esc(datetime.now().strftime('%Y-%m-%d %H:%M')) + '</div>'
        '<div class="box">' + info_lines + '</div>'
        '<div class="kpis">' + kpis + '</div>'
        + table_html +
        '<div class="foot">این گزارش به‌صورت خودکار توسط سامانه پایش وضعیت '
        + SITE_NAME + ' تولید شده است.</div>'
        '</body></html>'
    )


def show_logo(path, fallback):
    if os.path.exists(path):
        st.image(path, use_container_width=True)
    else:
        st.markdown(
            "<div style='border:1px solid #d9e2ec;border-radius:10px;padding:14px;"
            "text-align:center;color:#5b6b7c;font-size:13px'>" + fallback + "</div>",
            unsafe_allow_html=True,
        )


# =============================================================================
# 5) هدر و لوگوها
# =============================================================================
c1, c2, c3 = st.columns([1, 3, 1])
with c1:
    show_logo(LOGO_LEFT, 'لوگوی شما')
with c2:
    st.markdown(
        "<h2 style='text-align:center;margin-bottom:0'>" + APP_TITLE + "</h2>"
        "<p style='text-align:center;color:#7a8794;font-size:13px;margin-top:4px'>"
        + SUB_TITLE + "</p>",
        unsafe_allow_html=True,
    )
with c3:
    show_logo(LOGO_RIGHT, SITE_NAME)

# =============================================================================
# 6) بارگذاری داده
# =============================================================================
with st.spinner('در حال دریافت داده از شیت...'):
    raw_df, asset_df, data_source = load_all_data()

df_all = prepare(raw_df)

if df_all.empty:
    st.error('داده‌ای برای نمایش وجود ندارد. اتصال به شیت یا نام ستون‌ها را بررسی کنید.')
    st.caption('منبع داده: ' + data_source)
    st.stop()

# ادغام لیست تجهیزات شیت دوم (اگر موجود بود)
if not asset_df.empty and COL_EQUIP in asset_df.columns:
    extra = asset_df[[c for c in (COL_LINE, COL_UNIT, COL_EQUIP)
                      if c in asset_df.columns]].copy()
    for col in (COL_LINE, COL_UNIT, COL_EQUIP):
        if col not in extra.columns:
            extra[col] = ''
    extra[COL_LINE] = extra[COL_LINE].map(norm_line)
    extra[COL_UNIT] = extra[COL_UNIT].map(norm_unit)
    extra[COL_EQUIP] = extra[COL_EQUIP].map(norm_text)
    extra = extra[extra[COL_EQUIP] != '']

    known = set(zip(df_all[COL_LINE], df_all[COL_UNIT], df_all[COL_EQUIP]))
    missing_rows = [r for r in extra.drop_duplicates().itertuples(index=False)
                    if (r[0], r[1], r[2]) not in known]
    if missing_rows:
        filler = pd.DataFrame([{
            COL_DATE: date(1900, 1, 1),
            COL_LINE: r[0], COL_UNIT: r[1], COL_EQUIP: r[2],
            COL_H: np.nan, COL_V: np.nan, COL_A: np.nan, COL_T: np.nan,
            COL_MAX: np.nan, COL_S: 'نرمال',
        } for r in missing_rows])
        df_all = pd.concat([df_all, filler], ignore_index=True)
        df_all = df_all.sort_values([COL_DATE, COL_LINE, COL_UNIT],
                                    ascending=[False, True, True])

# =============================================================================
# 7) ورود کاربران
# =============================================================================
if 'user' not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.divider()
    left, mid, right = st.columns([1, 2, 1])
    with mid:
        st.markdown('### 🔐 ورود به سامانه')
        with st.form('login_form'):
            email_in = st.text_input('ایمیل سازمانی', placeholder='name@example.com')
            password_in = st.text_input('رمز عبور', type='password')
            submitted = st.form_submit_button('ورود به داشبورد',
                                              use_container_width=True)
        if submitted:
            email_in = (email_in or '').strip().lower()
            if email_in in USER_DB and USER_DB[email_in]['password'] == password_in:
                st.session_state.user = email_in
                st.rerun()
            elif email_in and email_in not in USER_DB:
                st.error('این ایمیل در سامانه ثبت نشده است.')
            else:
                st.error('رمز عبور نادرست است.')
        st.caption('رمز پیش‌فرض تمام کاربران: siman123')
    st.stop()

user_email = st.session_state.user
user_info = USER_DB[user_email]
is_sender = can_send(user_email)
is_editor = can_edit(user_email)

# =============================================================================
# 8) نوار کاربر
# =============================================================================
st.divider()
u1, u2, u3, u4 = st.columns([3, 2, 1, 1])
with u1:
    st.markdown('👤 ' + user_info['name'] + ' &nbsp;—&nbsp; `' + user_email
                + '` &nbsp;|&nbsp; نقش: ' + user_info['role'])
with u2:
    st.caption('📨 ارسال اعلان: ' + ('✅' if is_sender else '⛔')
               + ' | ✏️ تغییر داده: ' + ('✅' if is_editor else '⛔'))
with u3:
    if st.button('🔄 بروزرسانی', use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with u4:
    if st.button('خروج', use_container_width=True):
        st.session_state.user = None
        st.rerun()

st.divider()

# =============================================================================
# 9) فیلترها
# =============================================================================
st.markdown('#### 🔎 فیلترها (خط تولید ➔ واحد ➔ تجهیز)')
st.caption('منبع داده: ' + data_source + ' | تعداد کل رکورد: '
           + '{:,}'.format(len(df_all)))

f1, f2, f3, f4, f5 = st.columns([2, 2, 3, 2, 2])

lines_available = ordered(df_all[COL_LINE].dropna().unique().tolist(), LINE_PRIORITY)
with f1:
    sel_line = st.selectbox('۱) خط تولید', ['همه خطوط'] + lines_available)

unit_src = df_all if sel_line == 'همه خطوط' else df_all[df_all[COL_LINE] == sel_line]
units_available = ordered(unit_src[COL_UNIT].dropna().unique().tolist(), UNIT_PRIORITY)

with f2:
    sel_unit = st.selectbox('۲) واحد', ['همه واحدها'] + units_available,
                            key='unit_of_' + sel_line)

eq_src = unit_src
if sel_unit != 'همه واحدها':
    eq_src = eq_src[eq_src[COL_UNIT] == sel_unit]
equips_available = ordered(eq_src[COL_EQUIP].dropna().unique().tolist(), [])

with f3:
    if not equips_available:
        sel_equip = []
        st.selectbox('۳) عنوان تجهیز', ['-'], disabled=True)
    elif len(equips_available) == 1:
        sel_equip = [st.selectbox('۳) عنوان تجهیز', equips_available,
                                  key='eq_single_' + sel_line + '_' + sel_unit)]
    else:
        sel_equip = st.multiselect(
            '۳) عنوان تجهیز',
            ['همه تجهیزات'] + equips_available,
            default=['همه تجهیزات'],
            key='eq_multi_' + sel_line + '_' + sel_unit,
        )

with f4:
    sel_status = st.multiselect('وضعیت', ['نرمال', 'هشدار', 'بحرانی'],
                                default=['هشدار', 'بحرانی'])

with f5:
    days = st.slider('بازه روزهای اخیر', 1, 90, 7)

path_parts = [sel_line]
if sel_unit != 'همه واحدها':
    path_parts.append(sel_unit)
if sel_equip and 'همه تجهیزات' not in sel_equip:
    path_parts.append('، '.join(sel_equip))
filter_path_text = ' ➔ '.join(path_parts)
st.caption('مسیر فیلتر: ' + filter_path_text)

# --- اعمال فیلترها ---
start_date = datetime.now().date() - timedelta(days=days - 1)
df = df_all[df_all[COL_DATE] >= start_date].copy()

if sel_line != 'همه خطوط':
    df = df[df[COL_LINE] == sel_line]
if sel_unit != 'همه واحدها':
    df = df[df[COL_UNIT] == sel_unit]
if sel_equip and 'همه تجهیزات' not in sel_equip:
    df = df[df[COL_EQUIP].isin(sel_equip)]
if sel_status:
    df = df[df[COL_S].isin(sel_status)]

filter_is_specific = (
    sel_line != 'همه خطوط'
    or sel_unit != 'همه واحدها'
    or (bool(sel_equip) and 'همه تجهیزات' not in sel_equip)
)

st.divider()

# =============================================================================
# 10) تب‌ها
# =============================================================================
tab1, tab2, tab3, tab4 = st.tabs(
    ['📋 جدول داده‌ها', '📈 نمودارها', '📨 ارسال اعلان', '👥 کاربران']
)

# ---------------------------- تب ۱: جدول ----------------------------
with tab1:
    st.markdown('تعداد رکوردها: **' + '{:,}'.format(len(df)) + '**')

    if df.empty:
        st.info('با این فیلترها رکوردی یافت نشد.')
    else:
        styled = df.copy()
        styled[COL_S] = styled[COL_S].map(lambda s: STATUS_EMOJI.get(s, '') + ' ' + str(s))
        styled = styled.rename(columns=DISPLAY)
        st.dataframe(styled, use_container_width=True, height=460)

        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                '⬇️ دانلود CSV',
                data=df.to_csv(index=False).encode('utf-8-sig'),
                file_name='vibration_data_' + datetime.now().strftime('%Y%m%d') + '.csv',
                mime='text/csv',
                use_container_width=True,
            )
        with d2:
            report_meta = {
                'مسیر فیلتر': filter_path_text,
                'بازه زمانی': str(days) + ' روز اخیر (از ' + str(start_date)
                              + ' تا ' + str(datetime.now().date()) + ')',
                'وضعیت‌های انتخابی': '، '.join(sel_status) if sel_status else 'همه',
                'تهیه‌کننده': user_info['name'] + ' - ' + user_info['role'],
            }
            st.download_button(
                '🧾 دانلود گزارش (HTML قابل چاپ به PDF)',
                data=build_report_html(df, report_meta).encode('utf-8'),
                file_name='vibration_report_' + datetime.now().strftime('%Y%m%d_%H%M') + '.html',
                mime='text/html',
                use_container_width=True,
            )
        st.caption('برای PDF: فایل گزارش را در مرورگر باز کنید و با Ctrl+P '
                   'گزینه Save as PDF را انتخاب کنید.')

# ---------------------------- تب ۲: نمودارها ----------------------------
with tab2:
    if df.empty:
        st.info('داده‌ای برای نمودار نیست.')
    elif not filter_is_specific:
        st.info('📌 ابتدا از نوار فیلترها «خط تولید» یا «واحد» یا «تجهیز» را '
                'انتخاب کنید تا نمودارها نمایش داده شوند.')
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric('میانگین افقی', '{:.2f} mm/s'.format(df[COL_H].mean()))
        m2.metric('میانگین عمودی', '{:.2f} mm/s'.format(df[COL_V].mean()))
        m3.metric('میانگین دما', '{:.1f} °C'.format(df[COL_T].mean()))
        m4.metric('تجهیزات بحرانی', '{:,}'.format(int((df[COL_S] == 'بحرانی').sum())))

        daily = (df.groupby(COL_DATE)[[COL_H, COL_V, COL_A]].mean()
                   .reset_index().sort_values(COL_DATE))
        fig = go.Figure()
        for col, color in ((COL_H, '#0b3c6b'), (COL_V, '#1f8a70'), (COL_A, '#b3261e')):
            fig.add_trace(go.Scatter(x=daily[COL_DATE], y=daily[col],
                                     mode='lines+markers', name=DISPLAY[col],
                                     line=dict(color=color, width=2)))
        fig.add_hline(y=4.5, line_dash='dash', line_color='#e0a100',
                      annotation_text='هشدار 4.5')
        fig.add_hline(y=7.0, line_dash='dash', line_color='#b3261e',
                      annotation_text='بحرانی 7.0')
        fig.update_layout(title='روند میانگین ارتعاش روزانه (mm/s)',
                          template='plotly_white', height=420,
                          legend=dict(orientation='h', y=1.1))
        st.plotly_chart(fig, use_container_width=True)

        cA, cB = st.columns([3, 2])
        with cA:
            worst = (df.groupby(COL_EQUIP)[COL_MAX].max()
                       .sort_values(ascending=False).head(12).reset_index())
            fig2 = px.bar(worst, x=COL_MAX, y=COL_EQUIP, orientation='h',
                          title='۱۲ تجهیز با بیشترین ارتعاش',
                          color=COL_MAX, color_continuous_scale='Reds',
                          template='plotly_white')
            fig2.update_layout(height=430, yaxis_title='', xaxis_title='mm/s',
                               coloraxis_showscale=False)
            st.plotly_chart(fig2, use_container_width=True)

        with cB:
            share = df[COL_S].value_counts().reset_index()
            share.columns = ['وضعیت', 'تعداد']
            fig3 = px.pie(share, names='وضعیت', values='تعداد', hole=0.55,
                          title='سهم وضعیت‌ها',
                          color='وضعیت',
                          color_discrete_map={'نرمال': '#1f8a70',
                                              'هشدار': '#e0a100',
                                              'بحرانی': '#b3261e'})
            fig3.update_layout(height=430)
            st.plotly_chart(fig3, use_container_width=True)

        temp = (df.groupby(COL_DATE)[COL_T].mean()
                  .reset_index().sort_values(COL_DATE))
        fig4 = px.line(temp, x=COL_DATE, y=COL_T, markers=True,
                       title='روند میانگین دمای بلبرینگ (°C)',
                       template='plotly_white')
        fig4.update_layout(height=360, yaxis_title='°C', xaxis_title='')
        st.plotly_chart(fig4, use_container_width=True)

# ---------------------------- تب ۳: اعلان ----------------------------
with tab3:
    crit = df[df[COL_S] == 'بحرانی'].sort_values(COL_MAX, ascending=False)

    st.markdown('#### 🔴 تجهیزات نیازمند توجه')
    if crit.empty:
        st.success('در این بازه تجهیز بحرانی وجود ندارد.')
    else:
        show = crit[[COL_LINE, COL_UNIT, COL_EQUIP, COL_H, COL_V, COL_A,
                     COL_T, COL_S]].rename(columns=DISPLAY)
        st.dataframe(show, use_container_width=True, height=280)

    st.divider()
    st.markdown('#### 📨 پیش‌نویس اعلان')

    all_emails = list(USER_DB.keys())
    recipients = st.multiselect(
        'گیرندگان', all_emails, default=all_emails,
        format_func=lambda e: USER_DB[e]['name'] + ' - ' + e,
    )
    subject = st.text_input(
        'موضوع',
        'هشدار ارتعاش - ' + SITE_NAME + ' - ' + datetime.now().strftime('%Y/%m/%d'),
    )

    if crit.empty:
        body = 'در بازه انتخاب‌شده تجهیز بحرانی گزارش نشده است.'
    else:
        top = crit.head(10)
        lines = [
            'گزارش وضعیت تجهیزات بحرانی - ' + datetime.now().strftime('%Y/%m/%d'),
            'بازه: ' + str(days) + ' روز اخیر | فیلتر: ' + filter_path_text
            + ' | تعداد بحرانی: ' + str(len(crit)),
            '',
            'بدترین تجهیزات نیازمند توجه:',
        ]
        for i, (_, r) in enumerate(top.iterrows(), 1):
            lines.append(
                '{}. {} ({} / {}) - افقی {} | عمودی {} | محوری {} | دما {}°C'.format(
                    i, r[COL_EQUIP], r[COL_LINE], r[COL_UNIT],
                    r[COL_H], r[COL_V], r[COL_A], r[COL_T])
            )
        lines += ['', 'ارسال‌کننده: ' + user_info['name'] + ' - ' + user_info['role']]
        body = '\n'.join(lines)

    body = st.text_area('متن پیام', body, height=240)

    b1, b2 = st.columns(2)
    with b1:
        if is_sender:
            if st.button('📨 ثبت و ارسال اعلان', type='primary',
                         use_container_width=True):
                st.session_state.setdefault('sent_log', []).append({
                    'زمان': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'فرستنده': user_info['name'],
                    'موضوع': subject,
                    'گیرندگان': '، '.join(USER_DB[e]['name'] for e in recipients),
                    'تعداد بحرانی': len(crit),
                })
                st.success('اعلان برای ' + str(len(recipients))
                           + ' گیرنده ثبت شد (شبیه‌سازی ارسال).')
        else:
            st.button('📨 ارسال اعلان', disabled=True, use_container_width=True)
            st.caption('⛔ شما مجوز ارسال اعلان ندارید - مشاهده باز است، '
                       'ارسال فقط برای مدیران.')

    with b2:
        if recipients:
            mailto = ('mailto:' + ';'.join(recipients)
                      + '?subject=' + urllib.parse.quote(subject)
                      + '&body=' + urllib.parse.quote(body))
            st.markdown(
                '<a href="' + mailto + '" target="_blank" style="display:block;'
                'text-align:center;padding:9px;border:1px solid #0b3c6b;'
                'border-radius:8px;color:#0b3c6b;text-decoration:none">'
                '✉️ باز کردن در برنامه ایمیل</a>',
                unsafe_allow_html=True,
            )
        st.download_button('⬇️ دانلود متن اعلان',
                           data=(subject + '\n\n' + body).encode('utf-8-sig'),
                           file_name='notification.txt', mime='text/plain',
                           use_container_width=True)

    st.divider()
    st.markdown('#### 📜 تاریخچه اعلان‌ها')
    log = st.session_state.get('sent_log', [])
    if log:
        log_df = pd.DataFrame(log)
        st.dataframe(log_df, use_container_width=True)
        st.download_button(
            '⬇️ دانلود تاریخچه CSV',
            data=log_df.to_csv(index=False).encode('utf-8-sig'),
            file_name='notification_history.csv',
            mime='text/csv',
        )
    else:
        st.caption('هنوز اعلانی ارسال نشده است.')

# ---------------------------- تب ۴: کاربران ----------------------------
with tab4:
    st.markdown('#### 👥 کاربران سامانه')
    rows = [{
        'نام': v['name'],
        'ایمیل': k,
        'نقش': v['role'],
        'رمز': v['password'] if is_editor else '••••••••',
        'ارسال اعلان': '✅' if can_send(k) else '⛔',
        'مالک سیستم': '✅' if can_edit(k) else '—',
    } for k, v in USER_DB.items()]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=320)

    if is_editor:
        st.divider()
        st.markdown('#### ✏️ ویرایش رمز کاربر')
        target = st.selectbox(
            'کاربر', list(USER_DB.keys()),
            format_func=lambda e: USER_DB[e]['name'] + ' - ' + e,
        )
        new_pass = st.text_input('رمز جدید', type='password')
        if st.button('💾 ذخیره تغییرات', type='primary'):
            if new_pass.strip():
                USER_DB[target]['password'] = new_pass.strip()
                st.success('رمز کاربر به‌روزرسانی شد.')
            else:
                st.warning('رمز جدید را وارد کنید.')
        st.caption('⚠️ تغییر رمز تا زمان بازنشانی برنامه (Reboot) معتبر است. '
                   'برای دائمی‌شدن، مقدار password را در کد USER_DB اصلاح کنید.')
    else:
        st.caption('✏️ تغییر داده‌ها فقط توسط مالک سیستم امکان‌پذیر است.')

# =============================================================================
st.divider()
st.caption('آخرین به‌روزرسانی: ' + datetime.now().strftime('%Y-%m-%d %H:%M')
           + ' - ' + SITE_NAME)
