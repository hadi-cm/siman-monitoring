# -*- coding: utf-8 -*-
"""
=============================================================
  سیستم هوشمند پایش وضعیت ارتعاشات - سیمان تهران
  نسخه 7.6
-------------------------------------------------------------
  قواعد دسترسی:
    * همه کاربران -> همه تب‌ها و همه داده‌ها را می‌بینند (شفافیت کامل)
    * مدیران     -> فقط دکمه «ارسال اعلان» برایشان فعال است
    * مالک سیستم -> تنها کسی که می‌تواند کاربران و تنظیمات را تغییر دهد
-------------------------------------------------------------
  فایل‌های لازم در کنار همین اسکریپت:
    client_logo.png  ->  لوگوی سیمان تهران (سمت راست سربرگ)
    my_logo.png      ->  لوگوی شخصی        (سمت چپ سربرگ)

  نصب پیش‌نیازها:
    pip install streamlit pandas numpy plotly

  اجرا:
    streamlit run app.py
=============================================================
"""

import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# ==========================================================
#  1) تنظیمات پایه
# ==========================================================
st.set_page_config(
    page_title="سیستم هوشمند پایش وضعیت - سیمان تهران",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

APP_TITLE = "سیستم هوشمند پایش وضعیت - سیمان تهران"
CLIENT_LOGO = "client_logo.png"   # سیمان تهران  -> سمت راست
MY_LOGO = "my_logo.png"           # لوگوی شخصی   -> سمت چپ

SUPER_ADMIN = "cm.zandiyeh@gmail.com"     # تنها کسی که حق ویرایش دارد (مالک)

# ==========================================================
#  2) پایگاه کاربران  (برای افزودن کاربر جدید فقط یک خط اضافه کن)
# ==========================================================
USER_DB = {
    "cm.zandiyeh@gmail.com":         {"name": "هادی زندیه",          "role": "مالک سیستم / پیمانکار", "password": "siman123"},
    "vah.rezaei@gmail.com":          {"name": "وحید رضایی",           "role": "مدیر فنی",              "password": "siman123"},
    "me.vibration.shokri@gmail.com": {"name": "مهدی شکری",            "role": "مدیر پایش وضعیت",       "password": "siman123"},
    "tehrancement@gmail.com":        {"name": "کارشناس سیمان تهران",  "role": "مدیر بهره‌برداری",      "password": "siman123"},
    "alireza76ir@gmail.com":         {"name": "علیرضا",               "role": "کاربر",                 "password": "siman123"},
    "operator1@tehrancement.ir":     {"name": "اپراتور خط ۱",         "role": "کاربر",                 "password": "siman123"},
    "operator2@tehrancement.ir":     {"name": "اپراتور خط ۲",         "role": "کاربر",                 "password": "siman123"},
}

# املای جایگزین ایمیل‌ها (اگر کاربر با غلط املایی وارد شد، رد نشود)
EMAIL_ALIASES = {
    "tehrancement@gmail.com": "tehrancement@gmail.com",
    "tehrancment@gmail.com": "tehrancement@gmail.com",
    "tehrancment@tehrancement.ir": "tehrancement@gmail.com",
    "alireza76ir@Gmail.com": "alireza76ir@gmail.com",
}

# مدیران سازمان = فقط حق «ارسال اعلان»
NOTIFIERS = {
    SUPER_ADMIN,
    "vah.rezaei@gmail.com",
    "me.vibration.shokri@gmail.com",
    "tehrancement@gmail.com",
}

# ==========================================================
#  3) استایل (RTL + فونت وزیرمتن)
# ==========================================================
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;600;700&display=swap');

html, body, [class*="css"], .stApp, .stMarkdown, .stText, input, textarea, select, button {
    font-family: 'Vazirmatn', Tahoma, sans-serif !important;
}
.stApp { direction: rtl; }
.block-container { padding-top: 1.0rem; max-width: 1450px; }

.app-title {
    text-align: center;
    font-size: 27px;
    font-weight: 700;
    color: #12395c;
    line-height: 1.5;
    padding-top: 26px;
}
.app-sub {
    text-align: center;
    font-size: 13px;
    color: #6b7b8c;
    padding-bottom: 6px;
}
.logo-ph {
    border: 1px dashed #b9c6d4;
    border-radius: 12px;
    background: #f6f9fc;
    color: #8a9aab;
    font-size: 12px;
    text-align: center;
    padding: 22px 6px;
}
.kpi {
    border: 1px solid #e2e9f0;
    border-right: 5px solid #2e6da4;
    border-radius: 12px;
    background: #ffffff;
    padding: 12px 14px;
    box-shadow: 0 1px 4px rgba(18,57,92,.06);
}
.kpi .lbl { font-size: 13px; color: #6b7b8c; }
.kpi .val { font-size: 23px; font-weight: 700; color: #12395c; }
.kpi.warn { border-right-color: #e6a23c; }
.kpi.bad  { border-right-color: #d9534f; }
.kpi.ok   { border-right-color: #3fa45b; }
.sec-title {
    font-size: 17px; font-weight: 700; color: #12395c;
    border-bottom: 2px solid #e2e9f0; padding-bottom: 6px; margin: 8px 0 12px 0;
}
div[data-testid="stTabs"] button { font-size: 15px; font-weight: 600; }
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
#  4) توابع کمکی
# ==========================================================
def normalize_email(raw: str) -> str:
    e = (raw or "").strip().lower().replace(" ", "")
    return EMAIL_ALIASES.get(e, e)


def g2j(gy, gm, gd):
    """تبدیل تاریخ میلادی به شمسی"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    jy = 979 if gy > 1600 else 0
    gy = gy - 1600 if gy > 1600 else gy - 621
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm, jd = 1 + days // 31, 1 + days % 31
    else:
        jm, jd = 7 + (days - 186) // 30, 1 + (days - 186) % 30
    return jy, jm, jd


def jstr(d) -> str:
    jy, jm, jd = g2j(d.year, d.month, d.day)
    return f"{jy}/{jm:02d}/{jd:02d}"


def zone_of(v: float):
    """محدوده‌های ISO 10816 برای ماشین‌های متوسط"""
    if v < 2.8:
        return "سالم", "ok"
    if v < 4.5:
        return "پایش", "ok"
    if v < 7.1:
        return "هشدار", "warn"
    return "بحرانی", "bad"


def zone_color(z: str) -> str:
    return {"سالم": "#3fa45b", "پایش": "#2e6da4", "هشدار": "#e6a23c", "بحرانی": "#d9534f"}.get(z, "#888")


def logo(path: str, fallback: str):
    if Path(path).exists():
        try:
            st.image(path, width=165)
            return
        except Exception:
            pass
    st.markdown(f'<div class="logo-ph">{fallback}</div>', unsafe_allow_html=True)


# ==========================================================
#  5) سلسله‌مراتب تجهیزات و تولید داده
# ==========================================================
HIERARCHY = {
    "خط ۱": {
        "سنگ‌شکن": ["سنگ‌شکن فکی ۱۰۱", "سنگ‌شکن چکشی ۱۰۲"],
        "آسیاب مواد": ["آسیاب مواد ۲۰۱", "فن آسیاب مواد ۲۰۲"],
        "کوره": ["کوره ۳۰۱", "فن دودکش ۳۰۲", "خنک‌کن ۳۰۳"],
        "آسیاب سیمان": ["آسیاب سیمان ۴۰۱", "سپراتور ۴۰۲"],
    },
    "خط ۲": {
        "سنگ‌شکن": ["سنگ‌شکن فکی ۱۱۱", "سنگ‌شکن چکشی ۱۱۲"],
        "آسیاب مواد": ["آسیاب مواد ۲۱۱", "فن آسیاب مواد ۲۱۲"],
        "کوره": ["کوره ۳۱۱", "فن دودکش ۳۱۲"],
        "آسیاب سیمان": ["آسیاب سیمان ۴۱۱", "سپراتور ۴۱۲"],
        "بارگیرخانه": ["پکیج بارگیر ۵۰۱", "کمپرسور ۵۰۲"],
    },
}


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    rng = np.random.default_rng(1404)
    today = datetime.now().date()
    rows = []
    for line, units in HIERARCHY.items():
        for unit, eqs in units.items():
            for eq in eqs:
                base = float(rng.uniform(1.7, 6.2))
                for k in range(12):
                    d = today - timedelta(days=int(165 - k * 15) + int(rng.integers(-3, 4)))
                    vib = float(max(0.4, rng.normal(base, 0.9) + 0.025 * k))
                    temp = float(rng.normal(62, 7))
                    rpm = int(rng.integers(740, 1490))
                    z, _ = zone_of(vib)
                    rows.append(
                        {
                            "خط": line,
                            "واحد": unit,
                            "تجهیز": eq,
                            "تاریخ": d,
                            "تاریخ شمسی": jstr(d),
                            "ارتعاش (mm/s RMS)": round(vib, 2),
                            "دما (°C)": round(temp, 1),
                            "دور (RPM)": rpm,
                            "وضعیت": z,
                        }
                    )
    df = pd.DataFrame(rows).sort_values("تاریخ", ascending=False).reset_index(drop=True)
    return df


DF_ALL = load_data()

# ==========================================================
#  6) ورود به سیستم
# ==========================================================
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    h1, h2, h3 = st.columns([1, 3, 1])
    with h1:
        logo(CLIENT_LOGO, "لوگوی سیمان تهران")
    with h2:
        st.markdown(f'<div class="app-title">{APP_TITLE}</div>', unsafe_allow_html=True)
        st.markdown('<div class="app-sub">ورود به سامانه پایش وضعیت ارتعاشات</div>', unsafe_allow_html=True)
    with h3:
        logo(MY_LOGO, "لوگوی شخصی")

    st.write("")
    _, mid, _ = st.columns([1, 1.6, 1])
    with mid:
        st.markdown('<div class="sec-title">🔐 ورود به سامانه</div>', unsafe_allow_html=True)
        with st.form("login_form"):
            email_in = st.text_input("ایمیل سازمانی", placeholder="name@tehrancement.ir")
            pass_in = st.text_input("رمز عبور", type="password", placeholder="••••••••")
            ok = st.form_submit_button("ورود به داشبورد", use_container_width=True)

        if ok:
            em = normalize_email(email_in)
            if not em:
                st.warning("ایمیل را وارد کنید.")
            elif em not in USER_DB:
                st.error("این ایمیل در سامانه ثبت نشده است.")
                st.caption("مدیر سیستم: cm.zandiyeh@gmail.com")
            elif USER_DB[em]["password"] != pass_in.strip():
                st.error("رمز عبور نادرست است.")
            else:
                st.session_state.user = em
                st.rerun()

        st.caption("رمز پیش‌فرض همه کاربران: siman123")
        st.caption("مالک سیستم (تنها با حق تغییر تنظیمات): cm.zandiyeh@gmail.com")
    st.stop()

# ==========================================================
#  7) کاربر جاری و سطح دسترسی
# ==========================================================
EMAIL = st.session_state.user
USER = USER_DB[EMAIL]
IS_OWNER = EMAIL == SUPER_ADMIN          # حق تغییر کاربران/تنظیمات
CAN_SEND = EMAIL in NOTIFIERS or IS_OWNER  # حق ارسال اعلان

# ==========================================================
#  8) سربرگ (لوگو | عنوان | لوگو)
# ==========================================================
c1, c2, c3 = st.columns([1, 3.2, 1])
with c1:
    logo(CLIENT_LOGO, "لوگوی سیمان تهران")
with c2:
    st.markdown(f'<div class="app-title">{APP_TITLE}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="app-sub">کاربر: <b>{USER["name"]}</b> &nbsp;|&nbsp; '
        f'نقش: {USER["role"]} &nbsp;|&nbsp; '
        f'ارسال اعلان: {"مجاز ✅" if CAN_SEND else "فقط مشاهده 👁"} &nbsp;|&nbsp; '
        f'{jstr(datetime.now().date())}</div>',
        unsafe_allow_html=True,
    )
with c3:
    logo(MY_LOGO, "لوگوی شخصی")
    if st.button("خروج", use_container_width=True):
        st.session_state.user = None
        st.rerun()

st.divider()

# ==========================================================
#  9) فیلترهای سراسری زنجیره‌ای
# ==========================================================
st.markdown('<div class="sec-title">🔎 فیلترهای سراسری</div>', unsafe_allow_html=True)

f1, f2, f3 = st.columns(3)
lines = ["همه خطوط"] + list(HIERARCHY.keys())
line_sel = f1.selectbox("خط تولید", lines, index=0)

unit_pool = sorted({u for ln in (HIERARCHY if line_sel == "همه خطوط" else {line_sel: HIERARCHY[line_sel]})
                    for u in HIERARCHY[line_sel]}) if line_sel != "همه خطوط" else sorted({u for ln in HIERARCHY.values() for u in ln})
units = ["همه واحدها"] + unit_pool
unit_sel = f2.selectbox("واحد", units, index=0)

if line_sel == "همه خطوط":
    eq_pool = sorted({e for ln in HIERARCHY.values() for us in ln.values() for e in us})
elif unit_sel == "همه واحدها":
    eq_pool = sorted({e for us in HIERARCHY[line_sel].values() for e in us})
else:
    eq_pool = sorted(HIERARCHY[line_sel][unit_sel])
eqs = ["همه تجهیزات"] + eq_pool
eq_sel = f3.selectbox("تجهیز", eqs, index=0)

# فیلتر بازه زمانی (روی تاریخ‌های موجود، نمایش شمسی)
date_opts = sorted(DF_ALL["تاریخ شمسی"].unique())
if len(date_opts) >= 2:
    rng_sel = st.select_slider("بازه زمانی", options=date_opts, value=(date_opts[0], date_opts[-1]))
else:
    rng_sel = (date_opts[0], date_opts[-1])

DF = DF_ALL.copy()
if line_sel != "همه خطوط":
    DF = DF[DF["خط"] == line_sel]
if unit_sel != "همه واحدها":
    DF = DF[DF["واحد"] == unit_sel]
if eq_sel != "همه تجهیزات":
    DF = DF[DF["تجهیز"] == eq_sel]
DF = DF[(DF["تاریخ شمسی"] >= rng_sel[0]) & (DF["تاریخ شمسی"] <= rng_sel[1])]

if DF.empty:
    st.warning("برای این ترکیب فیلتر، داده‌ای ثبت نشده است. فیلترها را تغییر دهید.")
    st.stop()

# ==========================================================
# 10) کارت‌های آماری
# ==========================================================
latest = DF.sort_values("تاریخ").groupby(["خط", "واحد", "تجهیز"], as_index=False).last()
n_all = len(latest)
n_crit = int((latest["وضعیت"] == "بحرانی").sum())
n_warn = int((latest["وضعیت"] == "هشدار").sum())
avg_vib = float(latest["ارتعاش (mm/s RMS)"].mean())

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f'<div class="kpi"><div class="lbl">تجهیزات پایش‌شده</div><div class="val">{n_all}</div></div>', unsafe_allow_html=True)
with k2:
    st.markdown(f'<div class="kpi ok"><div class="lbl">میانگین ارتعاش</div><div class="val">{avg_vib:.2f} <span style="font-size:13px">mm/s</span></div></div>', unsafe_allow_html=True)
with k3:
    st.markdown(f'<div class="kpi warn"><div class="lbl">وضعیت هشدار</div><div class="val">{n_warn}</div></div>', unsafe_allow_html=True)
with k4:
    st.markdown(f'<div class="kpi bad"><div class="lbl">وضعیت بحرانی</div><div class="val">{n_crit}</div></div>', unsafe_allow_html=True)

st.write("")

# ==========================================================
# 11) تب‌ها (برای همه کاربران باز است)
# ==========================================================
t1, t2, t3, t4 = st.tabs(["📋 جدول داده‌ها", "📊 نمودارها", "📨 ارسال اعلان", "👤 مدیریت کاربران"])

# ---------- تب ۱: جدول ----------
with t1:
    st.markdown('<div class="sec-title">داده‌های اندازه‌گیری</div>', unsafe_allow_html=True)
    show = DF.sort_values("تاریخ", ascending=False)
    st.dataframe(
        show[["خط", "واحد", "تجهیز", "تاریخ شمسی", "ارتعاش (mm/s RMS)", "دما (°C)", "دور (RPM)", "وضعیت"]],
        use_container_width=True,
        hide_index=True,
        height=430,
    )
    st.download_button(
        "⬇️ دانلود CSV",
        data=show.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"vibration_{datetime.now():%Y%m%d}.csv",
        mime="text/csv",
    )

# ---------- تب ۲: نمودارها ----------
with t2:
    g1, g2 = st.columns([1.4, 1])

    with g1:
        st.markdown('<div class="sec-title">۱۰ تجهیز با بالاترین ارتعاش</div>', unsafe_allow_html=True)
        top = latest.sort_values("ارتعاش (mm/s RMS)", ascending=False).head(10).iloc[::-1]
        fig = px.bar(
            top, x="ارتعاش (mm/s RMS)", y="تجهیز", orientation="h",
            color="وضعیت", color_discrete_map={z: zone_color(z) for z in ["سالم", "پایش", "هشدار", "بحرانی"]},
            text="ارتعاش (mm/s RMS)",
        )
        fig.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10),
                          legend_title_text="وضعیت", yaxis_title="", xaxis_title="mm/s RMS")
        st.plotly_chart(fig, use_container_width=True)

    with g2:
        st.markdown('<div class="sec-title">سهم وضعیت‌ها</div>', unsafe_allow_html=True)
        cnt = latest["وضعیت"].value_counts().reset_index()
        cnt.columns = ["وضعیت", "تعداد"]
        pie = px.pie(cnt, names="وضعیت", values="تعداد", hole=0.45,
                     color="وضعیت", color_discrete_map={z: zone_color(z) for z in cnt["وضعیت"]})
        pie.update_layout(height=430, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(pie, use_container_width=True)

    st.markdown('<div class="sec-title">روند ارتعاش تجهیز انتخابی</div>', unsafe_allow_html=True)
    pick = st.selectbox("تجهیز برای نمایش روند", sorted(DF["تجهیز"].unique()))
    trend = DF[DF["تجهیز"] == pick].sort_values("تاریخ")
    lf = px.line(trend, x="تاریخ شمسی", y="ارتعاش (mm/s RMS)", markers=True)
    lf.add_hline(y=4.5, line_dash="dash", line_color="#e6a23c", annotation_text="هشدار")
    lf.add_hline(y=7.1, line_dash="dash", line_color="#d9534f", annotation_text="بحرانی")
    lf.update_layout(height=330, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="", yaxis_title="mm/s RMS")
    st.plotly_chart(lf, use_container_width=True)

# ---------- تب ۳: اعلان ----------
with t3:
    st.markdown('<div class="sec-title">ارسال اعلان به مدیران و کارشناسان</div>', unsafe_allow_html=True)

    if "notif_log" not in st.session_state:
        st.session_state.notif_log = []

    left, right = st.columns([1, 1.35])

    with left:
        st.markdown("**گیرندگان**")
        name_to_mail = {v["name"]: k for k, v in USER_DB.items()}
        recv = st.multiselect("گیرندگان (پیش‌فرض: همه)", list(name_to_mail.keys()), default=list(name_to_mail.keys()))
        subject = st.text_input("موضوع", value=f"گزارش وضعیت ارتعاشات - {jstr(datetime.now().date())}")

        crit_list = latest[latest["وضعیت"].isin(["بحرانی", "هشدار"])].sort_values(
            "ارتعاش (mm/s RMS)", ascending=False)
        body_default = (
            f"گزارش وضعیت پایش ارتعاشات\n"
            f"خط: {line_sel} | واحد: {unit_sel} | تجهیز: {eq_sel}\n"
            f"بازه: {rng_sel[0]} تا {rng_sel[1]}\n"
            f"تعداد تجهیزات بحرانی: {n_crit} | هشدار: {n_warn}\n\n"
            + ("\n".join([f"- {r['تجهیز']} ({r['واحد']}): {r['ارتعاش (mm/s RMS)']} mm/s - {r['وضعیت']}"
                          for _, r in crit_list.head(10).iterrows()]) or "موردی نیازمند توجه نیست.")
        )
        body = st.text_area("متن پیام (خودکار از داده‌های فیلترشده پر می‌شود)", value=body_default, height=210)

        if CAN_SEND:
            if st.button("📨 ارسال اعلان", type="primary", use_container_width=True):
                rec_mails = [name_to_mail[n] for n in recv]
                sent_real = False
                try:
                    smtp = st.secrets.get("smtp", None)
                    if smtp and rec_mails:
                        msg = MIMEText(body, "plain", "utf-8")
                        msg["Subject"] = subject
                        msg["From"] = smtp.get("from", smtp["user"])
                        msg["To"] = ", ".join(rec_mails)
                        with smtplib.SMTP(smtp["host"], int(smtp.get("port", 587))) as s:
                            s.starttls()
                            s.login(smtp["user"], smtp["password"])
                            s.sendmail(msg["From"], rec_mails, msg.as_string())
                        sent_real = True
                except Exception as ex:
                    st.warning(f"ارسال ایمیل واقعی انجام نشد ({ex}). اعلان در تاریخچه ثبت شد.")

                st.session_state.notif_log.insert(0, {
                    "زمان": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "فرستنده": USER["name"],
                    "موضوع": subject,
                    "گیرندگان": "، ".join(recv),
                    "وضعیت": "ایمیل ارسال شد" if sent_real else "ثبت در سیستم (شبیه‌سازی)",
                })
                st.success(f"اعلان برای {len(recv)} گیرنده ثبت شد.")
        else:
            st.info("👁 مشاهده فعال است؛ ارسال اعلان فقط توسط مدیران سازمان انجام می‌شود.")

    with right:
        st.markdown("**تجهیزات نیازمند توجه (بر اساس فیلتر فعلی)**")
        view = crit_list[["تجهیز", "واحد", "ارتعاش (mm/s RMS)", "وضعیت"]].head(10)
        if view.empty:
            st.success("همه تجهیزات در محدوده مجاز هستند. ✅")
        else:
            st.dataframe(view, use_container_width=True, hide_index=True, height=300)

        st.markdown("**تاریخچه اعلان‌ها**")
        if st.session_state.notif_log:
            log_df = pd.DataFrame(st.session_state.notif_log)
            st.dataframe(log_df, use_container_width=True, hide_index=True, height=220)
            st.download_button(
                "⬇️ دانلود تاریخچه اعلان‌ها (CSV)",
                data=log_df.to_csv(index=False).encode("utf-8-sig"),
                file_name="notifications.csv",
                mime="text/csv",
            )
        else:
            st.caption("هنوز اعلانی ارسال نشده است.")

# ---------- تب ۴: مدیریت کاربران ----------
with t4:
    st.markdown('<div class="sec-title">کاربران سامانه</div>', unsafe_allow_html=True)

    rows = []
    for em, info in USER_DB.items():
        rows.append({
            "ایمیل": em,
            "نام": info["name"],
            "نقش": info["role"],
            "رمز عبور": info["password"] if IS_OWNER else "********",
            "ارسال اعلان": "✅" if em in NOTIFIERS else "—",
            "تغییر تنظیمات": "✅" if em == SUPER_ADMIN else "—",
        })
    users_df = pd.DataFrame(rows)
    st.dataframe(users_df, use_container_width=True, hide_index=True, height=330)

    if IS_OWNER:
        st.markdown("**✏️ ویرایش کاربران (فقط مالک سیستم)**")
        edited = st.data_editor(
            users_df, use_container_width=True, hide_index=True, num_rows="dynamic",
            key="users_editor",
            column_config={
                "ایمیل": st.column_config.TextColumn(required=True),
                "نقش": st.column_config.SelectboxColumn(
                    options=["مالک سیستم / پیمانکار", "مدیر فنی", "مدیر پایش وضعیت",
                             "مدیر بهره‌برداری", "کاربر"]),
            },
        )
        if st.button("💾 ذخیره تغییرات کاربران", type="primary"):
            new_db = {}
            for _, r in edited.iterrows():
                em = normalize_email(str(r["ایمیل"]))
                if not em:
                    continue
                new_db[em] = {
                    "name": str(r["نام"]) if pd.notna(r["نام"]) else em,
                    "role": str(r["نقش"]) if pd.notna(r["نقش"]) else "کاربر",
                    "password": str(r["رمز عبور"]) if pd.notna(r["رمز عبور"]) and str(r["رمز عبور"]).strip() not in ("", "********") else "siman123",
                }
            USER_DB.clear()
            USER_DB.update(new_db)
            st.success("تغییرات کاربران ذخیره شد (تا پایان اجرای برنامه).")
            st.rerun()
    else:
        st.caption("ویرایش کاربران و رمزها فقط در اختیار مالک سیستم است. سایر کاربران فقط مشاهده می‌کنند.")

st.divider()
st.caption("سیستم هوشمند پایش وضعیت - سیمان تهران | نسخه 7.6 | محدوده‌های هشدار بر پایه ISO 10816")
