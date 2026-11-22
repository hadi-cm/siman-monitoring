# -*- coding: utf-8 -*-
"""
سیستم هوشمند پایش وضعیت - سیمان تهران
نسخه 6.8

قابلیت‌ها:
  - ورود با ایمیل و رمز عبور (۷ کاربر سازمانی)
  - فیلتر زنجیره‌ای: خط ← واحد ← تجهیز
  - نمایش نقاط اندازه‌گیری و شماره بیرینگ زیر هر تجهیز
  - پشتیبانی از بیرینگ ترکیبی مانند 6234+NU234 و خط تیره برای نقاط بدون بیرینگ
  - ستون وضعیت عیناً همان چیزی است که در شیت نوشته شده (هیچ منطق خودکاری ندارد)
  - رنگ‌آمیزی سلول وضعیت فقط برای خوانایی
  - نمودار دایره‌ای انتهای صفحه با شش دسته ثابت
  - هیچ شمارشی از «نقاط نیازمند توجه» انجام نمی‌شود
"""

import html
import os
import io
import datetime as dt

import pandas as pd
import streamlit as st
import plotly.express as px


# ============================================================
# 0. تنظیمات صفحه
# ============================================================

st.set_page_config(
    page_title="سیستم هوشمند پایش وضعیت-سیمان تهران",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700&display=swap');

        html, body, [class*="css"], .stMarkdown, .stText, p, div, span, label,
        input, textarea, select, button, table {
            font-family: 'Vazirmatn', Tahoma, 'Iranian Sans', sans-serif !important;
        }

        .stApp { direction: rtl; text-align: right; }

        .main-title {
            background: linear-gradient(90deg, #0d3b66 0%, #1d6fa5 60%, #2a9d8f 100%);
            color: #ffffff;
            padding: 20px 26px;
            border-radius: 14px;
            margin-bottom: 18px;
            box-shadow: 0 4px 14px rgba(13, 59, 102, .25);
        }
        .main-title h1 { margin: 0; font-size: 26px; font-weight: 700; }
        .main-title p  { margin: 6px 0 0 0; font-size: 14px; opacity: .9; }

        .equip-card {
            background: #f4f8fb;
            border-right: 6px solid #1d6fa5;
            border-radius: 10px;
            padding: 10px 16px;
            margin: 18px 0 8px 0;
        }
        .equip-card h3 { margin: 0; font-size: 17px; color: #0d3b66; }
        .equip-card span { font-size: 12px; color: #5a6b7b; }

        table.vib-table {
            width: 100%;
            border-collapse: collapse;
            direction: rtl;
            font-size: 14px;
            margin-bottom: 10px;
        }
        table.vib-table th {
            background: #0d3b66;
            color: #ffffff;
            padding: 9px 10px;
            text-align: center;
            font-weight: 600;
            border: 1px solid #0a2e50;
        }
        table.vib-table td {
            padding: 8px 10px;
            text-align: center;
            border: 1px solid #dbe4ec;
            color: #22262a;
        }
        table.vib-table tr:nth-child(even) td { background: #fafcfe; }
        table.vib-table tr:hover td { background: #eef6fd; }

        .stTabs [data-baseweb="tab"] { font-size: 15px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# 1. ورود کاربران
# ============================================================

USERS = {
    "alireza76ir@gmail.com":         {"password": "siman123", "name": "علیرضا",      "role": "کاربر"},
    "vah.rezaei@gmail.com":          {"password": "siman123", "name": "وهاب رضایی",  "role": "مدیر"},
    "cm.zandiyeh@gmail.com":         {"password": "siman123", "name": "هادی زندیه",  "role": "پیمانکار"},
    "me.vibration.shokri@gmail.com": {"password": "siman123", "name": "مهندس شکری",  "role": "مدیر"},
    "m.babahasan@gmail.com":         {"password": "siman123", "name": "م. باباحسن",  "role": "کاربر"},
    "freedocs.ir@gmail.com":         {"password": "siman123", "name": "فری داکس",    "role": "کاربر"},
    "tehrancment@gmail.com":         {"password": "siman123", "name": "سیمان تهران", "role": "مدیر"},
}

MANAGER_ROLES = ("مدیر",)


def do_login(email: str, password: str):
    email = (email or "").strip().lower()
    user = USERS.get(email)
    if user and user["password"] == password:
        return {"email": email, **user}
    return None


def login_screen():
    st.markdown(
        """
        <div class="main-title">
            <h1>سیستم هوشمند پایش وضعیت</h1>
            <p>شرکت سیمان تهران — ورود به سامانه</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_l, col_c, col_r = st.columns([1, 1.1, 1])
    with col_c:
        with st.form("login_form"):
            email = st.text_input("ایمیل سازمانی", placeholder="name@gmail.com")
            password = st.text_input("رمز عبور", type="password")
            ok = st.form_submit_button("ورود", use_container_width=True)

        if ok:
            user = do_login(email, password)
            if user:
                st.session_state["user"] = user
                st.rerun()
            else:
                st.error("ایمیل یا رمز عبور نادرست است.")


if "user" not in st.session_state:
    login_screen()
    st.stop()

CURRENT_USER = st.session_state["user"]
IS_MANAGER = CURRENT_USER["role"] in MANAGER_ROLES


# ============================================================
# 2. بارگذاری داده
# ============================================================

COLUMN_ALIASES = {
    "line":      ["خط", "خط تولید", "line"],
    "unit":      ["واحد", "یونیت", "بخش", "unit"],
    "equipment": ["تجهیز", "دستگاه", "ماشین", "تگ", "equipment", "tag"],
    "point":     ["نقطه", "نقطه اندازه‌گیری", "محل اندازه‌گیری", "موقعیت", "point"],
    "bearing":   ["بیرینگ", "شماره بیرینگ", "بلبرینگ", "یاتاقان", "bearing"],
    "direction": ["جهت", "جهت اندازه‌گیری", "direction"],
    "status":    ["وضعیت", "وضعیت ارتعاش", "وضعیت تجهیز", "status"],
    "date":      ["تاریخ", "تاریخ اندازه‌گیری", "date"],
    "rms":       ["rms", "مقدار", "ارتعاش", "سرعت ارتعاش", "mm/s"],
}

REQUIRED = ["line", "unit", "equipment", "point", "bearing", "direction", "status", "date", "rms"]

PERSIAN_LABELS = {
    "line": "خط",
    "unit": "واحد",
    "equipment": "تجهیز",
    "point": "نقطه اندازه‌گیری",
    "bearing": "شماره بیرینگ",
    "direction": "جهت",
    "status": "وضعیت",
    "date": "تاریخ",
    "rms": "RMS (mm/s)",
}


def _norm(text) -> str:
    if text is None:
        return ""
    return (
        str(text)
        .strip()
        .replace("ي", "ی")
        .replace("ك", "ک")
        .replace("\u200c", " ")
        .replace("  ", " ")
        .lower()
    )


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """نام ستون‌های شیت را به کلیدهای استاندارد تبدیل می‌کند."""
    mapping = {}
    used = set()
    for col in df.columns:
        n = _norm(col)
        for key, aliases in COLUMN_ALIASES.items():
            if key in used:
                continue
            if any(n == _norm(a) for a in aliases):
                mapping[col] = key
                used.add(key)
                break
        if col in mapping:
            continue
        for key, aliases in COLUMN_ALIASES.items():
            if key in used:
                continue
            if any(_norm(a) in n for a in aliases):
                mapping[col] = key
                used.add(key)
                break

    df = df.rename(columns=mapping)

    for key in REQUIRED:
        if key not in df.columns:
            df[key] = ""
    return df[REQUIRED].copy()


def sample_data() -> pd.DataFrame:
    """داده نمونه — برای تست برنامه؛ با بارگذاری فایل واقعی جایگزین می‌شود."""
    rows = [
        # خط ۸ — واحد آسیاب سیمان
        ("خط ۸", "واحد آسیب سیمان", "آسیاب سیمان ۸ — موتور اصلی", "نقطه ۱ (DE)", "6234+NU234", "افقی", "نرمال", "1405/08/15", 2.1),
        ("خط ۸", "واحد آسیاب سیمان", "آسیاب سیمان ۸ — موتور اصلی", "نقطه ۱ (DE)", "6234+NU234", "عمودی", "نرمال", "1405/08/15", 1.8),
        ("خط ۸", "واحد آسیاب سیمان", "آسیاب سیمان ۸ — موتور اصلی", "نقطه ۱ (DE)", "6234+NU234", "محوری", "نرمال", "1405/08/15", 1.2),
        ("خط ۸", "واحد آسیاب سیمان", "آسیاب سیمان ۸ — موتور اصلی", "نقطه ۲ (NDE)", "NU234", "افقی", "هشدار", "1405/08/15", 7.4),
        ("خط ۸", "واحد آسیاب سیمان", "آسیاب سیمان ۸ — موتور اصلی", "نقطه ۲ (NDE)", "NU234", "عمودی", "نیازمند مراقبت و کنترل", "1405/08/15", 5.6),
        ("خط ۸", "واحد آسیاب سیمان", "آسیاب سیمان ۸ — موتور اصلی", "نقطه ۲ (NDE)", "NU234", "محوری", "نرمال", "1405/08/15", 1.9),
        ("خط ۸", "واحد آسیاب سیمان", "آسیاب سیمان ۸ — گیربکس", "نقطه ۳ (HSS)", "—", "افقی", "خطر/ بحرانی", "1405/08/15", 11.2),
        ("خط ۸", "واحد آسیاب سیمان", "آسیاب سیمان ۸ — گیربکس", "نقطه ۳ (HSS)", "—", "عمودی", "هشدار", "1405/08/15", 8.1),
        ("خط ۸", "واحد آسیاب سیمان", "آسیاب سیمان ۸ — گیربکس", "نقطه ۳ (HSS)", "—", "محوری", "نیازمند مراقبت و کنترل", "1405/08/15", 4.4),
        # خط ۸ — واحد آسیاب مواد خام
        ("خط ۸", "واحد آسیاب مواد خام", "آسیاب مواد ۸ — موتور", "نقطه ۱ (DE)", "6320 M", "افقی", "نرمال", "1405/08/15", 2.4),
        ("خط ۸", "واحد آسیاب مواد خام", "آسیاب مواد ۸ — موتور", "نقطه ۱ (DE)", "6320 M", "عمودی", "نرمال", "1405/08/15", 2.0),
        ("خط ۸", "واحد آسیاب مواد خام", "آسیاب مواد ۸ — موتور", "نقطه ۱ (DE)", "6320 M", "محوری", "نرمال", "1405/08/15", 1.5),
        ("خط ۸", "واحد آسیاب مواد خام", "فن ID آسیاب مواد", "نقطه ۱ (DE)", "22222 E", "افقی", "هشدار", "1405/08/15", 6.3),
        ("خط ۸", "واحد آسیاب مواد خام", "فن ID آسیاب مواد", "نقطه ۱ (DE)", "22222 E", "عمودی", "نیازمند مراقبت و کنترل", "1405/08/15", 4.9),
        ("خط ۸", "واحد آسیاب مواد خام", "فن ID آسیاب مواد", "نقطه ۱ (DE)", "22222 E", "محوری", "نرمال", "1405/08/15", 2.2),
        # خط ۹ — واحد پخت
        ("خط ۹", "واحد پخت", "فن EP", "نقطه ۱ (DE)", "23136", "افقی", "خطر/ بحرانی", "1405/08/15", 12.5),
        ("خط ۹", "واحد پخت", "فن EP", "نقطه ۱ (DE)", "23136", "عمودی", "هشدار", "1405/08/15", 9.4),
        ("خط ۹", "واحد پخت", "فن EP", "نقطه ۱ (DE)", "23136", "محوری", "سایر", "1405/08/15", 3.3),
        # خط ۹ — واحد سیمان
        ("خط ۹", "واحد سیمان", "نوار نقاله ۹", "نقطه ۱ (DE)", "—", "افقی", "", "1405/08/15", 3.0),
        ("خط ۹", "واحد سیمان", "نوار نقاله ۹", "نقطه ۱ (DE)", "—", "عمودی", "سایر", "1405/08/15", 3.6),
    ]
    return pd.DataFrame(rows, columns=REQUIRED)


def load_from_google_sheet():
    """در صورت وجود service_account.json و متغیر SHEET_ID، داده از گوگل شیت خوانده می‌شود."""
    sheet_id = os.environ.get("SHEET_ID", "").strip()
    if not sheet_id:
        try:
            sheet_id = str(st.secrets.get("SHEET_ID", "")).strip()
        except Exception:
            sheet_id = ""

    cred_file = os.environ.get("GOOGLE_CREDENTIALS", "service_account.json")

    if not sheet_id or not os.path.exists(cred_file):
        return None

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ]
        creds = Credentials.from_service_account_file(cred_file, scopes=scopes)
        client = gspread.authorize(creds)
        ws = client.open_by_key(sheet_id).sheet1
        values = ws.get_all_values()
        if not values:
            return None
        header, body = values[0], values[1:]
        return pd.DataFrame(body, columns=header)
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def get_data(uploaded_bytes=None, uploaded_name=None) -> pd.DataFrame:
    df = None

    if uploaded_bytes is not None:
        try:
            if (uploaded_name or "").lower().endswith((".xlsx", ".xls")):
                df = pd.read_excel(io.BytesIO(uploaded_bytes))
            else:
                try:
                    df = pd.read_csv(io.BytesIO(uploaded_bytes), encoding="utf-8-sig")
                except UnicodeDecodeError:
                    df = pd.read_csv(io.BytesIO(uploaded_bytes), encoding="windows-1256")
        except Exception as exc:
            st.error(f"خطا در خواندن فایل: {exc}")
            df = None

    if df is None:
        df = load_from_google_sheet()

    if df is None:
        df = sample_data()

    df = normalize_columns(df)

    for col in REQUIRED:
        df[col] = (
            df[col]
            .astype(str)
            .replace({"nan": "", "None": "", "NaT": ""})
            .str.strip()
        )

    df["bearing"] = df["bearing"].replace({"": "—", "-": "—"})

    def _num(v):
        try:
            return float(str(v).replace(",", "").replace("٫", ".").strip())
        except Exception:
            return None

    df["rms_num"] = df["rms"].apply(_num)
    return df


# ============================================================
# 3. دسته‌بندی وضعیت (فقط برای نمودار و رنگ — نه برای نمایش)
# ============================================================

CATEGORIES = [
    "نرمال",
    "نیازمند مراقبت و کنترل",
    "هشدار",
    "خطر/ بحرانی",
    "سایر",
    "بدون وضعیت ثبت شده",
]

CATEGORY_COLORS = {
    "نرمال": "#2e8b57",
    "نیازمند مراقبت و کنترل": "#e8a33d",
    "هشدار": "#f2c744",
    "خطر/ بحرانی": "#d1495b",
    "سایر": "#8d99ae",
    "بدون وضعیت ثبت شده": "#c9d3dd",
}

CATEGORY_BG = {
    "نرمال": "background:#e6f4ea;",
    "نیازمند مراقبت و کنترل": "background:#fdf1de;",
    "هشدار": "background:#fdf8dc;",
    "خطر/ بحرانی": "background:#fbe4e7;",
    "سایر": "background:#eef0f4;",
    "بدون وضعیت ثبت شده": "background:#f2f5f8;",
}


def categorize(status) -> str:
    """متن ستون وضعیت را به یکی از شش دسته ثابت نسبت می‌دهد."""
    s = _norm(status)
    if s in ("", "nan", "none", "nat", "—", "-"):
        return "بدون وضعیت ثبت شده"
    if any(k in s for k in ["خطر", "بحرانی", "بحران", "اضطرار"]):
        return "خطر/ بحرانی"
    if "هشدار" in s or "اخطار" in s:
        return "هشدار"
    if any(k in s for k in ["مراقبت", "کنترل", "بررسی", "پایش"]):
        return "نیازمند مراقبت و کنترل"
    if any(k in s for k in ["نرمال", "سالم", "خوب", "عادی", "قبول"]):
        return "نرمال"
    return "سایر"


# ============================================================
# 4. سایدبار و بارگذاری داده
# ============================================================

with st.sidebar:
    st.markdown("### 👤 کاربر جاری")
    st.success(f"**{CURRENT_USER['name']}**\n\n{CURRENT_USER['email']}")
    st.caption(f"نقش: {CURRENT_USER['role']}")
    if st.button("🚪 خروج از حساب", use_container_width=True):
        st.session_state.pop("user", None)
        st.rerun()

    st.divider()
    st.markdown("### 📂 منبع داده")
    uploaded = st.file_uploader("بارگذاری فایل شیت ارتعاشات", type=["csv", "xlsx", "xls"])
    st.caption("در صورت بارگذاری نکردن، داده نمونه یا گوگل شیت استفاده می‌شود.")

    st.divider()
    st.markdown("### 🎛️ فیلترها")

df_all = get_data(
    uploaded.getvalue() if uploaded is not None else None,
    uploaded.name if uploaded is not None else None,
)

with st.sidebar:
    lines = ["همه"] + sorted(x for x in df_all["line"].unique() if x)
    sel_line = st.selectbox("خط تولید", lines)

    units_pool = df_all if sel_line == "همه" else df_all[df_all["line"] == sel_line]
    units = ["همه"] + sorted(x for x in units_pool["unit"].unique() if x)
    sel_unit = st.selectbox("واحد", units)

    equip_pool = units_pool if sel_unit == "همه" else units_pool[units_pool["unit"] == sel_unit]
    equips = ["همه"] + sorted(x for x in equip_pool["equipment"].unique() if x)
    sel_equip = st.selectbox("تجهیز", equips)

st.markdown(
    f"""
    <div class="main-title">
        <h1>سیستم هوشمند پایش وضعیت</h1>
        <p>شرکت سیمان تهران — داشبورد فنی ارتعاشات | کاربر:
        {html.escape(CURRENT_USER['name'])} ({html.escape(CURRENT_USER['role'])})</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# اعمال زنجیره‌ای فیلترها
df = df_all.copy()
if sel_line != "همه":
    df = df[df["line"] == sel_line]
if sel_unit != "همه":
    df = df[df["unit"] == sel_unit]
if sel_equip != "همه":
    df = df[df["equipment"] == sel_equip]


# ============================================================
# 5. جدول
# ============================================================

def render_table(sub: pd.DataFrame):
    """جدول HTML با ستون وضعیتِ دست‌نخورده و پس‌زمینه رنگی."""
    head = (
        "<tr>"
        f"<th>{PERSIAN_LABELS['point']}</th>"
        f"<th>{PERSIAN_LABELS['bearing']}</th>"
        f"<th>{PERSIAN_LABELS['direction']}</th>"
        f"<th>{PERSIAN_LABELS['status']}</th>"
        f"<th>{PERSIAN_LABELS['date']}</th>"
        f"<th>{PERSIAN_LABELS['rms']}</th>"
        "</tr>"
    )
    body = []
    for _, r in sub.iterrows():
        cat = categorize(r["status"])
        status_text = str(r["status"]).strip() if str(r["status"]).strip() else "—"
        rms = f"{r['rms_num']:.2f}" if pd.notna(r["rms_num"]) else "—"
        body.append(
            "<tr>"
            f"<td>{html.escape(str(r['point']))}</td>"
            f"<td dir='ltr'><b>{html.escape(str(r['bearing']))}</b></td>"
            f"<td>{html.escape(str(r['direction']))}</td>"
            f"<td style='{CATEGORY_BG[cat]}'><b>{html.escape(status_text)}</b></td>"
            f"<td dir='ltr'>{html.escape(str(r['date']))}</td>"
            f"<td dir='ltr'>{rms}</td>"
            "</tr>"
        )
    st.markdown(
        f"<table class='vib-table'>{head}{''.join(body)}</table>",
        unsafe_allow_html=True,
    )


tab_dash, tab_notify, tab_users, tab_about = st.tabs(
    ["📊 داشبورد ارتعاشات", "📨 ارسال اعلان", "👥 مدیریت کاربران", "ℹ️ راهنما"]
)

# ---------------- داشبورد ----------------
with tab_dash:
    if df.empty:
        st.warning("برای این انتخاب، داده‌ای یافت نشد.")
    else:
        for equip, group in df.groupby("equipment", sort=False):
            unit_label = group["unit"].iloc[0]
            line_label = group["line"].iloc[0]
            st.markdown(
                f"""
                <div class="equip-card">
                    <h3>{html.escape(str(equip))}</h3>
                    <span>خط: {html.escape(str(line_label))} — واحد: {html.escape(str(unit_label))}
                    — تعداد ردیف اندازه‌گیری: {len(group)}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            render_table(group)

        st.divider()
        st.download_button(
            "⬇️ دانلود داده فیلترشده (CSV)",
            data=df.drop(columns=["rms_num"]).to_csv(index=False).encode("utf-8-sig"),
            file_name="vibration_filtered.csv",
            mime="text/csv",
        )

        # ---------------- نمودار دایره‌ای ----------------
        st.markdown("### 🥧 نمودار دایره‌ای وضعیت")
        st.caption(
            "سهم درصدی هر وضعیت بر اساس همان دسته‌بندی ثابت. متن جدول دست‌نخورده است؛ "
            "این نمودار فقط گزارش تصویری می‌دهد."
        )

        cats = df["status"].apply(categorize).value_counts()
        present = [c for c in CATEGORIES if c in cats.index]
        pie_df = pd.DataFrame(
            {"دسته": present, "تعداد": [int(cats[c]) for c in present]}
        )

        if pie_df.empty:
            st.info("داده‌ای برای رسم نمودار نیست.")
        else:
            fig = px.pie(
                pie_df,
                names="دسته",
                values="تعداد",
                hole=0.42,
                color="دسته",
                color_discrete_map=CATEGORY_COLORS,
                category_orders={"دسته": CATEGORIES},
            )
            fig.update_traces(
                textposition="inside",
                textinfo="percent+value",
                insidetextorientation="auto",
                hovertemplate="%{label}<br>تعداد: %{value}<br>سهم: %{percent}<extra></extra>",
            )
            fig.update_layout(
                margin=dict(t=20, b=20, l=10, r=10),
                height=460,
                legend=dict(orientation="v", x=1.02, y=0.5),
                font=dict(family="Vazirmatn, Tahoma, sans-serif", size=14),
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("**جدول درصدها**")
            pie_df["درصد"] = (pie_df["تعداد"] / pie_df["تعداد"].sum() * 100).round(1)
            pie_show = pie_df.rename(columns={"دسته": "وضعیت", "تعداد": "تعداد ردیف"})
            pie_show["درصد"] = pie_show["درصد"].astype(str) + "٪"
            st.dataframe(pie_show, use_container_width=True, hide_index=True)

# ---------------- ارسال اعلان ----------------
with tab_notify:
    if not IS_MANAGER:
        st.info("این بخش فقط برای کاربران دارای نقش «مدیر» فعال است.")
    else:
        st.markdown("#### 📨 ارسال اعلان به کاربران")
        recipients = st.multiselect(
            "گیرندگان",
            options=list(USERS.keys()),
            format_func=lambda e: f"{USERS[e]['name']} — {e}",
            default=[],
        )
        subject = st.text_input("موضوع", value="گزارش وضعیت ارتعاشات — سیمان تهران")
        body = st.text_area(
            "متن پیام",
            value=(
                "با سلام،\n\n"
                "گزارش وضعیت ارتعاشات تجهیزات خط تولید به پیوست ارسال می‌گردد.\n"
                "لطفاً موارد دارای وضعیت هشدار و خطر/بحرانی را در اولویت بازدید قرار دهید.\n\n"
                "با تشکر\nواحد پایش وضعیت"
            ),
            height=180,
        )

        if st.button("ارسال اعلان", type="primary"):
            if not recipients:
                st.warning("حداقل یک گیرنده انتخاب کنید.")
            else:
                log = st.session_state.setdefault("sent_log", [])
                log.append(
                    {
                        "زمان": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "گیرندگان": ", ".join(recipients),
                        "موضوع": subject,
                    }
                )
                st.success(f"اعلان برای {len(recipients)} گیرنده ثبت شد.")

                # ارسال واقعی در صورت تنظیم SMTP در secrets
                try:
                    import smtplib
                    from email.mime.text import MIMEText

                    cfg = {}
                    try:
                        cfg = dict(st.secrets.get("smtp", {}))
                    except Exception:
                        cfg = {}

                    if cfg:
                        msg = MIMEText(body, "plain", "utf-8")
                        msg["Subject"] = subject
                        msg["From"] = cfg["user"]
                        msg["To"] = ", ".join(recipients)
                        with smtplib.SMTP(cfg["host"], int(cfg.get("port", 587))) as s:
                            s.starttls()
                            s.login(cfg["user"], cfg["password"])
                            s.sendmail(cfg["user"], recipients, msg.as_string())
                        st.success("ایمیل واقعی نیز ارسال شد.")
                    else:
                        st.info("کلید smtp در secrets تنظیم نشده؛ فقط ثبت داخلی انجام شد.")
                except Exception as exc:
                    st.warning(f"ارسال ایمیل انجام نشد: {exc}")

        if st.session_state.get("sent_log"):
            st.markdown("**تاریخچه ارسال‌ها**")
            st.dataframe(
                pd.DataFrame(st.session_state["sent_log"]),
                use_container_width=True,
                hide_index=True,
            )

# ---------------- مدیریت کاربران ----------------
with tab_users:
    if not IS_MANAGER:
        st.info("این بخش فقط برای کاربران دارای نقش «مدیر» فعال است.")
    else:
        st.markdown("#### 👥 فهرست کاربران سامانه")
        users_df = pd.DataFrame(
            [{"نام": v["name"], "ایمیل": k, "نقش": v["role"]} for k, v in USERS.items()]
        )
        st.dataframe(users_df, use_container_width=True, hide_index=True)
        st.caption("برای افزودن یا حذف کاربر، دیکشنری USERS در ابتدای فایل را ویرایش کنید.")

# ---------------- راهنما ----------------
with tab_about:
    st.markdown(
        """
        #### راهنمای کوتاه
        - **فیلتر زنجیره‌ای:** ابتدا خط، سپس واحد و در پایان تجهیز را انتخاب کنید؛ هر انتخاب، گزینه‌های مرحله بعد را محدود می‌کند.
        - **ستون وضعیت:** همان متنی است که در شیت نوشته شده؛ برنامه هیچ محاسبه یا قضاوت خودکاری انجام نمی‌دهد.
        - **شماره بیرینگ:** بیرینگ ترکیبی مانند `6234+NU234` پشتیبانی می‌شود و نقاط بدون بیرینگ با خط تیره نمایش داده می‌شوند.
        - **نمودار دایره‌ای:** شش دسته ثابت — نرمال، نیازمند مراقبت و کنترل، هشدار، خطر/ بحرانی، سایر، بدون وضعیت ثبت شده.
        - **منبع داده:** فایل CSV یا Excel شیت را از سایدبار بارگذاری کنید، یا با قرار دادن `service_account.json` و متغیر `SHEET_ID` داده را مستقیم از گوگل شیت بخوانید.
        """
    )
