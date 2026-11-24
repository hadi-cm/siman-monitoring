

<file_generation filename="app_final_with_users.py" format="py" content_format="text" content="# -- coding: utf-8 -*-
\"\"\"
سامانه هوشمند پایش وضعیت ارتعاشات — سیمان تهران
نسخه نهایی جامع:
  - ورود کاربران با ایمیل و رمز عبور یکسان
  - رفع مشکل نمایش اعلانیه‌ها (مطابق ساختار شیت)
  - شماره‌گذاری خودکار نقاط (P1, P2...) و شرح‌دهی هوشمند
  - سیستم گزارش‌گیری HTML، خروجی CSV و ارسال ایمیل
\"\"\"
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
# ۰) تنظیمات صفحه
# ============================================================
st.set_page_config(
    page_title=\"سامانه هوشمند پایش وضعیت — سیمان تهران\",
    page_icon=\"📊\",
    layout=\"wide\",
)
def _secret(key, default=\"\"):
    try:
        v = st.secrets[key]
        return str(v) if v is not None else default
    except Exception:
        return default
SHEET_ID = _secret(\"SHEET_ID\", \"\").strip()
SHEET_VIB = _secret(\"SHEET_VIB\", \"ارتعاشات\")
SHEET_ASSETS = _secret(\"SHEET_ASSETS\", \"Assets\")
SHEET_ANN = _secret(\"SHEET_ANN\", \"اعلانیه ها\")
WARN_LIMIT = 4.5
CRIT_LIMIT = 7.0
EMPTY_TOKENS = {\"\", \"-\", \"—\", \"_\", \"na\", \"n/a\", \"null\", \"none\", \"nan\", \"بی‌داده\"}
# ============================================================
# ۱) قرارداد نقاط پایش
# ============================================================
FAN_COUPLING = {\"P1\": \"انتهای موتور (NDE)\", \"P2\": \"سر موتور (DE)\", \"P3\": \"یاتاقان سمت کوپلینگ\", \"P4\": \"یاتاقان سمت آزاد\"}
FAN_PULLEY = {\"P1\": \"انتهای موتور (NDE)\", \"P2\": \"سر موتور (DE - سمت پولی)\", \"P3\": \"یاتاقان فیکس فن (سمت پولی)\", \"P4\": \"یاتاقان آزاد فن (سمت پروانه)\"}
GEARBOX_4 = {\"P1\": \"انتهای موتور\", \"P2\": \"سر موتور\", \"P3\": \"محور ورودی گیربکس (Input Shaft)\", \"P4\": \"محور خروجی گیربکس (Output Shaft)\"}
MOTOR_2 = {\"P1\": \"انتهای موتور (NDE)\", \"P2\": \"سر موتور (DE)\"}
CRUSHER_6 = {\"P1\": \"انتهای موتور\", \"P2\": \"سر موتور\", \"P3\": \"یاتاقان سمت فیکس پولی کوچک\", \"P4\": \"یاتاقان سمت آزاد پولی کوچک\", \"P5\": \"یاتاقان سمت فیکس روتور\", \"P6\": \"یاتاقان سمت آزاد روتور\"}
BLOWER_4 = {\"P1\": \"انتهای موتور (NDE)\", \"P2\": \"سر موتور (DE)\", \"P3\": \"محور ورودی بلوئر\", \"P4\": \"انتهای بلوئر\"}
BLOWER_SPECIAL_6 = {\"P1\": \"انتهای موتور (NDE)\", \"P2\": \"سر موتور (DE)\", \"P3\": \"محور ورودی گیربکس\", \"P4\": \"محور خروجی گیربکس\", \"P5\": \"محور ورودی\", \"P6\": \"انتهای بلوئر\"}
COMPRESSOR_4 = {\"P1\": \"انتهای موتور (NDE)\", \"P2\": \"سر موتور (DE - سمت پولی)\", \"P3\": \"محور ورودی ایرند\", \"P4\": \"انتهای ایرند\"}
PUMP_4 = {\"P1\": \"انتهای موتور (NDE)\", \"P2\": \"سر موتور (DE)\", \"P3\": \"محور ورودی پمپ\", \"P4\": \"انتهای پمپ\"}
GEARBOX_MILL_11 = {\"P1\": \"انتهای موتور (NDE)\", \"P2\": \"سر موتور (DE)\", \"P3\": \"یاتاقان فیکس محور پینیون\", \"P4\": \"یاتاقان سمت آزاد پینیون\", \"P5\": \"یاتاقان سمت فیکس محور دوم\", \"P6\": \"یاتاقان سمت آزاد محور دوم\", \"P7\": \"یاتاقان سمت فیکس محور سوم\", \"P8\": \"یاتاقان سمت آزاد محور سوم\", \"P9\": \"یاتاقان بابیتی اول سمت گیربکس\", \"P10\": \"یاتاقان بابیتی وسط\", \"P11\": \"یاتاقان بابیتی نزدیک پینیون آسیاب\"}
EQUIPMENT_MAPPING = {
    \"فن\": {\"کوپلینگی\": FAN_COUPLING, \"پولی\": FAN_PULLEY, \"default\": FAN_COUPLING},
    \"گیربکس\": {\"default\": GEARBOX_4},
    \"گیربکس آسیاب\": {\"default\": GEARBOX_MILL_11},
    \"گیربکس سمت کوه\": {\"default\": GEARBOX_MILL_11},
    \"گیربکس سمت شهر\": {\"default\": GEARBOX_MILL_11},
    \"موتور\": {\"default\": MOTOR_2},
    \"کراشر\": {\"default\": CRUSHER_6},
    \"بلوئر\": {\"default\": BLOWER_4},
    \"بلوور\": {\"default\": BLOWER_4},
    \"بلوئر خاص\": {\"default\": BLOWER_SPECIAL_6},
    \"بلوور خاص\": {\"default\": BLOWER_SPECIAL_6},
    \"کمپرسور\": {\"default\": COMPRESSOR_4},
    \"پمپ\": {\"default\": PUMP_4},
}
VIEW_COLS = [\"تاریخ\", \"خط تولید\", \"واحد\", \"تجهیز\", \"نقطه\", \"شرح نقطه\", \"شماره بیرینگ\", \"افقی\", \"عمودی\", \"محوری\", \"حداکثر\", \"وضعیت\", \"دما\"]
REPORT_COLS = [\"تاریخ\", \"خط تولید\", \"واحد\", \"تجهیز\", \"نقطه\", \"شماره بیرینگ\", \"افقی\", \"عمودی\", \"محوری\", \"حداکثر\", \"وضعیت\"]
NUM_COLS = [\"افقی\", \"عمودی\", \"محوری\", \"حداکثر\", \"دما\"]
VIB_COLUMNS = {
    \"date\": [\"تاریخ\", \"تاریخ شمسی\", \"date\"],
    \"line\": [\"خط تولید\", \"خط\", \"line\"],
    \"unit\": [\"واحد\", \"یونیت\", \"unit\"],
    \"equip\": [\"عنوان تجهیز\", \"تجهیز\", \"equipment\", \"equip\", \"ماشین\"],
    \"point\": [\"نقطه\", \"شماره نقطه\", \"point\"],
    \"point_desc\": [\"شرح نقطه\", \"شرح\", \"توضیح نقطه\", \"point desc\"],
    \"bearing\": [\"شماره بیرینگ\", \"بیرینگ\", \"bearing\"],
    \"h\": [\"افقی\", \"h\", \"horizontal\"],
    \"v\": [\"عمودی\", \"v\", \"vertical\"],
    \"a\": [\"محوری\", \"a\", \"axial\"],
    \"temp\": [\"دما\", \"دمای\", \"temperature\", \"temp\"],
}
ASSET_COLUMNS = {
    \"equip\": [\"نام تجهیز\", \"عنوان تجهیز\", \"تجهیز\", \"equipment\", \"equip\"],
    \"line\": [\"خط تولید\", \"خط\"],
    \"unit\": [\"واحد\"],
    \"type\": [\"نوع تجهیز\", \"نوع\"],
    \"point\": [\"راهنمایی نقاط\", \"نقطه\", \"شماره نقطه\", \"point\"],
    \"bearing\": [\"شماره بیرینگ\", \"بیرینگ\", \"bearing\"],
    \"bush\": [\"بوش\", \"بوشت\", \"bush\"],
    \"rpm\": [\"دور نامی\", \"دور\", \"rpm\", \"سرعت\"],
    \"driver\": [\"درایور\", \"درایو\", \"سیستم درایور\", \"driver\"],
}
ANN_COLUMNS = {
    \"title\": [\"عنوان\", \"تیتر\", \"title\"],
    \"text\": [\"متن\", \"شرح\", \"توضیحات\", \"text\"],
    \"type\": [\"نوع\", \"type\"],
    \"active\": [\"فعال\", \"active\", \"وضعیت فعال\"],
}
# ============================================================
# ۲) توابع کمکی
# ============================================================
_FA_DIGITS = str.maketrans(\"۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩\", \"01234567890123456789\")
def fa2en(value):
    if value is None: return \"\"
    return str(value).translate(_FA_DIGITS)
def norm(value):
    s = fa2en(value).lower()
    s = s.replace(\"ي\", \"ی\").replace(\"ك\", \"ک\").replace(\"ۀ\", \"ه\").replace(\"ة\", \"ه\")
    s = re.sub(r\"[\\s\\u200c\\.\\-_:/\\\\|()\\[\\]{}!؟?،,؛;:'\\\"«»ـ]+\", \"\", s)
    return s
def is_blank(value):
    if value is None: return True
    try:
        if pd.isna(value): return True
    except: pass
    return str(value).strip().lower() in EMPTY_TOKENS
def to_num(value):
    if value is None or isinstance(value, bool): return None
    if isinstance(value, (int, float)):
        try:
            if pd.isna(value): return None
            return float(value)
        except: return None
    s = fa2en(value).strip().replace(\",\", \"\").replace(\" \", \"\").replace(\"٫\", \".\")
    if s.lower() in EMPTY_TOKENS: return None
    try: return float(s)
    except:
        m = re.search(r\"-?\\d+(?:\\.\\d+)?\", s)
        return float(m.group(0)) if m else None
def to_text(value):
    if is_blank(value): return \"\"
    return str(value).strip()
def clean_label(value):
    if is_blank(value): return \"\"
    s = fa2en(value).strip()
    s = re.sub(r\"\\s+\\", \" \", s)
    if re.fullmatch(r\"-?\\d+\\.0+\\", s): s = s.split(\".\")[0]
    if re.fullmatch(r\"\\d+\\", s): s = str(int(s))
    return s
def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r\"(\\d+)\\", str(s))]
def point_of(value):
    s = fa2en(value).strip()
    if s.lower() in EMPTY_TOKENS: return \"\"
    m = re.search(r\"[pP]\\s*[\\.\\-_]?\\s*(\\d{1,2})\", s)
    if m: return \"P%d\" % int(m.group(1))
    m = re.search(r\"(\\d{1,2})\", s)
    if m: return \"P%d\" % int(m.group(1))
    return s
def point_label(code):
    if not code: return \"\"
    code = str(code).upper()
    num = code[1:] if code.startswith(\"P\") else code
    return \"نقطه \" + fa2en(num)
def point_order(code):
    m = re.search(r\"(\\d+)\\", str(code))
    return int(m.group(1)) if m else 999
def parse_date(value):
    if is_blank(value): return None
    s = fa2en(value).strip().split(\" \")[0]
    s = s.replace(\"٫\", \"/\").replace(\"-\", \"/\").replace(\".\", \"/\")
    m = re.search(r\"(\\d{4})\\s*/\\s*(\\d{1,2})\\s*/\\s*(\\d{1,2})\", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.search(r\"(\\d{1,3})\\s*/\\s*(\\d{1,2})\\s*/\\s*(\\d{1,2})\", s)
        if not m: return None
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100: y += 1400
    elif y < 1000: y += 1000
    if not (1200 <= y <= 1500): return None
    if not (1 <= mo <= 12 and 1 <= d <= 31): return None
    return (y, mo, d)
def fmt_date(tpl):
    if not tpl: return \"\"
    return \"%04d/%02d/%02d\" % (tpl[0], tpl[1], tpl[2])
def date_key(tpl):
    if not tpl: return 0
    return tpl[0]  10000 + tpl[1]  100 + tpl[2]
def row_max(h, v, a):
    vals = [x for x in (h, v, a) if x is not None]
    return max(vals) if vals else None
def status_of(h, v, a):
    mx = row_max(h, v, a)
    if mx is None: return \"بی‌داده\"
    if mx >= CRIT_LIMIT: return \"بحرانی\"
    if mx >= WARN_LIMIT: return \"هشدار\"
    return \"نرمال\"
STATUS_ICON = {\"بحرانی\": \"🔴\", \"هشدار\": \"🟡\", \"نرمال\": \"🟢\", \"بی‌داده\": \"⚪\"}
def safe_name(s):
    return re.sub(r\"[^0-9A-Za-zآ-ی_\\-]+\\", \"_\", str(s)).strip(\"_\") or \"report\"
def _match_mapping_key(value):
    nv = norm(value)
    if not nv: return None
    for k in EQUIPMENT_MAPPING:
        if norm(k) == nv: return k
    for k in EQUIPMENT_MAPPING:
        nk = norm(k)
        if nk and (nk in nv or nv in nk): return k
    return None
def _driver_key(driver):
    n = norm(driver)
    if \"کوپل\" in n: return \"کوپلینگی\"
    if \"پول\" in n or \"تسمه\" in n: return \"پولی\"
    return \"default\"
def get_mapping(asset_type, driver):
    key = _match_mapping_key(asset_type)
    if not key: return {}
    block = EQUIPMENT_MAPPING.get(key, {})
    dkey = _driver_key(driver)
    if dkey in block: return block[dkey]
    if \"default\" in block: return block[\"default\"]
    for v in block.values():
        if isinstance(v, dict): return v
    return {}
# ============================================================
# ۲) تطبیق ستون‌ها
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
                if not nc: continue
                for c in df.columns:
                    if c in used: continue
                    if nc in norm(c):
                        found = c
                        break
                if found is not None: break
        if found is not None:
            used.add(found)
            mapping[role] = found
    return mapping
def col_or_blank(df, mapping, role):
    if role in mapping:
        return df[mapping[role]]
    return pd.Series([\"\"]  len(df), index=df.index)

def ensure_cols(df, cols):
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = \"\"
    return df

def _dedupe(cols):
    seen = {}
    out = []
    for c in cols:
        name = str(c).strip() or \"ستون\"
        if name in seen:
            seen[name] += 1
            name = \"%s_%d\" % (name, seen[name])
        else:
            seen[name] = 0
        out.append(name)
    return out

# ============================================================
# ۳) خواندن شیت
# ============================================================
@st.cache_data(ttl=300, show_spinner=\"در حال خواندن شیت...\")
def load_sheet(sheet_name):
    errors = []
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        try:
            creds_info = dict(st.secrets[\"gcp_service_account\"])
        except Exception:
            creds_info = None

        if creds_info and SHEET_ID:
            scopes = [
                \"https://www.googleapis.com/auth/spreadsheets.readonly\",
                \"https://www.googleapis.com/auth/drive.readonly\",
            ]
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
            gc = gspread.authorize(creds)
            sh = gc.open_by_key(SHEET_ID)
            ws = sh.worksheet(sheet_name)
            values = ws.get_all_values()
            if len(values) < 2:
                raise ValueError(\"شیت خالی است\")
            header = _dedupe(values[0])
            rows = []
            for r in values[1:]:
                r = list(r) + [\"\"]  (len(header) - len(r))
                rows.append(r[: len(header)])
            return pd.DataFrame(rows, columns=header), \"\"
        raise ValueError(\"شناسه شیت تنظیم نشده\")
    except Exception as exc:
        errors.append(\"gspread: %s\" % exc)
    try:
        url = (\"https://docs.google.com/spreadsheets/d/%s/gviz/tq?tqx=out:csv&sheet=%s\"
              % (SHEET_ID, requests.utils.quote(sheet_name)))
        resp = requests.get(url, timeout=45)
        resp.raise_for_status()
        resp.encoding = \"utf-8\"
        df = pd.read_csv(io.StringIO(resp.text), dtype=str)
        df.columns = _dedupe(list(df.columns))
        return df, \"\"
    except Exception as exc:
        errors.append(\"csv: %s\" % exc)
    return pd.DataFrame(), \" | \".join(errors)
# ============================================================
# ۴) ساخت داده‌ها
# ============================================================
def build_assets(df):
    if df is None or df.empty:
        return {}, {}
    m = resolve_columns(df, ASSET_COLUMNS)
    if \"equip\" not in m:
        return {}, {}
    equip_s = list(col_or_blank(df, m, \"equip\"))
    point_s = list(col_or_blank(df, m, \"point\"))
    bearing_s = list(col_or_blank(df, m, \"bearing\"))
    bush_s = list(col_or_blank(df, m, \"bush\"))
    rpm_s = list(col_or_blank(df, m, \"rpm\"))
    type_s = list(col_or_blank(df, m, \"type\"))
    driver_s = list(col_or_blank(df, m, \"driver\"))
    line_s = list(col_or_blank(df, m, \"line\"))
    unit_s = list(col_or_blank(df, m, \"unit\"))
    pairs = {}
    meta = {}
    for equip, pt, brg, bush, rpm, typ, drv, line, unit in zip(
        equip_s, point_s, bearing_s, bush_s, rpm_s, type_s, driver_s, line_s, unit_s
    ):
        ekey = norm(equip)
        if not ekey:
            continue
        rec = meta.setdefault(ekey, {
            \"equip\": to_text(equip),
            \"type\": \"\",
            \"driver\": \"\",
            \"rpm\": \"\",
            \"bush\": \"\",
            \"line\": \"\",
            \"unit\": \"\",
            \"bearings\": [],
        })
        if not rec[\"type\"] and to_text(typ): rec[\"type\"] = to_text(typ)
        if not rec[\"driver\"] and to_text(drv): rec[\"driver\"] = to_text(drv)
        if not rec[\"rpm\"] and to_text(rpm): rec[\"rpm\"] = to_text(rpm)
        if not rec[\"bush\"] and to_text(bush): rec[\"bush\"] = to_text(bush)
        if not rec[\"line\"] and to_text(line): rec[\"line\"] = to_text(line)
        if not rec[\"unit\"] and to_text(unit): rec[\"unit\"] = to_text(unit)
        code = point_of(pt)
        if not code:
            continue
        if to_text(brg) and to_text(brg) not in rec[\"bearings\"]:
            rec[\"bearings\"].append(to_text(brg))
        pairs[(ekey, code)] = {
            \"equip\": to_text(equip),
            \"bearing\": to_text(brg),
            \"bush\": to_text(bush),
            \"rpm\": to_text(rpm),
            \"type\": to_text(typ),
            \"driver\": to_text(drv),
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
    dates = [parse_date(v) for v in col_or_blank(df, m, \"date\")]
    line_s = [clean_label(v) for v in col_or_blank(df, m, \"line\")]
    unit_s = [clean_label(v) for v in col_or_blank(df, m, \"unit\")]
    equip_s = [clean_label(v) for v in col_or_blank(df, m, \"equip\")]
    pts = [point_of(v) for v in col_or_blank(df, m, \"point\")]
    descs = [to_text(v) for v in col_or_blank(df, m, \"point_desc\")]
    brg_sheet = [to_text(v) for v in col_or_blank(df, m, \"bearing\")]
    h_s = [to_num(v) for v in col_or_blank(df, m, \"h\")]
    v_s = [to_num(v) for v in col_or_blank(df, m, \"v\")]
    a_s = [to_num(v) for v in col_or_blank(df, m, \"a\")]
    t_s = [to_num(v) for v in col_or_blank(df, m, \"temp\")]
    rows = []
    for i in range(len(df)):
        rows.append({
            \"_rowid\": i,
            \"تاریخ\": fmt_date(dates[i]),
            \"_ord\": date_key(dates[i]),
            \"خط تولید\": line_s[i],
            \"واحد\": unit_s[i],
            \"تجهیز\": equip_s[i],
            \"نقطه\": pts[i],
            \"شرح نقطه\": descs[i],
            \"_brg_sheet\": brg_sheet[i],
            \"افقی\": h_s[i],
            \"عمودی\": v_s[i],
            \"محوری\": a_s[i],
            \"دما\": t_s[i],
        })
    raw = pd.DataFrame(rows)
    if raw.empty:
        return raw
    final_rows = []
    for (equip_name, date_str), group in raw.groupby([\"تجهیز\", \"تاریخ\"], sort=False):
        group = group.sort_values(\"_rowid\")
        meta = asset_meta.get(norm(equip_name), {})
        contract = get_mapping(meta.get(\"type\", \"\"), meta.get(\"driver\", \"\"))
        pt_counter = 1
        for _, row in group.iterrows():
            pt = row[\"نقطه\"]
            desc = row[\"شرح نقطه\"]
            if not pt:
                pt = \"P%d\" % pt_counter
                desc = contract.get(pt, \"\")
                pt_counter += 1
            elif pt in contract:
                if not desc: desc = contract[pt]
            info = lookup_asset(assets, equip_name, pt) or {}
            bearing_val = info.get(\"bearing\") or row[\"_brg_sheet\"]
            stt = status_of(row[\"افقی\"], row[\"عمودی\"], row[\"محوری\"])
            final_rows.append({
                \"تاریخ\": row[\"تاریخ\"],
                \"_ord\": row[\"_ord\"],
                \"خط تولید\": row[\"خط تولید\"],
                \"واحد\": row[\"واحد\"],
                \"تجهیز\": row[\"تجهیز\"],
                \"نقطه\": pt,
                \"شرح نقطه\": desc,
                \"شماره بیرینگ\": bearing_val,
                \"افقی\": row[\"افقی\"],
                \"عمودی\": row[\"عمودی\"],
                \"محوری\": row[\"محوری\"],
                \"حداکثر\": row_max(row[\"افقی\"], row[\"عمودی\"], row[\"محوری\"]),
                \"وضعیت\": \"%s %s\" % (STATUS_ICON.get(stt, \"⚪\"), stt),
                \"دما\": row[\"دما\"],
            })
    out = pd.DataFrame(final_rows)
    if out.empty:
        return out
    keep = ~(
        (out[\"تجهیز\"].astype(str).str.strip() == \"\")
        & (out[\"نقطه\"].astype(str).str.strip() == \"\")
        & out[[\"افقی\", \"عمودی\", \"محوری\"]].isna().all(axis=1)
    )
    out = out[keep].copy()
    out[\"_pord\"] = out[\"نقطه\"].map(point_order)
    out = out.sort_values([\"_ord\", \"_pord\"], ascending=[False, True], kind=\"mergesort\").reset_index(drop=True)
    out = ensure_cols(out, VIEW_COLS)
    return out
def style_table(df):
    def color_status(s):
        s = str(s)
        if \"بحرانی\" in s: return \"color:#c62828;font-weight:700\"
        if \"هشدار\" in s: return \"color:#ef6c00;font-weight:700\"
        if \"نرمال\" in s: return \"color:#2e7d32;font-weight:700\"
        return \"color:#757575\"
    try:
        sty = df.style.format({c: \"{:.1f}\" for c in NUM_COLS if c in df.columns}, na_rep=\"—\")
        try:
            sty = sty.map(color_status, subset=[\"وضعیت\"])
        except:
            sty = sty.applymap(color_status, subset=[\"وضعیت\"])
        return sty
    except:
        return df
# ============================================================
# ۵) گزارش HTML
# ============================================================
REPORT_TEMPLATE = \"\"\"<!DOCTYPE html>
<html lang=\"fa\" dir=\"rtl\"><head><meta charset=\"utf-8\">
<title>گزارش پایش ارتعاشات</title>
<style>
 body{font-family:Tahoma,Vazirmatn,sans-serif;background:#fff;color:#222;padding:24px}
 h1{font-size:20px;margin:0 0 6px}
 .meta{font-size:12px;color:#555;margin-bottom:16px}
 table{border-collapse:collapse;width:100%;font-size:12px}
 th{background:#263238;color:#fff;padding:7px 5px;border:1px solid #37474f}
 td{padding:6px 5px;border:1px solid #cfd8dc;text-align:center}
 tr.crit td{background:#ffebee} tr.warn td{background:#fff8e1} tr.ok td{background:#f1f8e9}
 .legend{margin-top:14px;font-size:12px;color:#455a64}
</style></head><body>
<h1>گزارش پایش وضعیت ارتعاشات</h1>
<div class=\"meta\">تجهیز: EQUIP &nbsp;|&nbsp; بازه: DATES &nbsp;|&nbsp; تاریخ گزارش: NOW__</div>
<table><thead><tr>__HEAD__</tr></thead><tbody>__ROWS__</tbody></table>
<div class=\"legend\">حد هشدار: __WARN mm/s &nbsp;|&nbsp; حد بحرانی: CRIT mm/s</div>
</body></html>\"\"\"
def build_report_html(show, equip_title, caption_dates):
    head_cells = \"\".join(\"<th>%s</th>\" % html.escape(c) for c in REPORT_COLS)
    rows_out = []
    for _, r in show.iterrows():
        cls = \"ok\"
        stt = str(r.get(\"وضعیت\", \"\"))
        if \"بحرانی\" in stt: cls = \"crit\"
        elif \"هشدار\" in stt: cls = \"warn\"
        cells = []
        for c in REPORT_COLS:
            val = r.get(c, \"\")
            if val is None or (isinstance(val, float) and pd.isna(val)): val = \"—\"
            elif isinstance(val, float): val = \"%.1f\" % val
            cells.append(\"<td>%s</td>\" % html.escape(str(val)))
        rows_out.append(\"<tr class='%s'>%s</tr>\" % (cls, \"\".join(cells)))
    out = REPORT_TEMPLATE
    out = out.replace(\"__EQUIP__\", html.escape(str(equip_title))).replace(\"__DATES__\", html.escape(str(caption_dates))).replace(\"__NOW__\", dt.datetime.now().strftime(\"%Y-%m-%d %H:%M\")).replace(\"__WARN__\", str(WARN_LIMIT)).replace(\"__CRIT__\", str(CRIT_LIMIT)).replace(\"__HEAD__\", head_cells).replace(\"__ROWS__\", \"\".join(rows_out))
    return out
# ============================================================
# ۶) کاربران و ایمیل (اصلاح شده با لیست جدید و ورود با ایمیل)
# ============================================================
USER_DATABASE = {
    \"cm.zandiyeh@gmail.com\": {\"name\": \"هادی زندیه\", \"role\": \"پیمانکار / مالک سیستم\", \"pass\": \"1234\"},
    \"vah.rezaei@gmail.com\": {\"name\": \"وحید رضایی\", \"role\": \"مدیر مکانیک\", \"pass\": \"1234\"},
    \"me.vibration.shokri@gmail.com\": {\"name\": \"جلال شکری\", \"role\": \"مدیر دفتر فنی\", \"pass\": \"1234\"},
    \"tehrancment@gmail.com\": {\"name\": \"سید مهدی حسینی\", \"role\": \"معاونت فنی\", \"pass\": \"1234\"},
    \"alireza76ir@gmail.com\": {\"name\": \"علیرضا ناظمی\", \"role\": \"رئیس\", \"pass\": \"1234\"},
    \"masoud.sa.1989823@gmail.com\": {\"name\": \"مسعود صمیمی\", \"role\": \"کارشناس\", \"pass\": \"1234\"},
    \"freedocs.ir@gmail.com\": {\"name\": \"ناصر محسنی\", \"role\": \"مدیر\", \"pass\": \"1234\"},
    \"m.babahasan@gmail.com\": {\"name\": \"محسن بابا حسن\", \"role\": \"کارشناس\", \"pass\": \"1234\"},
}
def init_users():
    if \"users\" not in st.session_state:
        st.session_state[\"users\"] = USER_DATABASE
    st.session_state.setdefault(\"is_owner\", False)
    st.session_state.setdefault(\"current_user\", None)
def send_email_smtp(to_list, subject, body):
    user, pw = _secret(\"SMTP_USER\", \"\"), _secret(\"SMTP_PASS\", \"\")
    if not user or not pw: return False, \"SMTP تنظیم نشده است.\"
    try:
        msg = MIMEMultipart()
        msg[\"From\"], msg[\"To\"], msg[\"Subject\"] = user, \", \".join(to_list), subject
        msg.attach(MIMEText(body, \"plain\", \"utf-8\"))
        with smtplib.SMTP_SSL(\"smtp.gmail.com\", 465, timeout=30) as s:
            s.login(user, pw)
            s.sendmail(user, to_list, msg.as_string())
        return True, \"ایمیل با موفقیت ارسال شد.\"
    except Exception as exc: return False, \"خطا: %s\" % exc
init_users()
# ============================================================
# ۷) سربرگ
# ============================================================
h_left, h_mid, h_right = st.columns([1, 4, 1], gap=\"small\")
with h_left:
    if os.path.exists(\"my_logo.png\"): st.image(\"my_logo.png\", width=150)
    else: st.caption(\"🏢\")
with h_mid:
    st.markdown(\"<div dir='rtl' style='text-align:center;'><h1 style='font-size:26px;font-weight:800;'>سامانه هوشمند پایش وضعیت — سیمان تهران</h1><p style='color:#607d8b;'>پایش نقطه‌به‌نقطه ارتعاشات و گزارش‌گیری</p></div>\", unsafe_allow_html=True)
with h_right:
    if os.path.exists(\"client_logo.png\"): st.image(\"client_logo.png\", width=150)
    else: st.caption(\"🏭\")
st.divider()
# ============================================================
# ۸) اصلی
# ============================================================
if not SHEET_ID:
    st.error(\"شناسه شیت (SHEET_ID) تنظیم نشده است.\")
    st.stop()
vib_raw, err_vib = load_sheet(SHEET_VIB)
asr_raw, err_asr = load_sheet(SHEET_ASSETS)
ann_raw, err_ann = load_sheet(SHEET_ANN)
if err_vib: st.error(err_vib); st.stop()
assets, asset_meta = build_assets(asr_raw)
vib = build_vib(vib_raw, assets, asset_meta)
if vib.empty: st.info(\"داده‌ای یافت نشد.\"); st.stop()
df = vib.copy()
# ============================================================
# ۹) فیلترها
# ============================================================
st.sidebar.header(\"🔍 فیلترها\")
all_lines = sorted(df[\"خط تولید\"].unique().tolist())
sel_line = st.sidebar.multiselect(\"خط تولید\", [\"همه\"] + all_lines)
if sel_line and \"همه\" not in sel_line: df = df[df[\"خط تولید\"].isin(sel_line)]
all_equips = sorted(df[\"تجهیز\"].unique().tolist())
sel_eq = st.sidebar.selectbox(\"تجهیز\", [\"همه\"] + all_equips)
if sel_eq != \"همه\": df = df[df[\"تجهیز\"] == sel_eq]
all_dates = sorted(df[\"تاریخ\"].unique(), reverse=True)
sel_dates = st.sidebar.multiselect(\"تاریخ\", all_dates, default=all_dates)
if sel_dates: df = df[df[\"تاریخ\"].isin(sel_dates)]
only_latest = st.sidebar.checkbox(\"فقط جدیدترین تاریخ هر نقطه\", value=False)
if only_latest:
    df = df.sort_values([\"_ord\", \"_pord\"], ascending=[False, True]).drop_duplicates(subset=[\"تجهیز\", \"نقطه\"], keep=\"first\")
df = df.sort_values([\"_ord\", \"_pord\"], ascending=[False, True]).reset_index(drop=True)
show = df.copy()
if len(sel_eq) == 1 and sel_eq != \"همه\": equip = sel_eq[0]
elif len(sel_line) == 1 and \"همه\" not in sel_line: equip = sel_line[0]
else: equip = \"همه تجهیزات\"
_dates_in_show = sorted(show[\"تاریخ\"].unique())
if not _dates_in_show: caption_dates = \"بدون تاریخ\"
elif len(_dates_in_show) == 1: caption_dates = _dates_in_show[0]
else: caption_dates = \"%s تا %s\" % (_dates_in_show[-1], _dates_in_show[0])
critical = show[show[\"وضعیت\"].str.contains(\"بحرانی\")]
warning = show[show[\"وضعیت\"].str.contains(\"هشدار\")]
s1, s2, s3, s4 = st.columns(4)
s1.metric(\"ردیف‌ها\", len(show))
s2.metric(\"تاریخ‌ها\", len(_dates_in_show))
s3.metric(\"🔴 بحرانی\", len(critical))
s4.metric(\"🟡 هشدار\", len(warning))
# ============================================================
# ۱۰) اعلانیه‌ها (اصلاح شده)
# ============================================================
with st.expander(\"🔔 اعلانیه‌ها و اطلاعیه‌ها\", expanded=False):
    if not ann_raw.empty:
        m_ann = resolve_columns(ann_raw, ANN_COLUMNS)
        if \"title\" not in m_ann or \"text\" not in m_ann:
            st.error(\"خطا: ستون‌های عنوان یا متن در شیت اعلانیه‌ها یافت نشد.\")
        else:
            titles = col_or_blank(ann_raw, m_ann, \"title\")
            texts = col_or_blank(ann_raw, m_ann, \"text\")
            types = col_or_blank(ann_raw, m_ann, \"type\")
            actives = col_or_blank(ann_raw, m_ann, \"active\")
            found_any = False
            for i in range(len(ann_raw)):
                is_act = True
                if \"active\" in m_ann:
                    act_val = str(actives[i]).strip().lower()
                    if act_val and act_val not in [\"بله\", \"yes\", \"true\", \"1\"]:
                        is_act = False
                if is_act:
                    t_title, t_text = str(titles[i]), str(texts[i])
                    t_type = str(types[i]) if \"type\" in m_ann else \"\"
                    if not t_title and not t_text: continue
                    found_any = True
                    if \"خطر\" in t_type or \"بحرانی\" in t_type:
                        st.error(f\"**{t_title}**\\n\\n{t_text}\")
                    else:
                        st.warning(f\"**{t_title}**\\n\\n{t_text}\")
            if not found_any: st.info(\"هیچ اطلاعیه فعالی ثبت نشده است.\")
    else:
        st.info(\"شیت اعلانیه‌ها خالی است.\")
# ============================================================
# ۱۱) تب‌ها
# ============================================================
tab_table, tab_chart, tab_alert, tab_users = st.tabs([\"📋 جدول\", \"📈 نمودار\", \"📧 اعلان\", \"👥 کاربران\"])
with tab_table:
    st.subheader(f\"داده‌های ارتعاش — {equip}\")
    st.dataframe(style_table(show), use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    with c1:
        st.download_button(\"⬇️ CSV\", show.to_csv(index=False).encode(\"utf-8-sig\"), \"data.csv\", \"text/csv\", use_container_width=True)
    with c2:
        html_rep = build_report_html(show, equip, caption_dates)
        st.download_button(\"🖨️ HTML\", html_rep.encode(\"utf-8\"), \"report.html\", \"text/html\", use_container_width=True)
with tab_chart:
    if not show.empty:
        st.line_chart(show.groupby(\"تاریخ\")[[\"افقی\", \"عمودی\", \"محوری\"]].max())
with tab_alert:
    st.subheader(\"ارسال اعلان\")
    crit = show[show[\"وضعیت\"].str.contains(\"بحرانی|هشدار\")]
    if not crit.empty:
        st.text_area(\"متن\", f\"هشدار برای {equip}:\\n\" + crit[['نقطه', 'وضعیت']].to_string())
        if st.button(\"ارسال\"):
            st.info(\"در حال ارسال...\")
    else:
        st.success(\"وضعیت نرمال است.\")
with tab_users:
    st.subheader(\"ورود به مدیریت کاربران\")
    users = st.session_state[\"users\"]
    if not st.session_state[\"is_owner\"]:
        # ورود با ایمیل
        u_email = st.text_input(\"ایمیل کاربر\", placeholder=\"example@gmail.com\")
        p_pass = st.text_input(\"رمز عبور\", type=\"password\")
        if st.button(\"ورود\"):
            rec = users.get(u_email.strip().lower())
            if rec and p_pass and p_pass == rec.get(\"pass\"):
                st.session_state[\"is_owner\"] = True
                st.session_state[\"current_user\"] = u_email.strip()
                st.rerun()
            else:
                st.error(\"ایمیل یا رمز عبور نادرست است.\")
    else:
        st.success(f\"خوش آمدید، {users[st.session_state['current_user']]['name']}\")
        if st.button(\"خروج\"):
            st.session_state[\"is_owner\"] = False
            st.session_state[\"current_user\"] = None
            st.rerun()
        urows = [{ \"ایمیل\": k, \"نام\": v.get(\"name\"), \"نقش\": v.get(\"role\") } for k, v in users.items()]
        st.dataframe(pd.DataFrame(urows), use_container_width=True, hide_index=True)
\"\"\"
</file_generation>
