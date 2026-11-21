# -*- coding: utf-8 -*-
"""
سامانه پایش وضعیت تجهیزات سیمان تهران
نسخه ۹  |  بازنویسی کامل بر اساس ساختار واقعی دو شیت (Vib / Assets)
توسعه: مهندس هادی زندیه - فاز فیدار پارسیان
"""

import re
import base64
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

# ===============================================================
# 0) تنظیمات صفحه
# ===============================================================
st.set_page_config(page_title="پایش وضعیت تجهیزات سیمان تهران", layout="wide")

# ===============================================================
# 1) ورود کاربران
# ===============================================================
USER_CREDENTIALS = {
    "alireza76ir@gmail.com": "siman123",
    "vah.rezaei@gmail.com": "siman123",
    "cm.zandiyeh@gmail.com": "siman123",
    "m.babahasan@gmail.com": "siman123",
    "freedocs.ir@gmail.com": "siman123",
    "tehrancement@gmail.com": "siman123",
    "masoud.sa.1989823@gmail.com": "siman123",
}


def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return True

    st.markdown(
        "<h2 style='text-align:center;font-family:Tahoma;color:#1E3A8D;'>"
        "🔐 ورود به سامانه هوشمند پایش وضعیت سیمان تهران</h2>",
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        email = st.text_input("ایمیل کاربری:")
        password = st.text_input("رمز عبور:", type="password")
        submitted = st.form_submit_button("ورود به داشبورد")

        if submitted:
            email_clean = email.strip().lower()
            found = None
            for key in USER_CREDENTIALS:
                if key.strip().lower() == email_clean:
                    found = key
                    break

            if found and USER_CREDENTIALS[found].strip() == password.strip():
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ ایمیل یا رمز عبور اشتباه است.")
    return False


if not check_password():
    st.stop()


# ===============================================================
# 2) توابع کمکی
# ===============================================================
FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
EN_DIGITS = "0123456789"


def norm(x):
    """یکسان‌سازی متن فارسی/عربی/لاتین و حذف نویزها"""
    if x is None:
        return ""
    s = str(x).strip()
    if s.lower() in ("nan", "none", "nat"):
        return ""
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = (s.replace("ي", "ی").replace("ى", "ی").replace("ك", "ک")
          .replace("ۀ", "ه").replace("ة", "ه").replace("أ", "ا")
          .replace("إ", "ا").replace("آ", "ا"))
    s = (s.replace("\u200c", " ").replace("\xa0", " ")
          .replace("-", " ").replace("_", " ").replace(".", " ")
          .replace("(", " ").replace(")", " ").replace("،", " "))
    return " ".join(s.split()).lower()


def clean_num_text(x):
    """تبدیل نمایش عدد فارسی به عدد قابل تبدیل"""
    s = str(x).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = s.replace("٫", ".").replace("،", ".").replace(",", ".")
    s = s.replace(" ", "").replace("mm/s", "").replace("µm", "").replace("°c", "")
    return s


def to_num(series):
    s = series.map(clean_num_text)
    s = s.replace({"": None, "nan": None, "None": None, "---": None, "NaN": None, "-": None})
    return pd.to_numeric(s, errors="coerce")


def is_number(v):
    s = clean_num_text(v)
    if s in ("", "-", "nan", "None"):
        return False
    try:
        float(s)
        return True
    except Exception:
        return False


def numeric_ratio(series):
    vals = [str(v).strip() for v in series.tolist()]
    vals = [v for v in vals if v not in ("", "nan", "None", "NaN", "-")]
    if not vals:
        return 0.0
    ok = sum(1 for v in vals if is_number(v))
    return ok / float(len(vals))


def first_nonempty(series):
    for v in series.tolist():
        s = str(v).strip()
        if s not in ("", "nan", "None", "NaN", "-"):
            return s
    return ""


def find_col(columns, keywords, exclude=None):
    """پیدا کردن نام ستون با کلیدواژه (اول تطابق کامل، بعد تطابق جزئی)"""
    if columns is None:
        return None
    cols = [c for c in columns if not (exclude and c in exclude)]
    if not cols:
        return None
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if norm(c) == nk:
                return c
    for k in keywords:
        nk = norm(k)
        for c in cols:
            if nk and nk in norm(c):
                return c
    return None


def date_key(val):
    """
    کلید مرتب‌سازی تاریخ شمسی.
    نکته: عمداً از عملگر ضرب استفاده نشده تا هنگام کپی‌پیست، علامت‌ها از بین نروند.
    """
    s = norm(val)
    m = re.search(r"(\d{2,4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})", s)
    if m:
        y = int(m.group(1))
        mo = int(m.group(2))
        d = int(m.group(3))
        if y < 100:
            y = y + 1400
        return int("{}{:02d}{:02d}".format(y, mo, d))
    m = re.search(r"(\d{6,8})", s)
    if m:
        return int(m.group(1))
    return 0


def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100)
            + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1])
    jy = -1595 + (33 * (days // 12053))
    days = days % 12053
    jy = jy + (4 * (days // 1461))
    days = days % 1461
    if days > 365:
        jy = jy + ((days - 1) // 365)
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def today_key():
    now = datetime.now()
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    return int("{}{:02d}{:02d}".format(jy, jm, jd))


def get_image_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""


def point_guide(eq_name, eq_type=""):
    name = norm(eq_name) + " " + norm(eq_type)
    if "گیربکس" in name:
        return [
            ("P1", "انتهای موتور"),
            ("P2", "جلوی موتور"),
            ("P3", "محور ورودی گیربکس"),
            ("P4", "سمت آزاد محور ورودی"),
            ("P5", "سمت فیکس محور دوم"),
            ("P6", "سمت آزاد محور دوم"),
            ("P7", "سمت فیکس محور سوم"),
            ("P8", "سمت آزاد محور سوم"),
            ("P9", "بابیت اول سمت گیربکس"),
            ("P10", "بابیت دوم"),
            ("P11", "بابیت نزدیک پینیون آسیاب"),
        ]
    if "کراشر" in name or "سنگ شکن" in name or "سنگ‌شکن" in name:
        return [
            ("P1", "انتهای موتور"),
            ("P2", "سر موتور"),
            ("P3", "یاتاقان سمت فیکس (پولی کوچک)"),
            ("P4", "یاتاقان سمت آزاد (پولی کوچک)"),
            ("P5", "یاتاقان فیکس روتور"),
            ("P6", "یاتاقان سمت آزاد روتور"),
        ]
    if "فن" in name:
        return [
            ("P1", "انتهای موتور"),
            ("P2", "سر موتور"),
            ("P3", "یاتاقان فیکس"),
            ("P4", "یاتاقان آزاد"),
        ]
    if "بلوئر" in name:
        return [
            ("P1", "انتهای موتور"),
            ("P2", "سر موتور"),
            ("P3", "محور ورود بلوئر"),
            ("P4", "انتهای بلوئر"),
        ]
    if "کمپرسور" in name:
        return [
            ("P1", "انتهای موتور"),
            ("P2", "سر موتور"),
            ("P3", "سر ایرند"),
            ("P4", "انتهای ایرند"),
        ]
    return []


# ===============================================================
# 3) بارگذاری داده‌ها
# ===============================================================
VIB_URL = ("https://docs.google.com/spreadsheets/d/"
           "1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0")
ASSETS_URL = ("https://docs.google.com/spreadsheets/d/"
              "1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=1276803564")
ANN_URL = ("https://docs.google.com/spreadsheets/d/"
           "1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=2057447521")


def read_sheet(url):
    try:
        return pd.read_csv(url, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    except Exception:
        try:
            return pd.read_csv(url, dtype=str, keep_default_na=False)
        except Exception:
            return pd.DataFrame()


# ===============================================================
# 4) تبدیل ساختار Long شیت به جدول Wide (قلب برنامه)
# ===============================================================
EXCLUDE_MEAS = ["دور", "rpm", "هزینه", "قیمت", "مبلغ", "تعداد", "ردیف",
                "شماره", "سال", "کد", "اولویت", "الویت", "مدت", "تاریخ"]


def build_wide(df):
    """
    هر ردیف شیت = یک نقطه اندازه‌گیری (p1, p2, ...)
    خروجی: هر (تجهیز + تاریخ) = یک ردیف با ستون‌هایی مثل «P1 | عمودی»
    """
    info = {}

    if df is None or df.empty:
        return df, info

    work = df.copy()

    c_date = find_col(work.columns, ["تاریخ", "Date"])
    c_line = find_col(work.columns, ["خط تولید", "خط"])
    c_unit = find_col(work.columns, ["واحد"])
    c_eq = find_col(work.columns, ["عنوان تجهیز", "نام تجهیز", "تجهیز", "Asset"])

    # --- ستون نقطه: ستونی که بیشترین مقدار p1..pN را دارد ---
    c_pt = None
    best = 0
    for c in work.columns:
        vals = work[c].astype(str).str.strip().str.lower()
        n = int(vals.str.match(r"^p\s*\d+$").sum())
        if n > best:
            best = n
            c_pt = c

    info["ردیف خام"] = len(work)
    info["ستون تاریخ"] = c_date
    info["ستون خط تولید"] = c_line
    info["ستون واحد"] = c_unit
    info["ستون تجهیز"] = c_eq
    info["ستون نقطه"] = c_pt

    if c_pt is None or c_eq is None:
        info["خطا"] = "ستون نقطه یا ستون تجهیز شناسایی نشد."
        return work, info

    # --- ستون‌های اندازه‌گیری (عددی و غیر از نقطه/هزینه/دور) ---
    meas = []
    for c in work.columns:
        if c in (c_pt, c_eq, c_date, c_line, c_unit):
            continue
        nc = norm(c)
        if any(k in nc for k in EXCLUDE_MEAS):
            continue
        if numeric_ratio(work[c]) >= 0.5:
            meas.append(c)

    info["ستون‌های اندازه‌گیری"] = meas

    # --- کلیدهای کمکی ---
    pts = work[c_pt].astype(str).str.replace(r"\s+", "", regex=True).str.upper()
    pts = pts.where(pts.str.match(r"^P\d+$"), "")
    work["_pt"] = pts
    work["_eq"] = work[c_eq].map(norm)
    work["_date"] = work[c_date].map(norm) if c_date else ""

    if c_line:
        work[c_line] = work[c_line].replace("", None)
        work[c_line] = work[c_line].ffill()
    if c_unit:
        work[c_unit] = work[c_unit].replace("", None)
        work[c_unit] = work[c_unit].ffill()

    # پر کردن نام تجهیز و تاریخ برای ردیف‌هایی که فقط نقطه دارند
    for col in (c_eq, c_date):
        if col:
            work[col] = work[col].replace("", None).ffill()
    work["_eq"] = work[c_eq].map(norm)
    work["_date"] = work[c_date].map(norm) if c_date else ""
    work["_key"] = work["_eq"] + "||" + work["_date"]

    work = work[work["_eq"] != ""]

    # --- متادیتا: همه ستون‌های غیر اندازه‌گیری ---
    meta_cols = [c for c in work.columns
                 if c not in meas and c != c_pt and not str(c).startswith("_")]
    if "_key" in meta_cols:
        meta_cols.remove("_key")

    meta = work.groupby("_key")[meta_cols].agg(first_nonempty)

    # --- مقادیر: هر نقطه یک ردیف می‌سازد، مقادیر کنار هم می‌نشینند ---
    recs = []
    for key, g in work.groupby("_key"):
        row = {"_key": key}
        for _, r in g.iterrows():
            p = r["_pt"]
            if not p:
                continue
            for m in meas:
                v = str(r[m]).strip()
                if v in ("", "nan", "None", "NaN", "-"):
                    continue
                name = p + " | " + str(m).strip()
                if name in row:
                    continue
                row[name] = v
        recs.append(row)

    wide = pd.DataFrame(recs)
    if wide.empty:
        return work, info

    wide = wide.set_index("_key")
    out = meta.join(wide, how="outer").reset_index()

    # --- مرتب‌سازی طبیعی ستون‌های P ---
    vcols = [c for c in out.columns if re.match(r"^P\d+\s*\|", str(c))]

    def vkey(name):
        m = re.match(r"^P(\d+)\s*\|\s*(.*)$", str(name))
        if m:
            return (int(m.group(1)), m.group(2))
        return (999, str(name))

    vcols = sorted(vcols, key=vkey)

    lead = []
    for c in (c_date, c_line, c_unit, c_eq):
        if c and c in out.columns and c not in lead:
            lead.append(c)
    rest = [c for c in out.columns
            if c not in vcols and c not in lead and c != "_key" and not str(c).startswith("_")]
    out = out[lead + rest + vcols]

    # کلیدهای فیلتر
    out["_k_line"] = out[c_line].map(norm) if c_line else ""
    out["_k_unit"] = out[c_unit].map(norm) if c_unit else ""
    out["_k_eq"] = out[c_eq].map(norm) if c_eq else ""
    out["_k_date"] = out[c_date].map(norm) if c_date else ""
    out["_dkey"] = out[c_date].map(date_key) if c_date else 0

    if c_date:
        out = out.sort_values("_dkey", ascending=False)

    info["تجهیز یکتا"] = int(out["_k_eq"].nunique()) if c_eq else 0
    info["ردیف پس از تبدیل"] = len(out)
    info["تعداد ستون نقاط"] = len(vcols)

    return out, info


# ===============================================================
# 5) هدر
# ===============================================================
logo_siman = get_image_base64("client_logo.png")
logo_faz = get_image_base64("my_logo.png")

header_html = "<div style='display:flex;justify-content:space-between;align-items:center;"
header_html += "background:white;padding:14px 26px;border-radius:15px;margin-bottom:18px;"
header_html += "box-shadow:0 4px 8px rgba(0,0,0,0.08);'>"
header_html += "<img src='data:image/png;base64," + logo_faz + "' style='width:110px;'>"
header_html += "<div style='text-align:center;color:#1E3A8D;font-size:24px;font-weight:bold;font-family:Tahoma;'>"
header_html += "🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران</div>"
header_html += "<img src='data:image/png;base64," + logo_siman + "' style='width:110px;'>"
header_html += "</div>"
st.markdown(header_html, unsafe_allow_html=True)

# ===============================================================
# 6) اعلان‌ها
# ===============================================================
df_ann = read_sheet(ANN_URL)

if not df_ann.empty:
    c_tit = find_col(df_ann.columns, ["عنوان"])
    c_txt = find_col(df_ann.columns, ["متن"])
    c_typ = find_col(df_ann.columns, ["نوع"])
    c_act = find_col(df_ann.columns, ["فعال"])
    c_lbl = find_col(df_ann.columns, ["برچسب"])
    c_st = find_col(df_ann.columns, ["شروع"])
    c_en = find_col(df_ann.columns, ["انقضا", "پایان"])

    if c_tit and c_txt:
        view = df_ann.copy()
        if c_act:
            view = view[view[c_act].astype(str).str.strip() == "بله"]

        t_key = today_key()
        for _, row in view.iterrows():
            if c_st and c_en:
                ks = date_key(row[c_st])
                ke = date_key(row[c_en])
                if ks and ke and not (ks <= t_key <= ke):
                    continue

            t = str(row[c_tit]).strip()
            txt = str(row[c_txt]).strip()
            typ = str(row[c_typ]).strip() if c_typ else ""
            lbl = str(row[c_lbl]).strip() if c_lbl else ""

            if "خطر" in typ or "بحرانی" in typ:
                color, icon = "#ff4b4b", "🚨"
            elif "هشدار" in typ:
                color, icon = "#ff9800", "⚠️"
            elif "اطلاعیه" in typ or "گزارش" in typ:
                color, icon = "#2e7d32", "📢"
            else:
                color, icon = "#1E3A8D", "ℹ️"

            card = "<div style='background:" + color + ";padding:14px 18px;border-radius:12px;"
            card += "margin-bottom:10px;color:white;direction:rtl;text-align:right;font-family:Tahoma;'>"
            card += "<div style='display:flex;justify-content:space-between;align-items:center;'>"
            card += "<b style='font-size:17px;'>" + icon + " " + t + "</b>"
            card += "<span style='background:rgba(255,255,255,0.22);padding:3px 9px;border-radius:6px;font-size:12px;'>"
            card += lbl + "</span></div>"
            card += "<div style='margin-top:6px;font-size:14px;opacity:0.95;'>" + txt + "</div></div>"
            st.markdown(card, unsafe_allow_html=True)

# ===============================================================
# 7) پردازش داده اصلی
# ===============================================================
raw = read_sheet(VIB_URL)
df, info = build_wide(raw)
df_assets = read_sheet(ASSETS_URL)

if df is None or df.empty:
    st.error("❌ داده‌ای در شیت ارتعاشات پیدا نشد یا ساختار آن قابل تشخیص نبود.")
    with st.expander("🩺 اطلاعات تشخیص خودکار", expanded=True):
        st.write(info)
    st.stop()

c_date = find_col(df.columns, ["تاریخ"])
c_line = find_col(df.columns, ["خط تولید", "خط"])
c_unit = find_col(df.columns, ["واحد"])
c_eq = find_col(df.columns, ["عنوان تجهیز", "نام تجهیز", "تجهیز"])
vcols = [c for c in df.columns if re.match(r"^P\d+\s*\|", str(c))]
p_only = sorted({re.match(r"^(P\d+)", c).group(1) for c in vcols},
                key=lambda z: int(re.sub(r"\D", "", z)))

# ===============================================================
# 8) سایدبار
# ===============================================================
st.sidebar.header("🔍 فیلترها")


def uniq(series):
    vals = [v for v in series.dropna().astype(str).unique().tolist() if str(v).strip() != ""]
    return sorted(vals)


sel_line = st.sidebar.selectbox("📍 خط تولید:", ["همه"] + uniq(df["_k_line"]),
                                format_func=lambda k: k if k else "همه")
tmp = df if sel_line == "همه" else df[df["_k_line"] == sel_line]

sel_unit = st.sidebar.selectbox("🏢 واحد:", ["همه"] + uniq(tmp["_k_unit"]))
tmp = tmp if sel_unit == "همه" else tmp[tmp["_k_unit"] == sel_unit]

sel_eq = st.sidebar.selectbox("⚙️ تجهیز:", ["همه تجهیزات"] + uniq(tmp["_k_eq"]))
search = st.sidebar.text_input("🔎 جستجوی سریع:", placeholder="مثلاً: میل فن")

sel_date = st.sidebar.selectbox("🌙 تاریخ:", ["همه"] + uniq(df["_k_date"]))

st.sidebar.markdown("---")
with st.sidebar.expander("🩺 عیب‌یابی داده"):
    st.write("ردیف خام شیت:", info.get("ردیف خام"))
    st.write("ستون نقطه:", info.get("ستون نقطه"))
    st.write("ستون تجهیز:", info.get("ستون تجهیز"))
    st.write("ستون تاریخ:", info.get("ستون تاریخ"))
    st.write("ستون‌های اندازه‌گیری:", info.get("ستون‌های اندازه‌گیری"))
    st.write("ردیف پس از تبدیل:", info.get("ردیف پس از تبدیل"))
    st.write("تجهیز یکتا:", info.get("تجهیز یکتا"))

# اعمال فیلتر
fdf = df.copy()
if sel_line != "همه":
    fdf = fdf[fdf["_k_line"] == sel_line]
if sel_unit != "همه":
    fdf = fdf[fdf["_k_unit"] == sel_unit]
if sel_eq != "همه تجهیزات":
    fdf = fdf[fdf["_k_eq"] == sel_eq]
if search.strip():
    q = norm(search)
    fdf = fdf[fdf["_k_eq"].map(lambda v: q in v)]
if sel_date != "همه":
    fdf = fdf[fdf["_k_date"] == sel_date]

# ===============================================================
# 9) کارت مشخصات فنی + نقشه نقاط
# ===============================================================
if sel_eq != "همه تجهیزات" and not df_assets.empty:
    a_name = find_col(df_assets.columns, ["نام تجهیز", "عنوان تجهیز", "تجهیز", "Asset"])
    if a_name:
        an = df_assets[a_name].map(norm)
        arows = df_assets[an == sel_eq]
        if arows.empty:
            arows = df_assets[an.map(lambda x: bool(x) and (x in sel_eq or sel_eq in x))]

        if not arows.empty:
            def gv(keys, default="—"):
                c = find_col(df_assets.columns, keys)
                if not c:
                    return default
                v = first_nonempty(arows[c])
                return v if v else default

            e_type = gv(["نوع تجهیز", "نوع"])
            e_rpm = gv(["دور", "RPM"])
            e_unit = gv(["واحد"])
            e_cnt = gv(["تعداد نقاط"])
            e_drv = gv(["نوع انتقال", "انتقال", "کوپلینگ"])
            e_pt = gv(["راهنمای نقاط", "راهنما", "نقطه"])

            real_name = first_nonempty(arows[a_name]) or sel_eq

            card = "<div style='background:#f0f7ff;padding:18px 22px;border-radius:15px;"
            card += "border-right:10px solid #1E3A8D;margin-bottom:16px;direction:rtl;"
            card += "text-align:right;font-family:Tahoma;box-shadow:0 2px 8px rgba(0,0,0,0.06);'>"
            card += "<h3 style='color:#1E3A8D;margin:0 0 12px 0;'>🛠️ مشخصات فنی</h3>"
            card += "<div style='font-size:20px;font-weight:bold;color:#111;margin-bottom:10px;'>" + real_name + "</div>"
            card += "<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));"
            card += "gap:8px;font-size:15px;color:#333;'>"
            card += "<span><b style='color:#1E3A8D;'>نوع:</b> " + e_type + "</span>"
            card += "<span><b style='color:#1E3A8D;'>واحد:</b> " + e_unit + "</span>"
            card += "<span><b style='color:#1E3A8D;'>دور:</b> " + e_rpm + " RPM</span>"
            card += "<span><b style='color:#1E3A8D;'>تعداد نقاط:</b> " + e_cnt + "</span>"
            card += "<span><b style='color:#1E3A8D;'>انتقال حرکت:</b> " + e_drv + "</span>"
            card += "<span><b style='color:#1E3A8D;'>راهنمای شیت:</b> " + e_pt + "</span>"
            card += "</div></div>"
            st.markdown(card, unsafe_allow_html=True)

            # چیپ‌های نقشه نقاط
            chips = point_guide(real_name, e_type)
            if chips:
                have = set()
                for c in vcols:
                    if first_nonempty(fdf[c]) if not fdf.empty else "":
                        have.add(re.match(r"^(P\d+)", c).group(1))

                html = "<div style='background:#fff;border:1px dashed #1E3A8D;border-radius:12px;"
                html += "padding:12px 16px;margin-bottom:16px;direction:rtl;text-align:right;font-family:Tahoma;'>"
                html += "<b style='color:#1E3A8D;font-size:15px;'>📍 نقشه نقاط اندازه‌گیری (P-Map)</b>"
                html += "<div style='display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;'>"
                for code, desc in chips:
                    solid = "#1E3A8D" if code in have else "#c9d4e8"
                    fg = "#fff" if code in have else "#4a5568"
                    html += "<div style='background:" + solid + ";color:" + fg + ";padding:6px 12px;"
                    html += "border-radius:20px;font-size:13px;unicode-bidi:isolate;direction:rtl;'>"
                    html += "<b>" + code + "</b> · " + desc + "</div>"
                html += "</div></div>"
                st.markdown(html, unsafe_allow_html=True)

            # جدول لجستیک (بیرینگ/بوش/شماره فنی هر نقطه)
            pt_col = find_col(df_assets.columns, ["راهنمای نقاط", "نقطه", "Point"])
            keep = [c for c in [pt_col,
                                find_col(df_assets.columns, ["شماره فنی", "شماره"]),
                                find_col(df_assets.columns, ["مدل"]),
                                find_col(df_assets.columns, ["بیرینگ", "Bearing"]),
                                find_col(df_assets.columns, ["بوش", "Bush"])] if c]
            if keep:
                with st.expander("📦 اطلاعات قطعات و لجستیک", expanded=False):
                    st.dataframe(arows[keep], hide_index=True, use_container_width=True)

# ===============================================================
# 10) جدول داده‌ها
# ===============================================================
st.markdown("### 📊 تحلیل روند ارتعاشات")
st.caption("هر ردیف = یک تجهیز در یک تاریخ | ستون‌ها = نقاط اندازه‌گیری")

if fdf.empty:
    st.warning("با این فیلترها داده‌ای یافت نشد.")
else:
    show_cols = [c for c in fdf.columns if not str(c).startswith("_")]
    tbl = fdf[show_cols].copy()

    def color_cells(val):
        if not is_number(val):
            return ""
        v = float(clean_num_text(val))
        if v > 7.1:
            return "background-color:#ff4b4b;color:white"
        if v > 4.5:
            return "background-color:#ffa500;color:white"
        return "background-color:#2e7d32;color:white"

    use_cols = [c for c in vcols if c in tbl.columns]
    st.markdown("**تعداد ردیف نمایش‌داده‌شده:** " + str(len(tbl)))

    if use_cols:
        styled = tbl.style.map(color_cells, subset=use_cols)
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.dataframe(tbl, use_container_width=True, hide_index=True)

    # ---------- نمودار روند ----------
    if use_cols and sel_eq != "همه تجهیزات" and len(fdf) > 1 and c_date:
        st.markdown("#### 📈 روند تغییرات")
        tmp2 = fdf[[c_date] + use_cols].copy()
        tmp2[c_date] = tmp2[c_date].astype(str)
        long = tmp2.melt(id_vars=[c_date], var_name="نقطه", value_name="مقدار")
        long["مقدار"] = to_num(long["مقدار"])
        long = long.dropna(subset=["مقدار"])
        if not long.empty:
            fig = px.line(long, x=c_date, y="مقدار", color="نقطه", markers=True,
                          title="روند ارتعاش (mm/s)")
            fig.add_hline(y=4.5, line_dash="dash", line_color="orange",
                          annotation_text="هشدار 4.5")
            fig.add_hline(y=7.1, line_dash="dash", line_color="red",
                          annotation_text="بحرانی 7.1")
            fig.update_layout(font_family="Tahoma", height=460)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("مقدار عددی برای رسم نمودار موجود نیست.")

    # ---------- وضعیت سلامت ----------
    if use_cols:
        with st.expander("🩺 وضعیت سلامت (دایره‌ای)", expanded=False):
            num = fdf[use_cols].apply(to_num, axis=0)
            vmax = num.max(axis=1)

            def cat(v):
                if pd.isna(v):
                    return "نامشخص"
                if v > 7.1:
                    return "بحرانی"
                if v > 4.5:
                    return "هشدار"
                return "سالم"

            status = vmax.map(cat).value_counts()
            if not status.empty:
                figp = px.pie(values=status.values, names=status.index,
                              color=status.index, hole=0.4,
                              color_discrete_map={"سالم": "#2e7d32", "هشدار": "#ffa500",
                                                  "بحرانی": "#ff4b4b", "نامشخص": "#9e9e9e"})
                figp.update_layout(font_family="Tahoma")
                st.plotly_chart(figp, use_container_width=True)

# ===============================================================
# 11) فوتر
# ===============================================================
st.markdown(
    "<div style='text-align:center;margin-top:40px;color:#666;font-family:Tahoma;font-size:13px;'>"
    "طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>",
    unsafe_allow_html=True,
)
