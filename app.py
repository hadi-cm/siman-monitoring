# -*- coding: utf-8 -*-
"""
================================================================================
 داشبورد پایش ارتعاشات — نسخه ۴ (Professional Edition)
================================================================================
 محصول      : سیستم هوشمند پایش ارتعاشات تجهیزات دوار
 توسعه      : هادی (Hadi)
 نسخه       : 4.0.0
 تاریخ       : 1405-08-30
 قابلیت‌ها  : اتصال مستقیم به گوگل‌شیت + نقشه هوشمند نقاط + مرجع بیرینگ
              + سیستم اعلانیه (هشدار/بحرانی/روند صعودی) روی بله، تلگرام، ایمیل
 اجرا        : streamlit run app_v4_sheets_alerts_pro.py
 نیازمندی‌ها : pip install streamlit pandas numpy plotly requests
================================================================================
"""

import io
import json
import os
import random
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from urllib.parse import quote

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ================================================================
# تنظیمات صفحه
# ================================================================
st.set_page_config(page_title="پایش ارتعاشات | نسخه ۴", page_icon="📈", layout="wide")

st.markdown(
    """
    <style>
    html, body, [class*="css"] { font-family: Vazirmatn, Tahoma, sans-serif; }
    div[data-testid="stDataFrame"] { direction: rtl; }
    .badge { padding:2px 8px; border-radius:8px; font-size:12px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ================================================================
# ۱) تنظیمات اتصال به گوگل‌شیت
#    شناسه شیت = بخشی از لینک بین /d/ و /edit
#    مثال: https://docs.google.com/spreadsheets/d/1AbCdEf.../edit
#    شرط لازم: شیت با «هر کسی که لینک را دارد» قابل مشاهده باشد (Viewer)
# ================================================================
DEFAULT_SHEETS = {
    "measurements": ("", "Measurements"),   # (شناسه شیت، نام تب)
    "assets":       ("", "Assets"),
    "bearings":     ("", "Bearings"),
}

TTL_CACHE = 300  # ثانیه — هر ۵ دقیقه شیت دوباره خوانده می‌شود

# ================================================================
# ۲) نقشه هوشمند نقاط (قواعد نهایی مورد توافق)
#    قاعده کلی: P1 و P2 همیشه مال الکتروموتور است
#    (چون هیچ تجهیز دواری بدون الکتروموتور نیست)
# ================================================================
MOTOR_POINTS = {"P1": "انتهای موتور", "P2": "سر موتور"}


def _n(x) -> str:
    """نرمال‌سازی متن فارسی برای تطبیق مطمئن."""
    s = str(x or "").strip()
    return (s.replace("ي", "ی").replace("ك", "ک").replace("‌", "")
             .replace("0", "").strip().lower())


def get_smart_locations(asset_type, drive_type=""):
    """
    ورودی: نوع تجهیز و سیستم انتقال نیرو (از شیت Assets)
    خروجی: دیکشنری نقطه -> توضیح مکانی
    """
    t = _n(asset_type)
    d = _n(drive_type)
    p = dict(MOTOR_POINTS)

    # --- ترتیب مهم است: خاص‌ترها اول بررسی می‌شوند ---
    if "بلوئر خاص" in t or "بلور خاص" in t or "بلوئر ویژه" in t:
        p.update({
            "P3": "محور ورودی گیربکس",
            "P4": "محور خروجی گیربکس",
            "P5": "محور ورودی بلوئر",
            "P6": "انتهای بلوئر",
        })

    elif "کراشر" in t or "کراچر" in t or "سنگ شکن" in t:
        p.update({
            "P3": "یاتاقان فیکس پولی کوچک",
            "P4": "یاتاقان آزاد پولی کوچک",
            "P5": "یاتاقان فیکس روتور",
            "P6": "یاتاقان آزاد روتور",
        })

    elif "کمپرسور" in t or "کمپرسر" in t:
        p.update({
            "P3": "محور ورودی ایرند",
            "P4": "انتهای ایرند",
        })

    elif "بلوئر" in t or "بلور" in t or "فن دمنده" in t:
        p.update({
            "P3": "محور ورودی بلوئر",
            "P4": "انتهای بلوئر",
        })

    elif "فن" in t:
        # فن: بسته به سیستم انتقال نیرو
        if "کوپلینگ" in d:
            p.update({
                "P3": "یاتاقان سمت فیکس (سمت کوپلینگ)",
                "P4": "یاتاقان سمت پروانه",
            })
        elif "تسمه" in d or "پولی" in d or "تصمیه" in d or "تسمه‌ای" in d:
            p.update({
                "P3": "یاتاقان سمت پولی",
                "P4": "یاتاقان سمت پروانه",
            })
        else:
            p.update({
                "P3": "یاتاقان سمت کوپلینگ/پولی",
                "P4": "یاتاقان سمت پروانه",
            })

    elif "گیربکس" in t or "گیرباکس" in t:
        p.update({
            "P3": "محور ورودی گیربکس",
            "P4": "محور خروجی گیربکس",
        })

    # موتور تنها: فقط P1 و P2
    return p


def sort_points(points):
    """مرتب‌سازی P1..P6 به ترتیب عددی."""
    def key(v):
        s = str(v).upper().replace("P", "").strip()
        return int(s) if s.isdigit() else 99
    return sorted(points, key=key)


# ================================================================
# ۳) خواندن گوگل‌شیت
# ================================================================
def gviz_url(sheet_id: str, sheet_name: str = "") -> str:
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv"
    if sheet_name:
        url += f"&sheet={quote(sheet_name)}"
    return url


@st.cache_data(ttl=TTL_CACHE, show_spinner=False)
def load_sheet(sheet_id: str, sheet_name: str) -> pd.DataFrame:
    r = requests.get(gviz_url(sheet_id, sheet_name), timeout=25)
    r.raise_for_status()
    return pd.read_csv(io.StringIO(r.text))


ALIASES = {
    "date":    ["تاریخ", "date", "زمان", "تاریخ اندازه‌گیری"],
    "line":    ["خط", "line", "مسیر", "خط تولید"],
    "unit":    ["واحد", "unit", "بخش", "یونیت"],
    "asset":   ["تجهیز", "asset", "نام تجهیز", "ماشین", "تگ", "tag"],
    "type":    ["نوع تجهیز", "asset_type", "type", "نوع", "نوع تاسیسات"],
    "drive":   ["سیستم انتقال نیرو", "انتقال نیرو", "drive", "drive_type", "نوع انتقال"],
    "point":   ["نقطه", "point", "محل اندازه‌گیری", "موقعیت اندازه‌گیری", "تگ نقطه"],
    "dir":     ["جهت", "direction", "dir"],
    "value":   ["مقدار", "value", "ارتعاش", "rms", "mm/s", "سرعت rms"],
    "bearing": ["شماره بیرینگ", "بیرینگ", "bearing", "قطعه", "part"],
    "loc":     ["موقعیت", "محل", "location", "شرح"],
    "status":  ["وضعیت", "status"],
}


def pick_col(df: pd.DataFrame, key: str, required=True):
    for c in df.columns:
        for a in ALIASES[key]:
            if _n(a) == _n(c):
                return c
    if required:
        raise KeyError(f"ستون «{ALIASES[key][0]}» در شیت پیدا نشد. ستون‌های موجود: {list(df.columns)}")
    return None


def normalize_measurements(df: pd.DataFrame) -> pd.DataFrame:
    dcol = pick_col(df, "dir", required=False)
    out = pd.DataFrame({
        "date":  pd.to_datetime(df[pick_col(df, "date")], errors="coerce"),
        "line":  df[pick_col(df, "line")].astype(str).str.strip(),
        "unit":  df[pick_col(df, "unit")].astype(str).str.strip(),
        "asset": df[pick_col(df, "asset")].astype(str).str.strip(),
        "point": df[pick_col(df, "point")].astype(str).str.strip().str.upper(),
        "direction": df[dcol].astype(str).str.strip() if dcol else "—",
        "value": pd.to_numeric(df[pick_col(df, "value")], errors="coerce"),
    })
    return out.dropna(subset=["date", "value"])


def normalize_assets(df: pd.DataFrame) -> pd.DataFrame:
    tcol = pick_col(df, "type", required=False)
    dcol = pick_col(df, "drive", required=False)
    out = pd.DataFrame({
        "line":  df[pick_col(df, "line")].astype(str).str.strip(),
        "unit":  df[pick_col(df, "unit")].astype(str).str.strip(),
        "asset": df[pick_col(df, "asset")].astype(str).str.strip(),
        "type":  df[tcol].astype(str).str.strip() if tcol else "نامشخص",
        "drive": df[dcol].astype(str).str.strip() if dcol else "",
    }).drop_duplicates(subset=["line", "unit", "asset"])
    return out


def normalize_bearings(df: pd.DataFrame) -> pd.DataFrame:
    lcol = pick_col(df, "line", required=False)
    ucol = pick_col(df, "unit", required=False)
    loccol = pick_col(df, "loc", required=False)
    out = pd.DataFrame({
        "line":  df[lcol].astype(str).str.strip() if lcol else "",
        "unit":  df[ucol].astype(str).str.strip() if ucol else "",
        "asset": df[pick_col(df, "asset")].astype(str).str.strip(),
        "point": df[pick_col(df, "point")].astype(str).str.strip().str.upper(),
        "bearing": df[pick_col(df, "bearing")].astype(str).str.strip(),
        "loc": df[loccol].astype(str).str.strip() if loccol else "",
    })
    return out.drop_duplicates(subset=["asset", "point"])


# ================================================================
# ۴) داده نمونه (فقط وقتی شیت وصل نیست)
# ================================================================
def make_demo_data():
    random.seed(7)
    np.random.seed(7)
    assets = [
        ("خط ۱", "آسیاب", "بلوئر ۱", "بلوئر", "تسمه"),
        ("خط ۱", "آسیاب", "بلوئر ۲", "بلوئر خاص", "کوپلینگ"),
        ("خط ۱", "آسیاب", "کراشر مواد", "کراشر", ""),
        ("خط ۱", "آسیاب", "فن آسیاب", "فن", "تسمه"),
        ("خط ۱", "آسیاب", "فن مکنده ۲", "فن", "کوپلینگ"),
        ("خط ۲", "کوره", "کمپرسور هوا", "کمپرسور", ""),
        ("خط ۲", "کوره", "گیربکس اصلی", "گیربکس", ""),
        ("خط ۲", "کوره", "موتور جرثقیل", "موتور", ""),
    ]
    ast = pd.DataFrame(assets, columns=["line", "unit", "asset", "type", "drive"])

    rows = []
    days = 45
    today = datetime.now().date()
    for _, a in ast.iterrows():
        locs = get_smart_locations(a["type"], a["drive"])
        pts = sort_points(locs)
        for day in range(days):
            d = today - timedelta(days=days - 1 - day)
            for idx, pt in enumerate(pts):
                base = 2.2 + 0.6 * idx + random.uniform(-0.3, 0.4)
                drift = 0.055 * day * (1 if pt in ("P3", "P5") else 0.55)
                val = max(0.4, base + drift + np.random.normal(0, 0.22))
                for direction in ("H", "V", "A"):
                    rows.append((d, a["line"], a["unit"], a["asset"],
                                 pt, direction, round(val * random.uniform(0.85, 1.15), 2)))

    meas = pd.DataFrame(rows, columns=["date", "line", "unit", "asset", "point", "direction", "value"])
    meas["date"] = pd.to_datetime(meas["date"])

    bearing_bank = {
        "P1": "NU234/C3", "P2": "6205-2Z", "P3": "22210 E",
        "P4": "22212 E", "P5": "22311 E", "P6": "22313 E",
    }
    brows = []
    for _, a in ast.iterrows():
        for pt in sort_points(get_smart_locations(a["type"], a["drive"])):
            brows.append((a["line"], a["unit"], a["asset"], pt, bearing_bank.get(pt, "—"), ""))
    brg = pd.DataFrame(brows, columns=["line", "unit", "asset", "point", "bearing", "loc"])
    return meas, ast, brg


# ================================================================
# ۵) اعلانیه‌ها
# ================================================================
STATE_FILE = "sent_alerts.json"


def load_sent_keys():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_sent_keys(keys):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(keys), f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def build_alerts(meas: pd.DataFrame, loc_map: dict, warn: float, crit: float) -> pd.DataFrame:
    """ساخت اعلانیه بر اساس آخرین مقدار هر نقطه + روند صعودی."""
    if meas.empty:
        return pd.DataFrame()

    meas = meas.sort_values("date")
    alerts = []

    # --- الف) عبور از آستانه ---
    latest = meas.groupby(["line", "unit", "asset", "point"], dropna=False).tail(1)
    for _, r in latest.iterrows():
        sev = "بحرانی" if r["value"] >= crit else ("هشدار" if r["value"] >= warn else None)
        if not sev:
            continue
        loc = loc_map.get((r["line"], r["unit"], r["asset"]), {}).get(r["point"], "")
        alerts.append({
            "نوع": "عبور از آستانه",
            "شدت": sev,
            "خط": r["line"], "واحد": r["unit"], "تجهیز": r["asset"],
            "نقطه": r["point"], "موقعیت": loc,
            "مقدار": round(float(r["value"]), 2),
            "آستانه": crit if sev == "بحرانی" else warn,
            "تاریخ": r["date"],
            "کلید": f"{r['date'].date()}|{r['asset']}|{r['point']}|{sev}",
        })

    # --- ب) روند صعودی سریع (بیش از ۲۵٪ رشد نسبت به قرائت قبلی) ---
    for key, g in meas.groupby(["line", "unit", "asset", "point"], dropna=False):
        if len(g) < 2:
            continue
        prev, cur = float(g["value"].iloc[-2]), float(g["value"].iloc[-1])
        if prev > 0.5 and (cur - prev) / prev >= 0.25 and cur >= warn * 0.6 and cur < crit:
            loc = loc_map.get((key[0], key[1], key[2]), {}).get(key[3], "")
            alerts.append({
                "نوع": "روند صعودی",
                "شدت": "هشدار",
                "خط": key[0], "واحد": key[1], "تجهیز": key[2], "نقطه": key[3],
                "موقعیت": loc,
                "مقدار": round(cur, 2),
                "آستانه": round(warn * 0.6, 2),
                "تاریخ": g["date"].iloc[-1],
                "کلید": f"{g['date'].iloc[-1].date()}|{key[2]}|{key[3]}|trend",
            })

    df = pd.DataFrame(alerts)
    if df.empty:
        return df
    order = {"بحرانی": 0, "هشدار": 1}
    return df.sort_values(["شدت", "مقدار"],
                          key=lambda s: s.map(order) if s.name == "شدت" else s)


def alert_text(row) -> str:
    """متن اعلانیه برای ارسال در پیام‌رسان/ایمیل."""
    icon = "🔴" if row["شدت"] == "بحرانی" else "🟠"
    return (
        f"{icon} اعلانیه پایش ارتعاشات\n"
        f"شدت: {row['شدت']} ({row['نوع']})\n"
        f"خط: {row['خط']} | واحد: {row['واحد']}\n"
        f"تجهیز: {row['تجهیز']}\n"
        f"نقطه: {row['نقطه']} — {row['موقعیت']}\n"
        f"مقدار: {row['مقدار']} mm/s  (آستانه: {row['آستانه']})\n"
        f"تاریخ: {pd.to_datetime(row['تاریخ']).strftime('%Y-%m-%d')}"
    )


def send_bale(token: str, chat_id: str, text: str):
    url = f"https://tapi.bale.ai/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
    return r.status_code, r.text


def send_telegram(token: str, chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=20)
    return r.status_code, r.text


def send_email(host, port, user, password, to_addr, subject, body):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    with smtplib.SMTP_SSL(host, int(port), timeout=20) as s:
        s.login(user, password)
        s.sendmail(user, [to_addr], msg.as_string())
    return True


# ================================================================
# ۶) نوار کناری
# ================================================================
with st.sidebar:
    st.header("🔌 اتصال به گوگل‌شیت")
    with st.expander("تنظیم شناسه شیت‌ها", expanded=True):
        sid_m = st.text_input("شناسه شیتِ اندازه‌گیری", value=DEFAULT_SHEETS["measurements"][0])
        nm_m = st.text_input("نام تب اندازه‌گیری", value=DEFAULT_SHEETS["measurements"][1])
        sid_a = st.text_input("شناسه شیتِ تجهیزات", value=DEFAULT_SHEETS["assets"][0])
        nm_a = st.text_input("نام تب تجهیزات", value=DEFAULT_SHEETS["assets"][1])
        sid_b = st.text_input("شناسه شیتِ بیرینگ‌ها", value=DEFAULT_SHEETS["bearings"][0])
        nm_b = st.text_input("نام تب بیرینگ‌ها", value=DEFAULT_SHEETS["bearings"][1])
        st.caption("شناسه = بخش بین /d/ و /edit در لینک شیت. شیت باید برای مشاهده عمومی باز باشد.")

    if st.button("🔄 به‌روزرسانی داده‌ها", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.header("🎚 آستانه‌ها (mm/s RMS)")
    warn = st.number_input("حد هشدار", value=4.5, step=0.1, format="%.1f")
    crit = st.number_input("حد بحرانی", value=7.1, step=0.1, format="%.1f")

    st.divider()
    st.header("📣 کانال ارسال اعلانیه")
    channel = st.selectbox("روش ارسال", ["بله (Bale)", "تلگرام", "ایمیل", "فقط نمایش در داشبورد"])
    bot_token = st.text_input("توکن ربات", type="password")
    chat_id = st.text_input("شناسه چت / گروه")

    with st.expander("تنظیمات ایمیل"):
        smtp_host = st.text_input("SMTP Host", value="smtp.gmail.com")
        smtp_port = st.text_input("Port", value="465")
        smtp_user = st.text_input("ایمیل فرستنده")
        smtp_pass = st.text_input("رمز اپلیکیشن", type="password")
        mail_to = st.text_input("ایمیل گیرنده")

    auto_send = st.checkbox("ارسال خودکار اعلانیه‌های جدید", value=False)

# ================================================================
# ۷) بارگذاری داده
# ================================================================
data_source = "گوگل‌شیت"
try:
    if not sid_m or not sid_a:
        raise ValueError("شناسه شیت وارد نشده")
    meas_raw = load_sheet(sid_m, nm_m)
    assets_raw = load_sheet(sid_a, nm_a)
    bearings_raw = load_sheet(sid_b, nm_b) if sid_b else pd.DataFrame(columns=["asset", "point", "شماره بیرینگ"])

    meas = normalize_measurements(meas_raw)
    assets = normalize_assets(assets_raw)
    bearings = normalize_bearings(bearings_raw) if not bearings_raw.empty else pd.DataFrame(
        columns=["line", "unit", "asset", "point", "bearing", "loc"])
except Exception as e:
    data_source = "داده نمونه"
    meas, assets, bearings = make_demo_data()
    st.warning(f"اتصال به گوگل‌شیت برقرار نشد ({e}). برای مشاهده ساختار، داده نمونه بارگذاری شد.")

# --- نقشه موقعیت برای همه تجهیزات ---
loc_map = {}
meta = assets.set_index(["line", "unit", "asset"]).to_dict("index")
for key, row in meta.items():
    loc_map[key] = get_smart_locations(row["type"], row["drive"])
for key in meas.groupby(["line", "unit", "asset"]).groups:
    loc_map.setdefault(key, dict(MOTOR_POINTS))

bmap = bearings.set_index(["asset", "point"])["bearing"].to_dict() if not bearings.empty else {}

# ================================================================
# ۸) عنوان + وضعیت
# ================================================================
st.title("📈 داشبورد پایش ارتعاشات")
c1, c2, c3, c4 = st.columns(4)
c1.metric("منبع داده", data_source)
c2.metric("تعداد تجهیزات", f"{meas['asset'].nunique()}")
c3.metric("تعداد نقاط اندازه‌گیری", f"{meas.groupby(['asset', 'point']).ngroups}")
c4.metric("آخرین قرائت", meas["date"].max().strftime("%Y-%m-%d"))

# ================================================================
# ۹) فیلتر آبشاری
# ================================================================
f1, f2, f3 = st.columns(3)
line_sel = f1.selectbox("خط", ["همه"] + sorted(meas["line"].unique()))
m2 = meas if line_sel == "همه" else meas[meas["line"] == line_sel]
unit_sel = f2.selectbox("واحد", ["همه"] + sorted(m2["unit"].unique()))
m3 = m2 if unit_sel == "همه" else m2[m2["unit"] == unit_sel]
asset_sel = f3.selectbox("تجهیز", ["همه"] + sorted(m3["asset"].unique()))
view = m3 if asset_sel == "همه" else m3[m3["asset"] == asset_sel]

# ================================================================
# ۱۰) تب‌ها
# ================================================================
tab1, tab2, tab3, tab4 = st.tabs(
    ["📊 جدول اندازه‌گیری", "🧾 مرجع خرید و بیرینگ", "📉 نمودار روند", "🚨 اعلانیه‌ها"]
)

# ---------- تب ۱: جدول ----------
with tab1:
    st.subheader("آخرین قرائت هر نقطه")
    latest = view.sort_values("date").groupby(["line", "unit", "asset", "point"]).tail(1).copy()
    latest["موقعیت"] = latest.apply(
        lambda r: loc_map.get((r["line"], r["unit"], r["asset"]), {}).get(r["point"], "—"), axis=1)
    latest["شماره بیرینگ"] = latest.apply(lambda r: bmap.get((r["asset"], r["point"]), "—"), axis=1)
    latest["وضعیت"] = latest["value"].apply(
        lambda v: "🔴 بحرانی" if v >= crit else ("🟠 هشدار" if v >= warn else "🟢 سالم"))
    latest = latest.sort_values(
        ["line", "unit", "asset", "point"],
        key=lambda s: s.map(lambda v: int(str(v).replace("P", ""))
                            if str(v).upper().startswith("P") and str(v)[1:].isdigit() else 99)
        if s.name == "point" else s)

    st.dataframe(
        latest[["date", "line", "unit", "asset", "point", "موقعیت", "شماره بیرینگ",
                "direction", "value", "وضعیت"]]
        .rename(columns={"date": "تاریخ", "line": "خط", "unit": "واحد", "asset": "تجهیز",
                         "point": "نقطه", "direction": "جهت", "value": "مقدار (mm/s)"}),
        use_container_width=True, hide_index=True,
    )
    st.caption(f"حد هشدار: {warn} | حد بحرانی: {crit} mm/s RMS")

    st.download_button(
        "⬇️ دانلود CSV همین جدول",
        latest.to_csv(index=False).encode("utf-8-sig"),
        file_name="latest_vibration.csv", mime="text/csv",
    )

# ---------- تب ۲: خرید ----------
with tab2:
    st.subheader("لیست بیرینگ موردنیاز به تفکیک نقطه")
    if asset_sel == "همه":
        st.info("برای دیدن لیست دقیق، یک تجهیز را از فیلتر بالا انتخاب کنید.")
        src = assets.copy()
    else:
        src = assets[(assets["line"] == line_sel) & (assets["unit"] == unit_sel) &
                     (assets["asset"] == asset_sel)]
        if src.empty:
            src = assets[assets["asset"] == asset_sel]

    rows = []
    for _, a in src.iterrows():
        locs = get_smart_locations(a["type"], a["drive"])
        for pt in sort_points(locs):
            brg = bmap.get((a["asset"], pt), "")
            if not brg and not bearings.empty:
                sub = bearings[(bearings["asset"] == a["asset"]) & (bearings["point"] == pt)]
                brg = sub["bearing"].iloc[0] if not sub.empty else ""
            rows.append({"خط": a["line"], "واحد": a["unit"], "تجهیز": a["asset"],
                         "نوع تجهیز": a["type"], "نقطه": pt, "موقعیت": locs[pt],
                         "شماره بیرینگ": brg or "—"})
    buy = pd.DataFrame(rows)
    st.dataframe(buy, use_container_width=True, hide_index=True)

    if not buy.empty:
        st.download_button(
            "⬇️ دانلود لیست خرید (CSV)",
            buy.to_csv(index=False).encode("utf-8-sig"),
            file_name="bearing_purchase_list.csv", mime="text/csv",
        )

# ---------- تب ۳: نمودار ----------
with tab3:
    st.subheader("روند ارتعاشات")
    if asset_sel == "همه":
        st.info("برای رسم نمودار، یک تجهیز را از فیلتر بالا انتخاب کنید.")
    else:
        arow = assets[(assets["asset"] == asset_sel)].head(1)
        if not arow.empty:
            st.markdown(
                f"**نوع تجهیز:** {arow['type'].iloc[0]} | "
                f"**سیستم انتقال نیرو:** {arow['drive'].iloc[0] or '—'}")

        sub = view[view["asset"] == asset_sel].sort_values("date")
        if not sub.empty:
            ln0, un0 = sub["line"].iloc[0], sub["unit"].iloc[0]
            fig = go.Figure()
            for pt in sort_points(sub["point"].unique()):
                g = sub[sub["point"] == pt].groupby("date")["value"].max().reset_index()
                loc = loc_map.get((ln0, un0, asset_sel), {}).get(pt, "")
                fig.add_trace(go.Scatter(x=g["date"], y=g["value"], mode="lines+markers",
                                         name=f"{pt} — {loc}"))
            fig.add_hline(y=warn, line_dash="dash", line_color="orange", annotation_text="حد هشدار")
            fig.add_hline(y=crit, line_dash="dash", line_color="red", annotation_text="حد بحرانی")
            fig.update_layout(height=520, xaxis_title="تاریخ", yaxis_title="ارتعاش (mm/s RMS)",
                              legend=dict(orientation="h", y=-0.2), hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)

# ---------- تب ۴: اعلانیه‌ها ----------
with tab4:
    st.subheader("اعلانیه‌های فعال")
    alerts = build_alerts(view if asset_sel != "همه" else m3, loc_map, warn, crit)

    if alerts.empty:
        st.success("هیچ نقطه‌ای از آستانه عبور نکرده است. وضعیت سالم است. ✅")
    else:
        st.dataframe(
            alerts[["شدت", "نوع", "خط", "واحد", "تجهیز", "نقطه", "موقعیت",
                    "مقدار", "آستانه", "تاریخ"]],
            use_container_width=True, hide_index=True,
        )

        sent = load_sent_keys()
        new_alerts = alerts[~alerts["کلید"].isin(sent)]

        k1, k2, k3 = st.columns(3)
        k1.metric("کل اعلانیه", len(alerts))
        k2.metric("بحرانی", int((alerts["شدت"] == "بحرانی").sum()))
        k3.metric("ارسال‌نشده (جدید)", len(new_alerts))

        def dispatch(df_to_send, silent=False):
            ok, fail = 0, 0
            for _, r in df_to_send.iterrows():
                txt = alert_text(r)
                try:
                    if channel == "بله (Bale)":
                        code, _ = send_bale(bot_token, chat_id, txt)
                        ok += 1 if code == 200 else 0
                        fail += 0 if code == 200 else 1
                    elif channel == "تلگرام":
                        code, _ = send_telegram(bot_token, chat_id, txt)
                        ok += 1 if code == 200 else 0
                        fail += 0 if code == 200 else 1
                    elif channel == "ایمیل":
                        send_email(smtp_host, smtp_port, smtp_user, smtp_pass, mail_to,
                                   f"اعلانیه {r['شدت']} — {r['تجهیز']} / {r['نقطه']}", txt)
                        ok += 1
                    else:
                        ok += 1  # فقط نمایش
                    sent.add(r["کلید"])
                except Exception as e:
                    fail += 1
                    if not silent:
                        st.error(f"ارسال ناموفق برای {r['تجهیز']} / {r['نقطه']}: {e}")
            save_sent_keys(sent)
            return ok, fail

        b1, b2 = st.columns(2)
        if b1.button("📤 ارسال اعلانیه‌های جدید", use_container_width=True, type="primary"):
            if channel in ("بله (Bale)", "تلگرام") and (not bot_token or not chat_id):
                st.error("توکن ربات و شناسه چت را در نوار کناری وارد کنید.")
            elif channel == "ایمیل" and not (smtp_user and smtp_pass and mail_to):
                st.error("تنظیمات ایمیل را کامل کنید.")
            else:
                ok, fail = dispatch(new_alerts)
                st.success(f"ارسال موفق: {ok} | ناموفق: {fail}")
        if b2.button("✅ علامت‌گذاری همه به‌عنوان دیده‌شده", use_container_width=True):
            sent.update(alerts["کلید"].tolist())
            save_sent_keys(sent)
            st.info("همه اعلانیه‌ها دیده‌شده شدند.")

        if auto_send and not new_alerts.empty and (bot_token or channel == "فقط نمایش در داشبورد"):
            ok, fail = dispatch(new_alerts, silent=True)
            st.info(f"ارسال خودکار انجام شد — موفق: {ok} | ناموفق: {fail}")

    st.divider()
    st.caption("منطق اعلانیه: عبور از حد هشدار/بحرانی در آخرین قرائت، "
               "یا رشد بیش از ۲۵٪ نسبت به قرائت قبلی.")

# ================================================================
# ۱۱) پانویس و اطلاعات تهیه و توسعه
# ================================================================
st.divider()
col_info, col_dev = st.columns([3, 1])

with col_info:
    st.caption(f"نسخه ۴ | منبع داده: {data_source} | "
               f"آخرین به‌روزرسانی: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    st.caption("قاعده نقاط: P1 و P2 همیشه الکتروموتور؛ از P3 به بعد تجهیز گردان.")
    st.caption("معماری نقاط: موتور • گیربکس • فن (تسمه/کوپلینگ) • بلوئر • بلوئر خاص • "
               "کمپرسور • کراشر")

with col_dev:
    st.caption("🛠 **تهیه و توسعه:**")
    st.caption("👤 **هادی**")
    st.caption("🚀 **Vibration Monitoring System v4**")

# ================================================================
# تهیه و توسعه (Credits)
# ================================================================
# محصول        : سیستم هوشمند پایش ارتعاشات تجهیزات دوار
# توسعه‌دهنده  : هادی (Hadi)
# نسخه         : 4.0.0 — Professional Edition
# تاریخ        : 1405-08-30
# شرح          : مدیریت هوشمند نقاط اندازه‌گیری بر اساس نوع تجهیز و سیستم
#                انتقال نیرو، مرجع بیرینگ و لیست خرید، تحلیل روند و
#                سیستم اعلانیه خودکار چندکاناله (بله / تلگرام / ایمیل).
# ================================================================
