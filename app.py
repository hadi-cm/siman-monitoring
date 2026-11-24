# -*- coding: utf-8 -*-
"""
سامانه هوشمند پایش وضعیت ارتعاشات — سیمان تهران
نسخه اصلاح‌شده:
  ۱) نمایش کامل تاریخ‌ها (هیچ ردیفی حذف نمی‌شود)
  ۲) فیلتر خط تولید کامل (شامل خط ۸ و بقیه خطوط، با نرمال‌سازی 8.0 → 8)
  ۳) فیلتر چندتایی تاریخ + گزینه اختیاری «فقط جدیدترین تاریخ هر نقطه» (پیش‌فرض خاموش)
  ۴) هدر: لوگوی خودت چپ | عنوان وسط | لوگوی سیمان تهران راست
  ۵) مدیریت ۷ کاربر با ایمیل + ارسال واقعی ایمیل (SMTP) و mailto
"""

import os
import io
import re
import html
import smtplib
import datetime as dt
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pandas as pd
import requests
import streamlit as st

# ============================================================
# ۰) تنظیمات صفحه (اولین دستور Streamlit)
# ============================================================
st.set_page_config(
    page_title="سامانه هوشمند پایش وضعیت — سیمان تهران",
    page_icon="📊",
    layout="wide",
)


def _secret(key, default=""):
    try:
        v = st.secrets[key]
        return str(v) if v is not None else default
    except Exception:
        return default


SHEET_ID = _secret("SHEET_ID", "").strip()
SHEET_VIB = _secret("SHEET_VIB", "ارتعاشات")
SHEET_ASSETS = _secret("SHEET_ASSETS", "Assets")

# ---------- حدود هشدار ----------
WARN_LIMIT = 4.5   # mm/s
CRIT_LIMIT = 7.0   # mm/s

EMPTY_TOKENS = {"", "-", "—", "_", "na", "n/a", "null", "none", "nan", "بی‌داده"}

# شرح نقاط — آزادانه ویرایش کن. هر نقطه‌ای که اینجا نباشد، «نقطه N» نمایش داده می‌شود.
POINT_LABELS = {
    # "P1": "بیرینگ موتور — سمت کوپلینگ",
    # "P2": "بیرینگ موتور — سمت آزاد",
}

# ---------- ستون‌ها ----------
VIEW_COLS = ["تاریخ", "خط تولید", "واحد", "تجهیز", "نقطه", "شرح نقطه",
             "شماره بیرینگ", "افقی", "عمودی", "محوری", "حداکثر", "وضعیت", "دما"]

REPORT_COLS = ["تاریخ", "خط تولید", "واحد", "تجهیز", "نقطه", "شماره بیرینگ",
               "افقی", "عمودی", "محوری", "حداکثر", "وضعیت"]

NUM_COLS = ["افقی", "عمودی", "محوری", "حداکثر", "دما"]

VIB_COLUMNS = {
    "date":       ["تاریخ", "تاریخ شمسی", "date"],
    "line":       ["خط تولید", "خط", "line"],
    "unit":       ["واحد", "یونیت", "unit"],
    "equip":      ["عنوان تجهیز", "تجهیز", "equipment", "equip", "ماشین"],
    "point":      ["نقطه", "شماره نقطه", "point"],
    "point_desc": ["شرح نقطه", "شرح", "توضیح نقطه", "point desc"],
    "bearing":    ["شماره بیرینگ", "بیرینگ", "bearing"],
    "h":          ["افقی", "h", "horizontal"],
    "v":          ["عمودی", "v", "vertical"],
    "a":          ["محوری", "a", "axial"],
    "temp":       ["دما", "دمای", "temperature", "temp"],
}

ASSET_COLUMNS = {
    "equip":   ["عنوان تجهیز", "تجهیز", "equipment", "equip"],
    "point":   ["نقطه", "شماره نقطه", "point"],
    "bearing": ["شماره بیرینگ", "بیرینگ", "bearing"],
    "bush":    ["بوش", "bush"],
    "rpm":     ["دور", "rpm", "سرعت"],
}

# ============================================================
# ۱) توابع کمکی
# ============================================================
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def fa2en(value):
    if value is None:
        return ""
    return str(value).translate(_FA_DIGITS)


def norm(value):
    s = fa2en(value).lower()
    s = s.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه").replace("ة", "ه")
    s = re.sub(r"[\s\u200c\.\-_:/\\|()\[\]{}!؟?،,؛;:'\"«»ـ]+", "", s)
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
    if value is None or isinstance(value, bool):
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


def clean_label(value):
    """برچسب تمیز: ارقام فارسی→انگلیسی، حذف .0 انتهایی، یکسان‌سازی فاصله.
    مثال: 8.0 → '8'   |   'خط  ۸' → 'خط 8'   |   ۱۲ → '12'
    """
    if is_blank(value):
        return ""
    s = fa2en(value).strip()
    s = re.sub(r"\s+", " ", s)
    if re.fullmatch(r"-?\d+\.0+", s):
        s = s.split(".")[0]
    if re.fullmatch(r"\d+", s):
        s = str(int(s))
    return s


def natural_key(s):
    """مرتب‌سازی طبیعی: خط ۲ قبل از خط ۱۰"""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def point_of(value):
    """p1 / P 1 / نقطه ۱ / ۱  →  P1"""
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
    """تاریخ شمسی → (سال، ماه، روز)"""
    if is_blank(value):
        return None
    s = fa2en(value).strip().split(" ")[0]
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


def safe_name(s):
    return re.sub(r"[^0-9A-Za-zآ-ی_\-]+", "_", str(s)).strip("_") or "report"


# ============================================================
# ۲) تطبیق ستون‌ها (ضد KeyError)
# ============================================================
def resolve_columns(df, spec):
    used = set()
    mapping = {}
    normed = {}
    for c in df.columns:
        nc = norm(c)
        if nc and nc not in normed:
            normed[nc] = c

    for role, candidates in spec.items():
        found = None
        for cand in candidates:
            nc = norm(cand)
            if nc and nc in normed and normed[nc] not in used:
                found = normed[nc]
                break
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
        name = str(c).strip() or "ستون"
        if name in seen:
            seen[name] += 1
            name = "%s_%d" % (name, seen[name])
        else:
            seen[name] = 0
        out.append(name)
    return out


# ============================================================
# ۳) خواندن شیت
# ============================================================
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


# ============================================================
# ۴) ساخت داده تمیز
# ============================================================
def build_assets(df):
    """دیکشنری (نام تجهیز یکسان‌شده، کد نقطه) → اطلاعات بیرینگ"""
    if df is None or df.empty:
        return {}
    m = resolve_columns(df, ASSET_COLUMNS)
    if "equip" not in m or "point" not in m:
        return {}

    equip_s = list(col_or_blank(df, m, "equip"))
    point_s = list(col_or_blank(df, m, "point"))
    bearing_s = list(col_or_blank(df, m, "bearing"))
    bush_s = list(col_or_blank(df, m, "bush"))
    rpm_s = list(col_or_blank(df, m, "rpm"))

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
    return assets.get((ekey, code))


def build_vib(df, assets):
    """ساخت جدول تمیز ارتعاشات.

    ⚠️ رفع باگ: در این نسخه هیچ ردیفی dedupe یا حذف نمی‌شود؛
    تمام تاریخ‌های هر نقطه نگه داشته می‌شوند تا تاریخچه کامل دیده شود.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    m = resolve_columns(df, VIB_COLUMNS)

    dates = [parse_date(v) for v in col_or_blank(df, m, "date")]
    line_s = [clean_label(v) for v in col_or_blank(df, m, "line")]
    unit_s = [clean_label(v) for v in col_or_blank(df, m, "unit")]
    equip_s = [clean_label(v) for v in col_or_blank(df, m, "equip")]
    pts = [point_of(v) for v in col_or_blank(df, m, "point")]
    descs = [to_text(v) for v in col_or_blank(df, m, "point_desc")]
    brg_sheet = [to_text(v) for v in col_or_blank(df, m, "bearing")]
    h_s = [to_num(v) for v in col_or_blank(df, m, "h")]
    v_s = [to_num(v) for v in col_or_blank(df, m, "v")]
    a_s = [to_num(v) for v in col_or_blank(df, m, "a")]
    t_s = [to_num(v) for v in col_or_blank(df, m, "temp")]

    rows = []
    for i in range(len(df)):
        info = lookup_asset(assets, equip_s[i], pts[i]) or {}
        bearing = info.get("bearing") or brg_sheet[i]
        h, v, a = h_s[i], v_s[i], a_s[i]
        stt = status_of(h, v, a)
        rows.append({
            "تاریخ": fmt_date(dates[i]),
            "_ord": date_key(dates[i]),
            "خط تولید": line_s[i],
            "واحد": unit_s[i],
            "تجهیز": equip_s[i],
            "نقطه": pts[i],
            "شرح نقطه": descs[i] or point_label(pts[i]),
            "شماره بیرینگ": bearing,
            "افقی": h,
            "عمودی": v,
            "محوری": a,
            "حداکثر": row_max(h, v, a),
            "وضعیت": "%s %s" % (STATUS_ICON.get(stt, "⚪"), stt),
            "دما": t_s[i],
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    # حذف فقط ردیف‌های کاملاً خالی (بدون تجهیز، بدون نقطه و بدون هیچ عددی)
    keep = ~(
        (out["تجهیز"].astype(str).str.strip() == "")
        & (out["نقطه"].astype(str).str.strip() == "")
        & out[["افقی", "عمودی", "محوری"]].isna().all(axis=1)
    )
    out = out[keep].copy()

    out["_pord"] = out["نقطه"].map(point_order)
    out = out.sort_values(["_ord", "_pord"], kind="mergesort").reset_index(drop=True)
    out = ensure_cols(out, VIEW_COLS)
    return out


def style_table(df):
    def color_status(s):
        s = str(s)
        if "بحرانی" in s:
            return "color:#c62828;font-weight:700"
        if "هشدار" in s:
            return "color:#ef6c00;font-weight:700"
        if "نرمال" in s:
            return "color:#2e7d32;font-weight:700"
        return "color:#757575"

    try:
        sty = df.style.format(
            {c: "{:.1f}" for c in NUM_COLS if c in df.columns}, na_rep="—"
        )
        try:
            sty = sty.map(color_status, subset=["وضعیت"])
        except Exception:
            sty = sty.applymap(color_status, subset=["وضعیت"])
        return sty
    except Exception:
        return df


# ============================================================
# ۵) گزارش HTML قابل چاپ
# ============================================================
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
<h1>گزارش پایش وضعیت ارتعاشات</h1>
<div class="meta">تجهیز: __EQUIP__ &nbsp;|&nbsp; بازه: __DATES__ &nbsp;|&nbsp; تاریخ گزارش: __NOW__</div>
<table><thead><tr>__HEAD__</tr></thead><tbody>__ROWS__</tbody></table>
<div class="legend">حد هشدار: __WARN__ mm/s &nbsp;|&nbsp; حد بحرانی: __CRIT__ mm/s</div>
</body></html>"""


def build_report_html(show, equip_title, caption_dates):
    head_cells = "".join("<th>%s</th>" % html.escape(c) for c in REPORT_COLS)
    rows_out = []
    for _, r in show.iterrows():
        cls = "ok"
        stt = str(r.get("وضعیت", ""))
        if "بحرانی" in stt:
            cls = "crit"
        elif "هشدار" in stt:
            cls = "warn"
        cells = []
        for c in REPORT_COLS:
            val = r.get(c, "")
            if val is None or (isinstance(val, float) and pd.isna(val)):
                val = "—"
            elif isinstance(val, float):
                val = "%.1f" % val
            cells.append("<td>%s</td>" % html.escape(str(val)))
        rows_out.append("<tr class='%s'>%s</tr>" % (cls, "".join(cells)))

    out = REPORT_TEMPLATE
    out = out.replace("__EQUIP__", html.escape(str(equip_title)))
    out = out.replace("__DATES__", html.escape(str(caption_dates)))
    out = out.replace("__NOW__", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    out = out.replace("__WARN__", str(WARN_LIMIT))
    out = out.replace("__CRIT__", str(CRIT_LIMIT))
    out = out.replace("__HEAD__", head_cells)
    out = out.replace("__ROWS__", "".join(rows_out))
    return out


# ============================================================
# ۶) کاربران و ایمیل
# ============================================================
DEFAULT_USERS = {
    "admin":       {"name": "مالک سیستم",     "email": "admin@example.com",       "role": "مالک",     "pass": "admin"},
    "manager":     {"name": "مدیر تولید",     "email": "manager@example.com",     "role": "مدیر",     "pass": "1234"},
    "maintenance": {"name": "سرپرست تعمیرات", "email": "maintenance@example.com", "role": "تعمیرات",  "pass": "1234"},
    "mech":        {"name": "کارشناس مکانیک", "email": "mech@example.com",        "role": "مکانیک",   "pass": "1234"},
    "elec":        {"name": "کارشناس برق",    "email": "elec@example.com",        "role": "برق",      "pass": "1234"},
    "operator":    {"name": "اپراتور خط",     "email": "operator@example.com",    "role": "اپراتور",  "pass": "1234"},
    "viewer":      {"name": "ناظر",           "email": "viewer@example.com",      "role": "ناظر",     "pass": "1234"},
}


def init_users():
    if "users" not in st.session_state:
        users = {k: dict(v) for k, v in DEFAULT_USERS.items()}
        # جایگزینی ایمیل‌های واقعی از Secrets:  [users]  manager = "x@y.ir"
        try:
            for k, v in dict(st.secrets.get("users", {})).items():
                if k in users:
                    users[k]["email"] = str(v)
                else:
                    users[k] = {"name": k, "email": str(v), "role": "کاربر", "pass": "1234"}
        except Exception:
            pass
        st.session_state["users"] = users
    st.session_state.setdefault("is_owner", False)
    st.session_state.setdefault("alert_history", [])


def send_email_smtp(to_list, subject, body):
    user = _secret("SMTP_USER", "")
    pw = _secret("SMTP_PASS", "")
    if not user or not pw:
        return False, "SMTP_USER / SMTP_PASS در Secrets تنظیم نشده است."
    try:
        msg = MIMEMultipart()
        msg["From"] = user
        msg["To"] = ", ".join(to_list)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
            s.login(user, pw)
            s.sendmail(user, to_list, msg.as_string())
        return True, "ایمیل با موفقیت ارسال شد."
    except Exception as exc:
        return False, "خطا در ارسال ایمیل: %s" % exc


init_users()

# ============================================================
# ۷) سربرگ: لوگو چپ | عنوان وسط | لوگو راست
# ============================================================
h_left, h_mid, h_right = st.columns([1, 4, 1], gap="small")

with h_left:
    if os.path.exists("my_logo.png"):
        st.image("my_logo.png", width=150)
    else:
        st.caption("🏢")

with h_mid:
    st.markdown(
        """
<div dir="rtl" style="text-align:center;">
  <div style="font-size:26px;font-weight:800;line-height:1.7;margin-top:6px;">
    سامانه هوشمند پایش وضعیت — سیمان تهران
  </div>
  <div style="font-size:13px;color:#607d8b;margin-top:2px;">
    پایش نقطه‌به‌نقطه ارتعاشات، اتصال شماره بیرینگ از شیت Assets و گزارش قابل چاپ
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

with h_right:
    if os.path.exists("client_logo.png"):
        st.image("client_logo.png", width=150)
    else:
        st.caption("🏭")

st.divider()

# ============================================================
# ۸) بارگذاری داده
# ============================================================
if not SHEET_ID:
    st.error("شناسه شیت (SHEET_ID) تنظیم نشده است.")
    st.info(
        "در بخش Secrets برنامه، مقدار SHEET_ID را برابر شناسه فایل گوگل‌شیت قرار بده.\n\n"
        "شناسه، بخشی از آدرس بین /d/ تا /edit است."
    )
    st.stop()

vib_raw, vib_err = load_sheet(SHEET_VIB)
asr_raw, asr_err = load_sheet(SHEET_ASSETS)

if vib_raw.empty:
    st.error("داده‌ای برای نمایش پیدا نشد.")
    st.markdown("**پیام خواندن شیت ارتعاشات:**")
    st.code(vib_err or "بدون پیام", language="text")
    st.info(
        "۱) SHEET_ID را تنظیم کن.\n"
        "۲) نام تب‌ها باید «ارتعاشات» و «Assets» باشد.\n"
        "۳) دسترسی شیت را روی «هر کسی با لینک» بگذار."
    )
    st.stop()

if asr_raw.empty:
    st.warning("شیت Assets خوانده نشد؛ شماره بیرینگ فقط از شیت ارتعاشات برداشته می‌شود.")

assets = build_assets(asr_raw)
vib = build_vib(vib_raw, assets)

if vib.empty:
    st.error("پس از پردازش، ردیف معتبری باقی نماند. سرستون‌های شیت را بررسی کن.")
    st.write(list(vib_raw.columns))
    st.dataframe(vib_raw.head(10))
    st.stop()

df = vib.copy()   # ← رفع باگ NameError: df همیشه ساخته می‌شود

# ============================================================
# ۹) فیلترها
# ============================================================
st.sidebar.subheader("🔍 فیلترها")


def options_from(series):
    vals = []
    for v in series:
        s = clean_label(v)
        if s and s not in vals:
            vals.append(s)
    return sorted(vals, key=natural_key)


# --- خط تولید: گزینه‌ها از کل داده خام ساخته می‌شود (رفع باگ نبودن خط ۸) ---
_raw_map = resolve_columns(vib_raw, VIB_COLUMNS)
raw_line = col_or_blank(vib_raw, _raw_map, "line")
line_opts = options_from(list(raw_line) + list(df["خط تولید"]))
if line_opts:
    sel_line = st.sidebar.multiselect("خط تولید", line_opts, placeholder="همه خطوط")
    if sel_line:
        df = df[df["خط تولید"].isin(sel_line)]
else:
    sel_line = []

# --- واحد ---
unit_opts = options_from(df["واحد"])
if unit_opts:
    sel_unit = st.sidebar.multiselect("واحد", unit_opts, placeholder="همه واحدها")
    if sel_unit:
        df = df[df["واحد"].isin(sel_unit)]
else:
    sel_unit = []

# --- تجهیز ---
eq_opts = options_from(df["تجهیز"])
if eq_opts:
    sel_eq = st.sidebar.multiselect("تجهیز", eq_opts, placeholder="همه تجهیزات")
    if sel_eq:
        df = df[df["تجهیز"].isin(sel_eq)]
else:
    sel_eq = []

# --- تاریخ: چندتایی (رفع باگ نمایش فقط آخرین تاریخ) ---
st.sidebar.markdown("**تاریخ‌ها**")
all_dates = sorted({d for d in df["تاریخ"] if d}, reverse=True)
sel_dates = st.sidebar.multiselect(
    "انتخاب تاریخ (پیش‌فرض: همه)",
    all_dates,
    default=all_dates,
    placeholder="همه تاریخ‌ها",
)
if sel_dates and len(sel_dates) < len(all_dates):
    df = df[df["تاریخ"].isin(sel_dates)]

only_latest = st.sidebar.checkbox(
    "فقط جدیدترین تاریخ هر نقطه", value=False,
    help="خاموش = تاریخچه کامل هر نقطه نمایش داده می‌شود.",
)
if only_latest:
    df = (
        df.sort_values("_ord", kind="mergesort")
          .drop_duplicates(subset=["تجهیز", "نقطه"], keep="last")
    )

df = df.sort_values(["_ord", "_pord"], kind="mergesort").reset_index(drop=True)
show = df.copy()

if len(sel_eq) == 1:
    equip = sel_eq[0]
elif len(sel_line) == 1:
    equip = "خط %s" % sel_line[0]
else:
    equip = "همه تجهیزات"

_dates_in_show = sorted({d for d in show["تاریخ"] if d})
if not _dates_in_show:
    caption_dates = "بدون تاریخ"
elif len(_dates_in_show) == 1:
    caption_dates = _dates_in_show[0]
else:
    caption_dates = "%s تا %s (%d تاریخ)" % (_dates_in_show[0], _dates_in_show[-1], len(_dates_in_show))

# ---------- اعلانیه‌ها ----------
critical = show[show["وضعیت"].astype(str).str.contains("بحرانی")] if len(show) else show
warning = show[show["وضعیت"].astype(str).str.contains("هشدار")] if len(show) else show
n_alerts = len(critical) + len(warning)

s1, s2, s3, s4 = st.columns(4)
s1.metric("ردیف‌های نمایش‌داده‌شده", f"{len(show):,}")
s2.metric("تعداد تاریخ‌ها", f"{len(_dates_in_show)}")
s3.metric("🔴 بحرانی", f"{len(critical)}")
s4.metric("🟡 هشدار", f"{len(warning)}")

with st.expander(f"🔔 اعلانیه‌ها — {n_alerts} مورد", expanded=False):
    if n_alerts == 0:
        st.success("✅ هیچ اعلانیه‌ای وجود ندارد.")
    else:
        alert_cols = [c for c in ["تاریخ", "خط تولید", "واحد", "تجهیز", "نقطه",
                                  "شرح نقطه", "شماره بیرینگ", "حداکثر", "وضعیت"]
                      if c in show.columns]
        if len(critical):
            st.markdown("### 🔴 بحرانی — %d مورد" % len(critical))
            st.dataframe(critical[alert_cols], use_container_width=True, hide_index=True)
        if len(warning):
            st.markdown("### 🟡 هشدار — %d مورد" % len(warning))
            st.dataframe(warning[alert_cols], use_container_width=True, hide_index=True)

# ============================================================
# ۱۰) تب‌ها
# ============================================================
tab_table, tab_chart, tab_alert, tab_users = st.tabs(
    ["📋 جدول داده‌ها", "📈 نمودارها", "📧 ارسال اعلان", "👥 کاربران"]
)

# ---------------- جدول ----------------
with tab_table:
    st.subheader("داده‌های ارتعاش — %s" % equip)
    st.caption("بازه: %s" % caption_dates)

    f1, f2 = st.columns([1, 1])
    with f1:
        only_crit = st.checkbox("فقط ردیف‌های بحرانی و هشدار", value=False)
    with f2:
        pick_point = st.multiselect("نقطه", options_from(show["نقطه"]) if "نقطه" in show else [])

    tbl = show.copy()
    if only_crit:
        tbl = tbl[tbl["وضعیت"].astype(str).str.contains("بحرانی|هشدار")]
    if pick_point:
        tbl = tbl[tbl["نقطه"].isin(pick_point)]

    if tbl.empty:
        st.info("ردیفی برای نمایش نیست.")
    else:
        st.dataframe(style_table(tbl[VIEW_COLS]), use_container_width=True, hide_index=True)

    dc1, dc2 = st.columns(2)
    with dc1:
        csv = tbl[VIEW_COLS].to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ دانلود CSV", data=csv,
                           file_name="vibration_%s.csv" % safe_name(equip),
                           mime="text/csv", use_container_width=True)
    with dc2:
        html_report = build_report_html(tbl, equip, caption_dates)
        st.download_button("🖨️ دانلود گزارش HTML (قابل چاپ)",
                           data=html_report.encode("utf-8"),
                           file_name="report_%s.html" % safe_name(equip),
                           mime="text/html", use_container_width=True)

# ---------------- نمودار ----------------
with tab_chart:
    st.subheader("روند ارتعاش")
    if show.empty:
        st.info("داده‌ای برای نمودار نیست.")
    else:
        g = show.copy()
        g["_label_date"] = g["تاریخ"]

        st.markdown("**بیشترین مقدار هر جهت در هر تاریخ**")
        trend = g.groupby("_label_date")[["افقی", "عمودی", "محوری"]].max().sort_index()
        st.line_chart(trend)

        st.markdown("**میانگین/بیشترین ارتعاش هر نقطه**")
        by_point = g.groupby("نقطه")["حداکثر"].max().dropna().sort_values(ascending=False)
        if not by_point.empty:
            by_point.index = [str(c) + " - " + point_label(c) for c in by_point.index]
            st.bar_chart(by_point)

        st.markdown("**سهم وضعیت‌ها**")
        stt = g["وضعیت"].astype(str)
        for ic in ("🔴 ", "🟡 ", "🟢 ", "⚪ "):
            stt = stt.str.replace(ic, "", regex=False)
        st.bar_chart(stt.value_counts())

        if g["دما"].notna().any():
            st.markdown("**روند دما**")
            temp = g.groupby("_label_date")["دما"].max().sort_index()
            st.line_chart(temp)
        else:
            st.caption("ستون دما خالی است، بنابراین نمودار دما نمایش داده نمی‌شود.")

# ---------------- اعلان ----------------
with tab_alert:
    st.subheader("پیش‌نویس اعلان")
    crit_rows = show[show["وضعیت"].astype(str).str.contains("بحرانی|هشدار")] if len(show) else show

    if crit_rows.empty:
        st.success("در بازه انتخاب‌شده ردیف بحرانی یا هشدار وجود ندارد.")
    else:
        lines = ["گزارش پایش ارتعاشات — %s" % equip, "بازه: %s" % caption_dates, ""]
        for _, r in crit_rows.iterrows():
            lines.append(
                "%s | %s %s | نقطه %s | بیرینگ %s | افقی %s / عمودی %s / محوری %s | %s"
                % (
                    r.get("تاریخ", ""),
                    r.get("خط تولید", ""),
                    r.get("تجهیز", ""),
                    r.get("نقطه", ""),
                    r.get("شماره بیرینگ", "") or "—",
                    "%.1f" % r["افقی"] if pd.notna(r.get("افقی")) else "—",
                    "%.1f" % r["عمودی"] if pd.notna(r.get("عمودی")) else "—",
                    "%.1f" % r["محوری"] if pd.notna(r.get("محوری")) else "—",
                    r.get("وضعیت", ""),
                )
            )
        draft = "\n".join(lines)
        edited = st.text_area("متن آماده ارسال (قابل ویرایش)", draft, height=260)

        users = st.session_state["users"]
        email_map = {("%s — %s" % (v.get("name") or k, v.get("email", ""))): v.get("email", "")
                     for k, v in users.items() if v.get("email")}

        picked = st.multiselect("گیرندگان از میان کاربران", list(email_map.keys()),
                                default=[k for k in email_map if "manager" in k.lower()][:1])
        extra = st.text_input("گیرندگان دلخواه (با کاما جدا کن)", value="")

        to_list = [email_map[k] for k in picked if email_map.get(k)]
        for part in re.split(r"[,;\s]+", extra):
            if "@" in part:
                to_list.append(part.strip())
        to_list = list(dict.fromkeys(to_list))

        subject = "هشدار ارتعاش — %s — %s" % (equip, caption_dates)
        st.caption("گیرندگان: %s" % (", ".join(to_list) if to_list else "تعیین نشده"))

        b1, b2 = st.columns(2)
        with b1:
            if st.button("📤 ارسال ایمیل", use_container_width=True):
                if not to_list:
                    st.error("حداقل یک گیرنده انتخاب کن.")
                else:
                    ok, msg = send_email_smtp(to_list, subject, edited)
                    (st.success if ok else st.warning)(msg)
        with b2:
            import urllib.parse as up
            mailto = "mailto:%s?subject=%s&body=%s" % (
                ",".join(to_list), up.quote(subject), up.quote(edited)
            )
            st.markdown("[📨 باز کردن برنامه ایمیل](%s)" % mailto)

        if st.button("ثبت در تاریخچه"):
            st.session_state["alert_history"].append({
                "زمان": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "تجهیز": equip,
                "تعداد ردیف": len(crit_rows),
                "گیرندگان": len(to_list),
            })
            st.success("در تاریخچه ثبت شد.")

        if st.session_state["alert_history"]:
            st.markdown("**تاریخچه اعلان‌ها**")
            st.dataframe(pd.DataFrame(st.session_state["alert_history"]),
                         use_container_width=True, hide_index=True)

# ---------------- کاربران ----------------
with tab_users:
    st.subheader("مدیریت کاربران")
    users = st.session_state["users"]

    if not st.session_state["is_owner"]:
        st.info("برای مشاهده و ویرایش کاربران، با حساب مالک وارد شو.")
        u = st.text_input("نام کاربری", value="admin")
        p = st.text_input("رمز", type="password")
        if st.button("ورود به بخش مدیریت"):
            rec = users.get(u.strip())
            if rec and p and p == rec.get("pass"):
                st.session_state["is_owner"] = True
                st.session_state["current_user"] = u.strip()
                st.rerun()
            else:
                st.error("نام کاربری یا رمز نادرست است.")
        st.caption("کاربر پیش‌فرض: admin — رمز پیش‌فرض: admin (بعد از ورود عوض کن)")
    else:
        st.success("دسترسی مالک سیستم فعال است.")
        rows = [{
            "کاربر": k,
            "نام": v.get("name", ""),
            "ایمیل": v.get("email", ""),
            "نقش": v.get("role", ""),
            "رمز": v.get("pass", ""),
        } for k, v in users.items()]
        base = pd.DataFrame(rows)
        edited_users = st.data_editor(base, use_container_width=True, hide_index=True,
                                      num_rows="dynamic",
                                      key="users_editor")
        if st.button("💾 ذخیره تغییرات کاربران"):
            new_users = {}
            for _, r in edited_users.iterrows():
                k = str(r.get("کاربر", "")).strip()
                if not k:
                    continue
                new_users[k] = {
                    "name": str(r.get("نام", "") or ""),
                    "email": str(r.get("ایمیل", "") or ""),
                    "role": str(r.get("نقش", "") or ""),
                    "pass": str(r.get("رمز", "") or "1234"),
                }
            if new_users:
                st.session_state["users"] = new_users
                st.success("تغییرات ذخیره شد.")
                st.rerun()
            else:
                st.error("حداقل یک کاربر لازم است.")

        st.divider()
        st.markdown("**تغییر رمز مالک**")
        old = st.text_input("رمز فعلی", type="password", key="old_pw")
        new = st.text_input("رمز جدید", type="password", key="new_pw")
        if st.button("تغییر رمز"):
            if old == st.session_state["users"].get("admin", {}).get("pass") and new:
                st.session_state["users"]["admin"]["pass"] = new
                st.success("رمز تغییر کرد.")
            else:
                st.error("رمز فعلی نادرست است یا رمز جدید خالی است.")

        if st.button("خروج از حالت مالک"):
            st.session_state["is_owner"] = False
            st.rerun()

st.divider()
st.caption(
    "حد هشدار %s و حد بحرانی %s میلی‌متر بر ثانیه. "
    "شرح نقاط از دیکشنری POINT_LABELS در ابتدای فایل قابل ویرایش است."
    % (WARN_LIMIT, CRIT_LIMIT)
)
