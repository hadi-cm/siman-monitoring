import os
import html as html_lib
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import streamlit as st
st.set_page_config(
    page_title='سیستم هوشمند پایش وضعیت-سیمان تهران',
    page_icon='📊',
    layout='wide',
)
APP_TITLE = 'سیستم هوشمند پایش وضعیت-سیمان تهران'
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

def can_send(email):
    role = USER_DB.get(email, {}).get('role', '')
    return any(k in role for k in SEND_ROLES)

def can_edit(email):
    return email == OWNER_EMAIL

EXCEL_FILE = 'data.xlsx'
SHEET_NAME = 'ارتعاشات'
COL_DATE = 'تاریخ'
COL_LINE = 'خط تولید'
COL_UNIT = 'واحد'
COL_EQUIP = 'عنوان تجهیز'
COL_H = 'ارتعاش افقی (mm/s)'
COL_V = 'ارتعاش عمودی (mm/s)'
COL_A = 'ارتعاش محوری (mm/s)'
COL_T = 'دمای بلبرینگ (°C)'
COL_S = 'وضعیت'
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
    'کوره': ['گیربکس سمت کوه', 'گیربکس سمت شهر', 'گیربکس سمت اور',
             'موتور گیربکس باند برگشتی سمت اور'],
    'آسیاب سیمان': ['گیربکس سمت کوه', 'گیربکس سمت شهر', 'گیربکس سمت اور',
                    'موتور گیربکس باند برگشتی سمت اور', 'فن بگ‌هاوس'],
    'بارگیرخانه تهران': ['الواتور', 'کمپرسور'],
    'بارگیرخانه ۶': ['الواتور', 'کمپرسور'],
    'بارگیرخانه ۹': ['الواتور', 'کمپرسور'],
}

def build_sample_df():
    rng = np.random.default_rng(7)
    rows = []
    start = datetime.now() - timedelta(days=29)
    for line, units in LINE_UNITS.items():
        for unit in units:
            for eq in UNIT_COMPONENTS[unit]:
                title = eq + ' - ' + unit
                base = rng.uniform(1.5, 8.0)
                for day in range(30):
                    amp_h = base * rng.uniform(0.85, 1.9)
                    amp_v = base * rng.uniform(0.85, 1.9)
                    amp_a = base * rng.uniform(0.85, 1.9)
                    temp = rng.uniform(45, 85)
                    worst = max(amp_h, amp_v, amp_a)
                    if worst < 4.5:
                        status = 'نرمال'
                    elif worst < 7.0:
                        status = 'هشدار'
                    else:
                        status = 'بحرانی'
                    rows.append({
                        COL_DATE: (start + timedelta(days=day)).date(),
                        COL_LINE: line,
                        COL_UNIT: unit,
                        COL_EQUIP: title,
                        COL_H: round(amp_h, 2),
                        COL_V: round(amp_v, 2),
                        COL_A: round(amp_a, 2),
                        COL_T: round(temp, 1),
                        COL_S: status,
                    })
    return pd.DataFrame(rows)


@st.cache_data
def load_data():
    for fname in (EXCEL_FILE, 'ارتعاشات.xlsx', 'ارتعاشات.xls'):
        if os.path.exists(fname):
            try:
                xls = pd.ExcelFile(fname)
                sheet = SHEET_NAME if SHEET_NAME in xls.sheet_names else xls.sheet_names[0]
                raw = pd.read_excel(xls, sheet_name=sheet)
                return raw, 'فایل ' + fname + ' / شیت ' + sheet
            except Exception as exc:
                return build_sample_df(), 'خطا در خواندن فایل: ' + str(exc)
    return build_sample_df(), 'داده نمونه (فایل اکسل پیدا نشد)'


def prepare(df):
    df = df.copy()
    df[COL_DATE] = pd.to_datetime(df[COL_DATE], errors='coerce').dt.date
    for col in (COL_H, COL_V, COL_A, COL_T):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    for col in (COL_LINE, COL_UNIT, COL_EQUIP):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    if COL_S not in df.columns:
        worst = df[[COL_H, COL_V, COL_A]].max(axis=1, skipna=True)
        df[COL_S] = np.select([worst < 4.5, worst < 7.0],
                              ['نرمال', 'هشدار'], default='بحرانی')
    return df


raw_df, data_source = load_data()
df_all = prepare(raw_df)

missing = [c for c in (COL_DATE, COL_LINE, COL_UNIT, COL_EQUIP)
           if c not in df_all.columns]

STATUS_EMOJI = {'نرمال': '🟢', 'هشدار': '🟡', 'بحرانی': '🔴'}


def ordered(items, priority):
    clean = []
    for i in items:
        s = str(i)
        if s not in ('nan', 'None', '') and s not in clean:
            clean.append(s)
    head = [p for p in priority if p in clean]
    tail = sorted([i for i in clean if i not in priority])
    return head + tail


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
    '</style>'
)


def build_report_html(df_report, meta):
    esc = html_lib.escape

    if df_report.empty:
        kpi_items = [('تعداد رکورد', '0'), ('میانگین ارتعاش افقی', '-'),
                     ('میانگین دما', '-'), ('تجهیزات بحرانی', '-')]
        table_html = '<p>برای این ترکیب فیلترها رکوردی یافت نشد.</p>'
    else:
        kpi_items = [
            ('تعداد رکورد', '{:,}'.format(len(df_report))),
            ('میانگین ارتعاش افقی', '{:.2f} mm/s'.format(df_report[COL_H].mean())),
            ('میانگین دما', '{:.1f} °C'.format(df_report[COL_T].mean())),
            ('تجهیزات بحرانی', '{:,}'.format(int((df_report[COL_S] == 'بحرانی').sum()))),
        ]
        cols = list(df_report.columns)
        head = ''.join('<th>' + esc(str(c)) + '</th>' for c in cols)
        body = ''
        for _, row in df_report.iterrows():
            cells = ''
            for c in cols:
                val = row[c]
                cell = esc(str(val))
                if c == COL_S and str(val) == 'بحرانی':
                    cell = '<span class=\"crit\">' + cell + '</span>'
                cells += '<td>' + cell + '</td>'
            body += '<tr>' + cells + '</tr>'
        table_html = ('<table><thead><tr>' + head + '</tr></thead><tbody>'
                      + body + '</tbody></table>')

    kpis = ''
    for label, value in kpi_items:
        kpis += '<div class=\"kpi\"><div class=\"v\">' + esc(value) + '</div>'
        kpis += '<div class=\"l\">' + esc(label) + '</div></div>'

    info_lines = ''
    for key, value in meta.items():
        info_lines += '<div><b>' + esc(str(key)) + ':</b> ' + esc(str(value)) + '</div>'

    return (
        "<!DOCTYPE html><html lang='fa' dir='rtl'><head><meta charset='utf-8'>"
        '<title>گزارش پایش ارتعاش - سیمان تهران</title>' + REPORT_CSS + '</head><body>'
        '<h1>گزارش پایش وضعیت ارتعاش - سیمان تهران</h1>'
        '<div class=\"sub\">تاریخ گزارش: ' + esc(datetime.now().strftime('%Y-%m-%d %H:%M')) + '</div>'
        '<div class=\"box\">' + info_lines + '</div>'
        '<div class=\"kpis\">' + kpis + '</div>'
        + table_html +
        '<div class=\"foot\">این گزارش به‌صورت خودکار توسط سامانه پایش وضعیت تولید شده است.</div>'
        '</body></html>'
    )


def logo(path, fallback):
    if os.path.exists(path):
        st.image(path, use_container_width=True)
    else:
        st.markdown(
            "<div style='border:1px solid #d9e2ec;border-radius:10px;padding:14px;"
            "text-align:center;color:#5b6b7c;font-size:13px'>\" + fallback + '</div>',
            unsafe_allow_html=True,
        )


c1, c2, c3 = st.columns([1, 3, 1])
with c1:
    logo('my_logo.png', 'لوگوی شما')
with c2:
    st.markdown(
        "<h2 style='text-align:center;color:#0b3c6b;margin-bottom:0'>\" + APP_TITLE + '</h2>'
        "<p style='text-align:center;color:#7a8794;font-size:13px;margin-top:4px'>\"
        'پایش برخط ارتعاش و دمای تجهیزات</p>',
        unsafe_allow_html=True,
    )
with c3:
    logo('client_logo.png', 'سیمان تهران')


if 'user' not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.markdown('### 🔐 ورود به سامانه')
    with st.form('login_form'):
        email = st.text_input('ایمیل سازمانی', placeholder='name@example.com')
        password = st.text_input('رمز عبور', type='password')
        submitted = st.form_submit_button('ورود به داشبورد', use_container_width=True)

    if submitted:
        email = (email or '').strip().lower()
        if email in USER_DB and USER_DB[email]['password'] == password:
            st.session_state.user = email
            st.rerun()
        elif email and email not in USER_DB:
            st.error('این ایمیل در سامانه ثبت نشده است.')
        else:
            st.error('رمز عبور نادرست است.')

    st.caption('رمز پیش‌فرض تمام کاربران: siman123')
    st.stop()


user_email = st.session_state.user
user_info = USER_DB[user_email]
is_sender = can_send(user_email)
is_editor = can_edit(user_email)


u1, u2, u3 = st.columns([3, 2, 1])
with u1:
    st.markdown(
        '👤 ' + user_info['name'] + ' &nbsp;—&nbsp; `' + user_email +
        '` &nbsp;|&nbsp; نقش: ' + user_info['role'] + ''
    )
with u2:
    st.caption(
        '📨 ارسال اعلان: ' + ('✅' if is_sender else '⛔') +
        ' | ✏️ تغییر داده: ' + ('✅' if is_editor else '⛔')
    )
with u3:
    if st.button('خروج', use_container_width=True):
        st.session_state.user = None
        st.rerun()

st.divider()

if missing:
    st.error('این ستون‌ها در شیت پیدا نشد: ' + '، '.join(missing) +
             ' - نام ستون‌ها را در بالای کد اصلاح کنید.')
    st.stop()


st.markdown('#### 🔎 فیلترها (خط تولید ➔ واحد ➔ تجهیز)')
st.caption('منبع داده: ' + data_source)

f1, f2, f3, f4, f5 = st.columns([2, 2, 3, 2, 2])

lines_available = ordered(df_all[COL_LINE].dropna().unique().tolist(), LINE_PRIORITY)
with f1:
    sel_line = st.selectbox('۱) خط تولید', ['همه خطوط'] + lines_available)

if sel_line == 'همه خطوط':
    unit_src = df_all
else:
    unit_src = df_all[df_all[COL_LINE] == sel_line]

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
    sel_status = st.multiselect(
        'وضعیت', ['نرمال', 'هشدار', 'بحرانی'], default=['هشدار', 'بحرانی']
    )

with f5:
    days = st.slider('بازه روزهای اخیر', 1, 30, 7)

path_parts = [sel_line]
if sel_unit != 'همه واحدها':
    path_parts.append(sel_unit)
if sel_equip and 'همه تجهیزات' not in sel_equip:
    path_parts.append('، '.join(sel_equip))
filter_path_text = ' ➔ '.join(path_parts)
st.caption('مسیر فیلتر: ' + filter_path_text)

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


tab1, tab2, tab3, tab4 = st.tabs(
    ['📋 جدول داده‌ها', '📈 نمودارها', '📨 ارسال اعلان', '👥 کاربران']
)

with tab1:
    st.markdown('تعداد رکوردها: ' + '{:,}'.format(len(df)))

    if df.empty:
        st.info('با این فیلترها رکوردی یافت نشد.')
    else:
        styled = df.copy()
        styled[COL_S] = styled[COL_S].map(lambda s: STATUS_EMOJI.get(s, '') + ' ' + str(s))
        st.dataframe(styled, use_container_width=True, height=460)

        d1, d2 = st.columns(2)

        with d1:
            st.download_button(
                '⬇️ دانلود CSV',
                data=df.to_csv(index=False).encode('utf-8-sig'),
                file_name='vibration_data.csv',
                mime='text/csv',
                use_container_width=True,
            )

        with d2:
            report_meta = {
                'مسیر فیلتر': filter_path_text,
                'بازه زمانی': str(days) + ' روز اخیر (از ' + str(start_date) +
                              ' تا ' + str(datetime.now().date()) + ')',
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

        st.caption('برای PDF: فایل گزارش را در مرورگر باز کنید و با Ctrl+P گزینه Save as PDF را بزنید.')

with tab2:
    if df.empty:
        st.info('داده‌ای برای نمودار نیست.')
    elif not filter_is_specific:
        st.info('📌 ابتدا از نوار فیلترها «خط تولید» یا «واحد» یا «تجهیز» را انتخاب کنید تا نمودارها نمایش داده شوند.')
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric('میانگین ارتعاش افقی', '{:.2f} mm/s'.format(df[COL_H].mean()))
        m2.metric('میانگین ارتعاش عمودی', '{:.2f} mm/s'.format(df[COL_V].mean()))
        m3.metric('میانگین دما', '{:.1f} °C'.format(df[COL_T].mean()))
        m4.metric('تجهیزات بحرانی', int((df[COL_S] == 'بحرانی').sum()))

        daily = df.groupby(COL_DATE)[[COL_H, COL_V, COL_A]].mean()
        st.markdown('روند میانگین ارتعاش روزانه')
        st.line_chart(daily)

        st.markdown('میانگین دما بر اساس تجهیز')
        st.bar_chart(df.groupby(COL_EQUIP)[COL_T].mean())

with tab3:
    crit = df[df[COL_S] == 'بحرانی'].sort_values(COL_H, ascending=False)

    st.markdown('تجهیزات نیازمند توجه (بحرانی)')
    if crit.empty:
        st.success('در این بازه تجهیز بحرانی وجود ندارد.')
    else:
        show = crit[[COL_LINE, COL_UNIT, COL_EQUIP, COL_H, COL_V, COL_T, COL_S]]
        st.dataframe(show, use_container_width=True, height=280)

    st.markdown('پیش‌نویس اعلان')
    all_emails = list(USER_DB.keys())
    recipients = st.multiselect(
        'گیرندگان', all_emails, default=all_emails,
        format_func=lambda e: USER_DB[e]['name'] + ' - ' + e,
    )

    subject = st.text_input(
        'موضوع', 'هشدار ارتعاش - سیمان تهران - ' + datetime.now().strftime('%Y/%m/%d')
    )

    if crit.empty:
        body = 'در بازه انتخاب‌شده تجهیز بحرانی گزارش نشده است.'
    else:
        top = crit.head(10)
        lines = [
            'گزارش وضعیت تجهیزات بحرانی - ' + datetime.now().strftime('%Y/%m/%d'),
            'بازه: ' + str(days) + ' روز اخیر | فیلتر: ' + filter_path_text +
            ' | تعداد بحرانی: ' + str(len(crit)),
            '',
            'بدترین تجهیزات نیازمند توجه:',
        ]
        for i, (_, r) in enumerate(top.iterrows(), 1):
            lines.append(
                str(i) + '. ' + str(r[COL_EQUIP]) + ' (' + str(r[COL_LINE]) +
                ' / ' + str(r[COL_UNIT]) + ') - افقی ' + str(r[COL_H]) +
                ' | عمودی ' + str(r[COL_V]) + ' | دما ' + str(r[COL_T]) + '°C'
            )
        lines += ['', 'ارسال‌کننده: ' + user_info['name'] + ' - ' + user_info['role']]
        body = chr(10).join(lines)

    body = st.text_area('متن پیام', body, height=240)

    if is_sender:
        if st.button('📨 ارسال اعلان', type='primary', use_container_width=True):
            st.session_state.setdefault('sent_log', []).append({
                'زمان': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'فرستنده': user_info['name'],
                'موضوع': subject,
                'گیرندگان': '، '.join(USER_DB[e]['name'] for e in recipients),
                'تعداد بحرانی': len(crit),
            })
            st.success('اعلان برای ' + str(len(recipients)) + ' گیرنده ثبت شد (شبیه‌سازی ارسال).')
    else:
        st.button('📨 ارسال اعلان', disabled=True, use_container_width=True)
        st.caption('⛔ شما مجوز ارسال اعلان ندارید - مشاهده باز است، ارسال فقط برای مدیران.')

    st.divider()
    st.markdown('تاریخچه اعلان‌ها')
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

with tab4:
    st.markdown('کاربران سامانه')
    rows = [{
        'نام': v['name'],
        'ایمیل': k,
        'نقش': v['role'],
        'رمز': v['password'] if is_editor else '••••••••',
        'ارسال اعلان': '✅' if can_send(k) else '⛔',
    } for k, v in USER_DB.items()]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=320)

    if is_editor:
        st.markdown('ویرایش رمز کاربر')
        target = st.selectbox(
            'کاربر', list(USER_DB.keys()),
            format_func=lambda e: USER_DB[e]['name'] + ' - ' + e,
        )
        new_pass = st.text_input('رمز جدید', type='password')
        if st.button('ذخیره تغییرات', type='primary'):
            if new_pass.strip():
                USER_DB[target]['password'] = new_pass.strip()
                st.success('رمز کاربر به‌روزرسانی شد.')
            else:
                st.warning('رمز جدید را وارد کنید.')
    else:
        st.caption('✏️ تغییر داده‌ها فقط توسط مالک سیستم امکان‌پذیر است.')

st.divider()
st.caption('آخرین به‌روزرسانی: ' + datetime.now().strftime('%Y-%m-%d %H:%M') + ' - سیمان تهران')
"/>
