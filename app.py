import re
import base64
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="پایش وضعیت ارتعاشات – سیمان تهران", page_icon="🛠️", layout="wide")

# =====================================================================
# 1) ورود کاربران
# =====================================================================
USERS = {
    "alireza76ir@gmail.com": "siman123",
    "vah.rezaei@gmail.com": "siman123",
    "cm.zandiyeh@gmail.com": "siman123",
    "m.babahasan@gmail.com": "siman123",
    "freedocs.ir@gmail.com": "siman123",
    "tehrancement@gmail.com": "siman123",
    "masoud.sa.1989823@gmail.com": "siman123",
}

if "auth" not in st.session_state:
    st.session_state["auth"] = False

if not st.session_state["auth"]:
    st.markdown("## 🔐 ورود به سامانه هوشمند پایش وضعیت سیمان تهران")
    with st.form("login_form"):
        u = st.text_input("ایمیل کاربری")
        p = st.text_input("رمز عبور", type="password")
        submit = st.form_submit_button("ورود به داشبورد")
    if submit:
        if USERS.get(u.strip().lower()) == p.strip():
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("❌ ایمیل یا رمز عبور نادرست است.")
    st.stop()

# =====================================================================
# 2) توابع کمکی
# =====================================================================
FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
AR_DIGITS = "٠١٢٣٤٥٦٧٨٩"
EN_DIGITS = "0123456789"


def norm(x):
    """نرمال‌سازی متن فارسی/عربی برای تطبیق نام‌ها"""
    if x is None:
        return ""
    s = str(x).strip()
    if not s:
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
          .replace("،", " "))
    return " ".join(s.split()).lower()


def clean_num_text(x):
    s = str(x).strip()
    for f, e in zip(FA_DIGITS, EN_DIGITS):
        s = s.replace(f, e)
    for a, e in zip(AR_DIGITS, EN_DIGITS):
        s = s.replace(a, e)
    s = s.replace("٫", ".").replace("،", ".").replace(",", ".")
    return s.replace(" ", "")


def to_num(x):
    try:
        return float(clean_num_text(x))
    except Exception:
        return None


def point_keys(x):
    """از هر متنی شماره نقطه‌ها را بیرون می‌کشد: 'p3' -> ['3'] ، 'P1, P2' -> ['1','2']"""
    s = clean_num_text(norm(x))
    return re.findall(r"\d+", s)


def date_sort_key(val):
    s = norm(val)
    m = re.search(r"(\d{2,4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})", s)
    if m:
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if y < 100:
                y += 1400
            return int(f"{y}{mo:02d}{d:02d}")
        except Exception:
            return 0
    return 0


def smart_find_column(columns, keywords):
    if columns is None:
        return None
    cols = list(columns)
    normed = {c: norm(c) for c in cols}
    for k in keywords:
        nk = norm(k)
        if not nk:
            continue
        for c in cols:
            if normed[c] == nk:
                return c
    for k in keywords:
        nk = norm(k)
        if not nk:
            continue
        for c in cols:
            if nk in normed[c]:
                return c
    return None


def get_image_base64(path):
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""


# =====================================================================
# 3) بارگذاری داده‌ها
# =====================================================================
SHEET_ID = "1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs"
VIB_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
ASSETS_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=1276803564"
ANN_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=2057447521"


@st.cache_data(ttl=600, show_spinner="در حال دریافت داده از گوگل شیت ...")
def load_data():
    def _read(url):
        try:
            return pd.read_csv(url, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        except Exception:
            return pd.DataFrame()

    return _read(VIB_URL), _read(ASSETS_URL), _read(ANN_URL)


df_vib, df_assets, df_ann = load_data()

# ---- شناسایی ستون‌های شیت ارتعاشات ----
c_date = smart_find_column(df_vib.columns, ["تاریخ", "date"])
c_line = smart_find_column(df_vib.columns, ["خط تولید", "خط"])
c_unit = smart_find_column(df_vib.columns, ["واحد"])
c_equip = smart_find_column(df_vib.columns, ["عنوان تجهیز", "نام تجهیز", "تجهیز", "asset"])
c_point = smart_find_column(df_vib.columns, ["محل اندازه گیری", "محل اندازه‌گیری", "نقطه", "point", "محل"])
c_pic = smart_find_column(df_vib.columns, ["تصویر"])

# ---- شناسایی ستون‌های شیت Assets ----
a_name = smart_find_column(df_assets.columns, ["نام تجهیز", "عنوان تجهیز", "تجهیز", "asset"])
a_point = smart_find_column(df_assets.columns, ["راهنمای نقاط", "نقاط", "محل اندازه گیری", "point"])

ASSET_PREFIX = "A§"

if not df_vib.empty:
    df_vib["_k_line"] = df_vib[c_line].map(norm) if c_line else ""
    df_vib["_k_unit"] = df_vib[c_unit].map(norm) if c_unit else ""
    df_vib["_k_eq"] = df_vib[c_equip].map(norm) if c_equip else ""
    if c_date:
        df_vib["_k_date"] = df_vib[c_date].map(norm)
        df_vib["_dkey"] = df_vib[c_date].map(date_sort_key)
    else:
        df_vib["_k_date"] = ""
        df_vib["_dkey"] = 0

# =====================================================================
# 4) ساخت نقشه (Asset Map) از شیت مشخصات فنی
#    یک ردیف برای هر نقطه، پس بتوانیم شماره بیرینگ هر نقطه را جدا کنیم
# =====================================================================
spec_rename = {}          # نام ستون اصلی -> نام پیشونددار
am = pd.DataFrame()

if not df_assets.empty and a_name is not None:
    spec_cols_src = [c for c in df_assets.columns if c not in (a_name, a_point)]
    spec_rename = {c: ASSET_PREFIX + str(c) for c in spec_cols_src}

    am = df_assets.copy()
    for c in spec_cols_src:
        am[c] = am[c].map(lambda v: "" if v is None else str(v).strip())
    am = am.rename(columns=spec_rename)

    am["_a_eq"] = df_assets[a_name].map(norm)
    if a_point is not None:
        am["_pkeys"] = df_assets[a_point].map(lambda v: point_keys(v) or [""])
    else:
        am["_pkeys"] = [[""]] * len(am)
    am = am.explode("_pkeys").rename(columns={"_pkeys": "_pkey"})
    am["_pkey"] = am["_pkey"].astype(str)
    am = am[am["_a_eq"] != ""]

ASSET_NAMES = sorted({n for n in am["_a_eq"].unique() if n}) if not am.empty else []


def resolve_eq(eq_norm, names):
    """تطبیق نام تجهیز بین دو شیت (تطبیق دقیق، سپس تطبیق بخشی)"""
    if not eq_norm:
        return None
    if eq_norm in names:
        return eq_norm
    best = None
    for k in names:
        if eq_norm in k or k in eq_norm:
            if best is None or len(k) > len(best):
                best = k
    return best


# =====================================================================
# 5) هدر و اعلانیه‌ها
# =====================================================================
logo_client = get_image_base64("client_logo.png")
logo_me = get_image_base64("my_logo.png")

left_img = f"<img src='data:image/png;base64,{logo_me}' style='height:70px;'>" if logo_me else ""
right_img = f"<img src='data:image/png;base64,{logo_client}' style='height:70px;'>" if logo_client else ""

st.markdown(
    f"""
    <div style='display:flex; justify-content:space-between; align-items:center;
                background:#ffffff; padding:14px 26px; border-radius:16px;
                box-shadow:0 4px 14px rgba(0,0,0,0.08); margin-bottom:18px;'>
        <div>{left_img}</div>
        <div style='text-align:center; color:#1E3A8D; font-size:23px; font-weight:bold; font-family:Tahoma;'>
            🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران
        </div>
        <div>{right_img}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not df_ann.empty:
    n_tit = smart_find_column(df_ann.columns, ["عنوان", "title"])
    n_txt = smart_find_column(df_ann.columns, ["متن", "text"])
    n_typ = smart_find_column(df_ann.columns, ["نوع", "type"])
    n_act = smart_find_column(df_ann.columns, ["فعال", "active"])

    if n_tit and n_txt:
        for _, r in df_ann.iterrows():
            if n_act and norm(r[n_act]) not in ("بله", "yes", "true", "1"):
                continue
            title = str(r[n_tit]).strip()
            body = str(r[n_txt]).strip()
            typ = norm(r[n_typ]) if n_typ else ""
            if any(k in typ for k in ["خطر", "بحرانی"]):
                color, icon = "#dc3545", "🚨"
            elif any(k in typ for k in ["هشدار", "اخطار"]):
                color, icon = "#fd7e14", "⚠️"
            elif "موفق" in typ:
                color, icon = "#2e7d32", "✅"
            else:
                color, icon = "#1E3A8D", "ℹ️"
            st.markdown(
                f"""<div style="background:{color}; color:#fff; padding:12px 16px; border-radius:12px;
                        margin-bottom:8px; direction:rtl; text-align:right; font-family:Tahoma;">
                        <b>{icon} {title}</b><br><small>{body}</small></div>""",
                unsafe_allow_html=True,
            )

# =====================================================================
# 6) سایدبار: فیلتر آبشاری خط ← واحد ← تجهیز
# =====================================================================
st.sidebar.header("🔍 فیلترها")

warn_limit = 4.5
crit_limit = 7.1
show_chart = False
chart_modes = ["عمودی", "افقی", "محوری"]
sel_line = sel_unit = sel_eq = None
fdf = pd.DataFrame()

if not df_vib.empty:
    lines = sorted({x for x in df_vib["_k_line"].unique() if x})
    sel_line = st.sidebar.selectbox("📍 خط تولید", ["همه"] + lines)

    base = df_vib if sel_line == "همه" else df_vib[df_vib["_k_line"] == sel_line]
    units = sorted({x for x in base["_k_unit"].unique() if x})
    sel_unit = st.sidebar.selectbox("🏢 واحد", ["همه"] + units)

    if sel_unit != "همه":
        base = base[base["_k_unit"] == sel_unit]
    equips = sorted({x for x in base["_k_eq"].unique() if x})
    sel_eq = st.sidebar.selectbox("⚙️ تجهیز", ["همه تجهیزات"] + equips)

    # جستجو فقط داخل همان خط و واحد
    q = st.sidebar.text_input("🔎 جستجوی سریع تجهیز")
    fdf = base.copy()
    if sel_eq != "همه تجهیزات":
        fdf = fdf[fdf["_k_eq"] == sel_eq]
    if q:
        nq = norm(q)
        fdf = fdf[fdf["_k_eq"].map(lambda z: nq in z)]

    dates = sorted({d for d in fdf["_k_date"].unique() if d}, reverse=True)
    if not dates:
        dates = sorted({d for d in df_vib["_k_date"].unique() if d}, reverse=True)
    sel_date = st.sidebar.selectbox("🌙 تاریخ", ["همه تاریخ‌ها"] + dates)
    if sel_date != "همه تاریخ‌ها":
        fdf = fdf[fdf["_k_date"] == norm(sel_date)]

    fdf = fdf.sort_values(["_dkey"], ascending=False)

    st.sidebar.markdown("---")
    st.sidebar.header("⚠️ حدود هشدار")
    warn_limit = st.sidebar.slider("حد هشدار (نارنجی)", 0.0, 20.0, 4.5, 0.1)
    crit_limit = st.sidebar.slider("حد بحرانی (قرمز)", 0.0, 30.0, 7.1, 0.1)

    st.sidebar.markdown("---")
    st.sidebar.header("📈 نمودار روند")
    show_chart = st.sidebar.checkbox("نمایش نمودار", value=False)
    chart_modes = st.sidebar.multiselect("جهت‌ها", ["عمودی", "افقی", "محوری"],
                                         default=["عمودی", "افقی", "محوری"])

# =====================================================================
# 7) ادغام مشخصات Assets در جدول (کلیدی‌ترین بخش)
# =====================================================================
spec_cols = list(spec_rename.values())    # ستون‌های پیشونددار
spec_name = {v: k for k, v in spec_rename.items()}

if not fdf.empty:
    fdf["_a_eq"] = fdf["_k_eq"].map(lambda z: resolve_eq(z, ASSET_NAMES))
    fdf["_pkey"] = fdf[c_point].map(lambda v: (point_keys(v) or [""])[0]) if c_point else ""

    if not am.empty:
        pts = am[am["_pkey"].str.len() > 0]
        gns = am[am["_pkey"].str.len() == 0]

        if not pts.empty:
            pts = pts.drop_duplicates(subset=["_a_eq", "_pkey"], keep="first")
            fdf = fdf.merge(pts[["_a_eq", "_pkey"] + spec_cols],
                            on=["_a_eq", "_pkey"], how="left")
        else:
            for c in spec_cols:
                fdf[c] = ""

        if not gns.empty:
            g1 = gns.groupby("_a_eq", as_index=False).first()[["_a_eq"] + spec_cols]
            g1 = g1.rename(columns={c: c + "_GEN" for c in spec_cols})
            fdf = fdf.merge(g1, on="_a_eq", how="left")
            for c in spec_cols:
                gc = c + "_GEN"
                if gc in fdf.columns:
                    cur = fdf[c].fillna("").astype(str)
                    fdf[c] = cur.where(cur.str.strip() != "", fdf[gc].fillna("").astype(str))
                    fdf.drop(columns=[gc], inplace=True)
    else:
        for c in spec_cols:
            fdf[c] = ""

# =====================================================================
# 8) مشخصات فنی تجهیز + نقشه نقاط (بالای جدول، زیر اعلانیه‌ها)
# =====================================================================
if not fdf.empty and sel_eq and sel_eq != "همه تجهیزات":
    eq_key = resolve_eq(norm(sel_eq), ASSET_NAMES)

    if eq_key and not am.empty:
        d = am[am["_a_eq"] == eq_key].copy()
        d = d.rename(columns=spec_name)

        with st.expander(f"🛠️ مشخصات فنی تجهیز — {sel_eq}", expanded=True):
            r0 = d.iloc[0]

            def common(colnames):
                c = smart_find_column(d.columns, colnames)
                if not c:
                    return ""
                vals = [str(v).strip() for v in d[c] if str(v).strip() not in ("", "nan")]
                seen, out = set(), []
                for v in vals:
                    if v not in seen:
                        seen.add(v)
                        out.append(v)
                return " ، ".join(out)

            cards = [
                ("نام تجهیز", sel_eq),
                ("نوع تجهیز", common(["نوع تجهیز", "نوع"])),
                ("دور نامی (RPM)", common(["دور نامی", "دور", "rpm"])),
                ("خط تولید", common(["خط تولید", "خط"])),
                ("واحد", common(["واحد"])),
                ("شماره بیرینگ", common(["شماره بیرینگ", "بیرینگ"])),
                ("سیستم انتقال قدرت", common(["سیستم انتقال", "انتقال قدرت", "سیستم انتقال قدرت"])),
                ("نوع کوپلینگ", common(["کوپلینگ"])),
                ("نوع پولی", common(["پولی", "تسمه"])),
            ]
            cards = [(k, v) for k, v in cards if v]

            cols = st.columns(3)
            for i, (k, v) in enumerate(cards):
                with cols[i % 3]:
                    st.markdown(
                        f"""<div style="background:#f4f6fb; border-right:5px solid #1E3A8D;
                                border-radius:10px; padding:10px 14px; margin-bottom:10px;
                                font-family:Tahoma; direction:rtl;">
                                <div style="color:#6b7280; font-size:12px;">{k}</div>
                                <div style="color:#111827; font-size:15px; font-weight:bold;">{v}</div>
                            </div>""",
                        unsafe_allow_html=True,
                    )

            # --- بقیه ستون‌های Assets که در کارت‌ها نیامده‌اند ---
            shown = set()
            for names in [["نوع تجهیز", "نوع"], ["دور نامی", "دور"], ["خط"], ["واحد"],
                          ["شماره بیرینگ", "بیرینگ"], ["سیستم انتقال"], ["کوپلینگ"],
                          ["پولی"], ["تسمه"], ["نام تجهیز"], ["راهنمای نقاط", "نقاط"]]:
                c = smart_find_column(d.columns, names)
                if c:
                    shown.add(c)

            rest = [c for c in d.columns
                    if c not in shown and not str(c).startswith("_")
                    and d[c].astype(str).str.strip().ne("").any()]

            if rest:
                st.markdown("**سایر مشخصات ثبت‌شده در شیت Assets**")
                rows = []
                for c in rest:
                    vals = [str(v).strip() for v in d[c] if str(v).strip() not in ("", "nan")]
                    seen, uniq = set(), []
                    for v in vals:
                        if v not in seen:
                            seen.add(v)
                            uniq.append(v)
                    if uniq:
                        rows.append({"مشخصه": c, "مقدار": " ، ".join(uniq)})
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # --- نقشه نقاط اندازه‌گیری ---
        with st.expander("📌 نقشه نقاط اندازه‌گیری و شماره بیرینگ هر نقطه", expanded=True):
            pc = smart_find_column(d.columns, ["راهنمای نقاط", "نقاط", "محل اندازه گیری", "point"])
            bc = smart_find_column(d.columns, ["شماره بیرینگ", "بیرینگ"])
            sc = smart_find_column(d.columns, ["سیستم انتقال", "انتقال قدرت"])
            kc = smart_find_column(d.columns, ["کوپلینگ"])
            dc = smart_find_column(d.columns, ["شرح", "توضیح", "موقعیت"])

            def sort_point(v):
                ks = point_keys(v)
                return int(ks[0]) if ks else 999

            tmp = d.copy()
            if pc:
                tmp["__p"] = tmp[pc]
            else:
                tmp["__p"] = [f"P{k}" if k else "—" for k in d["_pkey"]]
            tmp = tmp.sort_values("__p", key=lambda s: s.map(sort_point))

            out_rows = []
            for _, rr in tmp.iterrows():
                pv = str(rr["__p"]).strip()
                pk = point_keys(pv)
                out_rows.append({
                    "نقطه": (f"P{pk[0]}" if pk else pv) if pv else "—",
                    "موقعیت / شرح": str(rr[dc]).strip() if dc else "",
                    "شماره بیرینگ": str(rr[bc]).strip() if bc else "",
                    "سیستم انتقال": str(rr[sc]).strip() if sc else "",
                    "کوپلینگ": str(rr[kc]).strip() if kc else "",
                })

            map_df = pd.DataFrame(out_rows)
            map_df = map_df.drop_duplicates(subset=["نقطه", "شماره بیرینگ"])

            if not map_df.empty:
                st.dataframe(map_df, use_container_width=True, hide_index=True)
                st.caption("این جدول برای بازرس فنی و مأمور خرید است: هر نقطه با بیرینگ خودش.")
            else:
                st.info("برای این تجهیز اطلاعاتی در شیت Assets پیدا نشد.")

    else:
        st.warning("⚠️ نام این تجهیز در شیت Assets پیدا نشد؛ تطبیق نام‌ها را بررسی کنید.")

# =====================================================================
# 9) جدول اصلی (با ستون‌های Assets داخل خود ردیف)
# =====================================================================
if not fdf.empty:
    vis_cols = [c for c in fdf.columns
                if not str(c).startswith("_") and str(c) not in spec_cols]

    out = fdf[vis_cols].reset_index(drop=True).copy()

    # ستون‌های Assets که داده دارند
    add = []
    for pc in spec_cols:
        if pc not in fdf.columns:
            continue
        s = fdf[pc].reset_index(drop=True).fillna("").astype(str)
        if s.str.strip().ne("").any():
            add.append((pc, s))

    # اولویت: شماره بیرینگ و بعد بقیه
    def prio(item):
        name = spec_name.get(item[0], item[0])
        n = norm(name)
        if "بیرینگ" in n:
            return 0
        if "انتقال" in n:
            return 1
        if "کوپلینگ" in n:
            return 2
        if "پولی" in n or "تسمه" in n:
            return 3
        return 5

    add.sort(key=prio)

    insert_at = 0
    for cand in ["محل اندازه گیری", "محل اندازه‌گیری", "نقطه", "محل"]:
        if cand in out.columns:
            insert_at = list(out.columns).index(cand) + 1
            break
    else:
        insert_at = min(5, len(out.columns))

    for i, (pc, s) in enumerate(add):
        label = spec_name.get(pc, pc)
        label = str(label).strip()
        while label in out.columns:
            label = label + " (Assets)"
        out.insert(insert_at + i, label, s.values)

    # ---- رنگ‌بندی ----
    num_cols = [c for c in out.columns
                if any(p in norm(c) for p in ["عمودی", "افقی", "محوری", "mm", "mm/s"])
                or re.search(r"p\d+", norm(c))]

    def color_vib(val):
        v = to_num(val)
        if v is None:
            return ""
        if v >= crit_limit:
            return "background-color:#dc3545; color:#fff; font-weight:bold;"
        if v >= warn_limit:
            return "background-color:#fd7e14; color:#fff; font-weight:bold;"
        return "background-color:#2e7d32; color:#fff;"

    st.markdown(f"### 📋 جدول ارتعاشات — {len(out)} ردیف")

    try:
        styler = out.style.map(color_vib, subset=[c for c in num_cols if c in out.columns])
    except AttributeError:
        styler = out.style.applymap(color_vib, subset=[c for c in num_cols if c in out.columns])

    st.dataframe(styler, use_container_width=True, hide_index=True, height=560)

    # ---- دانلود CSV ----
    st.download_button(
        "⬇️ دانلود جدول (CSV)",
        data=out.to_csv(index=False).encode("utf-8-sig"),
        file_name="vibration_table.csv",
        mime="text/csv",
    )

    # =================================================================
    # 10) نمودار روند
    # =================================================================
    if show_chart and c_date and len(fdf) > 1:
        vib_cols = [c for c in df_vib.columns
                    if any(p in norm(c) for p in ["عمودی", "افقی", "محوری"])
                    or re.search(r"p\d+", norm(c))]

        target = [c for c in vib_cols if any(m in c for m in chart_modes)]

        if target:
            p = fdf[[c_date] + target].copy()
            p["_dkey"] = p[c_date].map(date_sort_key)
            p = p.sort_values("_dkey")

            long = p.melt(id_vars=[c_date, "_dkey"], value_vars=target,
                          var_name="جهت / نقطه", value_name="مقدار")
            long["مقدار"] = long["مقدار"].map(to_num)
            long = long.dropna(subset=["مقدار"])

            if not long.empty:
                fig = px.line(long, x=c_date, y="مقدار", color="جهت / نقطه",
                              markers=True, title="روند ارتعاشات")
                fig.add_hline(y=warn_limit, line_dash="dash", line_color="orange",
                              annotation_text="هشدار")
                fig.add_hline(y=crit_limit, line_dash="dash", line_color="red",
                              annotation_text="بحرانی")
                fig.update_layout(direction="rtl", height=520)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("داده عددی برای رسم نمودار یافت نشد.")
        else:
            st.info("از سایدبار حداقل یک جهت را انتخاب کنید.")

else:
    st.info("با فیلترهای سایدبار، تجهیز مورد نظر را انتخاب کنید.")

st.markdown(
    '<div style="text-align:center; margin-top:40px; color:#777; font-family:Tahoma; font-size:13px;">'
    "طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>",
    unsafe_allow_html=True,
)
