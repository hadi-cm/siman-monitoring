# -*- coding: utf-8 -*-
"""
سیستم هوشمند پایش وضعیت ارتعاش - سیمان تهران
نسخه: v6.4

تغییرات این نسخه:
  1) شمارش نقاط نیازمند توجه حذف شد.
  2) دسته‌بندی وضعیت دقیقاً طبق لیست تاییدشده کاربر:
     نرمال / نیازمند مراقبت و کنترل / هشدار / خطر-بحرانی / سایر / بدون وضعیت ثبت شده
  3) جدول، متن ستون وضعیت را عیناً (بدون هیچ تغییر) نمایش می‌دهد؛
     دسته‌بندی فقط برای نمودار دایره‌ای انتهای صفحه استفاده می‌شود.

اجرا:
    pip install streamlit pandas openpyxl
    streamlit run vibration_monitor_tehran_cement_v6_4.py
"""

import math
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# تنظیمات صفحه
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="سیستم هوشمند پایش وضعیت - سیمان تهران",
    page_icon="📈",
    layout="wide",
)

# ---------------------------------------------------------------------------
# تنظیمات اتصال به گوگل شیت (در صورت نیاز پر شود)
#   - فایل کلید سرویس اکانت را کنار همین اسکریپت بگذارید: service_account.json
#   - شناسه شیت را در SHEET_ID قرار دهید
# ---------------------------------------------------------------------------
SERVICE_ACCOUNT_FILE = "service_account.json"
SHEET_ID = ""          # مثال: "1AbCdEfGhIjKlMnOpQrStUvWxYz"
SHEET_NAME = "Assets"  # نام تب داخل فایل گوگل شیت

# ---------------------------------------------------------------------------
# کاربران (قابل ویرایش)
# ---------------------------------------------------------------------------
PASSWORD = "siman123"

USERS = {
    "zandieh@tehrancement.ir":       {"name": "مهندس هادی زندیه",        "role": "مدیر ارشد"},
    "tehrancment@gmail.com":         {"name": "مهندس حسینی",             "role": "مدیر"},
    "maintenance@tehrancement.ir":   {"name": "واحد نگهداری و تعمیرات",  "role": "مدیر"},
    "production@tehrancement.ir":    {"name": "واحد تولید",              "role": "کاربر"},
    "electrical@tehrancement.ir":    {"name": "واحد برق و ابزار دقیق",   "role": "کاربر"},
    "quality@tehrancement.ir":       {"name": "واحد کنترل کیفیت",        "role": "کاربر"},
    "planning@tehrancement.ir":      {"name": "واحد برنامه‌ریزی",        "role": "کاربر"},
}

# ---------------------------------------------------------------------------
# ستون‌های شیت Assets (بر اساس فایل واقعی کاربر)
# ---------------------------------------------------------------------------
COLUMNS = [
    "نام تجهیز",      # A  (در شیت با عنوان «دام تجهیز» هم دیده شده)
    "خط تولید",       # B
    "واحد",           # C
    "نوع تجهیز",      # D
    "راهنمای نقاط",   # E  -> P1, P2, ...
    "شماره بیرینگ",   # F
    "بوش",            # G
    "دور نامی",       # H
    "سیستم درایور",   # I
    "وضعیت",          # ستون وضعیت (نوشته‌ی خود کاربر)
]

COLUMN_ALIASES = {
    "دام تجهیز": "نام تجهیز",
    "نام دستگاه": "نام تجهیز",
    "تجهیز": "نام تجهیز",
    "خط": "خط تولید",
    "واحد تولید": "واحد",
    "نقطه": "راهنمای نقاط",
    "نقاط": "راهنمای نقاط",
    "کد نقطه": "راهنمای نقاط",
    "بیرینگ": "شماره بیرینگ",
    "شماره برینگ": "شماره بیرینگ",
    "شماره بیرینگ‌ها": "شماره بیرینگ",
    "دور": "دور نامی",
    "دور موتور": "دور نامی",
    "درایور": "سیستم درایور",
    "وضعیت نقطه": "وضعیت",
}

# ---------------------------------------------------------------------------
# دسته‌بندی وضعیت (فقط برای نمودار دایره‌ای)
# ---------------------------------------------------------------------------
STATUS_CATEGORIES = [
    ("نرمال",                  ["نرمال", "سالم", "خوب", "عادی"],                              "#2e7d32"),
    ("نیازمند مراقبت و کنترل", ["نیازمند مراقبت و کنترل", "نیازمند مراقبت", "مراقبت",
                                "نیازمند کنترل", "کنترل", "بررسی"],                            "#f9a825"),
    ("هشدار",                  ["هشدار"],                                                      "#ef6c00"),
    ("خطر/بحرانی",             ["خطر/بحرانی", "خطر / بحرانی", "خطر", "بحرانی", "اضطرار"],      "#c62828"),
]
OTHER_COLOR = "#78909c"
EMPTY_COLOR = "#b0bec5"
EMPTY_LABEL = "بدون وضعیت ثبت شده"
OTHER_LABEL = "سایر"


# ---------------------------------------------------------------------------
# ابزارهای کمکی
# ---------------------------------------------------------------------------
def normalize_text(value) -> str:
    """یکسان‌سازی حروف عربی/فارسی و حذف فاصله‌های اضافی."""
    if value is None:
        return ""
    text = str(value)
    text = text.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_key(text):
    return normalize_text(text).replace(" ", "")


def categorize(status_value: str) -> str:
    """تبدیل متن آزاد ستون وضعیت به یکی از دسته‌های نمودار."""
    raw = normalize_text(status_value)
    if raw == "" or raw in ("-", "—", "nan", "None"):
        return EMPTY_LABEL
    probe = raw.replace(" ", "")
    for label, keywords, _color in STATUS_CATEGORIES:
        for kw in keywords:
            if normalize_key(kw) in probe:
                return label
    return OTHER_LABEL


def point_order(code) -> int:
    match = re.search(r"(\d+)", str(code))
    return int(match.group(1)) if match else 999


def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """یکسان‌سازی نام ستون‌ها و مرتب‌سازی مقادیر."""
    df = df.copy()
    df.columns = [normalize_text(c) for c in df.columns]
    df = df.rename(columns={k: v for k, v in COLUMN_ALIASES.items() if k in df.columns})

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNS]
    df = df.dropna(how="all")

    for col in COLUMNS:
        df[col] = df[col].apply(lambda v: "" if pd.isna(v) else str(v).strip())

    df = df[df["نام تجهیز"].apply(lambda v: v != "")]
    df["_order"] = df["راهنمای نقاط"].apply(point_order)
    df = df.sort_values(["خط تولید", "واحد", "نام تجهیز", "_order"], kind="mergesort")
    df = df.drop(columns=["_order"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# داده نمونه (تا زمان اتصال کامل به شیت)
# ---------------------------------------------------------------------------
def sample_data() -> pd.DataFrame:
    rows = []

    # --- فیدر آسیاب سنگ (۴ نقطه، بدون شماره بیرینگ) ---
    for p in ["P1", "P2", "P3", "P4"]:
        rows.append({
            "نام تجهیز": "فیدر آسیاب سنگ", "خط تولید": "8", "واحد": "آسیاب سنگ",
            "نوع تجهیز": "گیربکس", "راهنمای نقاط": p, "شماره بیرینگ": "",
            "بوش": "", "دور نامی": "", "سیستم درایور": "کوپلینگ", "وضعیت": "",
        })

    # --- کراشر (۶ نقطه) ---
    crusher = [
        ("P1", "6234+NU234",        "",       "1000", "نرمال"),
        ("P2", "6234",              "",       "1000", "نرمال"),
        ("P3", "22236/K30/W33/C3",  "AOH3136", "1000", "نیازمند مراقبت و کنترل"),
        ("P4", "22236/K30/W33/C3",  "AOH3136", "1000", "هشدار"),
        ("P5", "24192E CA K30/W33", "AOH4192", "220",  "نرمال"),
        ("P6", "24192E CA K30/W33", "AOH4192", "220",  ""),
    ]
    for p, brg, bush, rpm, stt in crusher:
        rows.append({
            "نام تجهیز": "کراشر", "خط تولید": "8", "واحد": "آسیاب سنگ",
            "نوع تجهیز": "کراشر", "راهنمای نقاط": p, "شماره بیرینگ": brg,
            "بوش": bush, "دور نامی": rpm, "سیستم درایور": "کوپلینگ", "وضعیت": stt,
        })

    # --- میل فن مواد ۸ (۴ نقطه) ---
    mill_fan = [
        ("P1", "22222",  "انتهای موتور",  "1000", "نرمال"),
        ("P2", "6322",   "سر موتور",      "1000", "هشدار"),
        ("P3", "22320",  "یاتاقان سمت کوره", "1000", "نیازمند مراقبت و کنترل"),
        ("P4", "22320",  "سمت آزاد",      "1000", "نرمال"),
    ]
    for p, brg, pos, rpm, stt in mill_fan:
        rows.append({
            "نام تجهیز": "میل فن مواد ۸", "خط تولید": "8", "واحد": "آسیاب سنگ",
            "نوع تجهیز": "فن", "راهنمای نقاط": p, "شماره بیرینگ": brg,
            "بوش": "", "دور نامی": rpm, "سیستم درایور": "کوپلینگ", "وضعیت": stt,
        })

    return pd.DataFrame(rows, columns=COLUMNS)


# ---------------------------------------------------------------------------
# خواندن داده: فایل آپلودی > گوگل شیت > داده نمونه
# ---------------------------------------------------------------------------
def read_uploaded(file) -> pd.DataFrame:
    if file.name.lower().endswith(".csv"):
        try:
            return pd.read_csv(file, encoding="utf-8-sig")
        except UnicodeDecodeError:
            file.seek(0)
            return pd.read_csv(file, encoding="cp1256")
    return pd.read_excel(file)


def read_gsheet() -> pd.DataFrame:
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
    client = gspread.authorize(creds)
    worksheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    records = worksheet.get_all_records()
    if not records:
        raise ValueError("شیت خالی است.")
    return pd.DataFrame(records)


@st.cache_data(show_spinner=False)
def load_data(_uploaded=None, use_gsheet: bool = True) -> tuple:
    if _uploaded is not None:
        return prepare_dataframe(read_uploaded(_uploaded)), "فایل آپلودی"
    if use_gsheet and SHEET_ID and os.path.exists(SERVICE_ACCOUNT_FILE):
        try:
            return prepare_dataframe(read_gsheet()), "گوگل شیت"
        except Exception as exc:  # noqa: BLE001
            st.warning(f"خواندن گوگل شیت ممکن نشد ({exc}). داده نمونه استفاده شد.")
    return prepare_dataframe(sample_data()), "داده نمونه"


# ---------------------------------------------------------------------------
# نمودار دایره‌ای (SVG، بدون وابستگی اضافی و با پشتیبانی کامل فارسی)
# ---------------------------------------------------------------------------
def build_donut_svg(items, size: int = 340, radius: int = 82, thickness: int = 40) -> str:
    """items: لیست (label, count, color)."""
    total = sum(c for _, c, _ in items)
    center = size / 2
    circumference = 2 * math.pi * radius

    circles = []
    offset = 0.0
    for _label, count, color in items:
        frac = count / total if total else 0
        dash = frac * circumference
        gap = circumference - dash
        circles.append(
            f'<circle r="{radius}" fill="none" stroke="{color}" stroke-width="{thickness}" '
            f'stroke-dasharray="{dash:.3f} {gap:.3f}" stroke-dashoffset="{-offset:.3f}" '
            f'stroke-linecap="butt"/>'
        )
        offset += dash

    svg = f"""
    <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">
      <g transform="translate({center},{center}) rotate(-90)">
        <circle r="{radius}" fill="none" stroke="#eceff1" stroke-width="{thickness}"/>
        {''.join(circles)}
      </g>
      <text x="{center}" y="{center - 6}" text-anchor="middle"
            font-size="14" fill="#607d8b" font-family="Tahoma, sans-serif">مجموع نقاط</text>
      <text x="{center}" y="{center + 22}" text-anchor="middle"
            font-size="24" fill="#263238" font-weight="bold" font-family="Tahoma, sans-serif">{total}</text>
    </svg>
    """
    return svg


def build_legend_html(items) -> str:
    total = sum(c for _, c, _ in items)
    rows = []
    for label, count, color in items:
        pct = (count / total * 100) if total else 0
        rows.append(
            f'<div style="display:flex;align-items:center;gap:10px;margin:6px 0;">'
            f'<span style="width:16px;height:16px;border-radius:4px;background:{color};'
            f'display:inline-block;flex:0 0 16px;"></span>'
            f'<span style="flex:1;font-size:14px;color:#263238;">{label}</span>'
            f'<span style="font-size:13px;color:#607d8b;">{count} نقطه</span>'
            f'<span style="font-size:14px;font-weight:bold;color:#263238;min-width:56px;'
            f'text-align:left;">{pct:.1f}%</span>'
            f'</div>'
        )
    return "".join(rows)


# ---------------------------------------------------------------------------
# استایل
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .main .block-container { direction: rtl; text-align: right; padding-top: 1.2rem; }
    .app-header {
        background: linear-gradient(90deg, #0d47a1 0%, #1976d2 55%, #42a5f5 100%);
        color: #fff; padding: 18px 24px; border-radius: 14px; margin-bottom: 18px;
        box-shadow: 0 6px 18px rgba(13, 71, 161, .25);
    }
    .app-header h1 { margin: 0; font-size: 22px; }
    .app-header p  { margin: 6px 0 0; font-size: 13px; opacity: .9; }
    .info-card {
        background: #f5f9ff; border: 1px solid #d6e4f7; border-radius: 12px;
        padding: 12px 14px; margin-bottom: 10px;
    }
    .info-card .lbl { font-size: 12px; color: #607d8b; }
    .info-card .val { font-size: 15px; color: #0d47a1; font-weight: bold; margin-top: 4px; }
    .legend-box {
        background: #fff; border: 1px solid #e0e6ed; border-radius: 12px;
        padding: 14px 18px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# ورود
# ---------------------------------------------------------------------------
if "user_email" not in st.session_state:
    st.session_state.user_email = None

if st.session_state.user_email is None:
    st.markdown(
        '<div class="app-header"><h1>سیستم هوشمند پایش وضعیت - سیمان تهران</h1>'
        "<p>ورود به سامانه</p></div>",
        unsafe_allow_html=True,
    )
    with st.form("login"):
        email = st.text_input("ایمیل سازمانی")
        password = st.text_input("رمز عبور", type="password")
        submitted = st.form_submit_button("ورود")
    if submitted:
        key = email.strip().lower()
        if key in {k.lower(): k for k in USERS}.keys() and password == PASSWORD:
            st.session_state.user_email = key
            st.rerun()
        else:
            st.error("ایمیل یا رمز عبور درست نیست.")
    st.stop()

current_email = st.session_state.user_email
user_info = USERS.get(current_email, {"name": current_email, "role": "کاربر"})
role = user_info["role"]

# ---------------------------------------------------------------------------
# هدر
# ---------------------------------------------------------------------------
st.markdown(
    f'<div class="app-header"><h1>سیستم هوشمند پایش وضعیت - سیمان تهران</h1>'
    f"<p>{user_info['name']} — {role}</p></div>",
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(f"**{user_info['name']}**")
    st.caption(role)
    uploaded = st.file_uploader("فایل شیت (csv / xlsx)", type=["csv", "xlsx", "xls"])
    use_gsheet = st.checkbox("خواندن از گوگل شیت", value=bool(SHEET_ID))
    if st.button("خروج"):
        st.session_state.user_email = None
        st.rerun()

df, source = load_data(uploaded, use_gsheet)

# ---------------------------------------------------------------------------
# تب‌ها
# ---------------------------------------------------------------------------
if role == "مدیر ارشد":
    tabs = st.tabs(["داشبورد", "ارسال اعلان", "مدیریت کاربران"])
elif role == "مدیر":
    tabs = st.tabs(["داشبورد", "ارسال اعلان"])
else:
    tabs = st.tabs(["داشبورد"])

dashboard = tabs[0]

# ---------------------------------------------------------------------------
# داشبورد
# ---------------------------------------------------------------------------
with dashboard:
    st.caption(f"منبع داده: {source} — تعداد ردیف‌ها: {len(df)}")

    if df.empty:
        st.warning("داده‌ای برای نمایش وجود ندارد.")
        st.stop()

    lines = sorted(df["خط تولید"].unique(), key=lambda v: (len(str(v)), str(v)))
    c1, c2, c3 = st.columns(3)

    with c1:
        line = st.selectbox("خط تولید", lines)
    units = sorted(df.loc[df["خط تولید"] == line, "واحد"].unique())
    with c2:
        unit = st.selectbox("واحد", units if units else ["-"])
    equipments = sorted(df.loc[(df["خط تولید"] == line) & (df["واحد"] == unit), "نام تجهیز"].unique())
    with c3:
        equipment = st.selectbox("تجهیز", equipments if equipments else ["-"])

    equipment_df = df[(df["خط تولید"] == line) & (df["واحد"] == unit) & (df["نام تجهیز"] == equipment)]
    equipment_df = equipment_df.sort_values(
        by="راهنمای نقاط", key=lambda s: s.apply(point_order), kind="mergesort"
    )

    unit_df = df[(df["خط تولید"] == line) & (df["واحد"] == unit)]

    if equipment_df.empty:
        st.info("برای انتخاب‌های بالا تجهیزی یافت نشد.")
    else:
        first = equipment_df.iloc[0]
        st.markdown(f"#### {equipment}")
        m1, m2, m3, m4 = st.columns(4)
        for col, label, value in (
            (m1, "نوع تجهیز", first["نوع تجهیز"]),
            (m2, "دور نامی (rpm)", first["دور نامی"]),
            (m3, "سیستم درایور", first["سیستم درایور"]),
            (m4, "تعداد نقاط", str(len(equipment_df))),
        ):
            with col:
                shown = value if str(value).strip() != "" else "—"
                st.markdown(
                    f'<div class="info-card"><div class="lbl">{label}</div>'
                    f'<div class="val">{shown}</div></div>',
                    unsafe_allow_html=True,
                )

        table = equipment_df[["راهنمای نقاط", "شماره بیرینگ", "بوش", "دور نامی", "سیستم درایور", "وضعیت"]].copy()
        table = table.rename(columns={"راهنمای نقاط": "کد نقطه"})
        table["شماره بیرینگ"] = table["شماره بیرینگ"].apply(
            lambda v: v if str(v).strip() != "" else "—"
        )
        table["بوش"] = table["بوش"].apply(lambda v: v if str(v).strip() != "" else "—")

        def color_status(val):
            cat = categorize(val)
            palette = {label: color for label, _k, color in STATUS_CATEGORIES}
            if cat in palette:
                return f"background-color:{palette[cat]}22; color:{palette[cat]}; font-weight:600;"
            if cat == EMPTY_LABEL:
                return "color:#90a4ae; font-style:italic;"
            return "color:#455a64; font-weight:600;"

        try:
            styles = table.style.map(color_status, subset=["وضعیت"])
        except AttributeError:
            styles = table.style.applymap(color_status, subset=["وضعیت"])

        st.dataframe(styles, use_container_width=True, hide_index=True)
        st.caption("متن ستون وضعیت عیناً از شیت خوانده می‌شود و هیچ محاسبه‌ای روی آن انجام نمی‌شود.")

    # -----------------------------------------------------------------
    # نمودار دایره‌ای انتهای صفحه
    # -----------------------------------------------------------------
    st.divider()
    st.markdown("### سهم درصدی وضعیت نقاط")

    scope = st.radio(
        "دامنه نمودار",
        ["تجهیز انتخاب‌شده", "کل واحد انتخاب‌شده", "کل شیت"],
        horizontal=True,
        index=0,
    )
    if scope == "تجهیز انتخاب‌شده":
        scope_df = equipment_df
    elif scope == "کل واحد انتخاب‌شده":
        scope_df = unit_df
    else:
        scope_df = df

    if scope_df.empty:
        st.info("داده‌ای برای رسم نمودار نیست.")
    else:
        cats = scope_df["وضعیت"].apply(categorize)
        items = []
        order_labels = [label for label, _k, _c in STATUS_CATEGORIES] + [OTHER_LABEL, EMPTY_LABEL]
        color_map = {label: color for label, _k, color in STATUS_CATEGORIES}
        color_map[OTHER_LABEL] = OTHER_COLOR
        color_map[EMPTY_LABEL] = EMPTY_COLOR

        for label in order_labels:
            count = int((cats == label).sum())
            if count > 0:
                items.append((label, count, color_map[label]))

        left, right = st.columns([1, 1])
        with left:
            st.markdown(build_donut_svg(items), unsafe_allow_html=True)
        with right:
            st.markdown(
                f'<div class="legend-box">{build_legend_html(items)}</div>',
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# تب ارسال اعلان (مدیر و مدیر ارشد)
# ---------------------------------------------------------------------------
if role in ("مدیر", "مدیر ارشد"):
    with tabs[1]:
        st.subheader("ارسال اعلان ایمیلی")
        with st.form("notify"):
            recipients = st.multiselect(
                "گیرندگان", options=list(USERS.keys()),
                format_func=lambda e: f"{USERS[e]['name']} — {e}",
            )
            subject = st.text_input("موضوع", value="اعلان پایش وضعیت - سیمان تهران")
            body = st.text_area("متن اعلان", height=160)
            send = st.form_submit_button("ارسال")
        if send:
            if not recipients:
                st.error("حداقل یک گیرنده انتخاب کنید.")
            else:
                try:
                    host = st.secrets.get("SMTP_HOST", "smtp.gmail.com")
                    port = int(st.secrets.get("SMTP_PORT", 587))
                    sender = st.secrets.get("SMTP_USER", "tehrancment@gmail.com")
                    app_pass = st.secrets.get("SMTP_PASS", "")

                    if not app_pass:
                        raise RuntimeError("رمز اپلیکیشن در secrets تنظیم نشده است.")

                    msg = MIMEMultipart()
                    msg["From"] = sender
                    msg["To"] = ", ".join(recipients)
                    msg["Subject"] = subject
                    msg.attach(MIMEText(body, "plain", "utf-8"))

                    with smtplib.SMTP(host, port) as server:
                        server.starttls()
                        server.login(sender, app_pass)
                        server.sendmail(sender, recipients, msg.as_string())

                    st.success("اعلان ارسال شد.")
                except Exception as exc:  # noqa: BLE001
                    st.warning(f"ارسال واقعی انجام نشد ({exc}). پیش‌نمایش متن اعلان:")
                    st.code(f"به: {', '.join(recipients)}\nموضوع: {subject}\n\n{body}")

# ---------------------------------------------------------------------------
# تب مدیریت کاربران (فقط مدیر ارشد)
# ---------------------------------------------------------------------------
if role == "مدیر ارشد":
    with tabs[2]:
        st.subheader("مدیریت کاربران")
        users_df = pd.DataFrame(
            [{"ایمیل": e, "نام": v["name"], "نقش": v["role"]} for e, v in USERS.items()]
        )
        st.dataframe(users_df, use_container_width=True, hide_index=True)
        st.caption("فهرست کاربران در دیکشنری USERS بالای فایل تعریف شده است.")
