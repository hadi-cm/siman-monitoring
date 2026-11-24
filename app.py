# -*- coding: utf-8 -*-
# سامانه هوشمند پایش وضعیت ارتعاشات - سیمان تهران
# نسخه بدون هیچ سه‌کوتیشن (رفع خطای unterminated triple-quoted string)

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
# 0) تنظیمات صفحه
# ============================================================
st.set_page_config(
    page_title="سامانه هوشمند پایش وضعیت - سیمان تهران",
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
SHEET_ANN = _secret("SHEET_ANN", "اعلانیه ها")

WARN_LIMIT = 4.5
CRIT_LIMIT = 7.0
EMPTY_TOKENS = {"", "-", "—", "_", "na", "n/a", "null", "none", "nan", "بی‌داده"}

# ============================================================
# 1) قرارداد نقاط پایش
# ============================================================
FAN_COUPLING = {
    "P1": "انتهای موتور (NDE)",
    "P2": "سر موتور (DE)",
    "P3": "یاتاقان سمت کوپلینگ",
    "P4": "یاتاقان سمت آزاد",
}
FAN_PULLEY = {
    "P1": "انتهای موتور (NDE)",
    "P2": "سر موتور (DE - سمت پولی)",
    "P3": "یاتاقان فیکس فن (سمت پولی)",
    "P4": "یاتاقان آزاد فن (سمت پروانه)",
}
GEARBOX_4 = {
    "P1": "انتهای موتور",
    "P2": "سر موتور",
    "P3": "محور ورودی گیربکس (Input Shaft)",
    "P4": "محور خروجی گیربکس (Output Shaft)",
}
MOTOR_2 = {
    "P1": "انتهای موتور (NDE)",
    "P2": "سر موتور (DE)",
}
CRUSHER_6 = {
    "P1": "انتهای موتور",
    "P2": "سر موتور",
    "P3": "یاتاقان سمت فیکس پولی کوچک",
    "P4": "یاتاقان سمت آزاد پولی کوچک",
    "P5": "یاتاقان سمت فیکس روتور",
    "P6": "یاتاقان سمت آزاد روتور",
}
BLOWER_4 = {
    "P1": "انتهای موتور (NDE)",
    "P2": "سر موتور (DE)",
    "P3": "محور ورودی بلوئر",
    "P4": "انتهای بلوئر",
}
BLOWER_SPECIAL_6 = {
    "P1": "انتهای موتور (NDE)",
    "P2": "سر موتور (DE)",
    "P3": "محور ورودی گیربکس",
    "P4": "محور خروجی گیربکس",
    "P5": "محور ورودی",
    "P6": "انتهای بلوئر",
}
COMPRESSOR_4 = {
    "P1": "انتهای موتور (NDE)",
    "P2": "سر موتور (DE - سمت پولی)",
    "P3": "محور ورودی ایرند",
    "P4": "انتهای ایرند",
}
PUMP_4 = {
    "P1": "انتهای موتور (NDE)",
    "P2": "سر موتور (DE)",
    "P3": "محور ورودی پمپ",
    "P4": "انتهای پمپ",
}
GEARBOX_MILL_11 = {
    "P1": "انتهای موتور (NDE)",
    "P2": "سر موتور (DE)",
    "P3": "یاتاقان فیکس محور پینیون",
    "P4": "یاتاقان سمت آزاد پینیون",
    "P5": "یاتاقان سمت فیکس محور دوم",
    "P6": "یاتاقان سمت آزاد محور دوم",
    "P7": "یاتاقان سمت فیکس محور سوم",
    "P8": "یاتاقان سمت آزاد محور سوم",
    "P9": "یاتاقان بابیتی اول سمت گیربکس",
    "P10": "یاتاقان بابیتی وسط",
    "P11": "یاتاقان بابیتی نزدیک پینیون آسیاب",
}

EQUIPMENT_MAPPING = {
    "فن": {"کوپلینگی": FAN_COUPLING, "پولی": FAN_PULLEY, "default": FAN_COUPLING},
    "گیربکس": {"default": GEARBOX_4},
    "گیربکس آسیاب": {"default": GEARBOX_MILL_11},
    "گیربکس سمت کوه": {"default": GEARBOX_MILL_11},
    "گیربکس سمت شهر": {"default": GEARBOX_MILL_11},
    "موتور": {"default": MOTOR_2},
    "کراشر": {"default": CRUSHER_6},
    "بلوئر": {"default": BLOWER_4},
    "بلوور": {"default": BLOWER_4},
    "بلوئر خاص": {"default": BLOWER_SPECIAL_6},
    "بلوور خاص": {"default": BLOWER_SPECIAL_6},
    "کمپرسور": {"default": COMPRESSOR_4},
    "پمپ": {"default": PUMP_4},
}

VIEW_COLS = ["تاریخ", "خط تولید", "واحد", "تجهیز", "نقطه", "شرح نقطه",
             "شماره بیرینگ", "افقی", "عمودی", "محوری", "حداکثر", "وضعیت", "دما"]
REPORT_COLS = ["تاریخ", "خط تولید", "واحد", "تجهیز", "نقطه",
               "شماره بیرینگ", "افقی", "عمودی", "محوری", "حداکثر", "وضعیت"]
NUM_COLS = ["افقی", "عمودی", "محوری", "حداکثر", "دما"]

VIB_COLUMNS = {
    "date": ["تاریخ", "تاریخ شمسی", "date"],
    "line": ["خط تولید", "خط", "line"],
    "unit": ["واحد", "یونیت", "unit"],
    "equip": ["عنوان تجهیز", "تجهیز", "equipment", "equip", "ماشین"],
    "point": ["نقطه", "شماره نقطه", "point"],
    "point_desc": ["شرح نقطه", "شرح", "توضیح نقطه", "point desc"],
    "bearing": ["شماره بیرینگ", "بیرینگ", "bearing"],
    "h": ["افقی", "h", "horizontal"],
    "v": ["عمودی", "v", "vertical"],
    "a": ["محوری", "a", "axial"],
    "temp": ["دما", "دمای", "temperature", "temp"],
}

ASSET_COLUMNS = {
    "equip": ["نام تجهیز", "عنوان تجهیز", "تجهیز", "equipment", "equip"],
    "line": ["خط تولید", "خط"],
    "unit": ["واحد"],
    "type": ["نوع تجهیز", "نوع"],
    "point": ["راهنمایی نقاط", "نقطه", "شماره نقطه", "point"],
    "bearing": ["شماره بیرینگ", "بیرینگ", "bearing"],
    "bush": ["بوش", "بوشت", "bush"],
    "rpm": ["دور نامی", "دور", "rpm", "سرعت"],
    "driver": ["درایور", "درایو", "سیستم درایور", "driver"],
}

ANN_COLUMNS = {
    "title": ["عنوان", "تیتر", "title", "موضوع"],
    "text": ["متن", "شرح", "توضیحات", "text"],
    "type": ["نوع", "type"],
    "active": ["فعال", "active", "وضعیت فعال"],
}

# ============================================================
# 2) توابع کمکی
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
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            if pd.isna(value):
                return None
            return float(value)
        except Exception:
            return None
    s = fa2en(value).strip().replace(",", "").replace(" ", "").replace("٫", ".")
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
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def point_of(value):
    s = fa2en(value).strip()
    if s.lower() in EMPTY_TOKENS:
        return ""
    m = re.search(r"[pP]\s*[\.\-_]?\s*(\d{1,2})", s)
    if m:
        return "P%d" % int(m.group(1))
    m = re.search(r"(\d{1,2})", s)
    if m:
        return "P%d" % int(m.group(1))
    return s


def point_label(code):
    if not code:
        return ""
    code = str(code).upper()
    num = code[1:] if code.startswith("P") else code
    return "نقطه " + fa2en(num)


def point_order(code):
    m = re.search(r"(\d+)", str(code))
    if m:
        return int(m.group(1))
    return 999


def parse_date(value):
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
    if vals:
        return max(vals)
    return None


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


def _match_mapping_key(value):
    nv = norm(value)
    if not nv:
        return None
    for k in EQUIPMENT_MAPPING:
        if norm(k) == nv:
            return k
    for k in EQUIPMENT_MAPPING:
        nk = norm(k)
        if nk and (nk in nv or nv in nk):
            return k
    return None


def _driver_key(driver):
    n = norm(driver)
    if "کوپل" in n:
        return "کوپلینگی"
    if "پول" in n or "تسمه" in n:
        return "پولی"
    return "default"


def get_mapping(asset_type, driver):
    key = _match_mapping_key(asset_type)
    if not key:
        return {}
    block = EQUIPMENT_MAPPING.get(key, {})
    dkey = _driver_key(driver)
    if dkey in block:
        return block[dkey]
    if "default" in block:
        return block["default"]
    for v in block.values():
        if isinstance(v, dict):
            return v
    return {}


# ============================================================
# 3) تطبیق ستون‌ها
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
# 4) خواندن شیت
# ============================================================
@st.cache_data(ttl=300, show_spinner="در حال خواندن شیت...")
def load_sheet(sheet_name):
    errors = []
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
                raise ValueError("شیت خالی است")
            header = _dedupe(values[0])
            rows = []
            for r in values[1:]:
                r = list(r) + [""] * (len(header) - len(r))
                rows.append(r[: len(header)])
            return pd.DataFrame(rows, columns=header), ""
        raise ValueError("شناسه شیت تنظیم نشده")
    except Exception as exc:
        errors.append("gspread: %s" % exc)

    try:
        url = ("https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:csv&sheet=%s"
               % (SHEET_ID, requests.utils.quote(sheet_name)))
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
# 5) ساخت داده‌ها
# ============================================================
def build_assets(df):
    if df is None or df.empty:
        return {}, {}
    m = resolve_columns(df, ASSET_COLUMNS)
    if "equip" not in m:
        return {}, {}

    equip_s = list(col_or_blank(df, m, "equip"))
    point_s = list(col_or_blank(df, m, "point"))
    bearing_s = list(col_or_blank(df, m, "bearing"))
    bush_s = list(col_or_blank(df, m, "bush"))
    rpm_s = list(col_or_blank(df, m, "rpm"))
    type_s = list(col_or_blank(df, m, "type"))
    driver_s = list(col_or_blank(df, m, "driver"))
    line_s = list(col_or_blank(df, m, "line"))
    unit_s = list(col_or_blank(df, m, "unit"))

    pairs = {}
    meta = {}
    for equip, pt, brg, bush, rpm, typ, drv, line, unit in zip(
        equip_s, point_s, bearing_s, bush_s, rpm_s, type_s, driver_s, line_s, unit_s
    ):
        ekey = norm(equip)
        if not ekey:
            continue

        rec = meta.setdefault(ekey, {
            "equip": to_text(equip),
            "type": "",
            "driver": "",
            "rpm": "",
            "bush": "",
            "line": "",
            "unit": "",
            "bearings": [],
        })
        if not rec["type"] and to_text(typ):
            rec["type"] = to_text(typ)
        if not rec["driver"] and to_text(drv):
            rec["driver"] = to_text(drv)
        if not rec["rpm"] and to_text(rpm):
            rec["rpm"] = to_text(rpm)
        if not rec["bush"] and to_text(bush):
            rec["bush"] = to_text(bush)
        if not rec["line"] and to_text(line):
            rec["line"] = to_text(line)
        if not rec["unit"] and to_text(unit):
            rec["unit"] = to_text(unit)

        code = point_of(pt)
        if not code:
            continue
        if to_text(brg) and to_text(brg) not in rec["bearings"]:
            rec["bearings"].append(to_text(brg))

        pairs[(ekey, code)] = {
            "equip": to_text(equip),
            "bearing": to_text(brg),
            "bush": to_text(bush),
            "rpm": to_text(rpm),
            "type": to_text(typ),
            "driver": to_text(drv),
        }
    return pairs, meta


def lookup_asset(assets, equip, code):
    ekey = norm(equip)
    if not ekey or not code:
        return None
    return assets.get((ekey, code))


def build_vib(df, assets, asset_meta):
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
        rows.append({
            "_rowid": i,
            "تاریخ": fmt_date(dates[i]),
            "_ord": date_key(dates[i]),
            "خط تولید": line_s[i],
            "واحد": unit_s[i],
            "تجهیز": equip_s[i],
            "نقطه": pts[i],
            "شرح نقطه": descs[i],
            "_brg_sheet": brg_sheet[i],
            "افقی": h_s[i],
            "عمودی": v_s[i],
            "محوری": a_s[i],
            "دما": t_s[i],
        })

    raw = pd.DataFrame(rows)
    if raw.empty:
        return raw

    final_rows = []
    for (equip_name, date_str), group in raw.groupby(["تجهیز", "تاریخ"], sort=False):
        group = group.sort_values("_rowid")
        meta = asset_meta.get(norm(equip_name), {})
        contract = get_mapping(meta.get("type", ""), meta.get("driver", ""))

        pt_counter = 1
        for _, row in group.iterrows():
            pt = row["نقطه"]
            desc = row["شرح نقطه"]

            if not pt:
                pt = "P%d" % pt_counter
                desc = contract.get(pt, "")
                pt_counter += 1
            elif pt in contract:
                if not desc:
                    desc = contract[pt]

            info = lookup_asset(assets, equip_name, pt) or {}
            bearing_val = info.get("bearing") or row["_brg_sheet"]

            stt = status_of(row["افقی"], row["عمودی"], row["محوری"])
            final_rows.append({
                "تاریخ": row["تاریخ"],
                "_ord": row["_ord"],
                "خط تولید": row["خط تولید"],
                "واحد": row["واحد"],
                "تجهیز": row["تجهیز"],
                "نقطه": pt,
                "شرح نقطه": desc,
                "شماره بیرینگ": bearing_val,
                "افقی": row["افقی"],
                "عمودی": row["عمودی"],
                "محوری": row["محوری"],
                "حداکثر": row_max(row["افقی"], row["عمودی"], row["محوری"]),
                "وضعیت": "%s %s" % (STATUS_ICON.get(stt, "⚪"), stt),
                "دما": row["دما"],
            })

    out = pd.DataFrame(final_rows)
    if out.empty:
        return out

    keep = ~(
        (out["تجهیز"].astype(str).str.strip() == "")
        & (out["نقطه"].astype(str).str.strip() == "")
        & out[["افقی", "عمودی", "محوری"]].isna().all(axis=1)
    )
    out = out[keep].copy()
    out["_pord"] = out["نقطه"].map(point_order)
    out = out.sort_values(["_ord", "_pord"], ascending=[False, True],
                          kind="mergesort").reset_index(drop=True)
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
        sty = df.style.format({c: "{:.1f}" for c in NUM_COLS if c in df.columns}, na_rep="—")
        try:
            sty = sty.map(color_status, subset=["وضعیت"])
        except Exception:
            sty = sty.applymap(color_status, subset=["وضعیت"])
        return sty
    except Exception:
        return df


# ============================================================
# 6) گزارش HTML
# ============================================================
REPORT_CSS = (
    "body{font-family:Tahoma,Vazirmatn,sans-serif;background:#fff;color:#222;padding:24px}"
    "h1{font-size:20px;margin:0 0 6px}"
    ".meta{font-size:12px;color:#555;margin-bottom:16px}"
    "table{border-collapse:collapse;width:100%;font-size:12px}"
    "th{background:#263238;color:#fff;padding:7px 5px;border:1px solid #37474f}"
    "td{padding:6px 5px;border:1px solid #cfd8dc;text-align:center}"
    "tr.crit td{background:#ffebee}"
    "tr.warn td{background:#fff8e1}"
    "tr.ok td{background:#f1f8e9}"
    ".legend{margin-top:14px;font-size:12px;color:#455a64}"
)


def build_report_html(show, equip_title, caption_dates):
    head_cells = "".join("<th>" + html.escape(c) + "</th>" for c in REPORT_COLS)

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
            if val is None:
                val = "—"
            elif isinstance(val, float):
                if pd.isna(val):
                    val = "—"
                else:
                    val = "%.1f" % val
            cells.append("<td>" + html.escape(str(val)) + "</td>")
        rows_out.append("<tr class='" + cls + "'>" + "".join(cells) + "</tr>")

    parts = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="fa" dir="rtl"><head><meta charset="utf-8">')
    parts.append("<title>گزارش پایش ارتعاشات</title>")
    parts.append("<style>" + REPORT_CSS + "</style>")
    parts.append("</head><body>")
    parts.append("<h1>گزارش پایش وضعیت ارتعاشات</h1>")
    parts.append('<div class="meta">تجهیز: ' + html.escape(str(equip_title))
                 + " &nbsp;|&nbsp; بازه: " + html.escape(str(caption_dates))
                 + " &nbsp;|&nbsp; تاریخ گزارش: "
                 + dt.datetime.now().strftime("%Y-%m-%d %H:%M") + "</div>")
    parts.append("<table><thead><tr>" + head_cells + "</tr></thead><tbody>")
    parts.append("".join(rows_out))
    parts.append("</tbody></table>")
    parts.append('<div class="legend">حد هشدار: ' + str(WARN_LIMIT)
                 + " mm/s &nbsp;|&nbsp; حد بحرانی: " + str(CRIT_LIMIT) + " mm/s</div>")
    parts.append("</body></html>")
    return "".join(parts)


# ============================================================
# 7) کاربران و ایمیل
# ============================================================
USER_DATABASE = {
    "cm.zandiyeh@gmail.com": {"name": "هادی زندیه", "role": "پیمانکار / مالک سیستم", "pass": "1234"},
    "vah.rezaei@gmail.com": {"name": "وحید رضایی", "role": "مدیر مکانیک", "pass": "1234"},
    "me.vibration.shokri@gmail.com": {"name": "جلال شکری", "role": "مدیر دفتر فنی", "pass": "1234"},
    "tehrancment@gmail.com": {"name": "سید مهدی حسینی", "role": "معاونت فنی", "pass": "1234"},
    "alireza76ir@gmail.com": {"name": "علیرضا ناظمی", "role": "رئیس", "pass": "1234"},
    "masoud.sa.1989823@gmail.com": {"name": "مسعود صمیمی", "role": "کارشناس", "pass": "1234"},
    "freedocs.ir@gmail.com": {"name": "ناصر محسنی", "role": "مدیر", "pass": "1234"},
    "m.babahasan@gmail.com": {"name": "محسن بابا حسن", "role": "کارشناس", "pass": "1234"},
}


def init_users():
    if "users" not in st.session_state:
        st.session_state["users"] = {k: dict(v) for k, v in USER_DATABASE.items()}
    st.session_state.setdefault("is_owner", False)
    st.session_state.setdefault("current_user", None)


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
# 8) سربرگ
# ============================================================
h_left, h_mid, h_right = st.columns([1, 4, 1], gap="small")

with h_left:
    if os.path.exists("my_logo.png"):
        st.image("my_logo.png", width=150)
    else:
        st.caption("🏢")

with h_mid:
    st.markdown(
        "<div dir='rtl' style='text-align:center;'>"
        "<div style='font-size:26px;font-weight:800;line-height:1.7;margin-top:6px;'>"
        "سامانه هوشمند پایش وضعیت — سیمان تهران"
        "</div>"
        "<div style='font-size:13px;color:#607d8b;margin-top:2px;'>"
        "پایش نقطه‌به‌نقطه ارتعاشات، اتصال شماره بیرینگ از شیت Assets و گزارش قابل چاپ"
        "</div></div>",
        unsafe_allow_html=True,
    )

with h_right:
    if os.path.exists("client_logo.png"):
        st.image("client_logo.png", width=150)
    else:
        st.caption("🏭")

st.divider()

# ============================================================
# 9) بارگذاری داده
# ============================================================
if not SHEET_ID:
    st.error("شناسه شیت (SHEET_ID) تنظیم نشده است.")
    st.stop()

vib_raw, vib_err = load_sheet(SHEET_VIB)
asr_raw, asr_err = load_sheet(SHEET_ASSETS)
ann_raw, ann_err = load_sheet(SHEET_ANN)

if vib_raw.empty:
    st.error("داده‌ای برای ارتعاشات پیدا نشد.")
    st.code(vib_err or "بدون پیام", language="text")
    st.stop()

assets, asset_meta = build_assets(asr_raw)
vib = build_vib(vib_raw, assets, asset_meta)

if vib.empty:
    st.error("پس از پردازش، ردیف معتبری باقی نماند.")
    st.stop()

df = vib.copy()

# ============================================================
# 10) فیلترها
# ============================================================
st.sidebar.subheader("🔍 فیلترها")


def options_from(series):
    vals = []
    for v in series:
        s = clean_label(v)
        if s and s not in vals:
            vals.append(s)
    return sorted(vals, key=natural_key)


_raw_map = resolve_columns(vib_raw, VIB_COLUMNS)
raw_line = col_or_blank(vib_raw, _raw_map, "line")
line_opts = options_from(list(raw_line) + list(df["خط تولید"]))
if line_opts:
    sel_line = st.sidebar.multiselect("خط تولید", line_opts, placeholder="همه خطوط")
    if sel_line:
        df = df[df["خط تولید"].isin(sel_line)]
else:
    sel_line = []

unit_opts = options_from(df["واحد"])
if unit_opts:
    sel_unit = st.sidebar.multiselect("واحد", unit_opts, placeholder="همه واحدها")
    if sel_unit:
        df = df[df["واحد"].isin(sel_unit)]
else:
    sel_unit = []

eq_opts = options_from(df["تجهیز"])
if eq_opts:
    sel_eq = st.sidebar.multiselect("تجهیز", eq_opts, placeholder="همه تجهیزات")
    if sel_eq:
        df = df[df["تجهیز"].isin(sel_eq)]
else:
    sel_eq = []

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
        df.sort_values(["_ord", "_pord"], ascending=[False, True], kind="mergesort")
          .drop_duplicates(subset=["تجهیز", "نقطه"], keep="first")
    )

df = df.sort_values(["_ord", "_pord"], ascending=[False, True],
                    kind="mergesort").reset_index(drop=True)
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
    caption_dates = "%s تا %s (%d تاریخ)" % (_dates_in_show[-1], _dates_in_show[0], len(_dates_in_show))

critical = show[show["وضعیت"].astype(str).str.contains("بحرانی")] if len(show) else show
warning = show[show["وضعیت"].astype(str).str.contains("هشدار")] if len(show) else show

s1, s2, s3, s4 = st.columns(4)
s1.metric("ردیف‌های نمایش‌داده‌شده", "{:,}".format(len(show)))
s2.metric("تعداد تاریخ‌ها", "{}".format(len(_dates_in_show)))
s3.metric("🔴 بحرانی", "{}".format(len(critical)))
s4.metric("🟡 هشدار", "{}".format(len(warning)))

# ============================================================
# 10-ب) کارت مشخصات تجهیز
# ============================================================
if len(sel_eq) == 1:
    eq_key = norm(sel_eq[0])
    meta = asset_meta.get(eq_key, {})
    mapping = get_mapping(meta.get("type", ""), meta.get("driver", ""))

    with st.container(border=True):
        st.markdown("### 🛠 مشخصات تجهیز: " + sel_eq[0])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("نوع تجهیز", meta.get("type") or "—")
        c2.metric("درایور", meta.get("driver") or "—")
        c3.metric("دور نامی (RPM)", meta.get("rpm") or "—")
        c4.metric("بوش", meta.get("bush") or "—")

        if meta.get("bearings"):
            st.caption("شماره بیرینگ‌های ثبت‌شده: " + " • ".join(meta["bearings"]))

        st.markdown("#### 📍 راهنمای نقاط پایش")
        if mapping:
            guide_df = pd.DataFrame(
                [{"نقطه": k, "شرح نقطه": v}
                 for k, v in sorted(mapping.items(), key=lambda kv: point_order(kv[0]))]
            )
            st.dataframe(guide_df, use_container_width=True, hide_index=True)
        else:
            st.info("برای این تجهیز، «نوع تجهیز» یا «درایور» در شیت Assets تطبیق داده نشد؛ شرح نقاط از شیت ارتعاشات خوانده می‌شود.")
elif len(sel_eq) > 1:
    st.caption("برای دیدن کارت مشخصات و راهنمای نقاط، فقط یک تجهیز را انتخاب کن.")

# ============================================================
# 11) اعلانیه‌ها
# ============================================================
with st.expander("🔔 اعلانیه‌ها و اطلاعیه‌ها", expanded=False):
    if ann_raw is None or ann_raw.empty:
        st.info("شیت اعلانیه‌ها خالی است یا یافت نشد.")
        if ann_err:
            st.caption(ann_err)
    else:
        m_ann = resolve_columns(ann_raw, ANN_COLUMNS)

        if "title" not in m_ann and "text" not in m_ann:
            st.error("ستون‌های «عنوان» و «متن» در شیت اعلانیه‌ها پیدا نشد.")
            st.caption("ستون‌های موجود در شیت: " + " | ".join(str(c) for c in ann_raw.columns))
        else:
            titles = col_or_blank(ann_raw, m_ann, "title")
            texts = col_or_blank(ann_raw, m_ann, "text")
            types = col_or_blank(ann_raw, m_ann, "type")
            actives = col_or_blank(ann_raw, m_ann, "active")

            YES_TOKENS = {"بله", "yes", "true", "1", "فعال", "on", "y", "✓", "✔"}
            found_any = False

            for i in range(len(ann_raw)):
                is_act = True
                if "active" in m_ann:
                    act_val = str(actives[i]).strip().lower()
                    if act_val and act_val not in YES_TOKENS:
                        is_act = False

                if not is_act:
                    continue

                t_title = to_text(titles[i])
                t_text = to_text(texts[i])
                t_type = to_text(types[i])

                if not t_title and not t_text:
                    continue

                found_any = True
                head = "**" + t_title + "**" if t_title else "**اعلانیه**"
                body = head + ("\n\n" + t_text if t_text else "")

                if ("خطر" in t_type) or ("بحرانی" in t_type) or ("critical" in t_type.lower()):
                    st.error(body)
                else:
                    st.warning(body)

            if not found_any:
                st.info("هیچ اطلاعیه فعالی در شیت ثبت نشده است.")

# ============================================================
# 12) تب‌ها
# ============================================================
tab_table, tab_chart, tab_alert, tab_users = st.tabs(
    ["📋 جدول داده‌ها", "📈 نمودارها", "📧 ارسال اعلان", "👥 کاربران"]
)

with tab_table:
    st.subheader("داده‌های ارتعاش — " + equip)
    st.caption("بازه: " + caption_dates)

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
        st.download_button(
            "⬇️ دانلود CSV",
            data=csv,
            file_name="vibration_" + safe_name(equip) + ".csv",
            mime="text/csv",
            use_container_width=True,
        )
    with dc2:
        html_report = build_report_html(tbl, equip, caption_dates)
        st.download_button(
            "🖨️ دانلود گزارش HTML (قابل چاپ)",
            data=html_report.encode("utf-8"),
            file_name="report_" + safe_name(equip) + ".html",
            mime="text/html",
            use_container_width=True,
        )

with tab_chart:
    st.subheader("روند ارتعاش")
    if show.empty:
        st.info("داده‌ای برای نمودار نیست.")
    else:
        g = show.copy()
        g["_label_date"] = g["تاریخ"]

        st.markdown("**بیشترین مقدار هر جهت در هر تاریخ**")
        trend = g.groupby("_label_date")[["افقی", "عمودی", "محوری"]].max().sort_index(ascending=False)
        st.line_chart(trend)

        st.markdown("**بیشترین ارتعاش هر نقطه**")
        by_point = g.groupby("نقطه")["حداکثر"].max().dropna().sort_values(ascending=False)
        if not by_point.empty:
            by_point.index = [str(c) + " - " + point_label(c) for c in by_point.index]
            st.bar_chart(by_point)

        if g["دما"].notna().any():
            st.markdown("**روند دما**")
            temp = g.groupby("_label_date")["دما"].max().sort_index(ascending=False)
            st.line_chart(temp)

with tab_alert:
    st.subheader("پیش‌نویس اعلان")
    crit_rows = show[show["وضعیت"].astype(str).str.contains("بحرانی|هشدار")] if len(show) else show

    if crit_rows.empty:
        st.success("در بازه انتخاب‌شده ردیف بحرانی یا هشدار وجود ندارد.")
    else:
        lines = ["گزارش پایش ارتعاشات — " + equip, "بازه: " + caption_dates, ""]
        for _, r in crit_rows.iterrows():
            hv = r.get("افقی")
            vv = r.get("عمودی")
            av = r.get("محوری")
            lines.append(
                "%s | %s %s | نقطه %s - %s | بیرینگ %s | افقی %s / عمودی %s / محوری %s | %s" % (
                    r.get("تاریخ", ""),
                    r.get("خط تولید", ""),
                    r.get("تجهیز", ""),
                    r.get("نقطه", ""),
                    r.get("شرح نقطه", ""),
                    r.get("شماره بیرینگ", "") or "—",
                    ("%.1f" % hv) if pd.notna(hv) else "—",
                    ("%.1f" % vv) if pd.notna(vv) else "—",
                    ("%.1f" % av) if pd.notna(av) else "—",
                    r.get("وضعیت", ""),
                )
            )
        draft = "\n".join(lines)
        edited = st.text_area("متن آماده ارسال (قابل ویرایش)", draft, height=260)

        users = st.session_state["users"]
        email_map = {}
        for k, v in users.items():
            label = (v.get("name") or k) + " — " + k
            email_map[label] = k

        picked = st.multiselect("گیرندگان از میان کاربران", list(email_map.keys()))
        extra = st.text_input("گیرندگان دلخواه (با کاما جدا کن)", value="")

        to_list = [email_map[k] for k in picked if email_map.get(k)]
        for part in re.split(r"[,;\s]+", extra):
            if "@" in part:
                to_list.append(part.strip())
        to_list = list(dict.fromkeys(to_list))

        subject = "هشدار ارتعاش — " + equip + " — " + caption_dates

        b1, b2 = st.columns(2)
        with b1:
            if st.button("📤 ارسال ایمیل", use_container_width=True):
                if not to_list:
                    st.error("حداقل یک گیرنده انتخاب کن.")
                else:
                    ok, msg = send_email_smtp(to_list, subject, edited)
                    if ok:
                        st.success(msg)
                    else:
                        st.warning(msg)
        with b2:
            import urllib.parse as up
            mailto = "mailto:" + ",".join(to_list)
            mailto += "?subject=" + up.quote(subject)
            mailto += "&body=" + up.quote(edited)
            st.markdown("[📨 باز کردن برنامه ایمیل](" + mailto + ")")

with tab_users:
    st.subheader("ورود به مدیریت کاربران")
    users = st.session_state["users"]

    if not st.session_state["is_owner"]:
        u_email = st.text_input("ایمیل کاربر", placeholder="example@gmail.com")
        p_pass = st.text_input("رمز عبور", type="password")
        if st.button("ورود"):
            key = u_email.strip().lower()
            rec = users.get(key)
            if rec and p_pass and p_pass == rec.get("pass"):
                st.session_state["is_owner"] = True
                st.session_state["current_user"] = key
                st.rerun()
            else:
                st.error("ایمیل یا رمز عبور نادرست است.")
    else:
        curr = st.session_state["current_user"]
        cur_name = users.get(curr, {}).get("name", curr)
        st.success("خوش آمدید، " + str(cur_name))

        if st.button("خروج"):
            st.session_state["is_owner"] = False
            st.session_state["current_user"] = None
            st.rerun()

        urows = [{"ایمیل": k, "نام": v.get("name", ""), "نقش": v.get("role", "")}
                 for k, v in users.items()]
        st.dataframe(pd.DataFrame(urows), use_container_width=True, hide_index=True)
