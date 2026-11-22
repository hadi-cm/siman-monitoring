# -*- coding: utf-8 -*-
"""
====================================================================
 سامانه هوشمند پایش وضعیت ارتعاشات - سیمان تهران
 نسخه نهایی: نمایش نقطه به نقطه (P1..P11) + شماره بیرینگ از شیت Assets
====================================================================
"""

import os
import re
import html
from datetime import datetime, date, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ==================================================================
# 1) تنظیمات اصلی
# ==================================================================
APP_TITLE = "سامانه هوشمند پایش وضعیت - سیمان تهران"
APP_SUB = "پایش ارتعاش تجهیزات دوار"

LOGO_MINE = "my_logo.png"
LOGO_CLIENT = "client_logo.png"

VIB_CSV_URL = ("https://docs.google.com/spreadsheets/d/e/"
               "2PACX-1vTI4vONsowudctVbskGkkSyQNqkkGZ8AuiykO9UKeE-8FSBZemWkR4q5DSAhpXEqwQkgsCUQy44Vvqx"
               "/pub?output=csv")
ASSET_CSV_URL = VIB_CSV_URL + "&gid=1728784730"

# آستانه‌های هشدار (mm/s RMS)
TH_WARN = 4.5
TH_CRIT = 7.0

USER_DB = {
    'cm.zandiyeh@gmail.com':         {'name': 'هادی زندیه',      'role': 'پیمانکار / مالک سیستم', 'password': 'siman123'},
    'vah.rezaei@gmail.com':          {'name': 'وحید رضایی',      'role': 'مدیر مکانیک',           'password': 'siman123'},
    'me.vibration.shokri@gmail.com': {'name': 'مهدی شکری',       'role': 'مدیر دفتر فنی',         'password': 'siman123'},
    'tehrancment@gmail.com':         {'name': 'سید مهدی حسینی',  'role': 'معاونت فنی',            'password': 'siman123'},
    'alireza76ir@gmail.com':         {'name': 'علیرضا',          'role': 'کارشناس',               'password': 'siman123'},
    'masoud.sa.1989823@gmail.com':   {'name': 'مسعود صمیمی',     'role': 'کارشناس',               'password': 'siman123'},
    'operator2@tehrancment.ir':      {'name': 'اپراتور خط ۲',    'role': 'کاربر',                 'password': 'siman123'},
}
OWNER_EMAIL = 'cm.zandiyeh@gmail.com'
SEND_ROLES = ('مدیر', 'معاونت', 'مالک')

# شرح پیش‌فرض نقاط اندازه‌گیری (قابل ویرایش)
POINT_LABELS = {
    'P1': 'انتهای موتور',
    'P2': 'سر موتور (سمت کوپلینگ)',
    'P3': 'یاتاقان سمت ثابت (فیکس)',
    'P4': 'یاتاقان سمت آزاد',
    'P5': 'نقطه ۵',
    'P6': 'نقطه ۶',
    'P7': 'نقطه ۷',
    'P8': 'نقطه ۸',
    'P9': 'نقطه ۹',
    'P10': 'نقطه ۱۰',
    'P11': 'نقطه ۱۱',
}

LINE_PRIORITY = ["خط تولید 1", "خط تولید 2", "خط تولید 3", "خط تولید 4",
                 "خط تولید 5", "خط تولید 6", "خط تولید 7", "خط تولید 8",
                 "خط تولید 9"]
UNIT_PRIORITY = ["سنگ شکن", "آسیاب مواد", "آسیاب سیمان", "کوره",
                 "بارگیرخانه", "بارگیرخانه ۶", "بارگیرخانه ۹"]

# نام ستون‌های استاندارد داخلی
C_DATE, C_JDATE = "تاریخ", "تاریخ شمسی"
C_LINE, C_UNIT, C_EQ = "خط تولید", "واحد", "عنوان تجهیز"
C_PT, C_PTNAME = "نقطه", "شرح نقطه"
C_BRG = "شماره بیرینگ"
C_H, C_V, C_A, C_T = "افقی", "عمودی", "محوری", "دما"
C_ST, C_DESC, C_ACT, C_COST, C_PRI = "وضعیت", "توضیحات", "اقدام اصلاحی", "هزینه", "اولویت"

FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"

# ==================================================================
# 2) ابزارهای متنی و عددی
# ==================================================================
def to_latin(v) -> str:
    """ارقام فارسی/عربی به لاتین + حذف کشیده و نویسه‌های کنترلی"""
    if v is None:
        return ""
    s = str(v)
    out = []
    for ch in s:
        if ch in FA_DIGITS:
            out.append(str(FA_DIGITS.index(ch)))
        elif ch in AR_DIGITS:
            out.append(str(AR_DIGITS.index(ch)))
        else:
            out.append(ch)
    s = "".join(out)
    s = s.replace("\u0640", "")      # کشیده
    s = s.replace("\u200c", " ")     # نیم‌فاصله
    s = s.replace("\u200f", "").replace("\u200e", "")
    return s.strip()


def norm_text(v: str) -> str:
    s = to_latin(v)
    s = s.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ه").replace("أ", "ا").replace("إ", "ا")
    s = re.sub(r"[\u064B-\u065F]", "", s)   # اعراب
    s = re.sub(r"\s+", " ", s)
    return s.strip(" -_،,.\t")


def name_key(v: str) -> str:
    """کلید تطبیق نام‌ها: بدون فاصله، بدون علامت، حروف یکسان‌شده"""
    s = norm_text(v).lower()
    s = re.sub(r"[^\w\u0600-\u06FF]+", "", s)
    return s


def fa_num(v) -> str:
    s = str(v)
    out = []
    for ch in s:
        if ch.isdigit():
            out.append(FA_DIGITS[int(ch)])
        else:
            out.append(ch)
    return "".join(out)


def clean_line(v) -> str:
    """خط تولید ۶۰ → خط تولید ۶ ، و نام‌های بدون عدد را دست‌نخورده نگه می‌دارد"""
    s = norm_text(v)
    if not s:
        return ""
    digits = re.findall(r"\d+", s)
    if digits:
        n = str(int(digits[-1]))
        if "خط" in s:
            return "خط تولید " + n
        return re.sub(r"\d+", n, s)
    return s


def to_num(v):
    """مقدار عددی با پذیرش ممیز / و ارقام فارسی؛ مقادیر متنی غیرعددی → NaN"""
    if v is None:
        return np.nan
    s = to_latin(v).strip()
    if s == "" or s.lower() in ("nan", "none", "null", "-"):
        return np.nan
    s2 = s.replace("،", "").replace(" ", "")
    if re.search(r"[^\d\.\-]", s2):
        return np.nan
    try:
        return float(s2.replace("..", "."))
    except Exception:
        return np.nan


# ---------- تبدیل دقیق تاریخ شمسی به میلادی (الگوریتم استاندارد) ----------
def jalali_to_gregorian(jy: int, jm: int, jd: int):
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186

    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1

    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    month_days = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    while gm <= 12 and gd > month_days[gm]:
        gd -= month_days[gm]
        gm += 1
    return gy, gm, gd


def parse_jalali(v):
    """رشته تاریخ شمسی → Timestamp میلادی. اگر تاریخ میلادی بود، مستقیم پذیرفته می‌شود."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return pd.NaT
    if isinstance(v, (pd.Timestamp, datetime)):
        return pd.Timestamp(v)

    s = to_latin(v).strip()
    s = re.sub(r"[^\d/\-\.]", "", s).replace("-", "/").replace(".", "/")
    parts = [p for p in s.split("/") if p != ""]
    if len(parts) != 3:
        return pd.NaT
    try:
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        return pd.NaT

    # تاریخ میلادی چهاررقمی
    if 1800 <= y <= 2200:
        try:
            return pd.Timestamp(year=y, month=m, day=d)
        except Exception:
            return pd.NaT

    # تاریخ شمسی دو رقمی: 05 → 1405
    if 0 < y < 100:
        y += 1400

    if not (1200 <= y <= 1600 and 1 <= m <= 12 and 1 <= d <= 31):
        return pd.NaT
    try:
        gy, gm, gd = jalali_to_gregorian(y, m, d)
        return pd.Timestamp(year=gy, month=gm, day=gd)
    except Exception:
        return pd.NaT


def parse_point(v) -> str:
    """p1 / P 1 / p-01 → P1"""
    s = to_latin(v).strip().upper()
    m = re.match(r"^P\s*[\-_\.]?\s*(\d{1,2})$", s)
    if m:
        return "P" + str(int(m.group(1)))
    return ""


# ==================================================================
# 3) بارگذاری و آماده‌سازی داده
# ==================================================================
def rename_by_rules(cols):
    """نگاشت نام ستون‌های شیت به نام‌های استاندارد داخلی"""
    mapping = {}
    for c in cols:
        cs = norm_text(c)
        low = cs.replace(" ", "")
        tgt = None
        if "تاریخ" in cs:
            tgt = C_DATE
        elif "خط" in cs:
            tgt = C_LINE
        elif "واحد" in cs:
            tgt = C_UNIT
        elif "بیرینگ" in cs or "بلبرینگ" in cs:
            tgt = C_BRG
        elif "توضیح" in cs:
            tgt = C_DESC
        elif "وضعیت" in cs:
            tgt = C_ST
        elif "اقدام" in cs:
            tgt = C_ACT
        elif "هزینه" in cs:
            tgt = C_COST
        elif "اولویت" in cs or "الویت" in cs:
            tgt = C_PRI
        elif "دما" in cs or "حرارت" in cs:
            tgt = C_T
        elif "عمودی" in cs:
            tgt = C_V
        elif "افقی" in cs:
            tgt = C_H
        elif "محوری" in cs or "اکسیال" in cs:
            tgt = C_A
        elif "محل" in cs and "اندازه" in cs:
            tgt = "محل اندازه گیری"
        elif "تصویر" in cs or "عکس" in cs:
            tgt = "تصویر"
        elif "نقطه" in cs or "نقاط" in cs:
            tgt = "نقاط"
        elif "عنوان" in cs or "تجهیز" in cs or "مکان" in cs or "نام" in cs:
            tgt = C_EQ
        if tgt and tgt not in mapping.values():
            mapping[c] = tgt
    return mapping


@st.cache_data(ttl=300, show_spinner=False)
def load_raw(vib_url: str, asset_url: str):
    vib = pd.read_csv(vib_url, dtype=str)
    vib.columns = [norm_text(c) for c in vib.columns]
    try:
        ast = pd.read_csv(asset_url, dtype=str)
        ast.columns = [norm_text(c) for c in ast.columns]
    except Exception:
        ast = pd.DataFrame()
    return vib, ast


def build_assets(ast: pd.DataFrame) -> pd.DataFrame:
    """ساخت جدول مرجع: (تجهیز، نقطه) → شماره بیرینگ / نوع تجهیز / دور نامی"""
    out = pd.DataFrame(columns=[C_EQ, "نقطه", C_BRG, "نوع تجهیز", "دور نامی", C_LINE, C_UNIT])
    if ast is None or ast.empty:
        return out

    cols = list(ast.columns)

    def find(*keys):
        for c in cols:
            cs = norm_text(c).replace(" ", "")
            if all(k in cs for k in keys):
                return c
        return None

    c_name = find("نام") or find("تجهیز") or find("عنوان")
    c_pt = find("نقاط") or find("نقطه") or find("راهنما")
    c_brg = find("بیرینگ")
    c_type = find("نوع")
    c_rpm = find("دور")
    c_line = find("خط")
    c_unit = find("واحد")

    if not c_name or not c_pt:
        return out

    df = ast.copy()
    df["_eq"] = df[c_name].map(norm_text)
    df["_pt"] = df[c_pt].map(parse_point)
    df = df[(df["_eq"] != "") & (df["_pt"] != "")]

    def col(c):
        return df[c].map(norm_text) if c else pd.Series([""] * len(df), index=df.index)

    res = pd.DataFrame({
        C_EQ: df["_eq"],
        "نقطه": df["_pt"],
        C_BRG: col(c_brg),
        "نوع تجهیز": col(c_type),
        "دور نامی": col(c_rpm),
        C_LINE: col(c_line),
        C_UNIT: col(c_unit),
    })
    res = res.drop_duplicates(subset=[C_EQ, "نقطه"], keep="first")
    return res


def build_vibration(vib: pd.DataFrame) -> pd.DataFrame:
    """ساخت جدول اصلی، یک ردیف برای هر نقطه در هر تاریخ"""
    empty = pd.DataFrame(columns=[C_DATE, C_JDATE, C_LINE, C_UNIT, C_EQ, C_PT,
                                  C_BRG, C_H, C_V, C_A, C_T, C_ST,
                                  C_DESC, C_ACT, C_COST, C_PRI])
    if vib is None or vib.empty:
        return empty

    df = vib.copy()
    df = df.rename(columns=rename_by_rules(df.columns))

    if C_DATE not in df.columns or C_EQ not in df.columns:
        return empty

    # --- تشخیص ستون نقطه: ستونی که بیشترین تطابق P# را دارد ---
    candidates = [c for c in [C_PT, "تصویر", "محل اندازه گیری"] if c in df.columns]
    best_col, best_score = None, 0.0
    for c in candidates:
        ser = df[c].dropna().astype(str)
        if len(ser) == 0:
            continue
        score = ser.map(lambda x: 1 if parse_point(x) else 0).mean()
        if score > best_score:
            best_col, best_score = c, score
    if best_col is None or best_score < 0.3:
        # ستونی برای نقطه پیدا نشد → یک نقطه عمومی
        df[C_PT] = "P1"
    else:
        df[C_PT] = df[best_col].map(parse_point)
        df.loc[df[C_PT] == "", C_PT] = "P1"

    # --- اعداد ---
    for c in (C_H, C_V, C_A, C_T):
        if c in df.columns:
            df[c] = df[c].map(to_num)
        else:
            df[c] = np.nan

    # --- متن‌ها ---
    df[C_LINE] = df[C_LINE].map(clean_line) if C_LINE in df.columns else ""
    df[C_UNIT] = df[C_UNIT].map(norm_text) if C_UNIT in df.columns else ""
    df[C_EQ] = df[C_EQ].map(norm_text)
    for c in (C_BRG, C_DESC, C_ACT, C_COST, C_PRI, C_ST):
        df[c] = df[c].map(norm_text) if c in df.columns else ""

    # --- تاریخ ---
    df[C_DATE] = df[C_DATE].map(parse_jalali)
    df = df.dropna(subset=[C_DATE])
    if df.empty:
        return empty

    df[C_JDATE] = df[C_DATE].map(lambda d: fa_num(d.strftime("%Y/%m/%d")))

    # --- وضعیت: مقدار شیت اگر بود، وگرنه محاسبه از بیشینه سه جهت ---
    mx = df[[C_H, C_V, C_A]].max(axis=1, skipna=True)
    calc = pd.Series("نرمال", index=df.index)
    calc[mx >= TH_WARN] = "هشدار"
    calc[mx >= TH_CRIT] = "بحرانی"
    st_norm = df[C_ST].map(lambda s: norm_text(s))
    st_norm = st_norm.replace({"": np.nan})
    st_norm = st_norm.replace({"نرمال": "نرمال", "هشدار": "هشدار", "بحرانی": "بحرانی"})
    df[C_ST] = st_norm.fillna(calc)

    df["_mx"] = mx.round(2)

    cols = [C_DATE, C_JDATE, C_LINE, C_UNIT, C_EQ, C_PT, C_BRG,
            C_H, C_V, C_A, C_T, C_ST, C_DESC, C_ACT, C_COST, C_PRI, "_mx"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df[cols].reset_index(drop=True)


def merge_bearing(df: pd.DataFrame, assets: pd.DataFrame) -> pd.DataFrame:
    """پر کردن شماره بیرینگ از شیت Assets بر اساس (تجهیز، نقطه)"""
    if df.empty or assets.empty:
        return df
    a = assets.copy()
    a["_k"] = a[C_EQ].map(name_key) + "|" + a["نقطه"]
    a = a.drop_duplicates("_k").set_index("_k")

    def lookup(row):
        k = name_key(row[C_EQ]) + "|" + row[C_PT]
        if k in a.index:
            b = a.at[k, C_BRG]
            if isinstance(b, str) and b.strip():
                return b.strip()
        return row[C_BRG] if isinstance(row[C_BRG], str) else ""

    df[C_BRG] = df.apply(lookup, axis=1)
    df[C_PTNAME] = df[C_PT].map(lambda p: POINT_LABELS.get(p, p))
    return df


def ordered_unique(values, priority):
    vals = [v for v in pd.Series(values).dropna().unique().tolist() if str(v).strip() != ""]
    pr = [p for p in priority if p in vals]
    rest = sorted([v for v in vals if v not in pr])
    return pr + rest


# ==================================================================
# 4) گزارش HTML
# ==================================================================
REPORT_CSS = """
<style>
  body{font-family:Tahoma,'Segoe UI',sans-serif;background:#f5f7fa;color:#1f2937;
       direction:rtl;padding:24px;}
  h1{font-size:20px;color:#123a63;border-bottom:3px solid #123a63;padding-bottom:10px;}
  .sub{color:#6b7280;font-size:12px;margin-bottom:16px;}
  .box{background:#fff;border:1px solid #dbe3ec;border-radius:10px;padding:14px 18px;
       margin-bottom:16px;font-size:13px;line-height:2;}
  .kpis{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px;}
  .kpi{flex:1;min-width:120px;background:#fff;border:1px solid #dbe3ec;border-radius:10px;
       padding:12px;text-align:center;}
  .kpi .v{font-size:20px;font-weight:bold;color:#123a63;}
  .kpi .l{font-size:11px;color:#6b7280;margin-top:4px;}
  table{width:100%;border-collapse:collapse;background:#fff;font-size:12px;
        border:1px solid #dbe3ec;border-radius:10px;overflow:hidden;}
  th{background:#123a63;color:#fff;padding:8px 6px;font-weight:normal;}
  td{padding:7px 6px;border-bottom:1px solid #eef2f7;text-align:center;}
  tr:nth-child(even) td{background:#fbfcfe;}
  .crit{background:#fee2e2 !important;color:#991b1b;font-weight:bold;}
  .warn{background:#fef3c7 !important;color:#92400e;font-weight:bold;}
  .foot{margin-top:18px;font-size:11px;color:#6b7280;text-align:center;}
</style>
"""


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def build_report_html(df: pd.DataFrame, meta: dict) -> str:
    kpi_items = [
        ("تعداد رکورد", len(df)),
        ("بحرانی", int((df[C_ST] == "بحرانی").sum()) if not df.empty else 0),
        ("هشدار", int((df[C_ST] == "هشدار").sum()) if not df.empty else 0),
        ("تعداد تجهیز", df[C_EQ].nunique() if not df.empty else 0),
    ]
    kpis = "".join(
        f'<div class="kpi"><div class="v">{esc(fa_num(v))}</div><div class="l">{esc(k)}</div></div>'
        for k, v in kpi_items
    )
    info = "".join(f"<div><b>{esc(k)}:</b> {esc(v)}</div>" for k, v in meta.items())

    heads = [C_JDATE, C_LINE, C_UNIT, C_EQ, C_PT, "شرح نقطه", C_BRG, C_H, C_V, C_A, C_T, C_ST]
    head_html = "".join(f"<th>{esc(h)}</th>" for h in heads)

    rows = []
    for _, r in df.iterrows():
        cls = "crit" if r[C_ST] == "بحرانی" else ("warn" if r[C_ST] == "هشدار" else "")
        cells = []
        for h in heads:
            val = r.get(h, "")
            if isinstance(val, float):
                val = "—" if np.isnan(val) else f"{val:.2f}"
            if h == C_PT:
                val = fa_num(str(val))
            cells.append(esc(val))
        rows.append(f'<tr class="{cls}">' + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")

    return (
        "<!DOCTYPE html><html lang='fa' dir='rtl'><head><meta charset='utf-8'>"
        f"<title>گزارش پایش ارتعاش</title>{REPORT_CSS}</head><body>"
        f"<h1>گزارش پایش وضعیت ارتعاش - سیمان تهران</h1>"
        f"<div class='sub'>تاریخ تهیه: {esc(fa_num(datetime.now().strftime('%Y/%m/%d - %H:%M')))}</div>"
        f"<div class='box'>{info}</div>"
        f"<div class='kpis'>{kpis}</div>"
        f"<table><thead><tr>{head_html}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        "<div class='foot'>این گزارش به‌صورت خودکار توسط سامانه پایش وضعیت تولید شده است.</div>"
        "</body></html>"
    )


# ==================================================================
# 5) رابط کاربری
# ==================================================================
st.set_page_config(page_title="پایش وضعیت - سیمان تهران", page_icon="📊", layout="wide")


def render_logo(path, caption):
    if os.path.exists(path):
        st.image(path, use_container_width=True)
    else:
        st.markdown(
            f"<div style='border:1px dashed #c9d6e4;border-radius:10px;padding:14px;"
            f"text-align:center;color:#7b8a99;font-size:12px'>{esc(caption)}</div>",
            unsafe_allow_html=True,
        )


c1, c2, c3 = st.columns([1, 4, 1])
with c1:
    render_logo(LOGO_MINE, "لوگوی شرکت")
with c2:
    st.markdown(
        f"<h2 style='text-align:center;margin-bottom:0'>{esc(APP_TITLE)}</h2>"
        f"<p style='text-align:center;color:#7b8a99;font-size:13px'>{esc(APP_SUB)}</p>",
        unsafe_allow_html=True,
    )
with c3:
    render_logo(LOGO_CLIENT, "لوگوی کارخانه")

# ---------------- ورود ----------------
if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.divider()
    st.markdown("### 🔐 ورود به سامانه")
    with st.form("login"):
        email = st.text_input("ایمیل سازمانی", placeholder="name@example.com")
        pwd = st.text_input("رمز عبور", type="password")
        ok = st.form_submit_button("ورود به داشبورد", use_container_width=True)
    if ok:
        e = (email or "").strip().lower()
        if e in USER_DB and USER_DB[e]["password"] == pwd:
            st.session_state.user = e
            st.rerun()
        elif e and e not in USER_DB:
            st.error("این ایمیل در سامانه ثبت نشده است.")
        else:
            st.error("رمز عبور نادرست است.")
    st.caption("رمز پیش‌فرض کاربران: siman123")
    st.stop()

user_email = st.session_state.user
uinfo = USER_DB[user_email]
is_owner = user_email == OWNER_EMAIL
can_send = is_owner or any(k in uinfo["role"] for k in SEND_ROLES)

b1, b2, b3 = st.columns([4, 3, 1])
with b1:
    st.markdown(f"👤 **{esc(uinfo['name'])}** — `{esc(user_email)}` | نقش: {esc(uinfo['role'])}")
with b2:
    st.caption("📨 ارسال اعلان: " + ("✅" if can_send else "⛔") +
               " | ✏️ تغییر داده: " + ("✅" if is_owner else "⛔"))
with b3:
    if st.button("خروج", use_container_width=True):
        st.session_state.user = None
        st.rerun()

st.divider()

# ---------------- بارگذاری ----------------
with st.spinner("در حال دریافت داده از گوگل شیت ..."):
    try:
        raw_vib, raw_ast = load_raw(VIB_CSV_URL, ASSET_CSV_URL)
        load_err = ""
    except Exception as e:
        raw_vib, raw_ast = pd.DataFrame(), pd.DataFrame()
        load_err = str(e)

if load_err:
    st.error("اتصال به گوگل شیت برقرار نشد. پیام فنی: " + load_err)
    st.info("بررسی کن: ۱) شیت برای 'انتشار به وب' تنظیم شده باشد. ۲) شناسه gid شیت Assets درست باشد.")
    st.stop()

assets = build_assets(raw_ast)
df_all = build_vibration(raw_vib)
df_all = merge_bearing(df_all, assets)

if df_all.empty:
    st.error("داده‌ای از شیت ارتعاشات خوانده نشد. ستون‌های مورد نیاز: تاریخ، خط تولید، واحد، عنوان تجهیز، "
             "محل اندازه گیری (یا ستون نقطه)، عمودی، افقی، محوری.")
    st.stop()

with st.sidebar:
    st.markdown("### ℹ️ وضعیت داده")
    st.write("رکورد خام شیت:", len(raw_vib))
    st.write("رکورد معتبر:", len(df_all))
    st.write("تجهیز:", df_all[C_EQ].nunique(), "| نقطه:", df_all[C_PT].nunique())
    st.write("بازه:", df_all[C_JDATE].min(), "تا", df_all[C_JDATE].max())
    st.caption("منبع: گوگل شیت (کش ۵ دقیقه‌ای)")
    if st.button("🔄 بروزرسانی داده", use_container_width=True):
        load_raw.clear()
        st.rerun()

# ---------------- فیلترها ----------------
st.markdown("#### 🔎 فیلترها (خط ➔ واحد ➔ تجهیز ➔ تاریخ)")

f1, f2, f3 = st.columns([2, 2, 3])

lines = ordered_unique(df_all[C_LINE], LINE_PRIORITY)
with f1:
    sel_line = st.selectbox("۱) خط تولید", ["همه خطوط"] + lines)

src_line = df_all if sel_line == "همه خطوط" else df_all[df_all[C_LINE] == sel_line]
units = ordered_unique(src_line[C_UNIT], UNIT_PRIORITY)
with f2:
    sel_unit = st.selectbox("۲) واحد", ["همه واحدها"] + units, key="u_" + sel_line)

src_unit = src_line if sel_unit == "همه واحدها" else src_line[src_line[C_UNIT] == sel_unit]
equips = ordered_unique(src_unit[C_EQ], [])
with f3:
    if len(equips) == 0:
        sel_eq = []
        st.selectbox("۳) عنوان تجهیز", ["-"], disabled=True)
    elif len(equips) == 1:
        sel_eq = [st.selectbox("۳) عنوان تجهیز", equips, key="e1_" + sel_line + sel_unit)]
    else:
        sel_eq = st.multiselect("۳) عنوان تجهیز", equips,
                                default=[equips[0]] if len(equips) < 12 else equips[:1],
                                key="em_" + sel_line + sel_unit)

# اعمال تا اینجا
df = df_all.copy()
if sel_line != "همه خطوط":
    df = df[df[C_LINE] == sel_line]
if sel_unit != "همه واحدها":
    df = df[df[C_UNIT] == sel_unit]
if sel_eq:
    df = df[df[C_EQ].isin(sel_eq)]

# ---------------- فیلتر تاریخ (بعد از تجهیز) ----------------
f4, f5, f6 = st.columns([2, 2, 2])
with f4:
    mode = st.radio("۴) فیلتر تاریخ", ["همه تاریخ‌ها", "بازه تاریخی", "تاریخ‌های خاص"],
                    horizontal=True, key="dmode")

dates_avail = sorted(df[C_JDATE].dropna().unique().tolist())
sel_d1 = sel_d2 = None
sel_dates = []

with f5:
    if mode == "بازه تاریخی":
        if len(dates_avail) >= 1:
            sel_d1 = st.selectbox("از تاریخ", dates_avail, index=0, key="d1")
            sel_d2 = st.selectbox("تا تاریخ", dates_avail, index=len(dates_avail) - 1, key="d2")
        else:
            st.info("تاریخی برای این انتخاب موجود نیست.")
    elif mode == "تاریخ‌های خاص":
        if dates_avail:
            sel_dates = st.multiselect("تاریخ‌ها", dates_avail, key="ds")
        else:
            st.info("تاریخی برای این انتخاب موجود نیست.")
    else:
        st.caption("تمام تاریخ‌های موجود این تجهیز نمایش داده می‌شود.")

if mode == "بازه تاریخی" and sel_d1 and sel_d2:
    if sel_d1 > sel_d2:
        sel_d1, sel_d2 = sel_d2, sel_d1
    df = df[(df[C_JDATE] >= sel_d1) & (df[C_JDATE] <= sel_d2)]
elif mode == "تاریخ‌های خاص" and sel_dates:
    df = df[df[C_JDATE].isin(sel_dates)]

# مسیر فیلتر
path = [sel_line]
if sel_unit != "همه واحدها":
    path.append(sel_unit)
if sel_eq:
    path.append("، ".join(sel_eq[:3]) + (" و ..." if len(sel_eq) > 3 else ""))
if mode == "بازه تاریخی" and sel_d1:
    path.append(f"{sel_d1} تا {sel_d2}")
elif mode == "تاریخ‌های خاص" and sel_dates:
    path.append("، ".join(sel_dates[:4]))
with f6:
    st.caption("🧭 مسیر: " + " ➔ ".join(path))
    st.caption(f"تعداد رکورد: {fa_num(len(df))}")

st.divider()

# ---------------- KPI ----------------
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("کل رکورد", fa_num(len(df)))
k2.metric("بحرانی", fa_num(int((df[C_ST] == "بحرانی").sum())))
k3.metric("هشدار", fa_num(int((df[C_ST] == "هشدار").sum())))
k4.metric("تجهیز", fa_num(df[C_EQ].nunique()))
k5.metric("میانگین بیشینه", f"{df['_mx'].mean():.2f} mm/s" if not df.empty else "—")

# ---------------- تب‌ها ----------------
tab1, tab2, tab3, tab4 = st.tabs(["📋 جدول داده‌ها", "📈 نمودارها", "📨 ارسال اعلان", "👥 کاربران"])

VIEW_COLS = [C_JDATE, C_LINE, C_UNIT, C_EQ, C_PT, C_PTNAME, C_BRG,
             C_H, C_V, C_A, C_T, C_ST, C_DESC, C_ACT, C_PRI]

with tab1:
    if df.empty:
        st.info("با این فیلترها رکوردی یافت نشد.")
    else:
        show = df.copy()
        show["وضعیت"] = show[C_ST].map(
            lambda s: {"بحرانی": "🔴 بحرانی", "هشدار": "🟡 هشدار", "نرمال": "🟢 نرمال"}.get(s, s))
        show = show.rename(columns={"وضعیت": "وضعیت"})
        st.dataframe(show[VIEW_COLS], use_container_width=True, height=520,
                     column_config={
                         C_JDATE: st.column_config.TextColumn("تاریخ شمسی", width="small"),
                         C_PT: st.column_config.TextColumn("نقطه", width="small"),
                     })

        d1, d2 = st.columns(2)
        with d1:
            st.download_button(
                "⬇️ دانلود CSV",
                data=df[VIEW_COLS].to_csv(index=False).encode("utf-8-sig"),
                file_name="vibration_data.csv", mime="text/csv",
                use_container_width=True,
            )
        with d2:
            meta = {
                "مسیر فیلتر": " ➔ ".join(path),
                "حالت تاریخ": mode,
                "بازه نمایش": f"{df[C_JDATE].min()} تا {df[C_JDATE].max()}",
                "تهیه‌کننده": f"{uinfo['name']} - {uinfo['role']}",
                "آستانه‌ها": f"هشدار {TH_WARN} | بحرانی {TH_CRIT} (mm/s)",
            }
            st.download_button(
                "🧾 گزارش HTML (قابل چاپ به PDF)",
                data=build_report_html(df, meta).encode("utf-8"),
                file_name=f"vibration_report_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
                mime="text/html", use_container_width=True,
            )
        st.caption("برای PDF: فایل را در مرورگر باز کن و Ctrl+P → Save as PDF.")

with tab2:
    if df.empty:
        st.info("داده‌ای برای نمودار نیست.")
    else:
        ch1, ch2 = st.columns(2)

        with ch1:
            fig = go.Figure()
            for col, name, color in ((C_H, "افقی", "#2563eb"), (C_V, "عمودی", "#16a34a"), (C_A, "محوری", "#dc2626")):
                tmp = df.dropna(subset=[col])
                if not tmp.empty:
                    fig.add_trace(go.Scatter(x=tmp[C_JDATE], y=tmp[col], mode="markers+lines",
                                             name=name, marker=dict(size=7, color=color), line=dict(color=color)))
            fig.add_hline(y=TH_WARN, line_dash="dash", line_color="#f59e0b",
                          annotation_text="هشدار ۴/۵")
            fig.add_hline(y=TH_CRIT, line_dash="dash", line_color="#dc2626",
                          annotation_text="بحرانی ۷")
            fig.update_layout(title="روند ارتعاش (mm/s)", height=400,
                              yaxis_title="mm/s", xaxis_title="تاریخ")
            st.plotly_chart(fig, use_container_width=True)

        with ch2:
            worst = (df.dropna(subset=["_mx"])
                       .sort_values("_mx", ascending=False)
                       .drop_duplicates(subset=[C_EQ, C_PT])
                       .head(12))
            if not worst.empty:
                worst = worst.assign(label=worst[C_EQ] + " - " + worst[C_PT])
                fig2 = px.bar(worst.sort_values("_mx"), x="_mx", y="label", orientation="h",
                              color=C_ST,
                              color_discrete_map={"بحرانی": "#dc2626", "هشدار": "#f59e0b", "نرمال": "#16a34a"},
                              title="۱۲ نقطه با بیشترین ارتعاش")
                fig2.update_layout(height=400, yaxis_title="", xaxis_title="mm/s", showlegend=True)
                st.plotly_chart(fig2, use_container_width=True)

        ch3, ch4 = st.columns(2)
        with ch3:
            cnt = df[C_ST].value_counts().reset_index()
            cnt.columns = ["وضعیت", "تعداد"]
            fig3 = px.pie(cnt, names="وضعیت", values="تعداد", hole=0.5,
                          title="سهم وضعیت‌ها",
                          color="وضعیت",
                          color_discrete_map={"بحرانی": "#dc2626", "هشدار": "#f59e0b", "نرمال": "#16a34a"})
            fig3.update_layout(height=380)
            st.plotly_chart(fig3, use_container_width=True)

        with ch4:
            tmp = df.dropna(subset=[C_T])
            if not tmp.empty:
                fig4 = px.line(tmp, x=C_JDATE, y=C_T, color=C_PT if tmp[C_PT].nunique() <= 6 else None,
                               markers=True, title="روند دما (°C)")
                fig4.update_layout(height=380, xaxis_title="تاریخ", yaxis_title="°C")
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("ستون دما در شیت ارتعاشات موجود نیست یا خالی است.")
                pts = df.groupby(C_PT)["_mx"].mean().reset_index()
                fig4 = px.bar(pts, x=C_PT, y="_mx", title="میانگین ارتعاش هر نقطه")
                fig4.update_layout(height=380)
                st.plotly_chart(fig4, use_container_width=True)

with tab3:
    st.markdown("#### 📨 ارسال اعلان وضعیت بحرانی")
    crit = df[df[C_ST] == "بحرانی"].copy()
    if crit.empty:
        st.success("در بازه انتخاب‌شده هیچ رکورد بحرانی ثبت نشده است. ✅")
    elif not can_send:
        st.warning("نقش کاربری شما مجوز ارسال اعلان ندارد.")
    else:
        st.error(f"🔴 {fa_num(crit[C_EQ].nunique())} تجهیز با وضعیت بحرانی در بازه انتخابی.")
        crit["_line"] = (crit[C_EQ] + " | نقطه " + crit[C_PT] + " | " +
                         crit[C_JDATE] + " | بیشینه " + crit["_mx"].round(2).astype(str) + " mm/s")
        body = "گزارش پایش وضعیت - سیمان تهران\n"
        body += f"مسیر: {' ➔ '.join(path)}\n"
        body += "=" * 40 + "\n"
        body += "\n".join(crit["_line"].tolist())
        body += "\n\n" + "=" * 40 + "\n"
        body += f"تهیه‌کننده: {uinfo['name']} ({uinfo['role']})\n"

        rcpt = st.multiselect("گیرندگان", list(USER_DB.keys()),
                              default=[OWNER_EMAIL], format_func=lambda x: f"{USER_DB[x]['name']} - {USER_DB[x]['role']}")
        subject = st.text_input("موضوع", "🚨 هشدار بحرانی ارتعاش - سیمان تهران")
        body = st.text_area("متن اعلان", body, height=260)
        st.download_button("⬇️ دانلود متن اعلان", body.encode("utf-8-sig"),
                           file_name="alert.txt", mime="text/plain")
        if rcpt:
            import urllib.parse
            mailto = "mailto:" + ",".join(rcpt) + "?subject=" + \
                     urllib.parse.quote(subject) + "&body=" + urllib.parse.quote(body)
            st.markdown(f"[📧 باز کردن برنامه ایمیل و ارسال به {fa_num(len(rcpt))} گیرنده]({mailto})")
            st.caption("برای ارسال خودکار بدون دخالت کاربر، تنظیم SMTP لازم است.")

with tab4:
    st.markdown("#### 👥 کاربران سامانه")
    udf = pd.DataFrame([{"نام": v["name"], "ایمیل": k, "نقش": v["role"],
                         "ارسال اعلان": "✅" if (k == OWNER_EMAIL or any(x in v["role"] for x in SEND_ROLES)) else "⛔"}
                        for k, v in USER_DB.items()])
    st.dataframe(udf, use_container_width=True, hide_index=True)

    if is_owner:
        st.markdown("##### ✏️ تغییر رمز (در حافظه همین نشست)")
        with st.form("pw"):
            target = st.selectbox("کاربر", list(USER_DB.keys()),
                                  format_func=lambda x: f"{USER_DB[x]['name']} ({x})")
            newpw = st.text_input("رمز جدید", type="password")
            if st.form_submit_button("ثبت رمز"):
                if newpw and len(newpw) >= 6:
                    USER_DB[target]["password"] = newpw
                    st.success("رمز در این نشست تغییر کرد. برای دائمی شدن، مقدار USER_DB را در کد ویرایش کن.")
                else:
                    st.warning("رمز باید حداقل ۶ نویسه باشد.")
    else:
        st.caption("ویرایش کاربران فقط برای مالک سیستم فعال است.")
