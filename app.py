# -*- coding: utf-8 -*-
# ============================================================================
#  داشبورد پایش ارتعاشات  |  نسخه ۶ (نسخه نهایی - جایگزین کد قبلی)
#  ویژگی‌ها:
#   ۱) رفع کامل مشکل به‌هم‌چسبیدن کلمات فارسی (خودترمیم متن)
#   ۲) اتصال «کد تجهیز» به «نام استاندارد» از شیت لیست تجهیزات (مثل VLOOKUP)
#   ۳) نمایش راست‌به‌چپ و فونت فارسی در همه بخش‌ها
#   ۴) پشتیبانی از تاریخ شمسی (۱۴۰۴/۰۸/۲۹)
#   ۵) ناحیه‌بندی استاندارد ISO 10816
#   ۶) فیلتر، نمودار، جدول و خروجی CSV
# ============================================================================

from __future__ import annotations

import re
from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

# ============================================================================
# بخش ۰ | تنظیمات اصلی  ← فقط همین چند خط را با مقادیر خودت تطبیق بده
# ============================================================================

SHEET_URL = st.secrets.get("SHEET_URL", "https://docs.google.com/spreadsheets/d/XXXX/edit")
SHEET_DATA = st.secrets.get("SHEET_DATA", "ارتعاشات")          # نام شیت داده‌ها
SHEET_EQUIP = st.secrets.get("SHEET_EQUIP", "لیست تجهیزات")     # نام شیت لیست تجهیزات
CREDS_FILE = "creds.json"                                       # فایل کلید سرویس‌اکانت

# نام‌های ممکن هر ستون در گوگل‌شیت (هر کدام پیدا شد، استفاده می‌شود)
ALIASES = {
    "code":  ["کد تجهیز", "کد", "کدتجهیز", "tag", "Tag", "equipment_code", "کد دستگاه"],
    "name":  ["نام تجهیز", "تجهیز", "نام دستگاه", "equipment", "equipment_name", "عنوان تجهیز"],
    "date":  ["تاریخ", "تاریخ ثبت", "date", "Date", "تاریخ اندازه‌گیری"],
    "rms":   ["RMS", "rms", "مقدار ارتعاش", "ارتعاش", "vibration", "Vibration", "RMS (mm/s)"],
    "temp":  ["دما", "temperature", "Temperature", "دمای روغن"],
    "point": ["نقطه", "جهت", "محل اندازه‌گیری", "point", "موقعیت"],
    "unit":  ["واحد", "unit", "واحد اندازه‌گیری"],
}

# ============================================================================
# بخش ۱ | تنظیمات صفحه و استایل راست‌به‌چپ
# ============================================================================

st.set_page_config(page_title="پایش ارتعاشات", page_icon="📊", layout="wide")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600&display=swap');
    html, body, [class*="css"], .stMarkdown, .stDataFrame, table,
    button, input, select, textarea, label, h1, h2, h3, h4, h5, h6 {
        font-family: "Vazirmatn", "Tahoma", "Segoe UI", sans-serif !important;
    }
    .stApp { direction: rtl; text-align: right; }
    [data-testid="stSidebar"] { direction: rtl; text-align: right; }
    .kpi-box {
        background: #f7f9fc; border: 1px solid #e3e8ef; border-radius: 14px;
        padding: 14px 18px; text-align: center;
    }
    .kpi-box .lbl { font-size: 13px; color: #64748b; }
    .kpi-box .val { font-size: 26px; font-weight: 700; color: #0f172a; }
    .vib-table { width: 100%; border-collapse: collapse; direction: rtl; font-size: 14px; }
    .vib-table th { background: #eef2f7; padding: 10px 8px; border: 1px solid #dbe2eb; }
    .vib-table td {
        padding: 9px 8px; border: 1px solid #e6ebf2;
        white-space: normal !important; word-wrap: break-word; line-height: 1.9;
    }
    .vib-table tr:nth-child(even) td { background: #fafcfe; }
    .zone-A td { border-right: 5px solid #16a34a !important; }
    .zone-B td { border-right: 5px solid #84cc16 !important; }
    .zone-C td { border-right: 5px solid #f59e0b !important; }
    .zone-D td { border-right: 5px solid #dc2626 !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# بخش ۲ | ابزارهای متن فارسی
# ============================================================================

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _RESHAPE_OK = True
except Exception:
    _RESHAPE_OK = False


def fa(text):
    """آماده‌سازی متن فارسی برای رسم در نمودار (در صورت نصب بودن کتابخانه‌ها)."""
    if not isinstance(text, str) or not text.strip() or not _RESHAPE_OK:
        return text
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


AR_DIGITS = {ord(a): ord(b) for a, b in zip("٠١٢٣٤٥٦٧٨٩", "0123456789")}
FA_DIGITS = {ord(a): ord(b) for a, b in zip("۰۱۲۳۴۵۶۷۸۹", "0123456789")}
INVISIBLE = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff]")


def normalize(text) -> str:
    """یکسان‌سازی ارقام، حذف کاراکترهای نامرئی و فشرده‌سازی فاصله‌ها."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    s = str(text).translate(AR_DIGITS).translate(FA_DIGITS)
    s = INVISIBLE.sub("", s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def build_lexicon(names) -> set:
    """ساخت دیکشنری کلمات مجاز از روی «لیست تجهیزات»."""
    lex = set()
    for n in names:
        for tok in re.split(r"[\s\u200c\-_/،,()\[\]«»\"'.:؛:]+", normalize(n)):
            tok = tok.strip()
            if len(tok) >= 2:
                lex.add(tok)
    return lex


def segment_token(tok: str, lexicon: set, max_len: int = 14) -> str:
    """بازسازی مرز کلمات چسبیده با «تطبیق حریصانه با دیکشنری»."""
    chunks, buf, i, n = [], "", 0, len(tok)
    while i < n:
        best = None
        for L in range(min(max_len, n - i), 1, -1):
            if tok[i:i + L] in lexicon:
                best = tok[i:i + L]
                break
        if best:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(best)
            i += len(best)
        else:
            buf += tok[i]
            i += 1
    if buf:
        chunks.append(buf)
    return " ".join(chunks)


def smart_clean(text, lexicon: set, enable: bool = True) -> str:
    """پاک‌سازی و خودترمیم نام‌ها: «آسیابسیمان9» ← «آسیاب سیمان 9»"""
    s = normalize(text)
    if not s:
        return ""
    # فاصله بین حرف و عدد (هر دو جهت) — دشمن شماره یک به‌هم‌چسبیدگی
    s = re.sub(r"(?<=[^\W\d_])(?=\d)", " ", s)
    s = re.sub(r"(?<=\d)(?=[^\W\d_])", " ", s)

    # تبدیل نیم‌فاصله به فاصله فقط برای تشخیص مرز (نمایش نهایی با فاصله است)
    s = s.replace("\u200c", " ")
    s = re.sub(r"[ ]{2,}", " ", s).strip()

    if not enable or not lexicon:
        return s

    fixed = []
    for part in s.split(" "):
        if len(part) > 3 and part not in lexicon and re.search(r"[^\W\d_]", part):
            fixed.append(segment_token(part, lexicon))
        else:
            fixed.append(part)
    return " ".join(fixed)


# ---------------------------- تاریخ شمسی ----------------------------

def jalali_to_gregorian(jy: int, jm: int, jd: int):
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    days += (jm - 1) * 31 if jm < 7 else ((jm - 7) * 30 + 186)
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
    sal = [0, 31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 13 and gd > sal[gm]:
        gd -= sal[gm]
        gm += 1
    return gy, gm, gd


def parse_date(value):
    s = normalize(value)
    if not s:
        return pd.NaT
    m = re.match(r"^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            if 1300 <= y <= 1500:
                gy, gm, gd = jalali_to_gregorian(y, mo, d)
                return pd.Timestamp(gy, gm, gd)
            return pd.Timestamp(y, mo, d)
        except Exception:
            return pd.NaT
    return pd.to_datetime(s, errors="coerce")


# ============================================================================
# بخش ۳ | خواندن داده از گوگل‌شیت (با حالت نمایشی در صورت قطعی)
# ============================================================================

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]


@st.cache_resource(show_spinner=False)
def get_client():
    import gspread
    from google.oauth2.service_account import Credentials
    try:
        info = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    except Exception:
        creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


@st.cache_data(ttl=180, show_spinner="در حال خواندن گوگل‌شیت ...")
def load_sheet(sheet_name: str) -> pd.DataFrame:
    client = get_client()
    ws = client.open_by_url(SHEET_URL).worksheet(sheet_name)
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header = [str(c).strip() for c in values[0]]
    return pd.DataFrame(values[1:], columns=header)


def demo_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """داده نمونه تا وقتی اتصال برقرار نشده (برای تست سریع)."""
    equip = pd.DataFrame({
        "کد تجهیز": ["EQ-101", "EQ-102", "EQ-103", "EQ-104", "EQ-105"],
        "نام تجهیز": ["آسیاب سیمان ۹", "نوار نقاله باند ۰۲۰", "فن آسپیراسیون",
                      "گیربکس اصلی آسیاب ۸", "الواتور سیمان"],
    })
    rows, base = [], date.today() - timedelta(days=30)
    rng = np.random.default_rng(7)
    for k in range(30):
        for code in equip["کد تجهیز"]:
            rows.append({
                "کد تجهیز": code,
                "تاریخ": (base + timedelta(days=k)).strftime("%Y-%m-%d"),
                "RMS": round(float(rng.uniform(1.2, 8.5)), 2),
                "دما": round(float(rng.uniform(35, 78)), 1),
                "نقطه": str(rng.choice(["افقی", "عمودی", "محوری"])),
                "واحد": "mm/s",
            })
    return pd.DataFrame(rows), equip


# ============================================================================
# بخش ۴ | آماده‌سازی داده
# ============================================================================

def pick(df: pd.DataFrame, key: str):
    for alias in ALIASES[key]:
        if alias in df.columns:
            return alias
    return None


def prepare(raw: pd.DataFrame, equip: pd.DataFrame, fix_text: bool) -> tuple[pd.DataFrame, set, list]:
    df = raw.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # --- لیست استاندارد تجهیزات ---
    e_code, e_name = pick(equip, "code"), pick(equip, "name")
    equip_names, code2name = [], {}
    if e_name:
        for _, r in equip.iterrows():
            nm = normalize(r[e_name])
            if nm:
                equip_names.append(nm)
                if e_code and normalize(r[e_code]):
                    code2name[normalize(r[e_code])] = nm

    lexicon = build_lexicon(equip_names)

    # --- ستون‌های شیت داده ---
    c_code, c_name = pick(df, "code"), pick(df, "name")
    c_date, c_rms = pick(df, "date"), pick(df, "rms")
    c_temp, c_point = pick(df, "temp"), pick(df, "point")

    if not c_rms:
        st.error("ستون «RMS» در شیت پیدا نشد. نام ستون‌ها را در دیکشنری ALIASES اضافه کن.")
        st.stop()

    out = pd.DataFrame()
    out["تاریخ"] = df[c_date].apply(parse_date) if c_date else pd.Timestamp.today()
    out["RMS"] = pd.to_numeric(df[c_rms].astype(str).str.replace(",", ""), errors="coerce")
    out["دما"] = pd.to_numeric(df[c_temp], errors="coerce") if c_temp else np.nan
    out["نقطه"] = df[c_point].astype(str) if c_point else "—"

    # --- تعیین نام استاندارد تجهیز ---
    if c_code and code2name:
        out["کد تجهیز"] = df[c_code].apply(normalize)
        out["نام تجهیز"] = out["کد تجهیز"].map(code2name)
    elif c_name:
        out["کد تجهیز"] = "—"
        out["نام تجهیز"] = df[c_name]
    else:
        st.error("نه «کد تجهیز» و نه «نام تجهیز» در شیت وجود ندارد.")
        st.stop()

    # اصلاح متن و تطبیق با لیست استاندارد
    fixed_log = []
    names, codes = [], []
    for code, nm in zip(out["کد تجهیز"], out["نام تجهیز"].fillna("")):
        original = normalize(nm)
        cleaned = smart_clean(original, lexicon, enable=fix_text) if fix_text else original
        codes.append(code)

        if cleaned in equip_names:
            names.append(cleaned)
        else:
            match = None
            if equip_names:
                import difflib
                hit = difflib.get_close_matches(cleaned, equip_names, n=1, cutoff=0.82)
                match = hit[0] if hit else None
            names.append(match or cleaned)
            if cleaned != original or (match and match != original):
                fixed_log.append({"مقدار اصلی": original, "اصلاح‌شده": names[-1]})

    out["کد تجهیز"] = codes
    out["نام تجهیز"] = names

    out = out.dropna(subset=["RMS"]).reset_index(drop=True)
    out["مقدار ارتعاش"] = out["RMS"]
    out["تاریخ"] = pd.to_datetime(out["تاریخ"], errors="coerce")
    return out, lexicon, fixed_log


def iso_zone(v: float) -> str:
    if pd.isna(v):
        return "—"
    if v < 1.8:
        return "A"
    if v < 4.5:
        return "B"
    if v < 11.0:
        return "C"
    return "D"


ZONE_LABEL = {"A": "خوب", "B": "قابل قبول", "C": "هشدار", "D": "خطر"}

# ============================================================================
# بخش ۵ | بارگذاری
# ============================================================================

st.title("📊 داشبورد پایش ارتعاشات")

raw, equip = pd.DataFrame(), pd.DataFrame()
try:
    raw = load_sheet(SHEET_DATA)
    equip = load_sheet(SHEET_EQUIP)
    is_demo = False
    if raw.empty:
        raise ValueError("شیت داده خالی است")
except Exception as exc:
    raw, equip = demo_data()
    is_demo = True
    st.caption(f"⚠️ اتصال به گوگل‌شیت برقرار نشد، داده‌های نمایشی استفاده شد. ({type(exc).__name__})")

with st.sidebar:
    st.header("⚙️ تنظیمات")
    fix_text = st.toggle("خودترمیم متن فارسی", value=True,
                         help="جدا کردن کلمات و اعداد چسبیده بر اساس لیست تجهیزات")
    st.divider()

df, LEXICON, FIXED_LOG = prepare(raw, equip, fix_text)

if df.empty:
    st.warning("داده‌ای برای نمایش وجود ندارد.")
    st.stop()

# ============================================================================
# بخش ۶ | فیلترها
# ============================================================================

valid_dates = df["تاریخ"].dropna()
min_d, max_d = (valid_dates.min().date(), valid_dates.max().date()) if len(valid_dates) else (
    date.today() - timedelta(days=30), date.today())

with st.sidebar:
    st.subheader("🔎 فیلترها")
    rng = st.date_input("بازه تاریخ", value=(min_d, max_d),
                        min_value=min_d, max_value=max_d, format="YYYY-MM-DD")

    all_names = sorted(df["نام تجهیز"].dropna().unique().tolist())
    chosen = st.multiselect("تجهیزات", all_names, default=all_names)

    max_rms = float(np.nanmax(df["RMS"])) if df["RMS"].notna().any() else 10.0
    rms_limit = st.slider("حد نمایش RMS (mm/s)", 0.0, max(15.0, round(max_rms + 1, 1)),
                          (0.0, max(15.0, round(max_rms + 1, 1))), 0.5)
    st.caption("تاریخ‌ها را میلادی وارد کن؛ نمایش شمسی جداگانه است.")

start_d, end_d = (rng if isinstance(rng, (tuple, list)) and len(rng) == 2 else (min_d, max_d))
mask = (
    df["نام تجهیز"].isin(chosen)
    & df["تاریخ"].dt.date.between(start_d, end_d)
    & df["RMS"].between(rms_limit[0], rms_limit[1])
)
flt = df.loc[mask].copy()
flt["ناحیه"] = flt["RMS"].apply(iso_zone)

# ============================================================================
# بخش ۷ | شاخص‌های کلیدی
# ============================================================================

k1, k2, k3, k4 = st.columns(4)
avg_rms = flt["RMS"].mean() if len(flt) else np.nan
danger = int((flt["ناحیه"].isin(["C", "D"])).sum()) if len(flt) else 0
for col, lbl, val in [
    (k1, "تعداد اندازه‌گیری", f"{len(flt):,}"),
    (k2, "تعداد تجهیزات", f"{flt['نام تجهیز'].nunique():,}"),
    (k3, "میانگین RMS (mm/s)", "—" if pd.isna(avg_rms) else f"{avg_rms:.2f}"),
    (k4, "اندازه‌گیری در ناحیه هشدار/خطر", f"{danger:,}"),
]:
    with col:
        st.markdown(f'<div class="kpi-box"><div class="lbl">{lbl}</div>'
                    f'<div class="val">{val}</div></div>', unsafe_allow_html=True)

st.write("")

# ============================================================================
# بخش ۸ | نمودارها
# ============================================================================

if flt.empty:
    st.info("با این فیلترها داده‌ای باقی نماند.")
else:
    import plotly.express as px
    import plotly.graph_objects as go

    LAYOUT = dict(
        font=dict(family="Vazirmatn, Tahoma", size=13),
        margin=dict(l=40, r=30, t=60, b=40),
        hoverlabel=dict(font_family="Vazirmatn, Tahoma"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
    )

    t1, t2 = st.tabs(["📈 روند زمانی", "🏭 مقایسه تجهیزات"])

    with t1:
        trend = (flt.dropna(subset=["تاریخ"])
                    .groupby(["تاریخ", "نام تجهیز"], as_index=False)["RMS"].mean())
        if trend.empty:
            st.info("تاریخ معتبری برای رسم روند موجود نیست.")
        else:
            fig = px.line(trend, x="تاریخ", y="RMS", color="نام تجهیز", markers=True,
                          title="روند میانگین ارتعاش (mm/s)")
            for thr, color in [(1.8, "#84cc16"), (4.5, "#f59e0b"), (11.0, "#dc2626")]:
                fig.add_hline(y=thr, line_dash="dot", line_color=color,
                              annotation_text=f"حد {thr}", annotation_font_size=11)
            fig.update_layout(**LAYOUT, height=460)
            st.plotly_chart(fig, use_container_width=True)

    with t2:
        left, right = st.columns([3, 2])
        with left:
            bar = (flt.groupby("نام تجهیز", as_index=False)["RMS"].mean()
                      .sort_values("RMS", ascending=False))
            fig2 = px.bar(bar, x="نام تجهیز", y="RMS", color="RMS",
                          color_continuous_scale=["#16a34a", "#84cc16", "#f59e0b", "#dc2626"],
                          title="میانگین ارتعاش هر تجهیز")
            fig2.update_layout(**LAYOUT, height=440, coloraxis_showscale=False)
            fig2.update_xaxes(tickangle=-25)
            st.plotly_chart(fig2, use_container_width=True)

        with right:
            dist = flt["ناحیه"].value_counts().reindex(["A", "B", "C", "D"]).fillna(0)
            labels = [f"{z} - {ZONE_LABEL[z]}" for z in dist.index]
            fig3 = go.Figure(go.Pie(labels=labels, values=dist.values, hole=0.55,
                                    marker_colors=["#16a34a", "#84cc16", "#f59e0b", "#dc2626"]))
            fig3.update_layout(**LAYOUT, height=440, title="توزیع نواحی ISO 10816")
            st.plotly_chart(fig3, use_container_width=True)

# ============================================================================
# بخش ۹ | جدول داده‌ها (HTML راست‌به‌چپ با شکستن صحیح کلمات)
# ============================================================================

st.subheader("📋 داده‌های فیلترشده")

show = flt.copy()
if "تاریخ" in show:
    show["تاریخ نمایش"] = show["تاریخ"].dt.strftime("%Y-%m-%d").fillna("—")

cols = ["کد تجهیز", "نام تجهیز", "تاریخ نمایش", "نقطه", "RMS", "دما", "ناحیه"]
cols = [c for c in cols if c in show.columns]
table = show[cols].head(400)

head_html = "".join(f"<th>{c}</th>" for c in table.columns)
rows_html = []
for _, r in table.iterrows():
    zone = str(r.get("ناحیه", "—"))
    cells = "".join(f"<td>{'' if pd.isna(r[c]) else r[c]}</td>" for c in table.columns)
    rows_html.append(f'<tr class="zone-{zone}">{cells}</tr>')

st.markdown(
    f'<div style="overflow-x:auto"><table class="vib-table">'
    f"<thead><tr>{head_html}</tr></thead><tbody>{''.join(rows_html)}</tbody></table></div>",
    unsafe_allow_html=True,
)
if len(show) > 400:
    st.caption(f"فقط ۴۰۰ ردیف اول از {len(show):,} ردیف نمایش داده شد.")

# ============================================================================
# بخش ۱۰ | گزارش خودترمیم و خروجی
# ============================================================================

c1, c2 = st.columns(2)

with c1:
    with st.expander(f"🧹 گزارش اصلاح متن ({len(FIXED_LOG)} مورد)"):
        if FIXED_LOG:
            st.dataframe(pd.DataFrame(FIXED_LOG).drop_duplicates().head(200),
                         use_container_width=True, hide_index=True)
        else:
            st.success("هیچ متنی نیاز به اصلاح نداشت؛ همه نام‌ها استاندارد بودند.")

with c2:
    csv = show.drop(columns=["تاریخ نمایش"], errors="ignore").to_csv(
        index=False, encoding="utf-8-sig")
    st.download_button("⬇️ دانلود خروجی CSV", data=csv,
                       file_name="vibration_report.csv", mime="text/csv",
                       use_container_width=True)

with st.expander("ℹ️ راهنمای سریع"):
    st.markdown("""
- **کد تجهیز** باید با ستون کد در شیت «لیست تجهیزات» یکی باشد؛ نام استاندارد خودکار جایگزین می‌شود (مثل VLOOKUP).
- اگر نامی در لیست نبود، سیستم با دیکشنری کلمات، چسبیدگی‌ها را باز می‌کند و نزدیک‌ترین نام استاندارد را انتخاب می‌کند.
- نواحی ISO 10816: **A** زیر ۱٫۸ | **B** تا ۴٫۵ | **C** تا ۱۱ | **D** بالای ۱۱ (mm/s).
""")

st.caption("نسخه ۶ | خودترمیم متن + اتصال کد تجهیز فعال")
