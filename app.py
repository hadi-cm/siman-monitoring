# -*- coding: utf-8 -*-
"""
=====================================================
ویژگی‌ها:
  • خواندن دو شیت «ارتعاشات» و «Assets» از همان فایل گوگل شیت
  • تشخیص هوشمند نام ستون‌ها (فاصله، نیم‌فاصله، ی/ك عربی، حروف بزرگ، غلط تایپی)
  • هیچ‌وقت KeyError نمی‌دهد؛ ستون پیدا نشود، خالی ساخته می‌شود
  • نمایش نقطه‌به‌نقطه (P1..P11) به جای تجمیع «حداکثر»
  • شماره بیرینگ از شیت Assets و در صورت نبود از خود شیت ارتعاشات
  • شرح فارسی نقاط در دیکشنری POINT_LABELS
  • فیلتر تاریخ بعد از انتخاب تجهیز: همه / بازه / تاریخ‌های خاص
  • نمودار، گزارش HTML قابل چاپ، CSV، پیش‌نویس اعلان و تب کاربران
"""

import io
import os
import re
import datetime as dt

import pandas as pd
import requests
import streamlit as st

# تنظیمات صفحه (این فقط برای تب بالای مرورگر است)
st.set_page_config(
    page_icon="📈",
    layout="wide"
)

# عنوان اصلی در وسط صفحه (این همان که بزرگ دیده می‌شود)
st.title("📈 سامانه هوشمند پایش وضعیت ـ سیمان تهران")

def _secret(key, default):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

SHEET_ID = str(_secret("SHEET_ID", "")).strip()
SHEET_VIB = "ارتعاشات"
SHEET_ASSETS = "Assets"
def _secret(key, default):
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

# ============================================================
# ابزارهای متنی و عددی
# ============================================================
FA_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"
)

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
    """تاریخ شمسی → (سال، ماه، روز). فقط ستون تاریخ اصلاح سال می‌شود."""
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


# ============================================================
# تطبیق ستون‌ها (ضد KeyError)
# ============================================================
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


# ============================================================
# خواندن شیت
# ============================================================
@st.cache_data(ttl=300, show_spinner="در حال خواندن شیت...")
def load_sheet(sheet_name):
    errors = []

    # ۱) سرویس اکانت
    try:
        import gspread
        from google.oauth2.service_account import Credentials

        creds_info = None
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
# ساخت داده تمیز
# ============================================================
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
        if given and any(k in given for k in ("بحرانی", "هشدار", "نرمال")):
            statuses.append(icon + " " + given)
        elif given:
            statuses.append(icon + " " + given)
        else:
            statuses.append(icon + " " + s)
    out["وضعیت"] = statuses

    # --- حذف ردیف‌های بی‌تاریخ ---
    out = out[out["_date_key"] > 0]
    out = out[out["تاریخ"].astype(str).str.strip() != ""]
    if out.empty:
        return pd.DataFrame()

    out["_ord"] = [point_order(c) for c in out["نقطه"]]
    out = out.sort_values(["_date_key", "_ord"], ascending=[False, True])
    return out


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


# ============================================================
# نمایش و گزارش
# ============================================================
def color_status(val):
    s = str(val)
    if "بحرانی" in s:
        return "color:#c62828;font-weight:700"
    if "هشدار" in s:
        return "color:#ef6c00;font-weight:700"
    if "نرمال" in s:
        return "color:#2e7d32;font-weight:700"
    return "color:#757575"


def style_table(df):
    try:
        sty = df.style.format({c: "{:.1f}" for c in NUM_COLS if c in df.columns}, na_rep="—")
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
<h1>گزارش پایش وضعیت ارتعاشات</h1>
<div class="meta">تجهیز: __EQUIP__ &nbsp;|&nbsp; بازه: __DATES__ &nbsp;|&nbsp; تاریخ گزارش: __NOW__</div>
<table><thead><tr>__HEAD__</tr></thead><tbody>__ROWS__</tbody></table>
<div class="legend">حد هشدار: ۴/۵ mm/s &nbsp;|&nbsp; حد بحرانی: ۷ mm/s</div>
</body></html>"""


def build_report_html(show, equip_title, caption_dates):
    head_cells = "".join("<th>%s</th>" % c for c in REPORT_COLS)
    rows = []
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
            cells.append("<td>%s</td>" % str(val))
        rows.append("<tr class='%s'>%s</tr>" % (cls, "".join(cells)))

    html = REPORT_TEMPLATE
    html = html.replace("__EQUIP__", str(equip_title))
    html = html.replace("__DATES__", str(caption_dates))
    html = html.replace("__NOW__", dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    html = html.replace("__HEAD__", head_cells)
    html = html.replace("__ROWS__", "".join(rows))
    return html


# ============================================================
# بارگذاری داده
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

assets = build_assets(asr_raw)
vib = build_vib(vib_raw, assets)

# ============================================================
# سربرگ
# ============================================================
c1, c2, c3 = st.columns([1, 3, 1])
with c1:
    if os.path.exists("my_logo.png"):
        st.image("my_logo.png", width=90)
with c3:
    if os.path.exists("client_logo.png"):
        st.image("client_logo.png", width=90)

st.caption("نمایش نقطه‌به‌نقطه، اتصال شماره بیرینگ از شیت Assets و گزارش قابل چاپ")

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

# ============================================================
# فیلترها
# ============================================================
st.sidebar.subheader("🔍 فیلترها")
dff = df.copy()
# فیلتر خط تولید
col_line = "خط تولید" if "خط تولید" in dff.columns else None
if col_line:
    lines = sorted(dff[col_line].dropna().astype(str).unique())
    sel_line = st.sidebar.multiselect("خط تولید", lines, placeholder="همه خطوط")
    if sel_line:
        dff = dff[dff[col_line].astype(str).isin(sel_line)]
# فیلتر واحد
col_unit = "واحد" if "واحد" in dff.columns else None
if col_unit:
    units = sorted(dff[col_unit].dropna().astype(str).unique())
    sel_unit = st.sidebar.multiselect("واحد", units, placeholder="همه واحدها")
    if sel_unit:
        dff = dff[dff[col_unit].astype(str).isin(sel_unit)]
# فیلتر تجهیز
col_eq = "عنوان تجهیز" if "عنوان تجهیز" in dff.columns else ("تجهیز" if "تجهیز" in dff.columns else None)
if col_eq:
    eqs = sorted(dff[col_eq].dropna().astype(str).unique())
    sel_eq = st.sidebar.multiselect("تجهیز", eqs, placeholder="همه تجهیزات")
    if sel_eq:
        dff = dff[dff[col_eq].astype(str).isin(sel_eq)]
# محاسبه وضعیت و اعلانیه‌ها
WARN_LIMIT = 4.5
CRIT_LIMIT = 7.1
num_cols = [c for c in dff.columns if c in ["افقی", "عمودی", "محوری"]]
for c in num_cols:
    dff[c] = pd.to_numeric(dff[c], errors="coerce")
if num_cols:
    dff["حداکثر"] = dff[num_cols].max(axis=1)
    dff["وضعیت"] = dff["حداکثر"].apply(
        lambda v: "🔴 بحرانی" if pd.notna(v) and v >= CRIT_LIMIT
        else ("🟡 هشدار" if pd.notna(v) and v >= WARN_LIMIT else "🟢 سالم")
    )
# نمایش اعلانیه‌ها در باکس بازشو
critical = dff[dff["وضعیت"] == "🔴 بحرانی"] if "وضعیت" in dff.columns else dff.iloc[0:0]
warning  = dff[dff["وضعیت"] == "🟡 هشدار"]  if "وضعیت" in dff.columns else dff.iloc[0:0]
n_alerts = len(critical) + len(warning)
with st.expander(f"🔔 اعلانیه‌ها — {n_alerts} مورد", expanded=False):
    if n_alerts == 0:
        st.success("✅ هیچ اعلانیه‌ای وجود ندارد.")
    else:
        show_cols = [c for c in ["تاریخ شمسی", "خط تولید", "واحد", "عنوان تجهیز", "حداکثر", "وضعیت"] if c in dff.columns]
        if len(critical):
            st.markdown(f"### 🔴 بحرانی — {len(critical)} مورد")
            st.dataframe(critical[show_cols], use_container_width=True, hide_index=True)
        if len(warning):
            st.markdown(f"### 🟡 هشدار — {len(warning)} مورد")
            st.dataframe(warning[show_cols], use_container_width=True, hide_index=True)
# نمایش جدول اصلی در بدنه صفحه
st.subheader("📊 جدول وضعیت")
st.dataframe(dff, use_container_width=True, hide_index=True)
# ============================================================
# تب‌ها
# ============================================================
tab_table, tab_chart, tab_alert, tab_users = st.tabs(
    ["📋 جدول داده‌ها", "📈 نمودارها", "📧 ارسال اعلان", "👥 کاربران"]
)

# ---------------- جدول ----------------
with tab_table:
    st.subheader("داده‌های ارتعاش — %s" % equip)
    st.caption("بازه: %s" % caption_dates)

    only_crit = st.checkbox("فقط ردیف‌های بحرانی و هشدار", value=False)
    tbl = show.copy()
    if only_crit:
        tbl = tbl[tbl["وضعیت"].astype(str).str.contains("بحرانی|هشدار")]

    if tbl.empty:
        st.info("ردیفی برای نمایش نیست.")
    else:
        st.dataframe(style_table(tbl[VIEW_COLS]), use_container_width=True, hide_index=True)

    dc1, dc2 = st.columns(2)
    with dc1:
        csv = tbl[VIEW_COLS].to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ دانلود CSV", data=csv, file_name="vibration_%s.csv" % equip,
                           mime="text/csv", use_container_width=True)
    with dc2:
        html_report = build_report_html(tbl, equip, caption_dates)
        st.download_button("🖨️ دانلود گزارش HTML (قابل چاپ)",
                           data=html_report.encode("utf-8"),
                           file_name="report_%s.html" % equip,
                           mime="text/html", use_container_width=True)

# ---------------- نمودار ----------------
with tab_chart:
    st.subheader("روند ارتعاش")
    if show.empty:
        st.info("داده‌ای برای نمودار نیست.")
    else:
        g = show.copy()
        g["_label_date"] = g["تاریخ"]
        trend = g.groupby("_label_date")[["افقی", "عمودی", "محوری"]].max().sort_index()
        st.markdown("**بیشترین مقدار هر جهت در هر تاریخ**")
        st.line_chart(trend)

        st.markdown("**میانگین ارتعاش هر نقطه (حداکثر سه جهت)**")
        by_point = (
            g.groupby("نقطه")["حداکثر"].max().dropna().sort_values(ascending=False)
        )
        if not by_point.empty:
            by_point.index = [c + " - " + point_label(c) for c in by_point.index]
            st.bar_chart(by_point)

        st.markdown("**سهم وضعیت‌ها**")
        stt = g["وضعیت"].astype(str).str.replace("🔴 ", "").str.replace("🟡 ", "")
        stt = stt.str.replace("🟢 ", "").str.replace("⚪ ", "")
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
    crit_rows = show[show["وضعیت"].astype(str).str.contains("بحرانی|هشدار")]
    if crit_rows.empty:
        st.success("در بازه انتخاب‌شده ردیف بحرانی یا هشدار وجود ندارد.")
    else:
        lines = ["گزارش پایش ارتعاشات — %s" % equip, "بازه: %s" % caption_dates, ""]
        for _, r in crit_rows.iterrows():
            lines.append(
                "%s | %s %s | %s | افقی %.1f / عمودی %.1f / محوری %.1f | %s"
                % (
                    r["تاریخ"], r["نقطه"], "(%s)" % r["شرح نقطه"] if r["شرح نقطه"] else "",
                    r["شماره بیرینگ"] or "بدون بیرینگ",
                    r["افقی"] if pd.notna(r["افقی"]) else 0.0,
                    r["عمودی"] if pd.notna(r["عمودی"]) else 0.0,
                    r["محوری"] if pd.notna(r["محوری"]) else 0.0,
                    r["وضعیت"],
                )
            )
        draft = "\n".join(lines)
        edited = st.text_area("متن آماده ارسال (قابل ویرایش)", draft, height=260)

        to_addr = st.text_input("گیرنده ایمیل", value=_secret("ALERT_EMAIL", ""))
        subject = "هشدار ارتعاش — %s — %s" % (equip, caption_dates)
        import urllib.parse as up
        mailto = "mailto:%s?subject=%s&body=%s" % (
            to_addr, up.quote(subject), up.quote(edited)
        )
        st.markdown("[📨 باز کردن برنامه ایمیل با متن آماده](%s)" % mailto)
        st.caption("روش جایگزین: متن را کپی کن و در ایمیل یا پیام‌رسان سازمانی بفرست.")

        if st.button("ثبت در تاریخچه"):
            st.session_state.setdefault("alert_history", []).append(
                {"time": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                 "equip": equip, "rows": len(crit_rows)}
            )
            st.success("در تاریخچه ثبت شد.")

        hist = st.session_state.get("alert_history", [])
        if hist:
            st.markdown("**تاریخچه اعلان‌ها**")
            st.dataframe(pd.DataFrame(hist), use_container_width=True, hide_index=True)

# ---------------- کاربران ----------------
with tab_users:
    st.subheader("مدیریت کاربران")
    st.session_state.setdefault("users", {"admin": "admin"})
    st.session_state.setdefault("is_owner", False)

    if not st.session_state["is_owner"]:
        pw = st.text_input("رمز مالک سیستم", type="password")
        if st.button("ورود به بخش مدیریت"):
            if pw and pw == st.session_state["users"].get("admin", "admin"):
                st.session_state["is_owner"] = True
                st.rerun()
            else:
                st.error("رمز نادرست است.")
        st.caption("نام کاربری پیش‌فرض: admin — رمز پیش‌فرض: admin (بعد از ورود عوض کن)")
    else:
        st.success("دسترسی مالک سیستم فعال است.")
        st.dataframe(
            pd.DataFrame(
                [{"کاربر": k, "رمز": "*" * len(v)} for k, v in st.session_state["users"].items()]
            ),
            use_container_width=True, hide_index=True,
        )
        with st.form("add_user"):
            nu = st.text_input("نام کاربر جدید")
            npw = st.text_input("رمز", type="password")
            if st.form_submit_button("افزودن / تغییر رمز"):
                if nu and npw:
                    st.session_state["users"][nu] = npw
                    st.success("ذخیره شد.")
                else:
                    st.error("نام و رمز را پر کن.")
        with st.form("change_pw"):
            old = st.text_input("رمز فعلی", type="password")
            new = st.text_input("رمز جدید", type="password")
            if st.form_submit_button("تغییر رمز مالک"):
                if old == st.session_state["users"].get("admin") and new:
                    st.session_state["users"]["admin"] = new
                    st.success("رمز تغییر کرد.")
                else:
                    st.error("رمز فعلی نادرست است.")
        if st.button("خروج از حالت مالک"):
            st.session_state["is_owner"] = False
            st.rerun()

st.divider()
st.caption(
    "حد هشدار ۴/۵ و حد بحرانی ۷ میلی‌متر بر ثانیه. "
    "شرح نقاط از دیکشنری POINT_LABELS در ابتدای فایل قابل ویرایش است."
)
