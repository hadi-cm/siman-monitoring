# -*- coding: utf-8 -*-
"""
=====================================================================
سامانه هوشمند پایش وضعیت ارتعاشات ـ سیمان تهران   |   app.py
=====================================================================
هدر صفحه:  لوگوی خودم (چپ) | عنوان (وسط) | لوگوی سیمان تهران (راست)

نام فایل لوگوها (کنار همین app.py قرار بگیرند):
    my_logo.png        ->  سمت چپ
    client_logo.png    ->  سمت راست

قابلیت‌ها:
  • خواندن دو شیت «ارتعاشات» و «Assets» از همان فایل گوگل‌شیت
  • تشخیص هوشمند نام ستون‌ها (نیم‌فاصله، ی/ك عربی، حروف بزرگ، غلط تایپی)
  • هیچ‌وقت KeyError نمی‌دهد؛ ستونی پیدا نشود، خالی ساخته می‌شود
  • نمایش نقطه‌به‌نقطه (P1..P11)
  • شماره بیرینگ از شیت Assets و در صورت نبود از خود شیت ارتعاشات
  • فیلتر خط / واحد / تجهیز + فیلتر تاریخ (همه / بازه / تاریخ‌های خاص)
  • نمودار، گزارش HTML قابل چاپ، CSV، پیش‌نویس و ارسال اعلان
  • مدیریت ۷ کاربر با ایمیل و نقش (پنل مالک)

Secrets موردنیاز (Settings > Secrets):
    SHEET_ID = "شناسه فایل گوگل شیت"

Secrets اختیاری:
    ALERT_EMAIL = "default@mail.ir"
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 465
    SMTP_USER = "you@gmail.com"
    SMTP_PASS = "App Password گوگل"

    [users]
    manager = "real@mail.ir"
    mech    = "real2@mail.ir"

    [gcp_service_account]   # اگر از Service Account استفاده می‌کنی
    type = "service_account"
    ...
=====================================================================
"""

import io
import os
import re
import datetime as dt

import pandas as pd
import requests
import streamlit as st

# =====================================================================
# 1) تنظیمات صفحه (باید اولین دستور Streamlit باشد)
# =====================================================================
st.set_page_config(
    page_title="سامانه پایش سیمان تهران",
    page_icon="📈",
    layout="wide",
)

# =====================================================================
# 2) هدر: لوگوی خودم (چپ) | عنوان (وسط) | لوگوی سیمان تهران (راست)
# =====================================================================
h_left, h_mid, h_right = st.columns([1, 4, 1], gap="small")

with h_left:
    if os.path.exists("my_logo.png"):
        st.image("my_logo.png", width=150)
    else:
        st.markdown(
            "<div style='text-align:center;font-size:44px;padding-top:10px'>🏢</div>",
            unsafe_allow_html=True,
        )

with h_mid:
    st.markdown(
        """
<div dir="rtl" style="text-align:center;">
  <h1 style="margin:0; padding-top:10px; line-height:1.8; font-weight:900;
             font-size:26px; letter-spacing:-.3px;">
    سامانه هوشمند پایش وضعیت ـ سیمان تهران
  </h1>
  <div style="color:#607d8b; font-size:13px; margin-top:2px;">
    پایش نقطه‌به‌نقطه ارتعاشات تجهیزات دوار
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

with h_right:
    if os.path.exists("client_logo.png"):
        st.image("client_logo.png", width=150)
    else:
        st.markdown(
            "<div style='text-align:center;font-size:44px;padding-top:10px'>🏗️</div>",
            unsafe_allow_html=True,
        )

st.divider()

# =====================================================================
# 3) ثابت‌ها و تنظیمات
# =====================================================================
def _secret(key, default):
    """خواندن ایمن Secrets (اگر فایل secrets نبود، برنامه کرش نکند)."""
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


SHEET_ID = str(_secret("SHEET_ID", "")).strip()
SHEET_VIB = "ارتعاشات"
SHEET_ASSETS = "Assets"

WARN_LIMIT = 4.5   # mm/s
CRIT_LIMIT = 7.0   # mm/s

# ---- شرح نقاط (قابل ویرایش) ----
POINT_LABELS = {
    "P1": "انتهای موتور",
    "P2": "سر موتور (سمت کوپلینگ)",
    "P3": "یاتاقان سمت فیکس میل فن",
    "P4": "یاتاقان سمت آزاد میل فن",
}

# ---- نام‌های محتمل ستون‌ها ----
COLUMNS = {
    "date":     ["تاریخ", "تاریخ ثبت", "تاریخ اندازه گیری", "تاریخ تست"],
    "line":     ["خط تولید", "خط"],
    "unit":     ["واحد"],
    "equip":    ["عنوان تجهیز", "نام تجهیز", "تجهیز", "مکان", "محل نصب"],
    "point":    ["تصویر", "نقطه", "شماره نقطه", "محل اندازه گیری"],
    "h":        ["افقی"],
    "v":        ["عمودی"],
    "a":        ["محوری"],
    "temp":     ["دما", "دمای", "درجه حرارت"],
    "desc":     ["توضیحات", "شرح"],
    "status":   ["وضعیت"],
    "bearing":  ["شماره بیرینگ", "بیرینگ"],
    "action":   ["اقدام اصلاحی", "اقدام"],
    "cost":     ["هزینه"],
    "priority": ["اولویت", "الویت"],
}

ASSET_COLUMNS = {
    "equip":   ["نام تجهیز", "عنوان تجهیز", "تجهیز"],
    "point":   ["راهنمایی نقاط", "نقطه", "شماره نقطه"],
    "bearing": ["شماره بیرینگ", "بیرینگ"],
    "bush":    ["بوش"],
    "rpm":     ["دور نامی"],
}

VIEW_COLS = [
    "تاریخ", "خط تولید", "واحد", "عنوان تجهیز", "نقطه", "شرح نقطه",
    "شماره بیرینگ", "افقی", "عمودی", "محوری", "حداکثر", "دما",
    "وضعیت", "توضیحات", "اقدام اصلاحی", "اولویت", "هزینه",
]

REPORT_COLS = [
    "تاریخ", "خط تولید", "واحد", "عنوان تجهیز", "نقطه", "شرح نقطه",
    "شماره بیرینگ", "افقی", "عمودی", "محوری", "دما", "وضعیت",
]

NUM_COLS = ["افقی", "عمودی", "محوری", "حداکثر", "دما"]

# ---- ۷ کاربر پیش‌فرض سامانه (نام / ایمیل / نقش / رمز) ----
DEFAULT_USERS = {
    "admin":       {"name": "مدیر سامانه",        "email": "admin@simentehran.ir",   "role": "مالک",    "pass": "admin"},
    "manager":     {"name": "مدیر کارخانه",        "email": "manager@simentehran.ir", "role": "مدیر",    "pass": "1234"},
    "maintenance": {"name": "سرپرست تعمیرات",      "email": "maint@simentehran.ir",   "role": "تعمیرات", "pass": "1234"},
    "mech":        {"name": "کارشناس مکانیک",      "email": "mech@simentehran.ir",    "role": "مکانیک",  "pass": "1234"},
    "elec":        {"name": "کارشناس برق",         "email": "elec@simentehran.ir",    "role": "برق",     "pass": "1234"},
    "operator":    {"name": "اپراتور خط",          "email": "op@simentehran.ir",      "role": "اپراتور", "pass": "1234"},
    "viewer":      {"name": "ناظر (فقط مشاهده)",   "email": "view@simentehran.ir",    "role": "ناظر",    "pass": "1234"},
}

# جایگزینی ایمیل‌های واقعی از Secrets بدون دست‌زدن به کد
try:
    _secret_users = dict(st.secrets.get("users", {}))
except Exception:
    _secret_users = {}
for _u, _mail in _secret_users.items():
    if _u in DEFAULT_USERS and _mail:
        DEFAULT_USERS[_u]["email"] = str(_mail).strip()

if "users" not in st.session_state:
    st.session_state["users"] = {k: dict(v) for k, v in DEFAULT_USERS.items()}
if "is_owner" not in st.session_state:
    st.session_state["is_owner"] = False

# =====================================================================
# 4) ابزارهای متنی و عددی
# =====================================================================
FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

EMPTY_TOKENS = {"", "nan", "none", "null", "nat", "-", "—", "‌", "0.0.0"}


def fa2en(value):
    if value is None:
        return ""
    return str(value).translate(FA_DIGITS)


def norm(value):
    """یکسان‌سازی نام ستون یا نام تجهیز برای تطبیق مطمئن."""
    if value is None:
        return ""
    s = str(value)
    s = s.replace("\u200c", "").replace("\u200e", "").replace("\u200f", "")
    s = s.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه").replace("ة", "ه")
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")
    s = fa2en(s).lower()
    s = re.sub(r"[\s\.\-_/\\()\[\]{}:،؛,;'\"؟?!*+=|«»ـ]+", "", s)
    return s


def is_blank(value):
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except Exception:
        pass
    return str(value).strip().lower() in EMPTY_TOKENS


def to_num(value):
    """تبدیل محتوا به عدد؛ ناموفق → None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return float(value)
    s = fa2en(value).strip().replace("،", "").replace(",", "").replace(" ", "")
    s = s.replace("٫", ".")
    if s.lower() in EMPTY_TOKENS:
        return None
    try:
        return float(s)
    except Exception:
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        if m:
            try:
                return float(m.group(0))
            except Exception:
                return None
    return None


def to_text(value):
    if is_blank(value):
        return ""
    return str(value).strip()


def point_of(value):
    """p1 / P 1 / نقطه ۱ / 1  →  P1"""
    s = fa2en(value).strip()
    if s.lower() in EMPTY_TOKENS:
        return ""
    m = re.search(r"[pP]\s*[\.\-_]?\s*(\d{1,2})", s)
    if m:
        return "P%d" % int(m.group(1))
    m = re.search(r"(\d{1,2})", s)
    if m:
        return "P%d" % int(m.group(1))
    return ""


def point_label(code):
    if not code:
        return ""
    code = str(code).upper()
    if code in POINT_LABELS:
        return POINT_LABELS[code]
    num = code[1:] if code.startswith("P") else code
    return "نقطه " + fa2en(num)


def point_order(code):
    m = re.search(r"(\d+)", str(code))
    return int(m.group(1)) if m else 999


def parse_date(value):
    """تاریخ شمسی → (سال، ماه، روز)."""
    if is_blank(value):
        return None
    s = fa2en(value).strip()
    s = s.split(" ")[0]
    s = s.replace("٫", "/").replace("-", "/").replace(".", "/")
    m = re.search(r"(\d{4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.search(r"(\d{1,3})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})", s)
        if not m:
            return None
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 1400
    elif y < 1000:
        y += 1000
    if not (1200 <= y <= 1500):
        return None
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return None
    return (y, mo, d)


def fmt_date(tpl):
    if not tpl:
        return ""
    return "%04d/%02d/%02d" % (tpl[0], tpl[1], tpl[2])


def date_key(tpl):
    if not tpl:
        return 0
    return tpl[0] * 10000 + tpl[1] * 100 + tpl[2]


def row_max(h, v, a):
    vals = [x for x in (h, v, a) if x is not None]
    return max(vals) if vals else None


def status_of(h, v, a):
    mx = row_max(h, v, a)
    if mx is None:
        return "بی‌داده"
    if mx >= CRIT_LIMIT:
        return "بحرانی"
    if mx >= WARN_LIMIT:
        return "هشدار"
    return "نرمال"


STATUS_ICON = {"بحرانی": "🔴", "هشدار": "🟡", "نرمال": "🟢", "بی‌داده": "⚪"}


# =====================================================================
# 5) تطبیق ستون‌ها (ضد KeyError)
# =====================================================================
def resolve_columns(df, spec):
    """برای هر نقش، نزدیک‌ترین ستون موجود را پیدا می‌کند."""
    used = set()
    mapping = {}
    normed = {}
    for c in df.columns:
        nc = norm(c)
        if nc and nc not in normed:
            normed[nc] = c

    for role, candidates in spec.items():
        found = None
        # ۱) تطبیق دقیق
        for cand in candidates:
            nc = norm(cand)
            if nc and nc in normed and normed[nc] not in used:
                found = normed[nc]
                break
        # ۲) تطبیق نسبی
        if found is None:
            for cand in candidates:
                nc = norm(cand)
                if not nc:
                    continue
                for c in df.columns:
                    if c in used:
                        continue
                    if nc in norm(c):
                        found = c
                        break
                if found is not None:
                    break
        if found is not None:
            used.add(found)
            mapping[role] = found
    return mapping


def col_or_blank(df, mapping, role):
    if role in mapping:
        return df[mapping[role]]
    return pd.Series([""] * len(df), index=df.index)


def ensure_cols(df, cols):
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df


def _dedupe(cols):
    seen = {}
    out = []
    for c in cols:
        name = str(c).strip()
        if not name:
            name = "ستون"
        if name in seen:
            seen[name] += 1
            name = "%s_%d" % (name, seen[name])
        else:
            seen[name] = 0
        out.append(name)
    return out


# =====================================================================
# 6) خواندن شیت
# =====================================================================
@st.cache_data(ttl=300, show_spinner="در حال خواندن شیت...")
def load_sheet(sheet_name):
    errors = []

    # ۱) سرویس اکانت
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        try:
            creds_info = dict(st.secrets["gcp_service_account"])
        except Exception:
            creds_info = None

        if creds_info and SHEET_ID:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly",
            ]
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
            gc = gspread.authorize(creds)
            sh = gc.open_by_key(SHEET_ID)
            ws = sh.worksheet(sheet_name)
            values = ws.get_all_values()
            if len(values) < 2:
                raise ValueError("شیت خالی است یا فقط سرستون دارد")
            header = _dedupe(values[0])
            rows = []
            for r in values[1:]:
                r = list(r) + [""] * (len(header) - len(r))
                rows.append(r[: len(header)])
            return pd.DataFrame(rows, columns=header), ""
        raise ValueError("شناسه شیت یا اطلاعات سرویس اکانت تنظیم نشده")
    except Exception as exc:
        errors.append("gspread: %s" % exc)

    # ۲) خروجی CSV عمومی
    try:
        url = (
            "https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:csv&sheet=%s"
            % (SHEET_ID, requests.utils.quote(sheet_name))
        )
        resp = requests.get(url, timeout=45)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        df = pd.read_csv(io.StringIO(resp.text), dtype=str)
        df.columns = _dedupe(list(df.columns))
        return df, ""
    except Exception as exc:
        errors.append("csv: %s" % exc)

    return pd.DataFrame(), " | ".join(errors)


# =====================================================================
# 7) ساخت داده تمیز
# =====================================================================
def build_assets(df):
    """دیکشنری (نام تجهیز یکسان‌شده، کد نقطه) → اطلاعات بیرینگ"""
    if df is None or df.empty:
        return {}
    m = resolve_columns(df, ASSET_COLUMNS)
    if "equip" not in m or "point" not in m:
        return {}

    equip_s = col_or_blank(df, m, "equip")
    point_s = col_or_blank(df, m, "point")
    bearing_s = col_or_blank(df, m, "bearing")
    bush_s = col_or_blank(df, m, "bush")
    rpm_s = col_or_blank(df, m, "rpm")

    out = {}
    for equip, pt, brg, bush, rpm in zip(equip_s, point_s, bearing_s, bush_s, rpm_s):
        code = point_of(pt)
        ekey = norm(equip)
        if not ekey or not code:
            continue
        out[(ekey, code)] = {
            "equip": to_text(equip),
            "bearing": to_text(brg),
            "bush": to_text(bush),
            "rpm": to_text(rpm),
        }
    return out


def lookup_asset(assets, equip, code):
    ekey = norm(equip)
    if not ekey or not code:
        return None
    hit = assets.get((ekey, code))
    if hit:
        return hit
    target = str(equip).strip()
    for (akey, acode), val in assets.items():
        if acode != code:
            continue
        if akey and (ekey in akey or akey in ekey):
            return val
        if target and (target in val["equip"] or val["equip"] in target):
            return val
    return None


def clean_line(value):
    s = to_text(value)
    if not s:
        return ""
    s = fa2en(s)
    m = re.fullmatch(r"(\d+)\.0*", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"\d+", s):
        return str(int(s))
    return s


def build_vib(df, assets):
    if df is None or df.empty:
        return pd.DataFrame()

    m = resolve_columns(df, COLUMNS)
    out = pd.DataFrame(index=df.index)

    # --- تاریخ ---
    raw_date = col_or_blank(df, m, "date")
    out["تاریخ"] = [fmt_date(parse_date(x)) for x in raw_date]
    out["_date_key"] = [date_key(parse_date(x)) for x in raw_date]

    # --- خط، واحد، تجهیز ---
    out["خط تولید"] = [clean_line(x) for x in col_or_blank(df, m, "line")]
    out["واحد"] = [to_text(x) for x in col_or_blank(df, m, "unit")]
    out["عنوان تجهیز"] = [to_text(x) for x in col_or_blank(df, m, "equip")]

    # --- نقطه: اول «تصویر»، بعد «محل اندازه گیری» ---
    raw_point = col_or_blank(df, m, "point")
    codes = [point_of(x) for x in raw_point]
    if all(c == "" for c in codes):
        for fallback in ["محل اندازه گیری", "نقطه", "شماره نقطه", "مکان"]:
            cand = resolve_columns(df, {"p": [fallback]})
            if "p" in cand:
                raw_point = df[cand["p"]]
                codes = [point_of(x) for x in raw_point]
                if any(c != "" for c in codes):
                    break
    out["نقطه"] = codes
    out["شرح نقطه"] = [point_label(c) for c in codes]

    # --- سه جهت اندازه‌گیری ---
    h = [to_num(x) for x in col_or_blank(df, m, "h")]
    v = [to_num(x) for x in col_or_blank(df, m, "v")]
    a = [to_num(x) for x in col_or_blank(df, m, "a")]
    out["افقی"] = h
    out["عمودی"] = v
    out["محوری"] = a
    out["حداکثر"] = [row_max(x, y, z) for x, y, z in zip(h, v, a)]

    # --- دما ---
    out["دما"] = [to_num(x) for x in col_or_blank(df, m, "temp")]

    # --- ستون‌های مدیریتی ---
    out["توضیحات"] = [to_text(x) for x in col_or_blank(df, m, "desc")]
    out["اقدام اصلاحی"] = [to_text(x) for x in col_or_blank(df, m, "action")]
    out["هزینه"] = [to_text(x) for x in col_or_blank(df, m, "cost")]
    out["اولویت"] = [to_text(x) for x in col_or_blank(df, m, "priority")]
    out["وضعیت ثبت‌شده"] = [to_text(x) for x in col_or_blank(df, m, "status")]
    vib_bearing = [to_text(x) for x in col_or_blank(df, m, "bearing")]

    # --- شماره بیرینگ: اول شیت ارتعاشات، بعد Assets ---
    bearings = []
    for i, idx in enumerate(out.index):
        own = vib_bearing[i] if i < len(vib_bearing) else ""
        if own:
            bearings.append(own)
            continue
        info = lookup_asset(assets, out.at[idx, "عنوان تجهیز"], out.at[idx, "نقطه"])
        bearings.append(info["bearing"] if info else "")
    out["شماره بیرینگ"] = bearings

    # --- وضعیت ---
    statuses = []
    for x, y, z, given in zip(h, v, a, out["وضعیت ثبت‌شده"]):
        s = status_of(x, y, z)
        icon = STATUS_ICON.get(s, "⚪")
        statuses.append(icon + " " + (given if given else s))
    out["وضعیت"] = statuses

    # --- حذف ردیف‌های بی‌تاریخ ---
    out = out[out["_date_key"] > 0]
    out = out[out["تاریخ"].astype(str).str.strip() != ""]
    if out.empty:
        return pd.DataFrame()

    out["_ord"] = [point_order(c) for c in out["نقطه"]]
    out = out.sort_values(["_date_key", "_ord"], ascending=[False, True])
    return out


# =====================================================================
# 8) نمایش و گزارش
# =====================================================================
def color_status(val):
    s = str(val)
    if "بحرانی" in s:
        return "color:#c62828;font-weight:700"
    if "هشدار" in s:
        return "color:#ef6c00;font-weight:700"
    if "نرمال" in s or "سالم" in s:
        return "color:#2e7d32;font-weight:700"
    return "color:#757575"


def style_table(df):
    try:
        sty = df.style.format(
            {c: "{:.1f}" for c in NUM_COLS if c in df.columns}, na_rep="—"
        )
        if "وضعیت" in df.columns:
            try:
                sty = sty.map(color_status, subset=["وضعیت"])
            except Exception:
                sty = sty.applymap(color_status, subset=["وضعیت"])
        return sty
    except Exception:
        return df


REPORT_TEMPLATE = """<!DOCTYPE html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8">
<title>گزارش پایش ارتعاشات</title>
<style>
 body{font-family:Tahoma,Vazirmatn,sans-serif;background:#fff;color:#222;padding:24px}
 h1{font-size:20px;margin:0 0 6px}
 .meta{font-size:12px;color:#555;margin-bottom:16px}
 table{border-collapse:collapse;width:100%;font-size:12px}
 th{background:#263238;color:#fff;padding:7px 5px;border:1px solid #37474f}
 td{padding:6px 5px;border:1px solid #cfd8dc;text-align:center}
 tr.crit td{background:#ffebee}
 tr.warn td{background:#fff8e1}
 tr.ok td{background:#f1f8e9}
 .legend{margin-top:14px;font-size:12px;color:#455a64}
</style></head><body>
<h1>گزارش پایش وضعیت ارتعاشات ـ سیمان تهران</h1>
<div class="meta">تجهیز: __EQUIP__ &nbsp;|&nbsp; بازه: __DATES__ &nbsp;|&nbsp; تاریخ گزارش: __NOW__</div>
<table><thead><tr>__HEAD__</tr></thead><tbody>__ROWS__</tbody></table>
<div class="legend">حد هشدار: ۴/۵ mm/s &nbsp;|&nbsp; حد بحرانی: ۷ mm/s</div>
</body></html>"""


def build_report_html(show, equip_title, caption_dates):
    cols = [c for c in REPORT_COLS if c in show.columns]
    head_cells = "".join("<th>%s</th>" % c for c in cols)
    rows = []
    for _, r in show.iterrows():
        cls = "ok"
        stt = str(r.get("وضعیت", ""))
        if "بحرانی" in stt:
            cls = "crit"
        elif "هشدار" in stt:
            cls = "warn"
        cells = []
        for c in cols:
            val = r.get(c, "")
            if val is None or (isinstance(val, float) and pd.isna(val)):
                val = "—"
            elif isinstance(val, float):
                val = "%.1f" % val
            cells.append("<td>%s</td>" % str(val))
        rows.append("<tr class='%s'>%s</tr>" % (cls, "".join(cells)))

    html = REPORT_TEMPLATE
    html = html.replace("__EQUIP__", str(equip_title))
    html = html.replace("__DATES__", str(caption_dates))
    html = html.replace("__NOW__", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    html = html.replace("__HEAD__", head_cells)
    html = html.replace("__ROWS__", "".join(rows))
    return html


def send_email_smtp(to_list, subject, body):
    """ارسال واقعی ایمیل. اگر Secrets تنظیم نشده باشد، پیام واضح برمی‌گرداند."""
    host = str(_secret("SMTP_HOST", "smtp.gmail.com")).strip()
    try:
        port = int(_secret("SMTP_PORT", 465))
    except Exception:
        port = 465
    user = str(_secret("SMTP_USER", "")).strip()
    pw = str(_secret("SMTP_PASS", "")).strip()

    if not user or not pw:
        return False, "SMTP_USER و SMTP_PASS در Secrets تنظیم نشده‌اند."
    if not to_list:
        return False, "گیرنده‌ای انتخاب نشده است."

    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = user
    msg["To"] = ", ".join(to_list)

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as srv:
                srv.login(user, pw)
                srv.sendmail(user, to_list, msg.as_string())
        else:
            with smtplib.SMTP(host, port, timeout=30) as srv:
                srv.starttls()
                srv.login(user, pw)
                srv.sendmail(user, to_list, msg.as_string())
        return True, "ایمیل برای %d گیرنده ارسال شد." % len(to_list)
    except Exception as exc:
        return False, "خطای ارسال: %s" % exc


# =====================================================================
# 9) بارگذاری داده
# =====================================================================
if not SHEET_ID:
    st.error("شناسه شیت (SHEET_ID) تنظیم نشده است.")
    st.info(
        "در بخش Secrets برنامه، مقدار SHEET_ID را برابر شناسه فایل گوگل‌شیت قرار بده.\n\n"
        "شناسه، بخشی از آدرس بین /d/ تا /edit است."
    )
    st.stop()

vib_raw, vib_err = load_sheet(SHEET_VIB)
asr_raw, asr_err = load_sheet(SHEET_ASSETS)

assets = build_assets(asr_raw)
vib = build_vib(vib_raw, assets)

if vib.empty:
    st.error("داده‌ای برای نمایش پیدا نشد.")
    st.markdown("**پیام خواندن شیت ارتعاشات:**")
    st.code(vib_err or "بدون پیام", language="text")
    if not vib_raw.empty:
        st.markdown("**سرستون‌های شناسایی‌شده در شیت:**")
        st.write(list(vib_raw.columns))
        st.markdown("**چند ردیف اول:**")
        st.dataframe(vib_raw.head(5))
    st.info(
        "۱) SHEET_ID را تنظیم کن.\n"
        "۲) نام تب‌ها باید «ارتعاشات» و «Assets» باشد.\n"
        "۳) دسترسی شیت را روی «هر کسی با لینک» بگذار."
    )
    st.stop()

if asr_raw.empty:
    st.warning("شیت Assets خوانده نشد؛ شماره بیرینگ فقط از شیت ارتعاشات برداشته می‌شود.")

# ✅ رفع خطای NameError: df قبل از هر استفاده ساخته می‌شود
df = vib.drop(columns=["_ord"], errors="ignore").copy()
df = ensure_cols(df, VIEW_COLS)

# خلاصه بالای صفحه
k1, k2, k3, k4 = st.columns(4)
k1.metric("تعداد رکورد", len(df))
k2.metric("تعداد تجهیزات", int(df["عنوان تجهیز"].nunique()) if "عنوان تجهیز" in df.columns else 0)
k3.metric("حد هشدار", "%.1f" % WARN_LIMIT, "mm/s")
k4.metric("حد بحرانی", "%.1f" % CRIT_LIMIT, "mm/s")

# =====================================================================
# 10) فیلترها
# =====================================================================
st.sidebar.subheader("🔍 فیلترها")
dff = df.copy()

# فیلتر خط تولید
col_line = "خط تولید" if "خط تولید" in dff.columns else None
if col_line:
    lines = sorted([x for x in dff[col_line].dropna().astype(str).unique() if x.strip()])
    sel_line = st.sidebar.multiselect("خط تولید", lines, placeholder="همه خطوط")
    if sel_line:
        dff = dff[dff[col_line].astype(str).isin(sel_line)]

# فیلتر واحد
col_unit = "واحد" if "واحد" in dff.columns else None
if col_unit:
    units = sorted([x for x in dff[col_unit].dropna().astype(str).unique() if x.strip()])
    sel_unit = st.sidebar.multiselect("واحد", units, placeholder="همه واحدها")
    if sel_unit:
        dff = dff[dff[col_unit].astype(str).isin(sel_unit)]

# فیلتر تجهیز
col_eq = "عنوان تجهیز" if "عنوان تجهیز" in dff.columns else None
sel_eq = []
if col_eq:
    eqs = sorted([x for x in dff[col_eq].dropna().astype(str).unique() if x.strip()])
    sel_eq = st.sidebar.multiselect("تجهیز", eqs, placeholder="همه تجهیزات")
    if sel_eq:
        dff = dff[dff[col_eq].astype(str).isin(sel_eq)]

equip = sel_eq[0] if len(sel_eq) == 1 else "همه تجهیزات"

# ---- فیلتر تاریخ (بعد از انتخاب تجهیز) ----
st.sidebar.markdown("---")
st.sidebar.subheader("📅 فیلتر تاریخ")
date_mode = st.sidebar.radio(
    "بازه نمایش", ["همه تاریخ‌ها", "بازه دلخواه", "تاریخ‌های خاص"], index=0
)

show = dff.copy()
caption_dates = "همه تاریخ‌ها"

if "_date_key" in show.columns and date_mode == "بازه دلخواه":
    dc1, dc2 = st.sidebar.columns(2)
    d_from = dc1.text_input("از تاریخ", placeholder="1403/01/01")
    d_to = dc2.text_input("تا تاریخ", placeholder="1404/12/29")

    k_from = date_key(parse_date(d_from)) if d_from.strip() else 0
    if d_to.strip():
        tpl_to = parse_date(d_to)
        k_to = date_key(tpl_to) if tpl_to else 0
        if tpl_to is None:
            st.sidebar.warning("تاریخ پایان نامعتبر است.")
            k_to = 99999999
    else:
        k_to = 99999999

    if d_from.strip() and parse_date(d_from) is None:
        st.sidebar.warning("تاریخ شروع نامعتبر است.")

    show = show[(show["_date_key"] >= k_from) & (show["_date_key"] <= k_to)]
    caption_dates = "%s تا %s" % (
        fmt_date(parse_date(d_from)) or "ابتدا",
        fmt_date(parse_date(d_to)) or "اکنون",
    )

elif "_date_key" in show.columns and date_mode == "تاریخ‌های خاص":
    d_opts = sorted(
        [x for x in show["تاریخ"].dropna().astype(str).unique() if x.strip()],
        reverse=True,
    )
    sel_dates = st.sidebar.multiselect("تاریخ‌ها", d_opts, placeholder="همه تاریخ‌ها")
    if sel_dates:
        show = show[show["تاریخ"].astype(str).isin(sel_dates)]
        caption_dates = "، ".join(sel_dates[:4])
        if len(sel_dates) > 4:
            caption_dates += " و %d تاریخ دیگر" % (len(sel_dates) - 4)

if show.empty:
    st.warning("با این فیلترها رکوردی باقی نماند. فیلترها را بازتر کن.")

# =====================================================================
# 11) اعلانیه‌ها
# =====================================================================
if "وضعیت" in show.columns:
    critical = show[show["وضعیت"].astype(str).str.contains("بحرانی", na=False)]
    warning = show[show["وضعیت"].astype(str).str.contains("هشدار", na=False)]
else:
    critical = show.iloc[0:0]
    warning = show.iloc[0:0]

n_alerts = len(critical) + len(warning)

with st.expander("🔔 اعلانیه‌ها — %d مورد" % n_alerts, expanded=False):
    if n_alerts == 0:
        st.success("هیچ اعلانیه‌ای وجود ندارد.")
    else:
        show_cols = [
            c for c in ["تاریخ", "خط تولید", "واحد", "عنوان تجهیز", "نقطه",
                        "شماره بیرینگ", "حداکثر", "وضعیت"]
            if c in show.columns
        ]
        if len(critical):
            st.markdown("### 🔴 بحرانی — %d مورد" % len(critical))
            st.dataframe(critical[show_cols], use_container_width=True, hide_index=True)
        if len(warning):
            st.markdown("### 🟡 هشدار — %d مورد" % len(warning))
            st.dataframe(warning[show_cols], use_container_width=True, hide_index=True)

# =====================================================================
# 12) جدول اصلی
# =====================================================================
st.subheader("📊 جدول وضعیت")
if show.empty:
    st.info("داده‌ای برای نمایش نیست.")
else:
    main_cols = [c for c in VIEW_COLS if c in show.columns]
    st.dataframe(style_table(show[main_cols]), use_container_width=True, hide_index=True)

# =====================================================================
# 13) تب‌ها
# =====================================================================
tab_table, tab_chart, tab_alert, tab_users = st.tabs(
    ["📋 جدول داده‌ها", "📈 نمودارها", "📧 ارسال اعلان", "👥 کاربران"]
)

# ---------------- تب جدول ----------------
with tab_table:
    st.subheader("داده‌های ارتعاش — %s" % equip)
    st.caption("بازه: %s" % caption_dates)

    only_crit = st.checkbox("فقط ردیف‌های بحرانی و هشدار", value=False)
    tbl = show.copy()
    if only_crit and "وضعیت" in tbl.columns:
        tbl = tbl[tbl["وضعیت"].astype(str).str.contains("بحرانی|هشدار", na=False)]

    cols = [c for c in VIEW_COLS if c in tbl.columns]

    if tbl.empty:
        st.info("ردیفی برای نمایش نیست.")
    else:
        st.dataframe(style_table(tbl[cols]), use_container_width=True, hide_index=True)

    dc1, dc2 = st.columns(2)
    safe_name = re.sub(r"[^\w\u0600-\u06FF\-]+", "_", str(equip)) or "vibration"

    with dc1:
        csv = tbl[cols].to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "⬇️ دانلود CSV",
            data=csv,
            file_name="vibration_%s.csv" % safe_name,
            mime="text/csv",
            use_container_width=True,
        )

    with dc2:
        html_report = build_report_html(tbl, equip, caption_dates)
        st.download_button(
            "🖨️ دانلود گزارش HTML (قابل چاپ)",
            data=html_report.encode("utf-8"),
            file_name="report_%s.html" % safe_name,
            mime="text/html",
            use_container_width=True,
        )

# ---------------- تب نمودار ----------------
with tab_chart:
    st.subheader("روند ارتعاش")
    if show.empty:
        st.info("داده‌ای برای نمودار نیست.")
    else:
        g = show.copy()
        g["_label_date"] = g["تاریخ"]

        dir_cols = [c for c in ["افقی", "عمودی", "محوری"] if c in g.columns]
        if dir_cols:
            trend = g.groupby("_label_date")[dir_cols].max().sort_index()
            st.markdown("**بیشترین مقدار هر جهت در هر تاریخ**")
            st.line_chart(trend)

        if "حداکثر" in g.columns:
            st.markdown("**بیشترین ارتعاش هر نقطه (حداکثر سه جهت)**")
            by_point = g.groupby("نقطه")["حداکثر"].max().dropna().sort_values(ascending=False)
            if not by_point.empty:
                by_point.index = [str(c) + " - " + point_label(c) for c in by_point.index]
                st.bar_chart(by_point)

        if "وضعیت" in g.columns:
            st.markdown("**سهم وضعیت‌ها**")
            stt = g["وضعیت"].astype(str)
            for icon in ["🔴 ", "🟡 ", "🟢 ", "⚪ "]:
                stt = stt.str.replace(icon, "", regex=False)
            st.bar_chart(stt.value_counts())

        if "دما" in g.columns and g["دما"].notna().any():
            st.markdown("**روند دما**")
            temp = g.groupby("_label_date")["دما"].max().sort_index()
            st.line_chart(temp)
        else:
            st.caption("ستون دما خالی است، بنابراین نمودار دما نمایش داده نمی‌شود.")

# ---------------- تب اعلان ----------------
with tab_alert:
    st.subheader("پیش‌نویس و ارسال اعلان")

    users = st.session_state["users"]
    email_choices = {}
    for uname, info in users.items():
        mail = str(info.get("email", "")).strip()
        if mail:
            email_choices[mail] = "%s (%s)" % (info.get("name", uname), info.get("role", ""))

    if "وضعیت" in show.columns:
        crit_rows = show[show["وضعیت"].astype(str).str.contains("بحرانی|هشدار", na=False)]
    else:
        crit_rows = show.iloc[0:0]

    if crit_rows.empty:
        st.success("در بازه انتخاب‌شده ردیف بحرانی یا هشدار وجود ندارد.")
    else:
        lines = ["گزارش پایش ارتعاشات — %s" % equip, "بازه: %s" % caption_dates, ""]
        for _, r in crit_rows.iterrows():
            h_val = r.get("افقی")
            v_val = r.get("عمودی")
            a_val = r.get("محوری")
            lines.append(
                "%s | %s %s | %s | افقی %.1f / عمودی %.1f / محوری %.1f | %s"
                % (
                    r.get("تاریخ", ""),
                    r.get("نقطه", ""),
                    ("(%s)" % r.get("شرح نقطه")) if r.get("شرح نقطه") else "",
                    r.get("شماره بیرینگ") or "بدون بیرینگ",
                    h_val if pd.notna(h_val) else 0.0,
                    v_val if pd.notna(v_val) else 0.0,
                    a_val if pd.notna(a_val) else 0.0,
                    r.get("وضعیت", ""),
                )
            )
        draft = "\n".join(lines)
        edited = st.text_area("متن آماده ارسال (قابل ویرایش)", draft, height=260)

        subject = "هشدار ارتعاش — %s — %s" % (equip, caption_dates)

        st.markdown("**گیرندگان**")
        default_addr = str(_secret("ALERT_EMAIL", "")).strip()
        if default_addr in email_choices:
            default_pick = [default_addr]
        else:
            default_pick = list(email_choices.keys())[:1]

        picked = st.multiselect(
            "انتخاب از کاربران سامانه",
            options=list(email_choices.keys()),
            default=default_pick,
            format_func=lambda m: "%s — %s" % (m, email_choices.get(m, "")),
        )
        extra = st.text_input("گیرنده اضافی (با کاما جدا کن)", "")
        to_list = picked + [x.strip() for x in extra.split(",") if x.strip()]

        st.caption("گیرندگان فعلی: %s" % ("، ".join(to_list) if to_list else "هیچ‌کس"))

        import urllib.parse as up

        mailto = "mailto:%s?subject=%s&body=%s" % (
            up.quote(",".join(to_list)) if to_list else "",
            up.quote(subject),
            up.quote(edited),
        )
        st.markdown("[📨 باز کردن برنامه ایمیل با متن آماده](%s)" % mailto)
        st.caption("روش جایگزین: متن را کپی کن و در ایمیل یا پیام‌رسان سازمانی بفرست.")

        send_col, hist_col = st.columns(2)

        with send_col:
            if st.button("✉️ ارسال ایمیل", use_container_width=True):
                ok, msg = send_email_smtp(to_list, subject, edited)
                if ok:
                    st.success(msg)
                    st.session_state.setdefault("alert_history", []).append(
                        {"time": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                         "equip": equip, "rows": len(crit_rows),
                         "to": len(to_list)}
                    )
                else:
                    st.error(msg)

        with hist_col:
            if st.button("📝 ثبت در تاریخچه", use_container_width=True):
                st.session_state.setdefault("alert_history", []).append(
                    {"time": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                     "equip": equip, "rows": len(crit_rows),
                     "to": len(to_list)}
                )
                st.success("در تاریخچه ثبت شد.")

        hist = st.session_state.get("alert_history", [])
        if hist:
            st.markdown("**تاریخچه اعلان‌ها**")
            st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)

# ---------------- تب کاربران ----------------
with tab_users:
    st.subheader("مدیریت کاربران")
    users = st.session_state["users"]

    # ---- حالت عمومی: فقط نمایش (بدون رمز) ----
    if not st.session_state["is_owner"]:
        st.info("برای دیدن ایمیل‌ها و ویرایش کاربران، رمز مالک سیستم را وارد کن.")

        pw = st.text_input("رمز مالک سیستم", type="password")
        if st.button("ورود به بخش مدیریت"):
            if pw and pw == str(users.get("admin", {}).get("pass", "admin")):
                st.session_state["is_owner"] = True
                st.rerun()
            else:
                st.error("رمز نادرست است.")

        st.caption("کاربر پیش‌فرض: admin — رمز پیش‌فرض: admin (بعد از ورود عوض کن)")

        st.markdown("**کاربران سامانه**")
        st.dataframe(
            pd.DataFrame(
                [
                    {"کاربر": k,
                     "نام": v.get("name", ""),
                     "نقش": v.get("role", ""),
                     "ایمیل": v.get("email", "")}
                    for k, v in users.items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    # ---- حالت مالک: ویرایش کامل ----
    else:
        st.success("دسترسی مالک سیستم فعال است.")

        st.markdown("**جدول کاربران — قابل ویرایش (نام، ایمیل، نقش، رمز)**")
        users_df = pd.DataFrame(
            [
                {"کاربر": k,
                 "نام": v.get("name", ""),
                 "ایمیل": v.get("email", ""),
                 "نقش": v.get("role", ""),
                 "رمز": v.get("pass", "")}
                for k, v in users.items()
            ]
        )
        edited_users = st.data_editor(
            users_df,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            key="users_editor",
        )
        if st.button("💾 ذخیره تغییرات کاربران", use_container_width=True):
            for _, row in edited_users.iterrows():
                ukey = str(row["کاربر"]).strip()
                if not ukey:
                    continue
                st.session_state["users"][ukey] = {
                    "name": str(row["نام"]).strip(),
                    "email": str(row["ایمیل"]).strip(),
                    "role": str(row["نقش"]).strip(),
                    "pass": str(row["رمز"]).strip(),
                }
            st.success("تغییرات کاربران ذخیره شد.")
            st.rerun()

        st.divider()

        st.markdown("**افزودن کاربر جدید**")
        with st.form("add_user"):
            c_a, c_b = st.columns(2)
            nu = c_a.text_input("نام کاربری (انگلیسی)")
            nn = c_b.text_input("نام و نام خانوادگی")
            c_c, c_d = st.columns(2)
            ne = c_c.text_input("ایمیل")
            nr = c_d.selectbox(
                "نقش", ["مدیر", "تعمیرات", "مکانیک", "برق", "اپراتور", "ناظر"]
            )
            npw = st.text_input("رمز", type="password")
            if st.form_submit_button("افزودن کاربر"):
                if nu and npw:
                    st.session_state["users"][nu.strip()] = {
                        "name": nn.strip(),
                        "email": ne.strip(),
                        "role": nr,
                        "pass": npw,
                    }
                    st.success("کاربر «%s» اضافه شد." % nu)
                    st.rerun()
                else:
                    st.error("نام کاربری و رمز را پر کن.")

        st.markdown("**تغییر رمز مالک**")
        with st.form("change_pw"):
            old = st.text_input("رمز فعلی", type="password")
            new = st.text_input("رمز جدید", type="password")
            if st.form_submit_button("تغییر رمز مالک"):
                if old == str(users.get("admin", {}).get("pass", "")) and new:
                    st.session_state["users"]["admin"]["pass"] = new
                    st.success("رمز مالک تغییر کرد.")
                else:
                    st.error("رمز فعلی نادرست است یا رمز جدید خالی است.")

        if st.button("خروج از حالت مالک"):
            st.session_state["is_owner"] = False
            st.rerun()

st.divider()
st.caption(
    "حد هشدار ۴/۵ و حد بحرانی ۷ میلی‌متر بر ثانیه. "
    "شرح نقاط از دیکشنری POINT_LABELS در ابتدای فایل قابل ویرایش است."
)
