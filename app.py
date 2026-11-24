# -*- coding: utf-8 -*-
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

try:
    import altair as alt
except Exception:
    alt = None

# ============================================================
# 0) تنظیمات صفحه
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
SHEET_ANN = _secret("SHEET_ANN", "اعلانیه ها")

WARN_LIMIT = 4.5   # mm/s
CRIT_LIMIT = 7.0   # mm/s

EMPTY_TOKENS = {"", "-", "—", "_", "na", "n/a", "null", "none", "nan", "بی‌داده"}

# ============================================================
# 1) قرارداد نقاط پایش
# ============================================================
FAN_COUPLING = {"P1": "انتهای موتور (NDE)", "P2": "سر موتور (DE)", "P3": "یاتاقان سمت کوپلینگ", "P4": "یاتاقان سمت آزاد"}
FAN_PULLEY = {"P1": "انتهای موتور (NDE)", "P2": "سر موتور (DE - سمت پولی)", "P3": "یاتاقان فیکس فن (سمت پولی)", "P4": "یاتاقان آزاد فن (سمت پروانه)"}
GEARBOX_4 = {"P1": "انتهای موتور", "P2": "سر موتور", "P3": "محور ورودی گیربکس (Input Shaft)", "P4": "محور خروجی گیربکس (Output Shaft)"}
MOTOR_2 = {"P1": "انتهای موتور (NDE)", "P2": "سر موتور (DE)"}
CRUSHER_6 = {"P1": "انتهای موتور", "P2": "سر موتور", "P3": "یاتاقان سمت فیکس پولی کوچک", "P4": "یاتاقان سمت آزاد پولی کوچک", "P5": "یاتاقان سمت فیکس روتور", "P6": "یاتاقان سمت آزاد روتور"}
BLOWER_4 = {"P1": "انتهای موتور (NDE)", "P2": "سر موتور (DE)", "P3": "محور ورودی بلوئر", "P4": "انتهای بلوئر"}
BLOWER_SPECIAL_6 = {"P1": "انتهای موتور (NDE)", "P2": "سر موتور (DE)", "P3": "محور ورودی گیربکس", "P4": "محور خروجی گیربکس", "P5": "محور ورودی", "P6": "انتهای بلوئر"}
COMPRESSOR_4 = {"P1": "انتهای موتور (NDE)", "P2": "سر موتور (DE - سمت پولی)", "P3": "محور ورودی ایرند", "P4": "انتهای ایرند"}
PUMP_4 = {"P1": "انتهای موتور (NDE)", "P2": "سر موتور (DE)", "P3": "محور ورودی پمپ", "P4": "انتهای پمپ"}
GEARBOX_MILL_11 = {"P1": "انتهای موتور (NDE)", "P2": "سر موتور (DE)", "P3": "یاتاقان فیکس محور پینیون", "P4": "یاتاقان سمت آزاد پینیون", "P5": "یاتاقان سمت فیکس محور دوم", "P6": "یاتاقان سمت آزاد محور دوم", "P7": "یاتاقان سمت فیکس محور سوم", "P8": "یاتاقان سمت آزاد محور سوم", "P9": "یاتاقان بابیتی اول سمت گیربکس", "P10": "یاتاقان بابیتی وسط", "P11": "یاتاقان بابیتی نزدیک پینیون آسیاب"}

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

REPORT_COLS = ["تاریخ", "خط تولید", "واحد", "تجهیز", "نقطه", "شماره بیرینگ",
               "افقی", "عمودی", "محوری", "حداکثر", "وضعیت"]

NUM_COLS = ["افقی", "عمودی", "محوری", "حداکثر", "دما"]

VIB_COLUMNS = {
    "date": ["تاریخ", "تاریخ شمسی", "date"],
    "line": ["خط تولید", "خط", "line"],
    "unit": ["واحد", "یونیت", "unit"],
    "equip": ["عنوان تجهیز", "تجهیز", "equipment", "equip", "ماشین"],
    "point": ["نقطه", "شماره نقطه", "point"],
    "point_desc": ["شرح نقطه", "شرح", "توضیح نقطه"],
    "bearing": ["شماره بیرینگ", "بیرینگ", "bearing"],
    "h": ["افقی", "horizontal"],
    "v": ["عمودی", "vertical"],
    "a": ["محوری", "axial"],
    "temp": ["دما", "دمای", "temperature"],
}

ASSET_COLUMNS = {
    "equip": ["نام تجهیز", "عنوان تجهیز", "تجهیز", "equipment"],
    "line": ["خط تولید", "خط"],
    "unit": ["واحد"],
    "type": ["نوع تجهیز", "نوع"],
    "point": ["راهنمایی نقاط", "نقطه", "شماره نقطه"],
    "bearing": ["شماره بیرینگ", "بیرینگ"],
    "bush": ["بوش", "بوشت"],
    "rpm": ["دور نامی", "دور", "سرعت"],
    "driver": ["درایور", "درایو", "سیستم درایور"],
}

ANN_COLUMNS = {
    "title": ["عنوان", "تیتر"],
    "text": ["متن", "شرح", "توضیحات"],
    "type": ["نوع"],
    "active": ["فعال", "وضعیت فعال"],
}

ACTIVE_TOKENS = {"بله", "yes", "true", "1", "✓", "فعال", "y", "x", "on", "دارد"}

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
        except Exception:
            pass
        return float(value)
    s = fa2en(value).strip().replace("،", "").replace(",", "").replace(" ", "").replace("٫", ".")
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


def options_from(series):
    vals = []
    for v in series:
        s = clean_label(v)
        if s and s not in vals:
            vals.append(s)
    return sorted(vals, key=natural_key)


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
    return ""


def point_label(code):
    if not code:
        return ""
    code = str(code).upper()
    num = code[1:] if code.startswith("P") else code
    return "نقطه " + fa2en(num)


def point_order(code):
    m = re.search(r"(\d+)", str(code))
    return int(m.group(1)) if m else 999


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
STATUS_COLOR = {"بحرانی": "#c62828", "هشدار": "#ef6c00", "نرمال": "#2e7d32", "بی‌داده": "#9e9e9e"}


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


def get_mapping(asset_type, driver):
    key = _match_mapping_key(asset_type)
    if not key:
        return {}
    block = EQUIPMENT_MAPPING.get(key, {})
    nd = norm(driver)
    if "کوپل" in nd:
        dkey = "کوپلینگی"
    elif "پول" in nd or "تسمه" in nd:
        dkey = "پولی"
    else:
        dkey = "default"
    if dkey in block:
        return block[dkey]
    if "default" in block:
        return block["default"]
    for val in block.values():
        if isinstance(val, dict):
            return val
    return {}


# ============================================================
# 3) تطبیق ستون‌ها و خواندن شیت
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
# 4) ساخت داده‌ها
# ============================================================
def build_assets(df):
    if df is None or df.empty:
        return {}, {}
    m = resolve_columns(df, ASSET_COLUMNS)
    if "equip" not in m:
        return {}, {}

    pairs = {}
    meta = {}
    for _, r in df.iterrows():
        equip = clean_label(r.get(m.get("equip", "")))
        if not equip:
            continue
        ekey = norm(equip)
        rec = meta.setdefault(ekey, {
            "equip": equip, "type": "", "driver": "", "rpm": "",
            "bush": "", "line": "", "unit": "", "bearings": [],
        })
        for field in ["type", "driver", "rpm", "bush", "line", "unit"]:
            if field in m and not rec.get(field):
                val = str(r.get(m[field], "")).strip()
                if val and val.lower() not in EMPTY_TOKENS:
                    rec[field] = val

        code = point_of(r.get(m.get("point", "")))
        brg = str(r.get(m.get("bearing", ""), "")).strip()
        if brg and brg.lower() not in EMPTY_TOKENS and brg not in rec["bearings"]:
            rec["bearings"].append(brg)
        if code:
            pairs[(ekey, code)] = {"bearing": brg, "type": rec.get("type", ""), "driver": rec.get("driver", "")}
    return pairs, meta


def build_vib(df, assets, asset_meta):
    if df is None or df.empty:
        return pd.DataFrame()

    m = resolve_columns(df, VIB_COLUMNS)
    rows = []
    for _, r in df.iterrows():
        equip = clean_label(r.get(m.get("equip", "")))
        if not equip:
            continue
        rows.append({
            "خط تولید": clean_label(r.get(m.get("line", ""))),
            "واحد": clean_label(r.get(m.get("unit", ""))),
            "تجهیز": equip,
            "نقطه": point_of(r.get(m.get("point", ""))),
            "تاریخ": fmt_date(parse_date(r.get(m.get("date", "")))),
            "_ord": date_key(parse_date(r.get(m.get("date", "")))),
            "افقی": to_num(r.get(m.get("h", ""))),
            "عمودی": to_num(r.get(m.get("v", ""))),
            "محوری": to_num(r.get(m.get("a", ""))),
            "دما": to_num(r.get(m.get("temp", ""))),
            "_brg": str(r.get(m.get("bearing", ""), "")).strip(),
            "_desc": str(r.get(m.get("point_desc", ""), "")).strip(),
            "_rid": len(rows),
        })

    if not rows:
        return pd.DataFrame()

    raw = pd.DataFrame(rows)
    final = []
    for (equip_name, date_str), group in raw.groupby(["تجهیز", "تاریخ"], sort=False):
        group = group.sort_values("_rid")
        meta = asset_meta.get(norm(equip_name), {})
        contract = get_mapping(meta.get("type", ""), meta.get("driver", ""))

        have_pts = group["نقطه"].astype(str).str.strip().ne("").sum()
        counter = 1 if have_pts == 0 else None

        for _, row in group.iterrows():
            pt = row["نقطه"]
            desc = row["_desc"]

            if not pt:
                pt = "P%d" % counter
                counter += 1
            if not desc:
                desc = contract.get(pt, "")
            if not desc:
                desc = point_label(pt)

            info = assets.get((norm(equip_name), pt), {})
            bearing = info.get("bearing") or row["_brg"]
            stt = status_of(row["افقی"], row["عمودی"], row["محوری"])

            final.append({
                "تاریخ": row["تاریخ"],
                "_ord": row["_ord"],
                "خط تولید": row["خط تولید"],
                "واحد": row["واحد"],
                "تجهیز": row["تجهیز"],
                "نقطه": pt,
                "شرح نقطه": desc,
                "شماره بیرینگ": bearing if bearing.lower() not in EMPTY_TOKENS else "",
                "افقی": row["افقی"],
                "عمودی": row["عمودی"],
                "محوری": row["محوری"],
                "حداکثر": row_max(row["افقی"], row["عمودی"], row["محوری"]),
                "وضعیت": "%s %s" % (STATUS_ICON.get(stt, "⚪"), stt),
                "دما": row["دما"],
            })

    out = pd.DataFrame(final)
    if out.empty:
        return out

    out = out[out["تاریخ"].astype(str).str.strip().ne("")]
    out["_pord"] = out["نقطه"].map(point_order)
    out = out.sort_values(["_ord", "_pord"], ascending=[False, True], kind="mergesort")
    out = out.reset_index(drop=True)
    return ensure_cols(out, VIEW_COLS)


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


def status_counts(show):
    res = {"بحرانی": 0, "هشدار": 0, "نرمال": 0, "بی‌داده": 0}
    if show is None or len(show) == 0:
        return res
    for s in show["وضعیت"].astype(str):
        for k in res:
            if k in s:
                res[k] += 1
                break
    return res


# ============================================================
# 5) نمودار دایره‌ای (SVG) برای گزارش HTML
# ============================================================
def build_donut_svg(counts):
    total = sum(counts.values())
    if total <= 0:
        return ""
    r = 70
    cx = cy = 95
    circ = 2 * 3.141592653589793 * r
    offset = 0.0
    parts = []
    for name in ["بحرانی", "هشدار", "نرمال", "بی‌داده"]:
        val = counts.get(name, 0)
        if val <= 0:
            continue
        frac = float(val) / total
        dash = frac * circ
        parts.append(
            '<circle cx="%d" cy="%d" r="%d" fill="none" stroke="%s" stroke-width="30" '
            'stroke-dasharray="%.2f %.2f" stroke-dashoffset="%.2f" '
            'transform="rotate(-90 %d %d)"></circle>'
            % (cx, cy, r, STATUS_COLOR[name], dash, circ - dash, -offset, cx, cy)
        )
        offset += dash

    legend = []
    for name in ["بحرانی", "هشدار", "نرمال", "بی‌داده"]:
        val = counts.get(name, 0)
        if val <= 0:
            continue
        pct = 100.0 * val / total
        legend.append(
            '<tr><td style="text-align:right"><span style="display:inline-block;width:12px;'
            'height:12px;background:%s;border-radius:3px;margin-left:6px"></span>%s</td>'
            '<td>%d</td><td>%.1f%%</td></tr>' % (STATUS_COLOR[name], name, val, pct)
        )

    svg = (
        '<div class="donut-wrap">'
        '<svg width="190" height="190" viewBox="0 0 190 190">'
        '<circle cx="95" cy="95" r="70" fill="none" stroke="#eceff1" stroke-width="30"></circle>'
        + "".join(parts) +
        '<text x="95" y="92" text-anchor="middle" font-size="20" font-weight="700" fill="#263238">%d</text>'
        '<text x="95" y="112" text-anchor="middle" font-size="11" fill="#607d8b">کل ردیف‌ها</text>'
        '</svg>' % total +
        '<table class="donut-legend"><thead><tr><th>وضعیت</th><th>تعداد</th><th>سهم</th></tr></thead>'
        '<tbody>' + "".join(legend) + '</tbody></table>'
        '</div>'
    )
    return svg


def build_report_html(show, equip_title, caption_dates):
    counts = status_counts(show)

    head_cells = "".join("<th>%s</th>" % html.escape(c) for c in REPORT_COLS)
    rows_out = []
    for _, r in show.iterrows():
        stt = str(r.get("وضعیت", ""))
        cls = "crit" if "بحرانی" in stt else ("warn" if "هشدار" in stt else "ok")
        cells = []
        for c in REPORT_COLS:
            val = r.get(c, "")
            if val is None:
                val = "—"
            else:
                try:
                    if pd.isna(val):
                        val = "—"
                except Exception:
                    pass
            if isinstance(val, float):
                val = "%.1f" % val
            cells.append("<td>%s</td>" % html.escape(str(val)))
        rows_out.append("<tr class='%s'>%s</tr>" % (cls, "".join(cells)))

    styles = [
        "body{font-family:Tahoma,Vazirmatn,sans-serif;background:#fff;color:#222;padding:24px}",
        "h1{font-size:20px;margin:0 0 6px}",
        ".meta{font-size:12px;color:#555;margin-bottom:16px}",
        "table.grid{border-collapse:collapse;width:100%;font-size:12px}",
        "table.grid th{background:#263238;color:#fff;padding:7px 5px;border:1px solid #37474f}",
        "table.grid td{padding:6px 5px;border:1px solid #cfd8dc;text-align:center}",
        "tr.crit td{background:#ffebee} tr.warn td{background:#fff8e1} tr.ok td{background:#f1f8e9}",
        ".legend{margin-top:14px;font-size:12px;color:#455a64}",
        ".section{margin-top:26px;page-break-inside:avoid}",
        ".section h2{font-size:16px;border-right:4px solid #263238;padding-right:8px}",
        ".donut-wrap{display:flex;align-items:center;gap:26px;flex-wrap:wrap}",
        "table.donut-legend{border-collapse:collapse;font-size:12px;min-width:240px}",
        "table.donut-legend th{background:#37474f;color:#fff;padding:6px 8px;border:1px solid #455a64}",
        "table.donut-legend td{padding:6px 8px;border:1px solid #cfd8dc;text-align:center}",
    ]

    out = "<!DOCTYPE html><html lang='fa' dir='rtl'><head><meta charset='utf-8'>"
    out += "<title>گزارش پایش ارتعاشات</title><style>" + "".join(styles) + "</style></head><body>"
    out += "<h1>گزارش پایش وضعیت ارتعاشات</h1>"
    out += "<div class='meta'>تجهیز: %s &nbsp;|&nbsp; بازه: %s &nbsp;|&nbsp; تاریخ گزارش: %s</div>" % (
        html.escape(str(equip_title)),
        html.escape(str(caption_dates)),
        dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    out += "<table class='grid'><thead><tr>" + head_cells + "</tr></thead><tbody>"
    out += "".join(rows_out)
    out += "</tbody></table>"
    out += "<div class='legend'>حد هشدار: %s mm/s &nbsp;|&nbsp; حد بحرانی: %s mm/s</div>" % (WARN_LIMIT, CRIT_LIMIT)

    out += "<div class='section'><h2>نمودار دایره‌ای وضعیت کلی تجهیزات</h2>"
    out += build_donut_svg(counts)
    out += "</div></body></html>"
    return out


# ============================================================
# 6) کاربران و ایمیل
# ============================================================
USER_DB = {
    "cm.zandiyeh@gmail.com": {"name": "هادی زندیه", "role": "پیمانکار / مالک سیستم", "pass": "1234"},
    "vah.rezaei@gmail.com": {"name": "وحید رضایی", "role": "مدیر مکانیک", "pass": "1234"},
    "me.vibration.shokri@gmail.com": {"name": "جلال شکری", "role": "مدیر دفتر فنی", "pass": "1234"},
    "tehrancment@gmail.com": {"name": "سید مهدی حسینی", "role": "معاونت فنی", "pass": "1234"},
    "alireza76ir@gmail.com": {"name": "علیرضا ناظمی", "role": "رئیس", "pass": "1234"},
    "masoud.sa.1989823@gmail.com": {"name": "مسعود صمیمی", "role": "کارشناس", "pass": "1234"},
    "freedocs.ir@gmail.com": {"name": "ناصر محسنی", "role": "مدیر", "pass": "1234"},
    "m.babahasan@gmail.com": {"name": "محسن بابا حسن", "role": "کارشناس", "pass": "1234"},
}


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


# ============================================================
# 7) سربرگ
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
        "سامانه هوشمند پایش وضعیت — سیمان تهران</div>"
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
# 8) بارگذاری داده
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

df_all = vib.copy()

# ============================================================
# 9) فیلترهای وابسته (Cascade)
# ============================================================
st.sidebar.subheader("🔍 فیلترها")

_raw_map = resolve_columns(vib_raw, VIB_COLUMNS)
raw_line = list(col_or_blank(vib_raw, _raw_map, "line"))
line_opts = options_from(raw_line + list(df_all["خط تولید"]))

work = df_all.copy()

if line_opts:
    sel_line = st.sidebar.multiselect("خط تولید", line_opts, placeholder="همه خطوط")
    if sel_line:
        work = work[work["خط تولید"].isin(sel_line)]
else:
    sel_line = []

unit_opts = options_from(work["واحد"])
if unit_opts:
    sel_unit = st.sidebar.multiselect("واحد", unit_opts, placeholder="همه واحدها")
    if sel_unit:
        work = work[work["واحد"].isin(sel_unit)]
else:
    sel_unit = []

eq_opts = options_from(work["تجهیز"])
if eq_opts:
    sel_eq = st.sidebar.multiselect("تجهیز", eq_opts, placeholder="همه تجهیزات")
    if sel_eq:
        work = work[work["تجهیز"].isin(sel_eq)]
else:
    sel_eq = []

st.sidebar.markdown("**تاریخ‌ها**")
all_dates = sorted({d for d in work["تاریخ"] if d}, reverse=True)
sel_dates = st.sidebar.multiselect("انتخاب تاریخ (پیش‌فرض: همه)", all_dates,
                                   default=all_dates, placeholder="همه تاریخ‌ها")
if sel_dates and len(sel_dates) < len(all_dates):
    work = work[work["تاریخ"].isin(sel_dates)]

only_latest = st.sidebar.checkbox("فقط جدیدترین تاریخ هر نقطه", value=False)
if only_latest:
    work = (
        work.sort_values(["_ord", "_pord"], ascending=[False, True], kind="mergesort")
            .drop_duplicates(subset=["تجهیز", "نقطه"], keep="first")
    )

show = work.sort_values(["_ord", "_pord"], ascending=[False, True], kind="mergesort").reset_index(drop=True)

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

counts = status_counts(show)

s1, s2, s3, s4 = st.columns(4)
s1.metric("ردیف‌های نمایش‌داده‌شده", "{:,}".format(len(show)))
s2.metric("تعداد تاریخ‌ها", "{}".format(len(_dates_in_show)))
s3.metric("🔴 بحرانی", "{}".format(counts["بحرانی"]))
s4.metric("🟡 هشدار", "{}".format(counts["هشدار"]))

# ============================================================
# 10) کارت مشخصات تجهیز
# ============================================================
if len(sel_eq) == 1:
    meta = asset_meta.get(norm(sel_eq[0]), {})
    mapping = get_mapping(meta.get("type", ""), meta.get("driver", ""))
    with st.container(border=True):
        st.markdown("### 🛠 مشخصات تجهیز: {}".format(sel_eq[0]))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("نوع تجهیز", meta.get("type") or "—")
        c2.metric("درایور", meta.get("driver") or "—")
        c3.metric("دور نامی (RPM)", meta.get("rpm") or "—")
        c4.metric("بوش", meta.get("bush") or "—")
        if meta.get("bearings"):
            st.caption("شماره بیرینگ‌های ثبت‌شده: " + " • ".join(meta["bearings"]))
        st.markdown("#### 📍 راهنمای نقاط پایش")
        if mapping:
            guide = pd.DataFrame(
                [{"نقطه": k, "شرح نقطه": v} for k, v in
                 sorted(mapping.items(), key=lambda kv: point_order(kv[0]))]
            )
            st.dataframe(guide, use_container_width=True, hide_index=True)
        else:
            st.info("برای این تجهیز، «نوع تجهیز» یا «درایور» در شیت Assets تطبیق داده نشد.")

# ============================================================
# 11) اعلانیه‌ها — فقط از شیت اعلانیه ها
# ============================================================
with st.expander("🔔 اعلانیه‌ها و اطلاعیه‌ها", expanded=False):
    if ann_raw.empty:
        st.info("شیت اعلانیه‌ها خالی یا یافت نشد.")
    else:
        m_ann = resolve_columns(ann_raw, ANN_COLUMNS)
        if "title" not in m_ann and "text" not in m_ann:
            st.error("ستون‌های «عنوان» یا «متن» در شیت اعلانیه‌ها پیدا نشد. ستون‌های موجود: "
                     + " ， ".join([str(c) for c in ann_raw.columns]))
        else:
            titles = col_or_blank(ann_raw, m_ann, "title")
            texts = col_or_blank(ann_raw, m_ann, "text")
            types = col_or_blank(ann_raw, m_ann, "type")
            actives = col_or_blank(ann_raw, m_ann, "active")

            found = False
            for i in range(len(ann_raw)):
                is_active = True
                if "active" in m_ann:
                    raw_act = str(actives.iloc[i]).strip().lower()
                    if raw_act and raw_act not in ACTIVE_TOKENS:
                        is_active = False
                if not is_active:
                    continue

                t_title = str(titles.iloc[i]).strip()
                t_text = str(texts.iloc[i]).strip()
                t_type = str(types.iloc[i]).strip()
                if t_title.lower() in EMPTY_TOKENS and t_text.lower() in EMPTY_TOKENS:
                    continue
                found = True
                if "خطر" in t_type or "بحرانی" in t_type or "critical" in t_type.lower():
                    st.error("**{}**\n\n{}".format(t_title, t_text))
                elif "اطلاع" in t_type or "info" in t_type.lower():
                    st.info("**{}**\n\n{}".format(t_title, t_text))
                else:
                    st.warning("**{}**\n\n{}".format(t_title, t_text))

            if not found:
                st.info("هیچ اطلاعیه فعالی ثبت نشده است.")

# ============================================================
# 12) تب‌ها
# ============================================================
tab_table, tab_chart, tab_alert, tab_users = st.tabs(
    ["📋 جدول داده‌ها", "📈 نمودارها", "📧 ارسال اعلان", "👥 کاربران"]
)

# ---------------- جدول ----------------
with tab_table:
    st.subheader("داده‌های ارتعاش — {}".format(equip))
    st.caption("بازه: {}".format(caption_dates))

    f1, f2 = st.columns([1, 1])
    with f1:
        only_crit = st.checkbox("فقط ردیف‌های بحرانی و هشدار", value=False)
    with f2:
        pick_point = st.multiselect("نقطه", options_from(show["نقطه"]) if "نقطه" in show.columns else [])

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
                           file_name="vibration_{}.csv".format(safe_name(equip)),
                           mime="text/csv", use_container_width=True)
    with dc2:
        html_report = build_report_html(tbl, equip, caption_dates)
        st.download_button("🖨️ دانلود گزارش HTML (قابل چاپ)",
                           data=html_report.encode("utf-8"),
                           file_name="report_{}.html".format(safe_name(equip)),
                           mime="text/html", use_container_width=True)

# ---------------- نمودارها ----------------
with tab_chart:
    if show.empty:
        st.info("داده‌ای برای نمودار نیست.")
    else:
        st.markdown("**بیشترین مقدار هر جهت در هر تاریخ**")
        trend = show.groupby("تاریخ")[["افقی", "عمودی", "محوری"]].max().sort_index(ascending=False)
        st.line_chart(trend)

        st.markdown("**بیشترین ارتعاش هر نقطه**")
        by_point = show.groupby("نقطه")["حداکثر"].max().dropna().sort_values(ascending=False)
        if not by_point.empty:
            by_point.index = [str(c) + " - " + point_label(c) for c in by_point.index]
            st.bar_chart(by_point)

        if show["دما"].notna().any():
            st.markdown("**روند دما**")
            temp = show.groupby("تاریخ")["دما"].max().sort_index(ascending=False)
            st.line_chart(temp)

        st.divider()
        st.markdown("### 🥧 نمودار دایره‌ای وضعیت کلی تجهیزات")
        pie_df = pd.DataFrame(
            [{"وضعیت": k, "تعداد": v} for k, v in counts.items() if v > 0]
        )
        if pie_df.empty:
            st.info("داده‌ای برای نمایش وجود ندارد.")
        elif alt is None:
            st.table(pie_df)
        else:
            pie = (
                alt.Chart(pie_df)
                .mark_arc(innerRadius=70, outerRadius=130)
                .encode(
                    theta=alt.Theta("تعداد:Q"),
                    color=alt.Color(
                        "وضعیت:N",
                        scale=alt.Scale(
                            domain=["بحرانی", "هشدار", "نرمال", "بی‌داده"],
                            range=[STATUS_COLOR["بحرانی"], STATUS_COLOR["هشدار"],
                                   STATUS_COLOR["نرمال"], STATUS_COLOR["بی‌داده"]],
                        ),
                        legend=alt.Legend(title="وضعیت"),
                    ),
                    tooltip=["وضعیت:N", "تعداد:Q"],
                )
                .properties(height=340, title="توزیع وضعیت ردیف‌های نمایش‌داده‌شده")
            )
            st.altair_chart(pie, use_container_width=True)

        lc1, lc2, lc3, lc4 = st.columns(4)
        total = sum(counts.values()) or 1
        lc1.metric("🔴 بحرانی", "{} ({:.0f}%)".format(counts["بحرانی"], 100.0 * counts["بحرانی"] / total))
        lc2.metric("🟡 هشدار", "{} ({:.0f}%)".format(counts["هشدار"], 100.0 * counts["هشدار"] / total))
        lc3.metric("🟢 نرمال", "{} ({:.0f}%)".format(counts["نرمال"], 100.0 * counts["نرمال"] / total))
        lc4.metric("⚪ بی‌داده", "{} ({:.0f}%)".format(counts["بی‌داده"], 100.0 * counts["بی‌داده"] / total))

# ---------------- ارسال اعلان ----------------
with tab_alert:
    st.subheader("پیش‌نویس اعلان")
    crit_rows = show[show["وضعیت"].astype(str).str.contains("بحرانی|هشدار")] if len(show) else show

    if crit_rows.empty:
        st.success("در بازه انتخاب‌شده ردیف بحرانی یا هشدار وجود ندارد.")
    else:
        lines = ["گزارش پایش ارتعاشات — {}".format(equip), "بازه: {}".format(caption_dates), ""]
        for _, r in crit_rows.iterrows():
            lines.append(
                "{} | {} {} | نقطه {} - {} | بیرینگ {} | افقی {} / عمودی {} / محوری {} | {}".format(
                    r.get("تاریخ", ""),
                    r.get("خط تولید", ""),
                    r.get("تجهیز", ""),
                    r.get("نقطه", ""),
                    r.get("شرح نقطه", ""),
                    r.get("شماره بیرینگ", "") or "—",
                    "%.1f" % r["افقی"] if pd.notna(r.get("افقی")) else "—",
                    "%.1f" % r["عمودی"] if pd.notna(r.get("عمودی")) else "—",
                    "%.1f" % r["محوری"] if pd.notna(r.get("محوری")) else "—",
                    r.get("وضعیت", ""),
                )
            )
        draft = "\n".join(lines)
        edited = st.text_area("متن آماده ارسال (قابل ویرایش)", draft, height=260)

        email_map = {
            "{} — {}".format(v.get("name") or k, k): k for k, v in USER_DB.items()
        }
        picked = st.multiselect("گیرندگان از میان کاربران", list(email_map.keys()),
                                default=[k for k in email_map if "cm.zandiyeh" in k][:1])
        extra = st.text_input("گیرندگان دلخواه (با کاما جدا کن)", value="")

        to_list = [email_map[k] for k in picked if email_map.get(k)]
        for part in re.split(r"[,;\s]+", extra):
            if "@" in part:
                to_list.append(part.strip())
        to_list = list(dict.fromkeys(to_list))

        subject = "هشدار ارتعاش — {} — {}".format(equip, caption_dates)

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
            mailto = "mailto:{}?subject={}&body={}".format(
                ",".join(to_list), up.quote(subject), up.quote(edited)
            )
            st.markdown("[📨 باز کردن برنامه ایمیل]({})".format(mailto))

# ---------------- کاربران ----------------
with tab_users:
    st.subheader("مدیریت کاربران")

    if "auth" not in st.session_state:
        st.info("ورود با ایمیل سازمانی و رمز عبور انجام می‌شود.")
        u = st.text_input("ایمیل کاربر", placeholder="example@gmail.com")
        p = st.text_input("رمز عبور", type="password")
        if st.button("ورود به سیستم"):
            rec = USER_DB.get(u.strip().lower())
            if rec and p and p == rec.get("pass"):
                st.session_state["auth"] = u.strip().lower()
                st.rerun()
            else:
                st.error("ایمیل یا رمز عبور نادرست است.")
    else:
        cur = st.session_state["auth"]
        st.success("خوش آمدید، {} ({})".format(USER_DB[cur]["name"], USER_DB[cur]["role"]))
        if st.button("خروج"):
            del st.session_state["auth"]
            st.rerun()

        urows = [{"ایمیل": k, "نام": v.get("name", ""), "نقش": v.get("role", "")}
                 for k, v in USER_DB.items()]
        st.dataframe(pd.DataFrame(urows), use_container_width=True, hide_index=True)
