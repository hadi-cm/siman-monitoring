# -*- coding: utf-8 -*-
"""
سیستم هوشمند پایش وضعیت ارتعاش - سیمان تهران
نسخه 7.7
"""

import io
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

# ==============================================================================
# 1) تنظیمات صفحه
# ==============================================================================
st.set_page_config(
    page_title="سیستم هوشمند پایش وضعیت-سیمان تهران",
    page_icon="📊",
    layout="wide",
)

APP_TITLE = "سیستم هوشمند پایش وضعیت-سیمان تهران"

# ==============================================================================
# 2) پایگاه کاربران
# ==============================================================================
USER_DB = {
    "cm.zandiyeh@gmail.com":           {"name": "هادی زندیه",     "role": "پیمانکار / مالک سیستم", "password": "siman123"},
    "vah.rezaei@gmail.com":            {"name": "وحید رضایی",     "role": "مدیر مکانیک",           "password": "siman123"},
    "me.vibration.shokri@gmail.com":   {"name": "مهدی شکری",      "role": "مدیر دفتر فنی",         "password": "siman123"},
    "tehrancment@gmail.com":           {"name": "سید مهدی حسینی", "role": "معاونت فنی",            "password": "siman123"},
    "alireza76ir@gmail.com":           {"name": "علیرضا",         "role": "کارشناس",               "password": "siman123"},
    "masoud.sa.1989823@gmail.com":     {"name": "مسعود صمیمی",    "role": "کارشناس",               "password": "siman123"},
    "operator2@tehrancment.ir":        {"name": "اپراتور خط ۲",   "role": "کاربر",                 "password": "siman123"},
}

OWNER_EMAIL = "cm.zandiyeh@gmail.com"

# نقش‌های مجاز به ارسال اعلان
SEND_ROLES = ("مدیر", "معاونت", "مالک")


# ==============================================================================
# 3) توابع دسترسی
# ==============================================================================
def can_send(email: str) -> bool:
    """ارسال اعلان: فقط مدیران، معاونت فنی و مالک سیستم."""
    role = USER_DB.get(email, {}).get("role", "")
    return any(k in role for k in SEND_ROLES)


def can_edit(email: str) -> bool:
    """تغییر داده‌ها و ایمیل‌ها: فقط مالک سیستم."""
    return email == OWNER_EMAIL


# ==============================================================================
# 4) داده نمونه
# ==============================================================================
@st.cache_data
def load_data() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    equipments = [
        ("فن آسیاب سیمان", "خط ۱"), ("آسیاب مواد خام", "خط ۱"),
        ("فن اصلی کوره", "خط ۱"),  ("الواتور کلینکر", "خط ۲"),
        ("فن سیمان", "خط ۲"),      ("آسیاب سیمان ۲", "خط ۲"),
        ("فن بگ‌هاوس", "خط ۲"),    ("الواتور مواد خام", "خط ۱"),
        ("آسیاب کلینکر", "خط ۱"),  ("فن خنک‌کن", "خط ۲"),
    ]
    rows = []
    start = datetime.now() - timedelta(days=29)
    for day in range(30):
        for eq, line in equipments:
            base = rng.uniform(1.5, 8.0)
            amp_h = base * rng.uniform(0.85, 1.9)
            amp_v = base * rng.uniform(0.85, 1.9)
            amp_a = base * rng.uniform(0.85, 1.9)
            temp = rng.uniform(45, 85)
            worst = max(amp_h, amp_v, amp_a)
            if worst < 4.5:
                status = "نرمال"
            elif worst < 7.0:
                status = "هشدار"
            else:
                status = "بحرانی"
            rows.append({
                "تاریخ": (start + timedelta(days=day)).date(),
                "خط تولید": line,
                "تجهیز": eq,
                "ارتعاش افقی (mm/s)": round(amp_h, 2),
                "ارتعاش عمودی (mm/s)": round(amp_v, 2),
                "ارتعاش محوری (mm/s)": round(amp_a, 2),
                "دمای بلبرینگ (°C)": round(temp, 1),
                "وضعیت": status,
            })
    return pd.DataFrame(rows)


df_all = load_data()

STATUS_EMOJI = {"نرمال": "🟢", "هشدار": "🟡", "بحرانی": "🔴"}


# ==============================================================================
# 5) هدر و لوگوها
# ==============================================================================
def logo(path: str, fallback: str):
    if os.path.exists(path):
        st.image(path, use_container_width=True)
    else:
        st.markdown(
            f"<div style='border:1px solid #d9e2ec;border-radius:10px;padding:14px;"
            f"text-align:center;color:#5b6b7c;font-size:13px'>{fallback}</div>",
            unsafe_allow_html=True,
        )


c1, c2, c3 = st.columns([1, 3, 1])
with c1:
    logo("my_logo.png", "لوگوی شما")
with c2:
    st.markdown(
        f"<h2 style='text-align:center;color:#0b3c6b;margin-bottom:0'>{APP_TITLE}</h2>"
        "<p style='text-align:center;color:#7a8794;font-size:13px;margin-top:4px'>"
        "پایش برخط ارتعاش و دمای تجهیزات</p>",
        unsafe_allow_html=True,
    )
with c3:
    logo("client_logo.png", "سیمان تهران")


# ==============================================================================
# 6) ورود به سامانه
# ==============================================================================
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.markdown("### 🔐 ورود به سامانه")
    with st.form("login_form"):
        email = st.text_input("ایمیل سازمانی", placeholder="name@example.com")
        password = st.text_input("رمز عبور", type="password")
        submitted = st.form_submit_button("ورود به داشبورد", use_container_width=True)

    if submitted:
        email = (email or "").strip().lower()
        if email in USER_DB and USER_DB[email]["password"] == password:
            st.session_state.user = email
            st.rerun()
        elif email and email not in USER_DB:
            st.error("این ایمیل در سامانه ثبت نشده است.")
        else:
            st.error("رمز عبور نادرست است.")

    st.caption("رمز پیش‌فرض تمام کاربران: siman123")
    st.stop()


user_email = st.session_state.user
user_info = USER_DB[user_email]
is_sender = can_send(user_email)
is_editor = can_edit(user_email)


# ==============================================================================
# 7) نوار کاربر
# ==============================================================================
u1, u2, u3 = st.columns([3, 2, 1])
with u1:
    st.markdown(
        f"👤 **{user_info['name']}** &nbsp;—&nbsp; `{user_email}` &nbsp;|&nbsp; نقش: **{user_info['role']}**"
    )
with u2:
    badges = []
    badges.append("📨 ارسال اعلان: " + ("✅" if is_sender else "⛔"))
    badges.append("✏️ تغییر داده: " + ("✅" if is_editor else "⛔"))
    st.caption(" | ".join(badges))
with u3:
    if st.button("خروج", use_container_width=True):
        st.session_state.user = None
        st.rerun()

st.divider()


# ==============================================================================
# 8) فیلترها (بیرون تب‌ها)
# ==============================================================================
st.markdown("#### 🔎 فیلترها")
f1, f2, f3, f4 = st.columns(4)

with f1:
    lines = ["همه خطوط"] + sorted(df_all["خط تولید"].unique().tolist())
    sel_line = st.selectbox("خط تولید", lines)

with f2:
    equip_pool = df_all if sel_line == "همه خطوط" else df_all[df_all["خط تولید"] == sel_line]
    equips = ["همه تجهیزات"] + sorted(equip_pool["تجهیز"].unique().tolist())
    sel_equip = st.multiselect("تجهیز", equips, default=["همه تجهیزات"])

with f3:
    sel_status = st.multiselect("وضعیت", ["نرمال", "هشدار", "بحرانی"],
                                default=["هشدار", "بحرانی"])

with f4:
    days = st.slider("بازه روزهای اخیر", 1, 30, 7)

start_date = datetime.now().date() - timedelta(days=days - 1)

df = df_all[(df_all["تاریخ"] >= start_date)].copy()
if sel_line != "همه خطوط":
    df = df[df["خط تولید"] == sel_line]
if "همه تجهیزات" not in sel_equip and sel_equip:
    df = df[df["تجهیز"].isin(sel_equip)]
if sel_status:
    df = df[df["وضعیت"].isin(sel_status)]

st.divider()


# ==============================================================================
# 9) تب‌ها
# ==============================================================================
tab1, tab2, tab3, tab4 = st.tabs(["📋 جدول داده‌ها", "📈 نمودارها", "📨 ارسال اعلان", "👥 کاربران"])

# ---------- تب ۱ ----------
with tab1:
    st.markdown(f"**تعداد رکوردها:** {len(df):,}")
    if df.empty:
        st.info("با این فیلترها رکوردی یافت نشد.")
    else:
        styled = df.copy()
        styled["وضعیت"] = styled["وضعیت"].map(lambda s: f"{STATUS_EMOJI.get(s,'')} {s}")
        st.dataframe(styled, use_container_width=True, height=460)
        st.download_button(
            "⬇️ دانلود CSV",
            data=df.to_csv(index=False).encode("utf-8-sig"),
            file_name="vibration_data.csv",
            mime="text/csv",
        )

# ---------- تب ۲ ----------
with tab2:
    if df.empty:
        st.info("داده‌ای برای نمودار نیست.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("میانگین ارتعاش افقی", f"{df['ارتعاش افقی (mm/s)'].mean():.2f} mm/s")
        m2.metric("میانگین ارتعاش عمودی", f"{df['ارتعاش عمودی (mm/s)'].mean():.2f} mm/s")
        m3.metric("میانگین دما", f"{df['دمای بلبرینگ (°C)'].mean():.1f} °C")
        m4.metric("تجهیزات بحرانی", int((df["وضعیت"] == "بحرانی").sum()))

        daily = df.groupby("تاریخ")[["ارتعاش افقی (mm/s)", "ارتعاش عمودی (mm/s)",
                                     "ارتعاش محوری (mm/s)"]].mean()
        st.markdown("**روند میانگین ارتعاش روزانه**")
        st.line_chart(daily)

        st.markdown("**میانگین دما بر اساس تجهیز**")
        st.bar_chart(df.groupby("تجهیز")["دمای بلبرینگ (°C)"].mean())

# ---------- تب ۳ ----------
with tab3:
    crit = df[df["وضعیت"] == "بحرانی"].sort_values(
        "ارتعاش افقی (mm/s)", ascending=False
    )

    st.markdown("**تجهیزات نیازمند توجه (بحرانی)**")
    if crit.empty:
        st.success("در این بازه تجهیز بحرانی وجود ندارد.")
    else:
        show = crit[["تجهیز", "خط تولید", "ارتعاش افقی (mm/s)",
                     "ارتعاش عمودی (mm/s)", "دمای بلبرینگ (°C)", "وضعیت"]]
        st.dataframe(show, use_container_width=True, height=280)

    st.markdown("**پیش‌نویس اعلان**")
    all_emails = list(USER_DB.keys())
    recipients = st.multiselect("گیرندگان", all_emails, default=all_emails,
                                format_func=lambda e: f"{USER_DB[e]['name']} — {e}")

    subject = st.text_input("موضوع", f"هشدار ارتعاش — سیمان تهران — {datetime.now():%Y/%m/%d}")

    if crit.empty:
        body = "در بازه انتخاب‌شده تجهیز بحرانی گزارش نشده است."
    else:
        top = crit.head(10)
        lines = [
            f"گزارش وضعیت تجهیزات بحرانی — {datetime.now():%Y/%m/%d}",
            f"بازه: {days} روز اخیر | خط: {sel_line} | تعداد بحرانی: {len(crit)}",
            "",
            "بدترین تجهیزات نیازمند توجه:",
        ]
        for i, (_, r) in enumerate(top.iterrows(), 1):
            lines.append(
                f"{i}. {r['تجهیز']} ({r['خط تولید']}) — "
                f"افقی {r['ارتعاش افقی (mm/s)']} | عمودی {r['ارتعاش عمودی (mm/s)']} | "
                f"دما {r['دمای بلبرینگ (°C)']}°C"
            )
        lines += ["", f"ارسال‌کننده: {user_info['name']} — {user_info['role']}"]
        body = "\n".join(lines)

    body = st.text_area("متن پیام", body, height=240)

    if is_sender:
        if st.button("📨 ارسال اعلان", type="primary", use_container_width=True):
            st.session_state.setdefault("sent_log", []).append({
                "زمان": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "فرستنده": user_info["name"],
                "موضوع": subject,
                "گیرندگان": ", ".join(USER_DB[e]["name"] for e in recipients),
                "تعداد بحرانی": len(crit),
            })
            st.success(f"اعلان برای {len(recipients)} گیرنده ثبت شد (شبیه‌سازی ارسال).")
    else:
        st.button("📨 ارسال اعلان", disabled=True, use_container_width=True)
        st.caption("⛔ شما مجوز ارسال اعلان ندارید — مشاهده باز است، ارسال فقط برای مدیران.")

    st.divider()
    st.markdown("**تاریخچه اعلان‌ها**")
    log = st.session_state.get("sent_log", [])
    if log:
        log_df = pd.DataFrame(log)
        st.dataframe(log_df, use_container_width=True)
        st.download_button(
            "⬇️ دانلود تاریخچه CSV",
            data=log_df.to_csv(index=False).encode("utf-8-sig"),
            file_name="notification_history.csv",
            mime="text/csv",
        )
    else:
        st.caption("هنوز اعلانی ارسال نشده است.")

# ---------- تب ۴ ----------
with tab4:
    st.markdown("**کاربران سامانه**")
    rows = [{
        "نام": v["name"],
        "ایمیل": k,
        "نقش": v["role"],
        "رمز": v["password"] if is_editor else "••••••••",
        "ارسال اعلان": "✅" if can_send(k) else "⛔",
    } for k, v in USER_DB.items()]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=320)

    if is_editor:
        st.markdown("**ویرایش رمز کاربر**")
        target = st.selectbox("کاربر", list(USER_DB.keys()),
                              format_func=lambda e: f"{USER_DB[e]['name']} — {e}")
        new_pass = st.text_input("رمز جدید", type="password")
        if st.button("ذخیره تغییرات", type="primary"):
            if new_pass.strip():
                USER_DB[target]["password"] = new_pass.strip()
                st.success("رمز کاربر به‌روزرسانی شد.")
            else:
                st.warning("رمز جدید را وارد کنید.")
    else:
        st.caption("✏️ تغییر داده‌ها فقط توسط مالک سیستم امکان‌پذیر است.")

st.divider()
st.caption(f"آخرین به‌روزرسانی: {datetime.now():%Y-%m-%d %H:%M} — سیمان تهران")
