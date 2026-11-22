# -*- coding: utf-8 -*-
"""
سیستم هوشمند پایش وضعیت ارتعاشات - سیمان تهران
------------------------------------------------
نسخه‌ی اصلاح‌شده:
  * عنوان کادر: سیستم هوشمند پایش وضعیت - سیمان تهران
  * فیلترهای زنجیره‌ای و واقعی: خط تولید -> واحد -> نام تجهیز
  * حذف کامل جدول پیش‌نمایش
  * شمارش تعداد نقاط فقط برای تجهیز انتخاب‌شده
  * مقاوم در برابر نیم‌فاصله، فاصله اضافه، «ي/ك» عربی و «ی/ک» فارسی
  * امکان اجرا با Google Sheets یا با فایل CSV/Excel محلی (حالت آفلاین)

اجرا:
    pip install streamlit pandas gspread google-auth plotly openpyxl
    streamlit run vibration_monitor_tehran_cement.py
"""

import json
import re
import datetime as dt

import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------
# تنظیمات صفحه
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="سیستم هوشمند پایش وضعیت - سیمان تهران",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# طرح ظاهری
# ----------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp { background: #f7f8fa; }
    .main-title {
        background: linear-gradient(90deg, #b8261c 0%, #e8582c 60%, #f0913d 100%);
        color: #ffffff;
        padding: 18px 24px;
        border-radius: 12px;
        box-shadow: 0 4px 14px rgba(0,0,0,.15);
        margin-bottom: 6px;
    }
    .main-title h1 { color:#fff; font-size: 22px; margin:0; }
    .main-title p  { color:#ffe6dc; font-size: 12px; margin:6px 0 0 0; }
    .card {
        background:#ffffff;
        border:1px solid #e6e8ec;
        border-radius:10px;
        padding:12px 14px;
        margin-bottom:10px;
        box-shadow:0 1px 3px rgba(0,0,0,.05);
    }
    .card .pt  { font-weight:700; color:#b8261c; font-size:17px; }
    .card .lbl { color:#8a8f98; font-size:11px; }
    .card .val { color:#1f2328; font-size:14px; font-weight:600; }
    .small-note { color:#8a8f98; font-size:12px; }
    div[data-testid="stMetricValue"] { font-size: 20px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# شِمای ستون‌های شیت تجهیزات (دقیقاً مطابق شیت شما)
# ----------------------------------------------------------------------------
COL_EQUIP = "نام تجهیز"
COL_LINE = "خط تولید"
COL_UNIT = "واحد"
COL_TYPE = "نوع تجهیز"
COL_POINT = "راهنمایی نقاط"
COL_BEAR = "شماره بیرینگ"
COL_BUSH = "بوش"
COL_RPM = "دور نامی"
COL_DRIVE = "سیستم درایور"

EQUIP_SCHEMA = [
    COL_EQUIP, COL_LINE, COL_UNIT, COL_TYPE,
    COL_POINT, COL_BEAR, COL_BUSH, COL_RPM, COL_DRIVE,
]

# ستون‌های شیت اندازه‌گیری (در صورت وجود)
M_EQUIP = "نام تجهیز"
M_POINT = "نقطه"
M_DATE = "تاریخ"
M_VALUE = "مقدار"

DASH = "—"          # نمایش خانه‌ی خالی
ALL = "همه"         # گزینه‌ی بدون فیلتر


# ----------------------------------------------------------------------------
# ابزار یکسان‌سازی متن (کلید حل مشکل پیدا نشدن ستون‌ها)
# ----------------------------------------------------------------------------
_AR_MAP = {"ي": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه", "أ": "ا", "إ": "ا", "آ": "ا"}


def norm(text) -> str:
    """یکسان‌سازی: حذف نیم‌فاصله/فاصله‌ی اضافه، تبدیل ی و ک عربی، یکسان‌سازی ارقام."""
    if text is None:
        return ""
    s = str(text)
    s = s.replace("\u200c", "").replace("\u200f", "").replace("\u200e", "")
    for a, b in _AR_MAP.items():
        s = s.replace(a, b)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_key(text) -> str:
    """کلید مقایسه: بدون فاصله و بدون حساسیت به بزرگی/کوچکی حروف."""
    return norm(text).replace(" ", "").casefold()


def match_columns(df: pd.DataFrame, schema: list) -> dict:
    """نگاشت نام ستون‌های واقعی شیت به شِمای استاندارد ما."""
    lookup = {norm_key(c): c for c in df.columns}
    mapping = {}
    for want in schema:
        hit = lookup.get(norm_key(want))
        if hit is not None:
            mapping[want] = hit
    return mapping


def apply_schema(df: pd.DataFrame, schema: list) -> tuple:
    """جدول را به شِمای استاندارد تبدیل می‌کند و فهرست ستون‌های گم‌شده را برمی‌گرداند."""
    mapping = match_columns(df, schema)
    missing = [c for c in schema if c not in mapping]
    out = pd.DataFrame()
    for col in schema:
        out[col] = df[mapping[col]] if col in mapping else pd.Series([""] * len(df))
    for col in out.columns:
        out[col] = out[col].apply(lambda v: "" if pd.isna(v) else norm(v))
    return out, missing


def show_val(v) -> str:
    v = norm(v)
    return v if v else DASH


# ----------------------------------------------------------------------------
# ورود کاربران
# ----------------------------------------------------------------------------
DEFAULT_USERS = {
    "admin@tehrancement.ir":   {"password": "admin1234", "role": "مدیر", "name": "مدیر سیستم"},
    "supervisor@tehrancement.ir": {"password": "sup1234", "role": "ناظر", "name": "ناظر ارتعاشات"},
}


def get_users() -> dict:
    try:
        users = dict(st.secrets.get("users", {}))
        if users:
            return users
    except Exception:
        pass
    return DEFAULT_USERS


# ----------------------------------------------------------------------------
# منبع داده
# ----------------------------------------------------------------------------
def _open_worksheet(url: str, cred_json: dict):
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(cred_json, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_url(url)


@st.cache_data(ttl=300, show_spinner=False)
def read_sheet(url: str, cred_json_str: str, worksheet_name: str = None) -> pd.DataFrame:
    cred_json = json.loads(cred_json_str)
    book = _open_worksheet(url, cred_json)
    if worksheet_name:
        ws = book.worksheet(worksheet_name)
    else:
        ws = book.sheet1
    rows = ws.get_all_records()
    return pd.DataFrame(rows)


def load_data() -> tuple:
    """برمی‌گرداند: (دیتافریم تجهیزات، دیتافریم اندازه‌گیری یا None، پیام وضعیت)."""
    sb = st.sidebar
    sb.markdown("### 🔗 منبع داده")
    mode = sb.radio(
        "نوع اتصال",
        ["گوگل شیت (آنلاین)", "فایل CSV / Excel (آفلاین)"],
        index=0,
        help="برای حالت بدون اینترنت، فایل CSV یا Excel تجهیزات را بارگذاری کنید.",
    )

    if mode.startswith("گوگل"):
        url = sb.text_input("لینک گوگل شیت تجهیزات", key="sheet_url")
        sheet_name = sb.text_input("نام شیت (اختیاری)", key="sheet_name")
        if not url:
            return None, None, "لینک گوگل شیت را در نوار کناری وارد کنید."
        try:
            cred = dict(st.secrets["gcp_service_account"])
        except Exception:
            return None, None, "اطلاعات سرویس‌اکانت (gcp_service_account) در secrets تنظیم نشده است."
        try:
            df = read_sheet(url, json.dumps(cred, sort_keys=True), sheet_name or None)
        except Exception as exc:
            return None, None, f"خطا در خواندن شیت: {exc}"
        return df, None, ""

    up = sb.file_uploader("فایل تجهیزات (CSV یا Excel)", type=["csv", "xlsx", "xls"])
    up_m = sb.file_uploader("فایل اندازه‌گیری‌ها (اختیاری)", type=["csv", "xlsx", "xls"])
    if not up:
        return None, None, "فایل تجهیزات را بارگذاری کنید."

    try:
        if up.name.lower().endswith(".csv"):
            df = pd.read_csv(up, dtype=str).fillna("")
        else:
            df = pd.read_excel(up, dtype=str).fillna("")
    except Exception as exc:
        return None, None, f"خطا در خواندن فایل تجهیزات: {exc}"

    df_m = None
    if up_m is not None:
        try:
            if up_m.name.lower().endswith(".csv"):
                df_m = pd.read_csv(up_m).fillna("")
            else:
                df_m = pd.read_excel(up_m).fillna("")
        except Exception as exc:
            st.warning(f"فایل اندازه‌گیری خوانده نشد: {exc}")

    return df, df_m, ""


# ----------------------------------------------------------------------------
# فیلترهای زنجیره‌ای
# ----------------------------------------------------------------------------
def cascading_filters(df: pd.DataFrame) -> tuple:
    """سه فیلتر واقعی و به‌هم‌پیوسته: خط تولید -> واحد -> نام تجهیز."""
    st.markdown("#### 🔍 انتخاب تجهیز")

    c1, c2, c3 = st.columns(3)

    # مرحله ۱ — خط تولید
    lines = sorted({norm(v) for v in df[COL_LINE] if norm(v)})
    line = c1.selectbox("خط تولید", [ALL] + lines, index=0, key="f_line")

    step1 = df if line == ALL else df[df[COL_LINE] == line]

    # مرحله ۲ — واحد (فقط واحدهای همان خط)
    units = sorted({norm(v) for v in step1[COL_UNIT] if norm(v)})
    unit = c2.selectbox("واحد", [ALL] + units, index=0, key="f_unit")

    step2 = step1 if unit == ALL else step1[step1[COL_UNIT] == unit]

    # مرحله ۳ — نام تجهیز (فقط تجهیزات همان خط و همان واحد)
    equips = sorted({norm(v) for v in step2[COL_EQUIP] if norm(v)})
    if not equips:
        c3.selectbox("نام تجهیز", ["—"], key="f_equip_empty", disabled=True)
        st.info("برای این ترکیب خط و واحد، تجهیزی در شیت ثبت نشده است.")
        return None, None, None, None

    equip = c3.selectbox("نام تجهیز", equips, index=0, key="f_equip")

    sel = step2[step2[COL_EQUIP] == equip]
    return line, unit, equip, sel


# ----------------------------------------------------------------------------
# کارت‌های نقاط
# ----------------------------------------------------------------------------
def point_cards(sel: pd.DataFrame):
    rows = sel.to_dict("records")
    st.markdown(f"### 🧭 شناسنامه نقاط — {norm(rows[0][COL_EQUIP])}")

    meta = []
    line = norm(rows[0][COL_LINE])
    unit = norm(rows[0][COL_UNIT])
    typ = norm(rows[0][COL_TYPE])
    rpm = norm(rows[0][COL_RPM])
    if line:
        meta.append(f"خط تولید: {line}")
    if unit:
        meta.append(f"واحد: {unit}")
    if typ:
        meta.append(f"نوع تجهیز: {typ}")
    if rpm:
        meta.append(f"دور نامی: {rpm}")
    if meta:
        st.markdown(
            f"<div class='small-note'>{'  |  '.join(meta)}</div>", unsafe_allow_html=True
        )

    cols = st.columns(max(1, min(4, len(rows))))
    for i, r in enumerate(rows):
        with cols[i % len(cols)]:
            st.markdown(
                f"""
                <div class='card'>
                    <div class='pt'>{show_val(r[COL_POINT])}</div>
                    <div class='lbl'>شماره بیرینگ</div>
                    <div class='val'>{show_val(r[COL_BEAR])}</div>
                    <div class='lbl' style='margin-top:6px;'>بوش</div>
                    <div class='val'>{show_val(r[COL_BUSH])}</div>
                    <div class='lbl' style='margin-top:6px;'>سیستم درایور</div>
                    <div class='val'>{show_val(r[COL_DRIVE])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ----------------------------------------------------------------------------
# نمودارها (در صورت وجود داده اندازه‌گیری)
# ----------------------------------------------------------------------------
def charts(df_m: pd.DataFrame, equip: str, sel: pd.DataFrame):
    st.markdown("### 📈 روند ارتعاشات")

    if df_m is None or df_m.empty:
        st.info(
            "برای رسم نمودار، فایل اندازه‌گیری‌ها را بارگذاری کنید "
            f"(ستون‌های مورد نیاز: «{M_EQUIP}»، «{M_POINT}»، «{M_DATE}»، «{M_VALUE}»)."
        )
        return

    m = match_columns(
        df_m, [M_EQUIP, M_POINT, M_DATE, M_VALUE,
               "ارتعاش کل", "Velocity RMS", "Acceleration", "Vibration"]
    )
    if M_EQUIP not in m or M_POINT not in m:
        st.warning("ستون «نام تجهیز» یا «نقطه» در فایل اندازه‌گیری پیدا نشد.")
        return

    value_col = m.get(M_VALUE) or m.get("ارتعاش کل") or m.get("Velocity RMS") or m.get("Vibration")

    work = df_m.copy()
    work["_equip"] = work[m[M_EQUIP]].apply(norm)
    work = work[work["_equip"] == equip]
    if work.empty:
        st.info("برای این تجهیز دادهای در فایل اندازه‌گیری ثبت نشده است.")
        return

    work["_point"] = work[m[M_POINT]].apply(norm)
    if M_DATE in m:
        work["_date"] = pd.to_datetime(work[m[M_DATE]], errors="coerce")
    else:
        work["_date"] = pd.RangeIndex(len(work))

    # آستانه‌ی هشدار (ISO 10816 عام، قابل تغییر)
    thr = st.slider("آستانه هشدار ارتعاش", 1.0, 20.0, 4.5, 0.5, key="thr")

    points = sorted({p for p in work["_point"] if p})
    for p in points:
        sub = work[work["_point"] == p].sort_values("_date")
        st.markdown(f"**نقطه {p}**")
        if value_col:
            y = pd.to_numeric(sub[value_col], errors="coerce")
            chart_df = pd.DataFrame({"تاریخ": sub["_date"].values, "مقدار": y.values}).dropna()
            if chart_df.empty:
                st.caption("داده‌ی عددی معتبری برای این نقطه وجود ندارد.")
                continue
            chart_df = chart_df.set_index("تاریخ")
            st.line_chart(chart_df, height=230)
            last = float(chart_df["مقدار"].iloc[-1])
            c1, c2 = st.columns(2)
            c1.metric("آخرین مقدار", f"{last:.2f}")
            if last >= thr:
                c2.error("وضعیت: نیازمند بررسی ⚠️")
            else:
                c2.success("وضعیت: نرمال ✅")
        else:
            st.caption("ستون مقدار ارتعاش در فایل پیدا نشد.")


# ----------------------------------------------------------------------------
# جریان اصلی
# ----------------------------------------------------------------------------
def login_gate() -> dict:
    if "user" in st.session_state:
        return st.session_state["user"]

    st.markdown(
        "<div class='main-title'><h1>سیستم هوشمند پایش وضعیت - سیمان تهران</h1>"
        "<p>ورود به سامانه</p></div>",
        unsafe_allow_html=True,
    )
    with st.form("login"):
        email = st.text_input("ایمیل سازمانی")
        pwd = st.text_input("رمز عبور", type="password")
        ok = st.form_submit_button("ورود")
    if ok:
        users = get_users()
        rec = users.get(email.strip().lower())
        if rec and str(rec.get("password")) == pwd:
            st.session_state["user"] = {
                "email": email.strip().lower(),
                "role": rec.get("role", "ناظر"),
                "name": rec.get("name", email),
            }
            st.rerun()
        else:
            st.error("ایمیل یا رمز عبور نادرست است.")
    st.stop()


def main():
    user = login_gate()

    df_raw, df_m, msg = load_data()

    # نوار کناری: هویت کاربر
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**{user['name']}**")
    st.sidebar.caption(f"{user['role']} • {user['email']}")
    if st.sidebar.button("خروج"):
        st.session_state.pop("user", None)
        st.rerun()

    # عنوان
    last_rec = "—"
    if df_m is not None and not df_m.empty:
        m = match_columns(df_m, [M_DATE])
        if M_DATE in m:
            d = pd.to_datetime(df_m[m[M_DATE]], errors="coerce").max()
            if pd.notna(d):
                last_rec = d.strftime("%Y-%m-%d")
    n_data = 0 if df_m is None else len(df_m)
    st.markdown(
        f"""
        <div class='main-title'>
            <h1>سیستم هوشمند پایش وضعیت - سیمان تهران</h1>
            <p>آخرین رکورد: {last_rec} &nbsp;|&nbsp; تعداد داده: {n_data}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if msg:
        st.warning(msg)
        st.stop()

    if df_raw is None or df_raw.empty:
        st.error("شیت تجهیزات خالی است یا خوانده نشد.")
        st.stop()

    # تبدیل به شِمای استاندارد
    df, missing = apply_schema(df_raw, EQUIP_SCHEMA)
    if missing:
        st.error(
            "این ستون‌ها در شیت پیدا نشد: " + "، ".join(missing)
            + "\n\nنام ستون‌ها در ردیف اول شیت باید دقیقاً یکی از این موارد باشد: "
            + "، ".join(EQUIP_SCHEMA)
        )
        st.stop()

    df = df[df[COL_EQUIP] != ""].reset_index(drop=True)

    line, unit, equip, sel = cascading_filters(df)
    if sel is None:
        st.stop()

    # تعداد نقاط — فقط برای همین تجهیز
    c1, c2, c3 = st.columns(3)
    c1.metric("تعداد نقاط این تجهیز", len(sel))
    c2.metric("خط تولید", line if line else ALL)
    c3.metric("واحد", unit if unit else ALL)

    point_cards(sel)
    charts(df_m, equip, sel)

    st.markdown(
        "<hr style='border:none;border-top:1px solid #e6e8ec;'>"
        "<div class='small-note'>سیستم هوشمند پایش وضعیت — سیمان تهران</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
