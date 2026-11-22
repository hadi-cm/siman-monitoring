# -*- coding: utf-8 -*-
"""
سامانه هوشمند پایش وضعیت ارتعاشات — سیمان تهران
نسخه ۴.۱ (تمیز و بدون جدول پیش‌نمایش)

قرارداد ما با شیت:
  هر چه در شیت هست همان نمایش داده می‌شود؛ نه بیشتر، نه کمتر.
  ستون‌های شیت تجهیزات:
     نام تجهیز | خط تولید | واحد | نوع تجهیز | راهنمایی نقاط |
     شماره بیرینگ | بوش | دور نامی | سیستم درایور

اجرا:
     pip install streamlit pandas plotly requests
     streamlit run vibration_monitor_v4_clean.py
"""

import os
import re
import json
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

import pandas as pd
import requests
import streamlit as st
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# تنظیمات پایه
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="پایش ارتعاشات سیمان تهران",
    page_icon="📈",
    layout="wide",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

DEFAULT_USERS = {
    "vah.rezaei":         {"password": "siman123", "role": "admin",  "name": "مدیر بهره‌برداری"},
    "me.vibration.shokri": {"password": "siman123", "role": "admin", "name": "مدیر پایش"},
    "tehrancement":       {"password": "siman123", "role": "admin",  "name": "مدیر فنی"},
    "alireza76ir":        {"password": "siman123", "role": "viewer", "name": "ناظر"},
    "cm.zandiy":          {"password": "siman123", "role": "viewer", "name": "ناظر"},
    "m.babahasan":        {"password": "siman123", "role": "viewer", "name": "ناظر"},
    "freedocs.ir":        {"password": "siman123", "role": "viewer", "name": "ناظر"},
}

DEFAULT_SETTINGS = {
    "vib_url": "",
    "asset_url": "",
    "threshold": 4.5,
    "smtp_host": "smtp.gmail.com",
    "smtp_port": 587,
    "smtp_user": "",
    "smtp_pass": "",
    "mail_to": "",
    "notify_enabled": False,
}

# ---------------------------------------------------------------------------
# استایل
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;600;700&display=swap');

html, body, [class*="css"], .stMarkdown, .stSelectbox, .stButton, .stTextInput {
    font-family: 'Vazirmatn', Tahoma, sans-serif;
}
.block-container { padding-top: 1.1rem; padding-bottom: 2.5rem; max-width: 1250px; }

.app-header {
    background: linear-gradient(135deg, #8c1c2b 0%, #c0392b 55%, #e67e22 100%);
    color: #fff; border-radius: 16px; padding: 18px 22px; margin-bottom: 14px;
    box-shadow: 0 6px 18px rgba(140, 28, 43, .18);
}
.app-header h1 { color: #fff; margin: 0; font-size: 1.45rem; line-height: 1.7; }
.app-header p  { margin: 6px 0 0; opacity: .92; font-size: .82rem; }

.filter-box {
    background: #fdfaf8; border: 1px solid #eadfd8; border-radius: 14px;
    padding: 14px 16px 4px; margin-bottom: 14px;
}
.filter-title { font-weight: 700; color: #8c1c2b; font-size: .95rem; margin-bottom: 6px; }

.pt-card {
    display: flex; align-items: center; gap: 10px;
    background: #fff; border: 1px solid #ece3dd; border-right: 4px solid #c0392b;
    border-radius: 10px; padding: 8px 12px; margin-bottom: 8px;
}
.pt-id {
    font-weight: 700; color: #8c1c2b; font-size: .95rem;
    min-width: 42px; text-align: center;
}
.pt-body { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: .8rem; color: #444; }
.pt-body b { color: #1f2933; font-weight: 600; }

.meta-line { font-size: .8rem; color: #6b7280; margin: -4px 0 12px; }

div[data-testid="stMetricValue"] { color: #8c1c2b; }
[data-testid="stSidebar"] { background: #fbf8f6; }
.stTabs [data-baseweb="tab"] { font-size: .88rem; }

@media (max-width: 720px) {
    .app-header h1 { font-size: 1.1rem; }
    .pt-body { font-size: .74rem; }
    .block-container { padding-left: .6rem; padding-right: .6rem; }
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# فایل‌های محلی
# ---------------------------------------------------------------------------
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(default, dict):
                merged = dict(default)
                merged.update(data)
                return merged
        except Exception:
            pass
    return dict(default) if isinstance(default, dict) else default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


USERS = load_json(USERS_FILE, DEFAULT_USERS)
SETTINGS = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)

# ---------------------------------------------------------------------------
# ابزارهای عمومی
# ---------------------------------------------------------------------------
AR2EN = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def clean_text(x):
    if x is None:
        return ""
    s = str(x).translate(AR2EN)
    s = s.replace("\u200c", " ").replace("\u200f", "").replace("\u200e", "")
    s = re.sub(r"\s+", " ", s).strip()
    if s.lower() in ("nan", "none", "nat"):
        return ""
    return s


def norm_key(s):
    return clean_text(s).lower()


def pick_col(df, candidates, required=True):
    """پیدا کردن نام ستون با تحمل نیم‌فاصله، فاصله اضافه و حروف بزرگ/کوچک."""
    keys = {c: norm_key(c) for c in df.columns}
    for cand in candidates:
        target = norm_key(cand)
        for col, k in keys.items():
            if k == target:
                return col
    for cand in candidates:
        target = norm_key(cand)
        for col, k in keys.items():
            if target and target in k:
                return col
    if required:
        return None
    return None


def to_num(series):
    return pd.to_numeric(
        series.astype(str).str.translate(AR2EN).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )


def sheet_csv_url(url):
    """تبدیل لینک گوگل شیت به لینک خروجی CSV."""
    if not isinstance(url, str) or not url.strip():
        return None
    u = url.strip()
    if u.lower().endswith(".csv") or "format=csv" in u:
        return u
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9\-_]+)", u)
    if not m:
        return None
    sid = m.group(1)
    g = re.search(r"[#&?]gid=([0-9]+)", u)
    gid = g.group(1) if g else "0"
    return f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"


@st.cache_data(ttl=180, show_spinner=False)
def read_sheet(url):
    csv_url = sheet_csv_url(url)
    if not csv_url:
        raise ValueError("لینک شیت معتبر نیست. لینک کامل گوگل شیت را وارد کنید.")
    r = requests.get(csv_url, timeout=20)
    r.raise_for_status()
    r.encoding = "utf-8"
    df = pd.read_csv(pd.io.common.StringIO(r.text), dtype=str)
    df.columns = [clean_text(c) for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# نرمال‌سازی داده‌ها (طبق ستون‌های شیت خودت)
# ---------------------------------------------------------------------------
ASSET_MAP = {
    "equipment": ["نام تجهیز", "تجهیز"],
    "line":      ["خط تولید", "خط"],
    "unit":      ["واحد"],
    "etype":     ["نوع تجهیز", "نوع"],
    "point":     ["راهنمایی نقاط", "نقاط", "نقطه"],
    "bearing":   ["شماره بیرینگ", "بیرینگ"],
    "bushing":   ["بوش"],
    "rpm":       ["دور نامی", "دور"],
    "driver":    ["سیستم درایور", "درایور", "سیستم انتقال نیرو"],
}

VIB_MAP = {
    "equipment": ["نام تجهیز", "تجهیز"],
    "point":     ["راهنمایی نقاط", "نقطه", "نقاط"],
    "date":      ["تاریخ", "زمان", "تاریخ ثبت", "تاریخچه"],
    "value":     ["مقدار ارتعاش", "مقدار", "RMS", "ارتعاش", "value"],
}


def normalize_assets(df):
    cols = {}
    missing = []
    for key, cands in ASSET_MAP.items():
        c = pick_col(df, cands, required=key in ("equipment", "line", "unit", "point"))
        if c is None and key in ("equipment", "line", "unit", "point"):
            missing.append(cands[0])
        cols[key] = c

    if missing:
        raise ValueError("این ستون‌ها در شیت تجهیزات پیدا نشد: " + "، ".join(missing))

    out = pd.DataFrame()
    out["equipment"] = df[cols["equipment"]].map(clean_text)
    out["line"] = df[cols["line"]].map(clean_text)
    out["unit"] = df[cols["unit"]].map(clean_text)
    out["point"] = df[cols["point"]].map(lambda v: clean_text(v).upper())
    out["etype"] = df[cols["etype"]].map(clean_text) if cols["etype"] else ""
    out["bearing"] = df[cols["bearing"]].map(clean_text) if cols["bearing"] else ""
    out["bushing"] = df[cols["bushing"]].map(clean_text) if cols["bushing"] else ""
    out["driver"] = df[cols["driver"]].map(clean_text) if cols["driver"] else ""
    out["rpm"] = df[cols["rpm"]].map(clean_text) if cols["rpm"] else ""

    out = out[(out["equipment"] != "") & (out["point"] != "")]
    out = out.drop_duplicates(subset=["equipment", "point"], keep="first")
    return out.reset_index(drop=True)


def normalize_vib(df):
    cols = {}
    for key, cands in VIB_MAP.items():
        cols[key] = pick_col(df, cands, required=key in ("equipment", "point", "value"))

    if cols["equipment"] is None or cols["point"] is None or cols["value"] is None:
        raise ValueError("در شیت ارتعاش، ستون‌های «نام تجهیز»، «نقطه» و «مقدار» لازم است.")

    out = pd.DataFrame()
    out["equipment"] = df[cols["equipment"]].map(clean_text)
    out["point"] = df[cols["point"]].map(lambda v: clean_text(v).upper())
    out["value"] = to_num(df[cols["value"]])

    if cols["date"]:
        d = pd.to_datetime(df[cols["date"]].astype(str).str.translate(AR2EN), errors="coerce")
        if d.isna().all():
            d = pd.to_datetime(
                df[cols["date"]].astype(str).str.translate(AR2EN),
                errors="coerce",
                dayfirst=True,
            )
        out["date"] = d
    else:
        out["date"] = pd.NaT

    out = out.dropna(subset=["value"])
    out = out[out["equipment"] != ""]
    if out["date"].isna().all():
        out["date"] = pd.Timestamp.now()
    out["date"] = out["date"].fillna(out["date"].max())
    return out.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# داده نمونه (فقط وقتی شیت وصل نیست)
# ---------------------------------------------------------------------------
def demo_assets():
    rows = []
    lines = {"8": "آسیاب سدگ", "7": "آسیاب مواد"}
    for line, unit in lines.items():
        for eq, etype, pts in [
            ("کرادر", "کرادر", ["P1", "P2", "P3", "P4", "P5", "P6"]),
            ("فیدر آسیاب سدگ", "گیربکس", ["P1", "P2", "P3", "P4"]),
        ]:
            for i, p in enumerate(pts):
                rows.append(
                    {
                        "equipment": eq,
                        "line": line,
                        "unit": unit,
                        "etype": etype,
                        "point": p,
                        "bearing": ["6234+NU234", "6234", "22236/K30/W33/C3", "", "24192E CA K30/W33", ""][i % 6],
                        "bushing": ["", "", "AOH3136", "AOH3136", "AOH4192", "AOH4192"][i % 6],
                        "driver": "کوپلینگ" if i < 2 else "تسمه",
                        "rpm": "1000" if i < 4 else "220",
                    }
                )
    return pd.DataFrame(rows)


def demo_vib(assets):
    import random

    random.seed(7)
    rows = []
    start = datetime.now() - timedelta(days=14)
    for _, a in assets.iterrows():
        base = 3.4 + (hash(a["point"]) % 10) / 12.0
        for d in range(15):
            for h in (6, 18):
                rows.append(
                    {
                        "equipment": a["equipment"],
                        "point": a["point"],
                        "date": start + timedelta(days=d, hours=h),
                        "value": round(base + random.uniform(-0.45, 0.95), 2),
                    }
                )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# ورود
# ---------------------------------------------------------------------------
def login_screen():
    st.markdown(
        """
<div class="app-header">
  <h1>📈 داشبورد پایش ارتعاشات — سیمان تهران</h1>
  <p>برای ورود، شناسه کاربری و رمز عبور خود را وارد کنید.</p>
</div>
""",
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns([1, 1.4, 1])
    with c2:
        with st.form("login_form"):
            user = st.selectbox("کاربر", list(USERS.keys()), index=0)
            pwd = st.text_input("رمز عبور", type="password")
            ok = st.form_submit_button("ورود", use_container_width=True)
        if ok:
            if USERS.get(user, {}).get("password") == pwd:
                st.session_state["auth"] = {
                    "user": user,
                    "role": USERS[user].get("role", "viewer"),
                    "name": USERS[user].get("name", ""),
                }
                st.rerun()
            else:
                st.error("رمز عبور درست نیست.")


if "auth" not in st.session_state:
    login_screen()
    st.stop()

AUTH = st.session_state["auth"]
IS_ADMIN = AUTH["role"] == "admin"


# ---------------------------------------------------------------------------
# بارگذاری داده‌ها
# ---------------------------------------------------------------------------
def load_data():
    asset_url = SETTINGS.get("asset_url", "").strip()
    vib_url = SETTINGS.get("vib_url", "").strip()
    demo = False
    err = None

    assets_df, vib_df = None, None
    try:
        if asset_url:
            assets_df = normalize_assets(read_sheet(asset_url))
    except Exception as e:
        err = f"شیت تجهیزات: {e}"

    try:
        if vib_url:
            vib_df = normalize_vib(read_sheet(vib_url))
    except Exception as e:
        err = (err + " | " if err else "") + f"شیت ارتعاش: {e}"

    if assets_df is None or assets_df.empty:
        assets_df = demo_assets()
        demo = True
    if vib_df is None or vib_df.empty:
        vib_df = demo_vib(assets_df)
        demo = True

    return assets_df, vib_df, demo, err


assets, vib, IS_DEMO, LOAD_ERR = load_data()

# ---------------------------------------------------------------------------
# نوار کناری: هویت کاربر
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 👤 حساب کاربری")
    role_fa = "مدیر سیستم" if IS_ADMIN else "ناظر"
    st.markdown(f"**{AUTH['user']}**")
    st.caption(f"{AUTH['name']} · {role_fa}")
    if st.button("خروج از حساب", use_container_width=True):
        st.session_state.pop("auth", None)
        st.rerun()

    st.divider()
    st.markdown("### 🔌 منبع داده")
    st.caption("وصل به شیت گوگل" if not IS_DEMO else "داده نمونه (شیت وصل نیست)")
    if LOAD_ERR:
        st.warning(LOAD_ERR, icon="⚠️")

    st.divider()
    st.caption(
        "فیلترهای انتخاب تجهیز، در بالای صفحه اصلی قرار دارند تا در موبایل هم دیده شوند."
    )

# ---------------------------------------------------------------------------
# هدر
# ---------------------------------------------------------------------------
st.markdown(
    f"""
<div class="app-header">
  <h1>📈 داشبورد پایش ارتعاشات سیمان تهران</h1>
  <p>آخرین رکورد: {datetime.now().strftime('%Y-%m-%d %H:%M')} · تعداد رکورد: {len(vib):,} · {'داده نمونه' if IS_DEMO else 'داده شیت'}</p>
</div>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# فیلترها — در صفحه اصلی، همیشه دیده می‌شوند
# ---------------------------------------------------------------------------
st.markdown('<div class="filter-box"><div class="filter-title">🔎 انتخاب تجهیز</div>', unsafe_allow_html=True)

f1, f2, f3, f4 = st.columns([1, 1.2, 1.6, 1])

lines = sorted([x for x in assets["line"].unique() if x], key=lambda s: (len(s), s))
with f1:
    line_sel = st.selectbox("خط تولید", ["همه"] + lines, index=0, key="flt_line")

units_pool = assets if line_sel == "همه" else assets[assets["line"] == line_sel]
units = sorted([x for x in units_pool["unit"].unique() if x])
with f2:
    unit_sel = st.selectbox("واحد", ["همه"] + units, index=0, key="flt_unit")

equip_pool = units_pool if unit_sel == "همه" else units_pool[units_pool["unit"] == unit_sel]
equips = sorted([x for x in equip_pool["equipment"].unique() if x])
with f3:
    eq_sel = st.selectbox("نام تجهیز", equips if equips else ["—"], index=0, key="flt_eq")

with f4:
    days = st.slider("بازه زمانی (روز)", 1, 90, 14, key="flt_days")

st.markdown("</div>", unsafe_allow_html=True)

if not equips:
    st.info("برای این خط و واحد، تجهیزی در شیت تعریف نشده است. فیلتر را تغییر دهید.")
    st.stop()

# ---------------------------------------------------------------------------
# محاسبات تجهیز انتخاب‌شده
# ---------------------------------------------------------------------------
eq_rows = assets[assets["equipment"] == eq_sel].copy()
point_order = sorted(eq_rows["point"].tolist(), key=lambda p: (len(p), p))

etype = clean_text(eq_rows["etype"].iloc[0]) if "etype" in eq_rows else ""
rpm = clean_text(eq_rows["rpm"].iloc[0]) if "rpm" in eq_rows else ""
line_of_eq = clean_text(eq_rows["line"].iloc[0])
unit_of_eq = clean_text(eq_rows["unit"].iloc[0])

start = datetime.now() - timedelta(days=days)
vib_eq = vib[(vib["equipment"] == eq_sel) & (vib["date"] >= pd.Timestamp(start))].copy()
all_eq = vib[vib["equipment"] == eq_sel]

threshold = float(SETTINGS.get("threshold", 4.5) or 4.5)

tabs = ["📊 تحلیل تجهیز"]
if IS_ADMIN:
    tabs += ["👥 کاربران", "⚙️ تنظیمات", "✉️ ارسال اعلان"]

tab_objs = st.tabs(tabs)

# ------------------------------- تب تحلیل -------------------------------
with tab_objs[0]:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("تعداد نقاط", len(point_order))
    m2.metric("بیشترین مقدار (mm/s)", f"{all_eq['value'].max():.2f}" if len(all_eq) else "—")
    m3.metric("میانگین (mm/s)", f"{all_eq['value'].mean():.2f}" if len(all_eq) else "—")
    over = all_eq[all_eq["value"] >= threshold]
    m4.metric("رکورد بالای هشدار", f"{len(over):,}")

    st.markdown(
        f'<div class="meta-line">خط {line_of_eq} · واحد {unit_of_eq}'
        + (f" · نوع {etype}" if etype else "")
        + (f" · دور نامی {rpm}" if rpm else "")
        + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### 🧭 شناسنامه نقاط و بیرینگ‌ها")
    for _, r in eq_rows.iterrows():
        bearing = clean_text(r.get("bearing", "")) or "—"
        bushing = clean_text(r.get("bushing", "")) or "—"
        driver = clean_text(r.get("driver", "")) or "—"
        st.markdown(
            f"""
<div class="pt-card">
  <div class="pt-id">{clean_text(r['point'])}</div>
  <div class="pt-body">
    <span>شماره بیرینگ: <b>{bearing}</b></span>
    <span>بوش: <b>{bushing}</b></span>
    <span>سیستم درایور: <b>{driver}</b></span>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

    st.markdown("#### 📈 روند ارتعاش")
    if vib_eq.empty:
        st.warning("برای این تجهیز در بازه انتخابی رکوردی ثبت نشده است.")
    else:
        chosen = st.multiselect(
            "نمایش نقاط",
            point_order,
            default=point_order[: min(6, len(point_order))],
            key="flt_points",
        )
        fig = go.Figure()
        palette = [
            "#c0392b", "#1f77b4", "#2e9e5b", "#8e44ad",
            "#e67e22", "#16a085", "#d81b60", "#34495e",
        ]
        for i, p in enumerate(chosen or point_order):
            d = vib_eq[vib_eq["point"] == p].sort_values("date")
            if d.empty:
                continue
            fig.add_trace(
                go.Scatter(
                    x=d["date"],
                    y=d["value"],
                    mode="lines+markers",
                    name=p,
                    line=dict(width=2, color=palette[i % len(palette)]),
                    marker=dict(size=4),
                )
            )

        fig.add_hline(
            y=threshold,
            line_dash="dash",
            line_color="#e67e22",
            annotation_text="هشدار",
            annotation_position="right",
        )
        fig.update_layout(
            height=430,
            margin=dict(l=10, r=10, t=30, b=10),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            xaxis_title="",
            yaxis_title="ارتعاش (mm/s RMS)",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        fig.update_xaxes(showgrid=True, gridcolor="#f0eae6")
        fig.update_yaxes(showgrid=True, gridcolor="#f0eae6")
        st.plotly_chart(fig, use_container_width=True)

# ------------------------------- تب کاربران ------------------------------
if IS_ADMIN:
    with tab_objs[1]:
        st.markdown("#### 👥 مدیریت کاربران")
        st.caption("رمز هر کاربر را می‌توانی همین‌جا عوض کنی؛ نیازی به باز کردن کد نیست.")

        edited = []
        for email, info in list(USERS.items()):
            c1, c2, c3, c4 = st.columns([2, 1.2, 1.6, 0.7])
            c1.markdown(f"**{email}**")
            role = c2.selectbox(
                "نقش",
                ["admin", "viewer"],
                index=0 if info.get("role") == "admin" else 1,
                key=f"role_{email}",
                format_func=lambda r: "مدیر" if r == "admin" else "ناظر",
                label_visibility="collapsed",
            )
            pwd = c3.text_input(
                "رمز", value=info.get("password", ""), key=f"pwd_{email}",
                label_visibility="collapsed",
            )
            edited.append((email, role, pwd))
            c4.caption("")

        cc1, cc2 = st.columns(2)
        if cc1.button("💾 ذخیره تغییرات کاربران", use_container_width=True):
            for email, role, pwd in edited:
                USERS[email]["role"] = role
                USERS[email]["password"] = pwd
            save_json(USERS_FILE, USERS)
            st.success("ذخیره شد. دفعه بعد که وارد شوند، رمز جدید اعمال است.")
        if cc2.button("🔄 بازخوانی از فایل", use_container_width=True):
            st.rerun()

        st.divider()
        st.markdown("#### ➕ افزودن کاربر")
        with st.form("add_user"):
            a1, a2, a3 = st.columns([2, 1.2, 1.6])
            new_mail = a1.text_input("شناسه / ایمیل")
            new_role = a2.selectbox("نقش", ["viewer", "admin"], format_func=lambda r: "ناظر" if r == "viewer" else "مدیر")
            new_pwd = a3.text_input("رمز", value="siman123")
            if st.form_submit_button("افزودن"):
                if not new_mail.strip():
                    st.error("شناسه را وارد کن.")
                elif new_mail.strip() in USERS:
                    st.error("این کاربر از قبل هست.")
                else:
                    USERS[new_mail.strip()] = {"password": new_pwd, "role": new_role, "name": ""}
                    save_json(USERS_FILE, USERS)
                    st.success("کاربر اضافه شد.")
                    st.rerun()

# ------------------------------- تب تنظیمات ------------------------------
if IS_ADMIN:
    with tab_objs[2]:
        st.markdown("#### ⚙️ تنظیمات شیت و آستانه هشدار")
        with st.form("settings_form"):
            s1 = st.text_input("لینک شیت تجهیزات", value=SETTINGS.get("asset_url", ""))
            s2 = st.text_input("لینک شیت ارتعاش", value=SETTINGS.get("vib_url", ""))
            s3 = st.number_input(
                "آستانه هشدار (mm/s)", min_value=0.1, max_value=50.0,
                value=float(SETTINGS.get("threshold", 4.5)), step=0.1,
            )
            if st.form_submit_button("💾 ذخیره تنظیمات", use_container_width=True):
                SETTINGS["asset_url"] = s1.strip()
                SETTINGS["vib_url"] = s2.strip()
                SETTINGS["threshold"] = float(s3)
                save_json(SETTINGS_FILE, SETTINGS)
                read_sheet.clear()
                st.success("ذخیره شد.")
                st.rerun()

        st.caption(
            "نکته: شیت باید با گزینه «هر کسی که لینک را دارد، ببیند» به اشتراک گذاشته شده باشد."
        )

        st.divider()
        st.markdown("#### ✉️ تنظیمات ایمیل (SMTP)")
        with st.form("smtp_form"):
            e1, e2 = st.columns([3, 1])
            host = e1.text_input("سرور SMTP", value=SETTINGS.get("smtp_host", "smtp.gmail.com"))
            port = e2.number_input("پورت", 1, 65535, int(SETTINGS.get("smtp_port", 587)))
            user = st.text_input("ایمیل فرستنده", value=SETTINGS.get("smtp_user", ""))
            pwd = st.text_input("رمز اپلیکیشن", value=SETTINGS.get("smtp_pass", ""), type="password")
            to = st.text_input("ایمیل گیرندگان (با کاما جدا کن)", value=SETTINGS.get("mail_to", ""))
            enabled = st.checkbox("ارسال خودکار اعلان فعال باشد", value=bool(SETTINGS.get("notify_enabled", False)))
            if st.form_submit_button("💾 ذخیره تنظیمات ایمیل", use_container_width=True):
                SETTINGS.update(
                    {
                        "smtp_host": host,
                        "smtp_port": int(port),
                        "smtp_user": user,
                        "smtp_pass": pwd,
                        "mail_to": to,
                        "notify_enabled": enabled,
                    }
                )
                save_json(SETTINGS_FILE, SETTINGS)
                st.success("ذخیره شد.")

# ------------------------------- تب اعلان --------------------------------
if IS_ADMIN:
    with tab_objs[3]:
        st.markdown("#### ✉️ ارسال اعلانیه")
        st.caption("یک پیام کوتاه برای گیرندگان تنظیم‌شده در تب تنظیمات بفرست.")

        alarm_points = []
        if len(all_eq):
            g = all_eq.groupby("point")["value"].max()
            alarm_points = [f"{p} ({v:.2f})" for p, v in g[g >= threshold].items()]

        default_body = (
            f"تجهیز: {eq_sel} (خط {line_of_eq} / {unit_of_eq})\n"
            f"آستانه هشدار: {threshold} mm/s\n"
            + ("نقاط بالای هشدار: " + "، ".join(alarm_points) if alarm_points else "همه نقاط در محدوده مجاز.")
        )

        subject = st.text_input("موضوع", value=f"اعلانیه ارتعاش — {eq_sel}")
        body = st.text_area("متن پیام", value=default_body, height=160)

        if st.button("📤 ارسال ایمیل", use_container_width=True):
            to_list = [x.strip() for x in str(SETTINGS.get("mail_to", "")).replace("؛", ",").split(",") if x.strip()]
            if not to_list:
                st.error("در تب تنظیمات، ایمیل گیرندگان را وارد کن.")
            elif not SETTINGS.get("smtp_user") or not SETTINGS.get("smtp_pass"):
                st.error("ایمیل فرستنده و رمز اپلیکیشن را در تنظیمات وارد کن.")
            else:
                try:
                    msg = MIMEText(body, "plain", "utf-8")
                    msg["Subject"] = subject
                    msg["From"] = SETTINGS["smtp_user"]
                    msg["To"] = ", ".join(to_list)
                    with smtplib.SMTP(SETTINGS["smtp_host"], int(SETTINGS["smtp_port"]), timeout=25) as s:
                        s.starttls()
                        s.login(SETTINGS["smtp_user"], SETTINGS["smtp_pass"])
                        s.sendmail(SETTINGS["smtp_user"], to_list, msg.as_string())
                    st.success("ایمیل ارسال شد.")
                except Exception as e:
                    st.error(f"ارسال نشد: {e}")

st.markdown(
    '<div class="meta-line" style="margin-top:26px;">داشبورد پایش ارتعاشات · نسخه ۴.۱ · '
    "هر چه در شیت نوشته شده، همان نمایش داده می‌شود.</div>",
    unsafe_allow_html=True,
)
