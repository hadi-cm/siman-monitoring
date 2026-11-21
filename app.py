# -*- coding: utf-8 -*-
"""
====================================================================
 داشبورد پایش ارتعاشات سیمان تهران — نسخه ۴.۰
====================================================================
 توسعه و طراحی: مهندس هادی زندیه (Eng. Hadi Zandieh)
 تاریخ: ۳۰ آبان ۱۴۰۵

 نیازمندی‌ها:
     pip install streamlit pandas numpy plotly requests

 اجرا:
     streamlit run app.py
====================================================================
"""

import json
import os
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr
from io import StringIO

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ==================================================================
# ۰) تنظیمات صفحه
# ==================================================================
st.set_page_config(
    page_title="داشبورد پایش ارتعاشات سیمان تهران",
    page_icon="📈",
    layout="wide",
)

USERS_FILE = "users.json"
EMAIL_CFG_FILE = "email_config.json"

st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem;}
      .credit {color:#8a8a8a; font-size:12px; line-height:1.7;}
      div[data-testid="stMetricValue"] {font-size: 26px;}
    </style>
    """,
    unsafe_allow_html=True,
)

# ==================================================================
# ۱) کاربران مجاز (کلید ورود به سیستم)
#    نقش‌ها: admin = مدیر (دسترسی کامل)  |  viewer = ناظر (فقط مشاهده)
# ==================================================================
DEFAULT_USERS = {
    "alireza76ir@gmail.com":         {"password": "siman123", "role": "viewer"},
    "vah.rezaei@gmail.com":          {"password": "siman123", "role": "admin"},
    "cm.zandiy@gmail.com":           {"password": "siman123", "role": "viewer"},
    "me.vibration.shokri@gmail.com": {"password": "siman123", "role": "admin"},
    "m.babahasan@gmail.com":         {"password": "siman123", "role": "viewer"},
    "freedocs.ir@gmail.com":         {"password": "siman123", "role": "viewer"},
    "tehrancement@gmail.com":        {"password": "siman123", "role": "admin"},
}


def save_users(users: dict) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data:
                return data
        except Exception:
            pass
    save_users(DEFAULT_USERS)
    return {k: dict(v) for k, v in DEFAULT_USERS.items()}


# ==================================================================
# ۲) تنظیمات ایمیل اعلانیه
# ==================================================================
DEFAULT_EMAIL_CFG = {
    "host": "smtp.gmail.com",
    "port": 465,
    "sender": "",
    "app_password": "",
    "sender_name": "پایش ارتعاشات سیمان تهران",
    "recipients": [],
}


def load_email_cfg() -> dict:
    cfg = dict(DEFAULT_EMAIL_CFG)
    if os.path.exists(EMAIL_CFG_FILE):
        try:
            with open(EMAIL_CFG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_email_cfg(cfg: dict) -> None:
    with open(EMAIL_CFG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def parse_recipients(text: str) -> list:
    raw = (text or "").replace("،", ",").replace(";", ",").replace("\n", ",")
    out, seen = [], set()
    for part in raw.split(","):
        e = part.strip()
        if e and "@" in e and e.lower() not in seen:
            seen.add(e.lower())
            out.append(e)
    return out


def send_email(cfg: dict, subject: str, html: str, recipients: list) -> int:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((cfg.get("sender_name") or "پایش ارتعاشات", cfg["sender"]))
    msg["To"] = ", ".join(recipients)
    msg.set_content("برای مشاهده این پیام به یک برنامه ایمیل با پشتیبانی HTML نیاز است.",
                    subtype="plain")
    msg.add_alternative(html, subtype="html")

    host = cfg["host"]
    port = int(cfg.get("port", 465))

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as server:
            server.login(cfg["sender"], cfg["app_password"])
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls()
            server.login(cfg["sender"], cfg["app_password"])
            server.send_message(msg)
    return len(recipients)


# ==================================================================
# ۳) نقشه نقاط اندازه‌گیری
#    قاعده: P1 و P2 همیشه الکتروموتور؛ از P3 به بعد تجهیز گردان
# ==================================================================
def point_role(point: str) -> str:
    p = str(point).strip().upper()
    if p == "P1":
        return "بیرینگ DE الکتروموتور"
    if p == "P2":
        return "بیرینگ NDE الکتروموتور"
    return "بیرینگ تجهیز گردان"


def sort_points(series):
    def key(x):
        s = str(x).strip().upper()
        return (0, int(s[1:])) if s.startswith("P") and s[1:].isdigit() else (1, 99)
    return sorted(series, key=key)


# ==================================================================
# ۴) وضعیت و آستانه‌ها (بر پایه ISO 10816)
# ==================================================================
def classify(v) -> tuple:
    try:
        v = float(v)
    except Exception:
        return "نامشخص", "⚪", "#8a8a8a"
    if v < 2.8:
        return "سالم", "🟢", "#2e9e5b"
    if v < 4.5:
        return "قابل قبول", "🟡", "#c9a227"
    if v < 7.1:
        return "هشدار", "🟠", "#e07b1a"
    return "بحرانی", "🔴", "#d22f2f"


# ==================================================================
# ۵) داده
# ==================================================================
EQUIPMENT_BASE = {
    "آسیاب سیمان ۱": 3.1,
    "آسیاب سیمان ۲": 4.7,
    "فن دپارتمان": 2.3,
    "الواتور کلینکر": 5.6,
    "کمپرسور ۳": 7.0,
}


def build_sample_data(days: int = 10, per_day: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = []
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    for name, base in EQUIPMENT_BASE.items():
        for d in range(days):
            for k in range(per_day):
                ts = now - timedelta(days=days - 1 - d, hours=k * 3)
                for p in range(1, 7):
                    v = base * (0.85 + 0.10 * p) + rng.normal(0, 0.35) + 0.02 * d
                    rows.append(
                        {
                            "timestamp": ts,
                            "equipment": name,
                            "point": f"P{p}",
                            "value": round(max(0.2, v), 2),
                            "temp": round(45 + v * 4 + rng.normal(0, 1.8), 1),
                        }
                    )
    return pd.DataFrame(rows)


COL_ALIASES = {
    "timestamp": ["timestamp", "زمان", "تاریخ", "date", "time"],
    "equipment": ["equipment", "تجهیز", "دستگاه", "machine", "tag"],
    "point": ["point", "نقطه", "شماره نقطه", "نقطه اندازه‌گیری", "نقطه اندازه گیری"],
    "value": ["value", "مقدار", "ارتعاش", "vibration", "mm/s", "rms"],
    "temp": ["temp", "دما", "temperature"],
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    rename = {}
    for target, alts in COL_ALIASES.items():
        if target in df.columns:
            continue
        for alt in alts:
            match = [c for c in df.columns if c.strip().lower() == alt.strip().lower()]
            if match:
                rename[match[0]] = target
                break
    df = df.rename(columns=rename)

    if "value" not in df.columns:
        raise ValueError("ستون مقدار ارتعاش پیدا نشد. ستون‌ها باید شامل value یا ارتعاش باشند.")
    if "equipment" not in df.columns:
        df["equipment"] = "تجهیز نامشخص"
    if "point" not in df.columns:
        df["point"] = "P1"
    if "timestamp" not in df.columns:
        df["timestamp"] = datetime.now()
    if "temp" not in df.columns:
        df["temp"] = np.nan

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df["point"] = df["point"].astype(str).str.strip().str.upper()
    df["equipment"] = df["equipment"].astype(str).str.strip()
    return df.sort_values("timestamp").reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=120)
def load_from_url(url: str) -> pd.DataFrame:
    if "docs.google.com/spreadsheets" in url and "/edit" in url:
        url = url.split("/edit")[0] + "/export?format=csv"
    resp = requests.get(url, timeout=25)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    raw = pd.read_csv(StringIO(resp.text))
    return normalize_columns(raw)


# ==================================================================
# ۶) صفحه ورود
# ==================================================================
def login_page(users: dict) -> None:
    st.markdown("### 📈 داشبورد پایش ارتعاشات سیمان تهران")
    st.caption("برای مشاهده داده‌ها، با ایمیل سازمانی خود وارد شوید.")
    st.divider()

    left, mid, right = st.columns([1, 1.4, 1])
    with mid:
        with st.form("login_form"):
            email = st.text_input("ایمیل", placeholder="name@company.com")
            password = st.text_input("رمز عبور", type="password", placeholder="••••••••")
            ok = st.form_submit_button("ورود به سیستم", use_container_width=True)

        if ok:
            key = (email or "").strip().lower()
            rec = users.get(key)
            if rec and str(rec.get("password", "")) == password:
                st.session_state["user"] = key
                st.session_state["login_at"] = datetime.now().isoformat(timespec="seconds")
                st.rerun()
            else:
                st.error("ایمیل یا رمز عبور صحیح نیست.")

        st.caption("دسترسی فقط برای افراد مجاز. در صورت فراموشی رمز، با مدیر سیستم تماس بگیرید.")


# ==================================================================
# ۷) تب‌های اصلی
# ==================================================================
def tab_overview(df: pd.DataFrame, equipments: list) -> None:
    latest = (
        df.sort_values("timestamp")
        .groupby(["equipment", "point"], as_index=False)
        .tail(1)
    )

    total = len(equipments)
    crit = latest[latest["value"] >= 7.1]["equipment"].nunique()
    warn = latest[(latest["value"] >= 4.5) & (latest["value"] < 7.1)]["equipment"].nunique()
    ok = total - len(set(latest[latest["value"] >= 4.5]["equipment"]))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("تجهیزات پایش‌شده", total)
    c2.metric("وضعیت سالم", max(ok, 0))
    c3.metric("هشدار", warn)
    c4.metric("بحرانی", crit)

    st.divider()

    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("**میانگین ارتعاش تجهیزات (mm/s)**")
        bar = (
            latest.groupby("equipment", as_index=False)["value"]
            .mean()
            .sort_values("value")
        )
        colors = [classify(v)[2] for v in bar["value"]]
        fig = go.Figure(
            go.Bar(
                x=bar["value"],
                y=bar["equipment"],
                orientation="h",
                marker_color=colors,
                text=[f"{v:.1f}" for v in bar["value"]],
                textposition="outside",
            )
        )
        fig.update_layout(
            height=330,
            margin=dict(l=10, r=20, t=10, b=10),
            xaxis_title="mm/s",
            yaxis_title="",
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("**آخرین وضعیت هر نقطه**")
        table = latest.copy()
        table["وضعیت"] = [classify(v)[1] + " " + classify(v)[0] for v in table["value"]]
        table = table.rename(
            columns={
                "equipment": "تجهیز",
                "point": "نقطه",
                "value": "ارتعاش (mm/s)",
                "temp": "دما (°C)",
                "timestamp": "زمان",
            }
        )
        st.dataframe(
            table[["تجهیز", "نقطه", "ارتعاش (mm/s)", "دما (°C)", "وضعیت"]],
            use_container_width=True,
            hide_index=True,
            height=300,
        )

    st.divider()
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "⬇️ دریافت داده جاری (CSV)",
        data=csv,
        file_name=f"vibration_{datetime.now():%Y%m%d_%H%M}.csv",
        mime="text/csv",
    )


def tab_equipment(df: pd.DataFrame, equipments: list) -> None:
    c1, c2 = st.columns([2, 2])
    with c1:
        eq = st.selectbox("انتخاب تجهیز", equipments, key="eq_select")
    with c2:
        days = st.slider("بازه زمانی (روز)", 1, 60, 14, key="days_slider")

    sub = df[(df["equipment"] == eq) & (df["timestamp"] >= datetime.now() - timedelta(days=days))]
    if sub.empty:
        st.warning("برای این تجهیز در بازه انتخاب‌شده داده‌ای ثبت نشده است.")
        return

    pts = sort_points(sub["point"].unique())
    fig = go.Figure()
    for p in pts:
        g = sub[sub["point"] == p].sort_values("timestamp")
        if g.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=g["timestamp"],
                y=g["value"],
                mode="lines+markers",
                name=f"{p} — {point_role(p)}",
            )
        )
    for level, color, label in [(4.5, "#e07b1a", "هشدار"), (7.1, "#d22f2f", "بحرانی")]:
        fig.add_hline(y=level, line_dash="dash", line_color=color,
                      annotation_text=label, annotation_position="right")
    fig.update_layout(
        height=430,
        margin=dict(l=10, r=60, t=20, b=10),
        yaxis_title="ارتعاش (mm/s RMS)",
        xaxis_title="",
        legend=dict(orientation="h", y=-0.25),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**آمار توصیفی نقاط**")
    stat = (
        sub.groupby("point")["value"]
        .agg(["count", "mean", "max", "min"])
        .reindex(pts)
        .reset_index()
    )
    stat["نقش"] = [point_role(p) for p in stat["point"]]
    stat["وضعیت"] = [classify(v)[1] for v in stat["max"]]
    stat = stat.rename(
        columns={
            "point": "نقطه",
            "count": "تعداد",
            "mean": "میانگین",
            "max": "بیشینه",
            "min": "کمینه",
        }
    )
    st.dataframe(stat.round(2), use_container_width=True, hide_index=True)


def tab_alerts(df: pd.DataFrame) -> None:
    latest = (
        df.sort_values("timestamp")
        .groupby(["equipment", "point"], as_index=False)
        .tail(1)
        .copy()
    )
    latest["severity"] = latest["value"].apply(lambda v: classify(v)[0])
    hit = latest[latest["value"] >= 4.5].sort_values("value", ascending=False)

    st.markdown("**اعلانیه‌های فعال (ارتعاش ≥ 4.5 mm/s)**")
    if hit.empty:
        st.success("هیچ نقطه‌ای بالای آستانه هشدار نیست. وضعیت تجهیزات مطلوب است.")
        return

    hit["وضعیت"] = [classify(v)[1] + " " + classify(v)[0] for v in hit["value"]]
    out = hit.rename(
        columns={
            "equipment": "تجهیز",
            "point": "نقطه",
            "value": "ارتعاش (mm/s)",
            "timestamp": "آخرین اندازه‌گیری",
        }
    )
    st.dataframe(
        out[["تجهیز", "نقطه", "ارتعاش (mm/s)", "وضعیت", "آخرین اندازه‌گیری"]],
        use_container_width=True,
        hide_index=True,
    )

    st.session_state["pending_alerts"] = hit
    st.caption(f"{len(hit)} نقطه در وضعیت هشدار یا بحرانی است.")


def tab_notify(df: pd.DataFrame, cfg: dict, is_admin: bool) -> None:
    st.markdown("**ارسال اعلانیه ایمیلی**")

    if not is_admin:
        st.info("ارسال اعلانیه فقط برای مدیران سیستم فعال است.")
        return

    latest = (
        df.sort_values("timestamp")
        .groupby(["equipment", "point"], as_index=False)
        .tail(1)
        .copy()
    )
    hit = latest[latest["value"] >= 4.5].sort_values("value", ascending=False)

    if hit.empty:
        st.success("موردی برای ارسال نیست.")
        return

    body_rows = "".join(
        f"<tr><td>{r.equipment}</td><td>{r.point}</td>"
        f"<td>{r.value:.2f}</td><td>{classify(r.value)[0]}</td></tr>"
        for r in hit.itertuples()
    )
    html = f"""
    <div dir="rtl" style="font-family:Tahoma,Arial,sans-serif;font-size:14px">
      <h3 style="color:#1f3a5f;margin:0 0 10px">اعلانیه پایش ارتعاشات</h3>
      <p style="color:#555;margin:0 0 12px">زمان گزارش: {datetime.now():%Y-%m-%d %H:%M}</p>
      <table border="1" cellpadding="8" cellspacing="0"
             style="border-collapse:collapse;border-color:#ddd;font-size:13px">
        <thead style="background:#f2f6fb">
          <tr><th>تجهیز</th><th>نقطه</th><th>ارتعاش (mm/s)</th><th>وضعیت</th></tr>
        </thead>
        <tbody>{body_rows}</tbody>
      </table>
      <p style="color:#888;font-size:12px;margin-top:14px">
        این پیام به‌صورت خودکار توسط داشبورد پایش ارتعاشات سیمان تهران ارسال شده است.
      </p>
    </div>
    """

    st.caption(f"{len(hit)} نقطه بالای آستانه هشدار است.")
    with st.expander("پیش‌نمایش متن ایمیل"):
        st.components.v1.html(html, height=320, scrolling=True)

    recipients_text = st.text_area(
        "گیرندگان (با کاما جدا کنید)",
        value=", ".join(cfg.get("recipients", [])),
        height=90,
        key="notify_recipients",
    )
    recipients = parse_recipients(recipients_text)
    st.caption("دریافت‌کنندگان فعلی: " + (", ".join(recipients) if recipients else "هیچ") + " | "
               f"تعداد: {len(recipients)}")

    ready = bool(cfg.get("sender")) and bool(cfg.get("app_password")) and bool(recipients)
    if not ready:
        st.warning("ابتدا در تب «تنظیمات ایمیل» فرستنده، رمز اپلیکیشن و حداقل یک گیرنده را ذخیره کنید.")

    subject = f"اعلانیه ارتعاشات — {len(hit)} نقطه در وضعیت هشدار ({datetime.now():%Y-%m-%d %H:%M})"
    if st.button("✉️ ارسال اعلانیه", type="primary", disabled=not ready):
        try:
            n = send_email(
                {**cfg, "recipients": recipients},
                subject,
                html,
                recipients,
            )
            st.success(f"ایمیل برای {n} گیرنده ارسال شد.")
        except Exception as exc:
            st.error(f"ارسال انجام نشد: {exc}")


def tab_email_settings(cfg: dict, is_admin: bool) -> None:
    if not is_admin:
        st.info("تنظیمات ارسال ایمیل فقط برای مدیران سیستم در دسترس است.")
        return

    st.markdown("**تنظیمات سرور ایمیل**")
    st.caption("برای جیمیل باید رمز اپلیکیشن ۱۶ رقمی بسازید (Security → App passwords).")

    with st.form("email_cfg_form"):
        c1, c2 = st.columns(2)
        host = c1.text_input("سرور SMTP", value=cfg.get("host", "smtp.gmail.com"))
        port = c2.number_input("پورت", value=int(cfg.get("port", 465)), step=1,
                               min_value=1, max_value=65535)
        sender = st.text_input("ایمیل فرستنده", value=cfg.get("sender", ""),
                               placeholder="me.vibration.shokri@gmail.com")
        pwd = st.text_input("رمز اپلیکیشن", value=cfg.get("app_password", ""), type="password")
        name = st.text_input("نام نمایشی فرستنده",
                             value=cfg.get("sender_name", "پایش ارتعاشات سیمان تهران"))
        recips = st.text_area(
            "گیرندگان پیش‌فرض",
            value=", ".join(cfg.get("recipients", [])),
            height=90,
        )
        saved = st.form_submit_button("💾 ذخیره تنظیمات", use_container_width=True)

    if saved:
        new_cfg = {
            "host": host.strip() or "smtp.gmail.com",
            "port": int(port),
            "sender": sender.strip(),
            "app_password": pwd,
            "sender_name": name.strip() or "پایش ارتعاشات سیمان تهران",
            "recipients": parse_recipients(recips),
        }
        save_email_cfg(new_cfg)
        st.success("تنظیمات ذخیره شد.")
        st.rerun()

    st.divider()
    if st.button("✉️ ارسال ایمیل آزمایشی"):
        recipients = cfg.get("recipients", [])
        if not (cfg.get("sender") and cfg.get("app_password") and recipients):
            st.warning("فرستنده، رمز و حداقل یک گیرنده لازم است.")
        else:
            try:
                html = (
                    '<div dir="rtl" style="font-family:Tahoma">'
                    "<h3>ایمیل آزمایشی</h3>"
                    f"<p>اتصال سرور ایمیل با موفقیت برقرار شد. {datetime.now():%Y-%m-%d %H:%M}</p>"
                    "</div>"
                )
                n = send_email(cfg, "ایمیل آزمایشی — پایش ارتعاشات", html, recipients)
                st.success(f"ایمیل آزمایشی برای {n} گیرنده ارسال شد.")
            except Exception as exc:
                st.error(f"ارسال انجام نشد: {exc}")

    st.caption("توجه: رمز در فایل email_config.json به‌صورت متن ساده ذخیره می‌شود.")


def tab_users(users: dict, is_admin: bool) -> None:
    if not is_admin:
        st.info("مدیریت کاربران فقط برای مدیران سیستم در دسترس است.")
        return

    st.markdown("**کاربران مجاز**")
    rows = [
        {
            "ایمیل": email,
            "نقش": "مدیر" if rec.get("role") == "admin" else "ناظر",
        }
        for email, rec in users.items()
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**افزودن یا ویرایش کاربر**")
        with st.form("user_form"):
            email = st.text_input("ایمیل", placeholder="name@company.com")
            pwd = st.text_input("رمز عبور", type="password")
            role = st.selectbox("نقش", options=["viewer", "admin"],
                                format_func=lambda x: "مدیر" if x == "admin" else "ناظر")
            submitted = st.form_submit_button("ثبت", use_container_width=True)
        if submitted:
            key = (email or "").strip().lower()
            if not key or "@" not in key:
                st.error("ایمیل معتبر وارد کنید.")
            elif not pwd:
                st.error("رمز عبور را وارد کنید.")
            else:
                users[key] = {"password": pwd, "role": role}
                save_users(users)
                st.success(f"{key} ذخیره شد.")
                st.rerun()

    with c2:
        st.markdown("**حذف دسترسی**")
        with st.form("del_form"):
            target = st.selectbox("انتخاب کاربر", options=[""] + sorted(users.keys()))
            deleted = st.form_submit_button("حذف", use_container_width=True)
        if deleted:
            if not target:
                st.error("یک کاربر انتخاب کنید.")
            elif target == st.session_state.get("user"):
                st.error("حساب خودتان را نمی‌توانید حذف کنید.")
            elif len([1 for r in users.values() if r.get("role") == "admin"]) <= 1 \
                    and users.get(target, {}).get("role") == "admin":
                st.error("آخرین مدیر سیستم قابل حذف نیست.")
            else:
                users.pop(target, None)
                save_users(users)
                st.success("دسترسی حذف شد.")
                st.rerun()


# ==================================================================
# ۸) برنامه اصلی
# ==================================================================
def main() -> None:
    users = load_users()
    email_cfg = load_email_cfg()

    if not st.session_state.get("user"):
        login_page(users)
        return

    current = st.session_state["user"]
    rec = users.get(current)
    if not rec:
        st.session_state.pop("user", None)
        st.warning("دسترسی این حساب حذف شده است.")
        st.rerun()

    is_admin = rec.get("role") == "admin"

    # ---------------- نوار کناری ----------------
    with st.sidebar:
        st.markdown("### 📈 پایش ارتعاشات")
        st.caption(("👤 مدیر سیستم" if is_admin else "👁 ناظر") + f" — {current}")
        if st.button("خروج از حساب", use_container_width=True):
            st.session_state.pop("user", None)
            st.rerun()

        st.divider()
        st.markdown("**منبع داده**")
        mode = st.radio(
            "انتخاب منبع",
            options=["داده نمونه", "لینک شیت / CSV"],
            index=0,
            label_visibility="collapsed",
        )
        data_url = ""
        if mode == "لینک شیت / CSV":
            data_url = st.text_input(
                "آدرس CSV یا شناسه گوگل‌شیت",
                placeholder="https://docs.google.com/spreadsheets/d/.../edit",
            ).strip()
            if st.button("به‌روزرسانی داده", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

        st.divider()
        st.caption(f"نسخه ۴.۰ | {datetime.now():%Y-%m-%d %H:%M}")

    # ---------------- بارگذاری داده ----------------
    df, source_name = None, ""
    if mode == "لینک شیت / CSV" and data_url:
        try:
            df = load_from_url(data_url)
            source_name = "گوگل‌شیت / CSV"
        except Exception as exc:
            st.error(f"خواندن داده ناموفق بود: {exc}")
            st.info("داده نمونه نمایش داده می‌شود تا داشبورد از کار نیفتد.")
    if df is None:
        df = normalize_columns(build_sample_data())
        source_name = "داده نمونه"

    if df.empty:
        st.warning("داده‌ای برای نمایش وجود ندارد.")
        return

    equipments = sorted(df["equipment"].unique().tolist())

    # ---------------- عنوان ----------------
    st.title("داشبورد پایش ارتعاشات سیمان تهران")
    st.caption(f"منبع داده: {source_name} | تعداد رکورد: {len(df):,} | "
               f"آخرین رکورد: {df['timestamp'].max():%Y-%m-%d %H:%M}")

    tabs = st.tabs(
        ["🗂 نمای کلی", "📊 جزئیات تجهیز", "🚨 اعلانیه‌ها",
         "✉️ ارسال اعلان", "⚙️ تنظیمات ایمیل", "🔑 کاربران"]
    )
    with tabs[0]:
        tab_overview(df, equipments)
    with tabs[1]:
        tab_equipment(df, equipments)
    with tabs[2]:
        tab_alerts(df)
    with tabs[3]:
        tab_notify(df, email_cfg, is_admin)
    with tabs[4]:
        tab_email_settings(email_cfg, is_admin)
    with tabs[5]:
        tab_users(users, is_admin)

    # ---------------- پانویس ----------------
    st.divider()
    c_left, c_right = st.columns([3, 1])
    with c_left:
        st.markdown(
            f'<div class="credit">نسخه ۴.۰ | منبع: {source_name} | '
            f'آخرین به‌روزرسانی: {datetime.now():%Y-%m-%d %H:%M}<br>'
            "قاعده نقاط: P1 و P2 الکتروموتور؛ از P3 به بعد تجهیز گردان.</div>",
            unsafe_allow_html=True,
        )
    with c_right:
        st.markdown(
            '<div class="credit" style="text-align:left">طراحی و توسعه<br>'
            "<b>م. هادی زندیه</b></div>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
