# -*- coding: utf-8 -*-
"""
==============================================================================
 سیستم هوشمند پایش وضعیت - سیمان تهران
 نسخه 7.5  |  Vibration Condition Monitoring Dashboard
------------------------------------------------------------------------------
 قوانین دسترسی (طبق درخواست کارفرما):
   1) شفافیت کامل: همه کاربران همه تب‌ها و همه داده‌ها را می‌بینند.
   2) ارسال اعلان: فقط «مدیران» (و مالک سیستم) می‌توانند دکمه ارسال را بزنند.
   3) تغییر داده‌ها / ایمیل‌ها / رمزها: فقط «سوپرادمین» = cm.zandiyeh@gmail.com
   4) مدیران هیچ حق تغییری در داده‌ها و کاربران ندارند، فقط ارسال فایل/اعلان.

 نصب پیش‌نیازها:
   pip install streamlit pandas plotly
 اجرا:
   streamlit run vibration_monitor_tehran_cement_v7_5.py

 فایل‌های کنار کد:
   client_logo.png   -> لوگوی سیمان تهران (سمت راست هدر)
   my_logo.png       -> لوگوی شخصی (سمت چپ هدر)
==============================================================================
"""

import os
import io
import base64
import random
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    HAS_SMTP = True
except Exception:
    HAS_SMTP = False

# ============================================================================
#  تنظیمات پایه
# ============================================================================
APP_TITLE = "سیستم هوشمند پایش وضعیت-سیمان تهران"
APP_SUB = "پایش ارتعاشات و آنالیز وضعیت تجهیزات دوار"
CLIENT_LOGO_FILE = "client_logo.png"
MY_LOGO_FILE = "my_logo.png"
DEFAULT_PASSWORD = "siman123"

# ایمیل پذیرفته‌شده حتی با تایپ اشتباه کاربر
EMAIL_ALIASES = {
    "tehrancement@tehrancement.ir": "tehrancment@tehrancement.ir",
    "tehrancment@gmail.com": "tehrancment@tehrancement.ir",
    "tehrancement@tehrancement.ir": "tehrancment@tehrancement.ir",
    "me.vibration.shokri@gmail.com": "me.vibration.shokri@tehrancement.ir",
    "vah.rezaei@gmail.com": "vah.rezaei@tehrancement.ir",
}

DEFAULT_USERS = [
    {"email": "cm.zandiyeh@gmail.com",          "name": "هادی زندیه",       "role": "سوپرادمین", "duty": "پیمانکار خدمات / مالک سیستم", "password": "siman123"},
    {"email": "vah.rezaei@tehrancement.ir",     "name": "وحید رضایی",       "role": "مدیر",      "duty": "مدیر تعمیرات و نگهداری",     "password": "siman123"},
    {"email": "me.vibration.shokri@tehrancement.ir", "name": "مهدی شکری",   "role": "مدیر",      "duty": "مدیر پایش وضعیت",            "password": "siman123"},
    {"email": "tehrancment@tehrancement.ir",    "name": "دفتر فنی سیمان تهران", "role": "مدیر",  "duty": "مدیر فنی کارخانه",           "password": "siman123"},
    {"email": "a.karimi@tehrancement.ir",       "name": "علیرضا کریمی",     "role": "کاربر",     "duty": "کارشناس ارتعاشات",           "password": "siman123"},
    {"email": "s.mousavi@tehrancement.ir",      "name": "سعید موسوی",       "role": "کاربر",     "duty": "سرپرست شیفت مکانیک",         "password": "siman123"},
    {"email": "f.ahmadi@tehrancement.ir",       "name": "فاطمه احمدی",      "role": "کاربر",     "duty": "کارشناس دفتر فنی",           "password": "siman123"},
]

# آیا سوپرادمین (مالک سیستم) هم حق ارسال اعلان داشته باشد؟
ALLOW_SUPERADMIN_SEND = True

# ============================================================================
#  ساختار خطوط و تجهیزات
# ============================================================================
LINES = {
    "خط ۱": {
        "آسیاب مواد": ["آسیاب مواد ۱", "آسیاب مواد ۲"],
        "کوره و پخت": ["کوره ۱", "خنک‌کن ۱", "فن دودکش ۱"],
        "آسیاب سیمان": ["آسیاب سیمان ۱", "آسیاب سیمان ۲"],
    },
    "خط ۲": {
        "آسیاب مواد": ["آسیاب مواد ۳"],
        "کوره و پخت": ["کوره ۲", "خنک‌کن ۲", "فن دودکش ۲"],
        "آسیاب سیمان": ["آسیاب سیمان ۳", "آسیاب سیمان ۴"],
    },
    "خط ۳ (توسعه)": {
        "سنگ‌شکن": ["سنگ‌شکن چکشی ۳", "نوار نقاله اصلی ۳"],
        "آسیاب سیمان": ["آسیاب سیمان ۵", "سپراتور ۵"],
    },
}

POINTS = ["موتور اصلی", "گیربکس", "یاتاقان محرک", "فن خنک‌کن"]

STATUS_ORDER = ["سالم", "هشدار", "بحرانی", "پایش ویژه", "در حال تعمیر", "خارج از سرویس"]
STATUS_COLORS = {
    "سالم": "#2e9e5b",
    "هشدار": "#f2b134",
    "بحرانی": "#d9534f",
    "پایش ویژه": "#4a7bd6",
    "در حال تعمیر": "#8e6bd1",
    "خارج از سرویس": "#7a7a7a",
}

# ============================================================================
#  تبدیل تاریخ میلادی به شمسی
# ============================================================================
def g2j(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100)
            + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1])
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


# ============================================================================
#  تولید داده نمونه (در نسخه نهایی با خواندن اکسل/دیتابیس جایگزین می‌شود)
# ============================================================================
def status_of(v, warn, crit):
    if v >= crit:
        return "بحرانی"
    if v >= warn:
        return "هشدار"
    return "سالم"


@st.cache_data(show_spinner=False)
def build_data() -> pd.DataFrame:
    rnd = random.Random(2026)
    end = date(2026, 11, 22)
    dates = []
    for i in range(59, -1, -1):
        d = date.fromordinal(end.toordinal() - i)
        jy, jm, jd = g2j(d.year, d.month, d.day)
        dates.append(f"{jy:04d}/{jm:02d}/{jd:02d}")

    rows = []
    idx = 0
    for line, units in LINES.items():
        for unit, equips in units.items():
            for eq in equips:
                idx += 1
                warn, crit = 4.5, 7.1
                base = 1.7 + rnd.random() * 3.3
                special = None
                if idx % 13 == 0:
                    special = "خارج از سرویس"
                elif idx % 9 == 0:
                    special = "در حال تعمیر"
                elif idx % 7 == 0:
                    special = "پایش ویژه"

                for point in POINTS:
                    p_base = base + rnd.random() * 1.1
                    for ds in dates:
                        v = p_base + rnd.gauss(0, 0.55)
                        if rnd.random() < 0.04:
                            v += 1.1
                        v = round(max(0.4, v), 1)
                        rows.append({
                            "تاریخ": ds,
                            "خط": line,
                            "واحد": unit,
                            "تجهیز": eq,
                            "نقطه اندازه‌گیری": point,
                            "مقدار ارتعاش (mm/s)": v,
                            "حد هشدار": warn,
                            "حد بحرانی": crit,
                            "وضعیت": special if special else status_of(v, warn, crit),
                        })
    return pd.DataFrame(rows)


# ============================================================================
#  ابزارهای کمکی
# ============================================================================
def logo_b64(path):
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception:
            return None
    return None


def user_record(email):
    if not email:
        return None
    for u in st.session_state.users:
        if str(u.get("email", "")).strip().lower() == email.strip().lower():
            return u
    return None


def role_of(email):
    rec = user_record(email)
    return (rec or {}).get("role", "کاربر")


def is_superadmin(email):
    return role_of(email) == "سوپرادمین"


def is_manager(email):
    return role_of(email) == "مدیر"


def can_send(email):
    return is_manager(email) or (ALLOW_SUPERADMIN_SEND and is_superadmin(email))


def send_email(to_list, subject, body):
    if not HAS_SMTP:
        return False, "کتابخانه smtplib در دسترس نیست."
    try:
        cfg = st.secrets["smtp"]
    except Exception:
        return False, "تنظیمات SMTP تعریف نشده است (ارسال به صورت شبیه‌سازی ثبت شد)."
    try:
        msg = MIMEMultipart()
        msg["From"] = cfg["from"]
        msg["To"] = ", ".join(to_list)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        srv = smtplib.SMTP(cfg["host"], int(cfg.get("port", 587)), timeout=25)
        srv.starttls()
        srv.login(cfg["user"], cfg["password"])
        srv.sendmail(cfg["from"], list(to_list), msg.as_string())
        srv.quit()
        return True, "ایمیل با موفقیت ارسال شد."
    except Exception as e:
        return False, f"خطا در ارسال ایمیل: {e}"


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


# ============================================================================
#  صفحه و استایل
# ============================================================================
st.set_page_config(page_title=APP_TITLE, page_icon="📈", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Vazirmatn', Tahoma, sans-serif;
    direction: rtl;
}
.stApp { background: #f5f7fa; }

.hdr {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    direction: rtl;
    background: linear-gradient(120deg, #0f2d52 0%, #1b4f8a 55%, #2a6fb5 100%);
    border-radius: 16px;
    padding: 16px 26px;
    box-shadow: 0 6px 20px rgba(15, 45, 82, .25);
    margin-bottom: 14px;
}
.hdr-logo {
    width: 118px; height: 78px;
    background: rgba(255,255,255,.94);
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    overflow: hidden;
    flex: 0 0 auto;
    box-shadow: 0 2px 8px rgba(0,0,0,.18);
}
.hdr-logo img { max-width: 108px; max-height: 70px; object-fit: contain; }
.hdr-logo span { color: #1b4f8a; font-size: 11px; font-weight: 700; text-align: center; line-height: 1.5; }
.hdr-title { flex: 1 1 auto; text-align: center; color: #fff; }
.hdr-title h1 { margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -.2px; }
.hdr-title p  { margin: 6px 0 0; font-size: 13px; opacity: .85; }

.filter-box {
    background: #ffffff;
    border: 1px solid #dde5ef;
    border-top: 4px solid #1b4f8a;
    border-radius: 14px;
    padding: 12px 18px 4px;
    margin-bottom: 14px;
    box-shadow: 0 3px 12px rgba(20, 50, 90, .07);
}
.filter-box h4 { margin: 0 0 6px; color: #0f2d52; font-size: 15px; font-weight: 800; }

.kpi {
    background: #fff; border-radius: 14px; padding: 14px 16px;
    border-right: 5px solid #1b4f8a; box-shadow: 0 3px 10px rgba(20,50,90,.07);
}
.kpi .lbl { font-size: 12.5px; color: #6b7a8d; margin-bottom: 6px; }
.kpi .val { font-size: 23px; font-weight: 800; color: #0f2d52; }

.userchip {
    background: #eaf2fb; border: 1px solid #cbdcef; border-radius: 10px;
    padding: 8px 12px; font-size: 13px; color: #16365c; margin-bottom: 10px;
}
.userchip b { color: #0f2d52; }

div.stButton > button {
    border-radius: 10px; font-weight: 700; padding: .5rem 1.15rem;
}
.stTabs [data-baseweb="tab"] { font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ============================================================================
#  وضعیت نشست
# ============================================================================
if "users" not in st.session_state:
    st.session_state.users = [dict(u) for u in DEFAULT_USERS]
if "history" not in st.session_state:
    st.session_state.history = []
if "user" not in st.session_state:
    st.session_state.user = None


# ============================================================================
#  هدر لوگو + عنوان
# ============================================================================
def render_header():
    c_b64 = logo_b64(CLIENT_LOGO_FILE)
    m_b64 = logo_b64(MY_LOGO_FILE)

    right = (f'<img src="data:image/png;base64,{c_b64}" />' if c_b64
             else '<span>لوگوی<br>سیمان تهران</span>')
    left = (f'<img src="data:image/png;base64,{m_b64}" />' if m_b64
            else '<span>لوگوی<br>شخصی</span>')

    st.markdown(f"""
    <div class="hdr">
        <div class="hdr-logo">{right}</div>
        <div class="hdr-title">
            <h1>{APP_TITLE}</h1>
            <p>{APP_SUB}</p>
        </div>
        <div class="hdr-logo">{left}</div>
    </div>
    """, unsafe_allow_html=True)


render_header()


# ============================================================================
#  فرم ورود
# ============================================================================
if st.session_state.user is None:
    col_l, col_m, col_r = st.columns([1, 1.4, 1])
    with col_m:
        st.markdown('<div class="filter-box"><h4>🔐 ورود به سامانه</h4></div>',
                    unsafe_allow_html=True)
        with st.form("login_form", clear_on_submit=False):
            em = st.text_input("ایمیل سازمانی", placeholder="name@tehrancement.ir")
            pw = st.text_input("رمز عبور", type="password", placeholder="••••••••")
            ok = st.form_submit_button("ورود به داشبورد", use_container_width=True)

        if ok:
            email = (em or "").strip().lower()
            email = EMAIL_ALIASES.get(email, email)
            rec = user_record(email)
            if rec is None:
                st.error("این ایمیل در سامانه ثبت نشده است.")
            elif str(rec.get("password", "")) != (pw or ""):
                st.error("رمز عبور نادرست است.")
            else:
                st.session_state.user = rec["email"]
                st.rerun()

        st.caption("رمز پیش‌فرض تمام کاربران:  siman123")
        st.caption("مالک سیستم (تنها با حق تغییر تنظیمات):  cm.zandiyeh@gmail.com")
    st.stop()


# ============================================================================
#  پس از ورود
# ============================================================================
CUR = st.session_state.user
CUR_REC = user_record(CUR) or {}
CUR_ROLE = CUR_REC.get("role", "کاربر")
SUPER = is_superadmin(CUR)
MGR = is_manager(CUR)
CAN_SEND = can_send(CUR)

with st.sidebar:
    st.markdown(
        f'<div class="userchip">کاربر: <b>{CUR_REC.get("name", "-")}</b><br>'
        f'نقش: <b>{CUR_ROLE}</b><br>سمت: {CUR_REC.get("duty", "-")}<br>'
        f'<span style="font-size:11.5px;color:#5c6f85">{CUR}</span></div>',
        unsafe_allow_html=True)
    if st.button("خروج از حساب", use_container_width=True):
        st.session_state.user = None
        st.rerun()
    st.divider()
    st.caption("دسترسی‌ها")
    st.caption("👁 مشاهده همه بخش‌ها: همه کاربران")
    st.caption("📤 ارسال اعلان: فقط مدیران")
    st.caption("✏ تغییر داده‌ها و کاربران: فقط مالک سیستم")


# ============================================================================
#  فیلترهای سراسری (زیر تیتر، بیرون از تب‌ها)
# ============================================================================
df_all = build_data()

st.markdown('<div class="filter-box"><h4>🎛 فیلترهای سراسری — روی کل داشبورد اعمال می‌شود</h4></div>',
            unsafe_allow_html=True)

fc1, fc2, fc3, fc4, fc5 = st.columns([1.15, 1.15, 1.15, 1, 1])

with fc1:
    sel_lines = st.multiselect("خط تولید", list(LINES.keys()),
                               default=list(LINES.keys()), key="f_lines")

with fc2:
    unit_opts = []
    for ln in sel_lines:
        for un in LINES.get(ln, {}):
            if un not in unit_opts:
                unit_opts.append(un)
    sel_units = st.multiselect("واحد", unit_opts, default=unit_opts,
                               key="f_units_" + str(abs(hash(tuple(sel_lines)))))

with fc3:
    eq_opts = []
    for ln in sel_lines:
        for un in sel_units:
            for eq in LINES.get(ln, {}).get(un, []):
                if eq not in eq_opts:
                    eq_opts.append(eq)
    sel_equips = st.multiselect("تجهیز", eq_opts, default=eq_opts,
                                key="f_equip_" + str(abs(hash((tuple(sel_lines), tuple(sel_units))))))

all_dates = sorted(df_all["تاریخ"].unique().tolist())
with fc4:
    d_from = st.selectbox("از تاریخ", all_dates, index=0, key="f_from")
with fc5:
    d_to = st.selectbox("تا تاریخ", all_dates, index=len(all_dates) - 1, key="f_to")

if d_from > d_to:
    d_from, d_to = d_to, d_from

df = df_all[
    df_all["خط"].isin(sel_lines)
    & df_all["واحد"].isin(sel_units)
    & df_all["تجهیز"].isin(sel_equips)
    & (df_all["تاریخ"] >= d_from)
    & (df_all["تاریخ"] <= d_to)
].copy()

st.caption(f"بازه انتخابی: {d_from} تا {d_to}  |  تعداد رکورد: {len(df):,}")

if df.empty:
    st.warning("با این فیلترها هیچ رکوردی یافت نشد. فیلترها را بازتر کنید.")
    st.stop()


# ============================================================================
#  کارت‌های آماری
# ============================================================================
latest = df.sort_values("تاریخ").groupby(["خط", "واحد", "تجهیز"], as_index=False).tail(1)

n_equip = latest["تجهیز"].nunique()
n_crit = int((latest["وضعیت"] == "بحرانی").sum())
n_warn = int((latest["وضعیت"] == "هشدار").sum())
avg_v = float(df["مقدار ارتعاش (mm/s)"].mean())
max_v = float(df["مقدار ارتعاش (mm/s)"].max())
worst = df.loc[df["مقدار ارتعاش (mm/s)"].idxmax()]

k1, k2, k3, k4, k5 = st.columns(5)
for col, lbl, val in [
    (k1, "تجهیزات پایش‌شده", f"{n_equip}"),
    (k2, "تجهیزات بحرانی", f"{n_crit}"),
    (k3, "تجهیزات هشدار", f"{n_warn}"),
    (k4, "میانگین ارتعاش (mm/s)", f"{avg_v:.2f}"),
    (k5, "بیشترین ارتعاش (mm/s)", f"{max_v:.1f}"),
]:
    col.markdown(f'<div class="kpi"><div class="lbl">{lbl}</div>'
                 f'<div class="val">{val}</div></div>', unsafe_allow_html=True)

st.caption(f"بیشترین مقدار ثبت‌شده در بازه: {worst['تجهیز']} — "
           f"{worst['نقطه اندازه‌گیری']} — {worst['مقدار ارتعاش (mm/s)']} mm/s — {worst['تاریخ']}")
st.write("")


# ============================================================================
#  تب‌ها
# ============================================================================
tab1, tab2, tab3, tab4 = st.tabs(
    ["📋 جدول داده‌ها", "📊 نمودارها", "📤 ارسال اعلان", "👥 مدیریت کاربران"])

# ---------------------------------------------------------------- جدول
with tab1:
    st.subheader("داده‌های پایش ارتعاشات")
    st.dataframe(df.sort_values(["تاریخ", "تجهیز"], ascending=[False, True]),
                 use_container_width=True, height=470)

    c1, c2 = st.columns([1, 1])
    with c1:
        st.download_button("⬇ دریافت CSV داده‌های فیلترشده",
                           data=to_csv_bytes(df),
                           file_name="vibration_data.csv",
                           mime="text/csv",
                           use_container_width=True)
    with c2:
        summ = (df.groupby(["خط", "واحد", "تجهیز"])
                  .agg(میانگین=("مقدار ارتعاش (mm/s)", "mean"),
                       بیشترین=("مقدار ارتعاش (mm/s)", "max"))
                  .reset_index().round(2))
        st.download_button("⬇ دریافت خلاصه وضعیت تجهیزات",
                           data=to_csv_bytes(summ),
                           file_name="equipment_summary.csv",
                           mime="text/csv",
                           use_container_width=True)

# ---------------------------------------------------------------- نمودارها
with tab2:
    col_a, col_b = st.columns([1, 1.25])

    with col_a:
        st.subheader("توزیع وضعیت تجهیزات")
        counts = latest["وضعیت"].value_counts()
        labels = [s for s in STATUS_ORDER if s in counts.index]
        values = [int(counts[s]) for s in labels]
        fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.45,
            marker=dict(colors=[STATUS_COLORS[s] for s in labels],
                        line=dict(color="#ffffff", width=2)),
            textinfo="label+percent",
            hovertemplate="%{label}<br>%{value} تجهیز<extra></extra>",
        ))
        fig.update_layout(height=430, margin=dict(t=20, b=20, l=10, r=10),
                          showlegend=True, legend=dict(orientation="h", y=-0.12),
                          font=dict(family="Vazirmatn, Tahoma", size=13))
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("۱۰ تجهیز با بیشترین ارتعاش")
        top = (df.groupby("تجهیز")["مقدار ارتعاش (mm/s)"].max()
                 .sort_values(ascending=False).head(10).sort_values())
        colors = []
        for v in top.values:
            colors.append("#d9534f" if v >= 7.1 else ("#f2b134" if v >= 4.5 else "#2e9e5b"))
        fig2 = go.Figure(go.Bar(
            x=top.values, y=top.index, orientation="h",
            marker=dict(color=colors),
            text=[f"{v:.1f}" for v in top.values], textposition="outside",
            hovertemplate="%{y}<br>%{x} mm/s<extra></extra>",
        ))
        fig2.add_vline(x=4.5, line_dash="dash", line_color="#f2b134",
                       annotation_text="هشدار")
        fig2.add_vline(x=7.1, line_dash="dash", line_color="#d9534f",
                       annotation_text="بحرانی")
        fig2.update_layout(height=430, margin=dict(t=20, b=20, l=10, r=30),
                           xaxis_title="mm/s RMS",
                           font=dict(family="Vazirmatn, Tahoma", size=12))
        st.plotly_chart(fig2, use_container_width=True)

# ---------------------------------------------------------------- اعلان
with tab3:
    st.subheader("ارسال اعلان وضعیت بحرانی")

    worst10 = (df.groupby(["خط", "واحد", "تجهیز", "نقطه اندازه‌گیری"])
                 ["مقدار ارتعاش (mm/s)"].max().reset_index()
                 .sort_values("مقدار ارتعاش (mm/s)", ascending=False)
                 .head(10).round(2))

    st.markdown("**۱۰ مورد نیازمند توجه در بازه انتخابی:**")
    st.dataframe(worst10, use_container_width=True, height=280)

    rc = st.multiselect("گیرندگان ایمیل",
                        [f"{u['name']} — {u['email']}" for u in st.session_state.users],
                        default=[f"{u['name']} — {u['email']}" for u in st.session_state.users])

    subject = st.text_input("موضوع پیام",
                            value=f"هشدار ارتعاشات تجهیزات — {d_from} تا {d_to}")

    lines_txt = [f"گزارش وضعیت ارتعاشات سیمان تهران",
                 f"بازه: {d_from} تا {d_to}",
                 f"تعداد تجهیزات بحرانی: {n_crit} | هشدار: {n_warn}",
                 "",
                 "موارد بحرانی:"]
    crit_rows = df[df["وضعیت"] == "بحرانی"].sort_values("مقدار ارتعاش (mm/s)", ascending=False).head(15)
    if crit_rows.empty:
        lines_txt.append("- مورد بحرانی ثبت نشده است.")
    else:
        for _, r in crit_rows.iterrows():
            lines_txt.append(f"- {r['خط']} / {r['واحد']} / {r['تجهیز']} — "
                             f"{r['نقطه اندازه‌گیری']}: {r['مقدار ارتعاش (mm/s)']} mm/s ({r['تاریخ']})")
    lines_txt += ["", "این پیام به صورت خودکار از سامانه پایش وضعیت ارسال شده است."]
    body = st.text_area("متن پیام", value="\n".join(lines_txt), height=220)

    b1, b2 = st.columns([1, 2])
    with b1:
        do_send = st.button(
            "📨 ارسال اعلان",
            disabled=not CAN_SEND,
            use_container_width=True,
            help="ارسال فقط برای مدیران مجاز است."
        )
    with b2:
        if not CAN_SEND:
            st.info("شما دسترسی ارسال ندارید؛ فقط مدیران می‌توانند اعلان ارسال کنند. "
                    "مشاهده همه بخش‌ها برای شما آزاد است.")

    if do_send:
        if not rc:
            st.warning("حداقل یک گیرنده انتخاب کنید.")
        else:
            emails = [x.split(" — ")[-1].strip() for x in rc]
            success, msg = send_email(emails, subject, body)
            st.session_state.history.append({
                "زمان": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                "فرستنده": CUR_REC.get("name", CUR),
                "گیرندگان": len(emails),
                "موضوع": subject,
                "نتیجه": "ارسال واقعی" if success else "شبیه‌سازی",
            })
            if success:
                st.success(msg)
            else:
                st.warning(msg + " — اعلان در تاریخچه ثبت شد.")

    if st.session_state.history:
        st.divider()
        st.markdown("**تاریخچه اعلان‌ها:**")
        hist = pd.DataFrame(st.session_state.history[::-1])
        st.dataframe(hist, use_container_width=True)
        st.download_button("⬇ دریافت تاریخچه اعلان‌ها (CSV)",
                           data=to_csv_bytes(hist),
                           file_name="notification_history.csv",
                           mime="text/csv")

    st.divider()
    st.caption("برای ارسال واقعی ایمیل، فایل .streamlit/secrets.toml را طبق راهنما بسازید.")

# ---------------------------------------------------------------- کاربران
with tab4:
    st.subheader("کاربران سامانه")
    if SUPER:
        st.caption("شما مالک سیستم هستید: می‌توانید نام، نقش و رمز کاربران را تغییر دهید.")
    else:
        st.caption("مشاهده برای همه آزاد است؛ تغییر کاربران فقط توسط مالک سیستم انجام می‌شود.")

    users_df = pd.DataFrame(st.session_state.users)[["name", "email", "role", "duty", "password"]]
    users_df.columns = ["نام", "ایمیل", "نقش", "سمت", "رمز عبور"]

    if SUPER:
        edited = st.data_editor(
            users_df,
            use_container_width=True,
            num_rows="dynamic",
            disabled=["ایمیل"],
            column_config={
                "نقش": st.column_config.SelectboxColumn(
                    "نقش", options=["سوپرادمین", "مدیر", "کاربر"], required=True),
                "رمز عبور": st.column_config.TextColumn("رمز عبور"),
            },
            key="users_editor",
        )
        if st.button("💾 ذخیره تغییرات کاربران", use_container_width=False):
            new_users = []
            for _, r in edited.iterrows():
                em = str(r["ایمیل"]).strip().lower()
                if not em:
                    continue
                new_users.append({
                    "email": em,
                    "name": str(r["نام"]).strip(),
                    "role": str(r["نقش"]).strip() or "کاربر",
                    "duty": str(r["سمت"]).strip(),
                    "password": str(r["رمز عبور"]).strip() or DEFAULT_PASSWORD,
                })
            if new_users:
                st.session_state.users = new_users
                st.success("تغییرات کاربران ذخیره شد.")
                st.rerun()
            else:
                st.error("جدول نمی‌تواند خالی باشد.")
    else:
        masked = users_df.copy()
        masked["رمز عبور"] = "••••••"
        st.dataframe(masked, use_container_width=True)

    st.divider()
    c1, c2 = st.columns([1, 2])
    with c1:
        st.download_button("⬇ دریافت فهرست کاربران (CSV)",
                           data=to_csv_bytes(users_df),
                           file_name="users.csv",
                           mime="text/csv",
                           use_container_width=True)

st.divider()
st.caption(f"© {APP_TITLE} — نسخه 7.5 | تهیه و توسعه: هادی زندیه (پیمانکار خدمات)")
