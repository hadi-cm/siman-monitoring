python
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import re
# ==========================================
# 1. پیکربندی و تنظیمات اصلی (CONFIG)
# ==========================================
APP_TITLE = 'سیستم هوشمند پایش وضعیت - سیمان تهران'
LOGO_URL = "https://cdn-icons-png.flaticon.com/512/2970/2970141.png" 
# دیتابیس کاربران
USER_DB = {
    'cm.zandiyeh@gmail.com':         {'name': 'هادی زندیه',     'role': 'پیمانکار / مالک سیستم', 'password': 'siman123'},
    'vah.rezaei@gmail.com':          {'name': 'وحید رضایی',     'role': 'مدیر مکانیک',           'password': 'siman123'},
    'me.vibration.shokri@gmail.com': {'name': 'مهدی شکری',      'role': 'مدیر دفتر فنی',         'password': 'siman123'},
    'tehrancment@gmail.com':         {'name': 'سید مهدی حسینی', 'role': 'معاونت فنی',            'password': 'siman123'},
    'alireza76ir@gmail.com':         {'name': 'علیرضا',         'role': 'کارشناس',               'password': 'siman123'},
    'masoud.sa.1989823@gmail.com':   {'name': 'مسعود صمیمی',    'role': 'کارشناس',               'password': 'siman123'},
    'operator2@tehrancment.ir':      {'name': 'اپراتور خط ۲',   'role': 'کاربر',                 'password': 'siman123'},
}
OWNER_EMAIL = 'cm.zandiyeh@gmail.com'
SEND_ROLES = ('مدیر', 'معاونت', 'مالک')
# لینک‌های گوگل شیت
BASE_CSV = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vTI4vONsowudctVbskGkkSyQNqkkGZ8AuiykO9UKeE-8FSBZemWkR4q5DSAhpXEqwQkgsCUQy44Vvqx/pub?output=csv'
VIB_CSV_URL   = BASE_CSV                      
EQUIP_CSV_URL = BASE_CSV + '&gid=1728784730'  
# ستون‌ها
COL_DATE, COL_LINE, COL_UNIT, COL_EQUIP = 'تاریخ', 'خط تولید', 'واحد', 'عنوان تجهیز'
COL_H, COL_V, COL_A, COL_T, COL_S = 'افقی', 'عمودی', 'محوری', 'دما', 'وضعیت'
FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
# ==========================================
# 2. توابع پردازش (ENGINE)
# ==========================================
def to_latin(v):
    out = ''; 
    for ch in str(v):
        if ch in FA_DIGITS: out += str(FA_DIGITS.index(ch))
        else: out += ch
    return out
def fa_num(v):
    out = '';
    for ch in str(v):
        if ch.isdigit(): out += FA_DIGITS[int(ch)]
        else: out += ch
    return out
def norm_text(v):
    # حذف کشیده، فاصله‌های اضافه و تبدیل به لاتین برای تطبیق دقیق
    s = str(v).replace('ـ', '').strip()
    return ' '.join(s.split())
def clean_line_name(v):
    # اصلاح نام خطوط (حذف صفرهای اضافه مثل ۶۰ -> ۶)
    s = to_latin(v).strip()
    digits = ''.join(filter(str.isdigit, s))
    if digits:
        # تبدیل عدد به فرمت استاندارد (مثلا 06 -> 6)
        val = str(int(digits)) 
        return f"خط تولید {fa_num(val)}"
    return norm_text(v)
def parse_jalali(v):
    s = to_latin(v).strip().replace('-', '/').replace('.', '/')
    parts = s.split('/')
    if len(parts) != 3: return pd.NaT
    try:
        jy, jm, jd = int(parts[0]), int(parts[1]), int(parts[2])
        return pd.Timestamp(year=jy + 621, month=1, day=1)
    except: return pd.NaT
def to_num(v):
    s = to_latin(str(v)).replace('ـ', '').strip()
    if s in ('nan', 'None', '', 'عدم دسترسی', 'دکوپل', 'قطع', 'نامشخص', 'N/A'):
        return np.nan
    try:
        return float(s.replace('/', '.'))
    except: return np.nan
@st.cache_data(ttl=300)
def load_and_sync_data():
    try:
        # ۱. لود شیت ارتعاشات
        v_df = pd.read_csv(VIB_CSV_URL)
        v_df.columns = [str(c).strip() for c in v_df.columns]
        # نگاشت ستون‌ها در ارتعاشات
        ren = {}
        for c in v_df.columns:
            cs = c.replace('ـ', '').strip()
            if 'تاریخ' in cs: ren[c] = COL_DATE
            elif 'خط' in cs: ren[c] = COL_LINE
            elif 'واحد' in cs: ren[c] = COL_UNIT
            elif 'عنوان' in cs: ren[c] = COL_EQUIP
            elif 'افقی' in cs: ren[c] = COL_H
            elif 'عمودی' in cs: ren[c] = COL_V
            elif 'محوری' in cs: ren[c] = COL_A
            elif 'دما' in cs: ren[c] = COL_T
        v_df = v_df.rename(columns=ren)
        # ۲. لود شیت تجهیزات
        a_df = pd.read_csv(EQUIP_CSV_URL)
        a_df.columns = [str(c).strip() for c in a_df.columns]
        # پیدا کردن ستون‌های تجهیزات
        def pick(cands):
            for c in a_df.columns:
                for k in cands:
                    if k in c: return c
            return None
        c_line, c_unit, c_eq = pick(['خط']), pick(['واحد']), pick(['تجهیز', 'دستگاه', 'نام'])
        if c_line and c_unit and c_eq:
            a_df = a_df[[c_line, c_unit, c_eq]].dropna()
            a_df.columns = [COL_LINE, COL_UNIT, COL_EQUIP]
            # نرمال‌سازی برای تطبیق
            a_df[COL_LINE] = a_df[COL_LINE].apply(clean_line_name)
            a_df[COL_UNIT] = a_df[COL_UNIT].apply(norm_text)
            a_df[COL_EQUIP] = a_df[COL_EQUIP].apply(norm_text)
            a_df = a_df.drop_duplicates()
        else:
            a_df = pd.DataFrame()
        return v_df, a_df, "متصل"
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), f"خطا: {e}"
def prepare_final_df(v_df, a_df):
    if v_df.empty: return pd.DataFrame(), pd.DataFrame()
    # پاکسازی ارتعاشات
    df = v_df.copy()
    for c in [COL_H, COL_V, COL_A, COL_T]:
        if c in df.columns: df[c] = df[c].apply(to_num)
    df[COL_DATE] = df[COL_DATE].map(parse_jalali)
    df = df.dropna(subset=[COL_DATE, COL_LINE, COL_EQUIP])
    # نرمال‌سازی برای تطبیق با شیت تجهیزات
    df[COL_LINE] = df[COL_LINE].apply(clean_line_name)
    df[COL_UNIT] = df[COL_UNIT].apply(norm_text)
    # نکته طلایی: ما نام تجهیز را در اینجا تغییر نمی‌دهیم، فقط برای جستجو آماده می‌کنیم
    df[COL_EQUIP_CLEAN] = df[COL_EQUIP].apply(norm_text)
    # تجمیع
    agg_keys = [COL_DATE, COL_LINE, COL_UNIT, COL_EQUIP]
    df_agg = df.groupby(agg_keys, as_index=False).agg({
        COL_H: 'max', COL_V: 'max', COL_A: 'max', COL_T: 'max'
    })
    df_agg['حداکثر'] = df_agg[[COL_H, COL_V, COL_A]].max(axis=1).round(2)
    df_agg[COL_S] = 'نرمال'
    df_agg.loc[df_agg['حداکثر'] >= 4.5, COL_S] = 'هشدار'
    df_agg.loc[df_agg['حداکثر'] >= 7.0, COL_S] = 'بحرانی'
    return df_agg, a_df
# ==========================================
# 3. رابط کاربری (UI)
# ==========================================
def main():
    st.set_page_config(page_title=APP_TITLE, page_icon='📊', layout='wide')
    # --- ورود ---
    if 'user_email' not in st.session_state: st.session_state.user_email = None
    if not st.session_state.user_email:
        st.title("🔐 ورود به سامانه")
        email = st.text_input("ایمیل:")
        pwd = st.text_input("رمز عبور:", type="password")
        if st.button("ورود"):
            if email in USER_DB and USER_DB[email]['password'] == pwd:
                st.session_state.user_email = email
                st.rerun()
            else: st.error("نام کاربری یا رمز اشتباه است.")
        return
    user_info = USER_DB[st.session_state.user_email]
    is_editor = (st.session_state.user_email == OWNER_EMAIL)
    is_sender = any(k in user_info['role'] for k in SEND_ROLES)
    # --- هدر ---
    col_l, col_t = st.columns([1, 6])
    with col_l: st.image(LOGO_URL, width=80)
    with col_t:
        st.title(APP_TITLE)
        st.caption(f"👤 {user_info['name']} | 🔑 {user_info['role']}")
    if st.sidebar.button("🚪 خروج"):
        st.session_state.user_email = None
        st.rerun()
    # --- لود داده‌ها ---
    raw_v, raw_a, status = load_and_sync_data()
    if raw_v.empty:
        st.error(f"خطا در اتصال: {status}"); st.stop()
    df_all, a_df = prepare_final_df(raw_v, raw_a)
    # --- فیلترها ---
    st.markdown("---")
    f1, f2, f3, f4, f5 = st.columns([2, 2, 3, 2, 2])
    # ۱. فیلتر خط
    lines = sorted(df_all[COL_LINE].unique())
    with f1: sel_line = st.selectbox("۱) خط تولید", ["همه خطوط"] + lines)
    # ۲. فیلتر واحد
    unit_src = df_all if sel_line == "همه خطوط" else df_all[df_all[COL_LINE] == sel_line]
    units = sorted(unit_src[COL_UNIT].unique())
    with f2: sel_unit = st.selectbox("۲) واحد", ["همه واحدها"] + units, key=f"u_{sel_line}")
    # ۳. فیلتر تجهیز (بسیار مهم: حل مشکل عدم نمایش داده)
    eq_src = unit_src if sel_unit == "همه واحدها" else unit_src[unit_src[COL_UNIT] == sel_unit]
    # ما از لیست تجهیزات شیت دوم استفاده می‌کنیم تا حتی اگر در ارتعاش نبود هم دیده شود
    # اما برای نمایش در فیلتر، فقط آن‌هایی را می‌آوریم که در این واحد هستند
    if sel_line != "همه خطوط" or sel_unit != "همه واحدها":
        # فیلتر کردن لیست تجهیزات بر اساس انتخاب‌های بالا
        a_filtered = a_df if (sel_line == "همه خطوط" and sel_unit == "همه واحدها") else \
                     a_df if sel_line == "همه خطوط" else \
                     a_df[(a_df[COL_LINE] == sel_line) & (a_df[COL_UNIT] == sel_unit)]
        equips_list = sorted(a_filtered[COL_EQUIP].unique())
    else:
        equips_list = sorted(a_df[COL_EQUIP].unique())
    with f3:
        if not equips_list:
            sel_equip = []
            st.selectbox("۳) عنوان تجهیز", ["-"], disabled=True)
        elif len(equips_list) == 1:
            sel_equip = [st.selectbox("۳) عنوان تجهیز", equips_list, key=f"eq_{sel_line}_{sel_unit}")]
        else:
            sel_equip = st.multiselect("۳) عنوان تجهیز", ["همه تجهیزات"] + equips_list, default=["همه تجهیزات"], key=f"eq_{sel_line}_{sel_unit}")
    # ۴. فیلتر تاریخ (جدید)
    with f4:
        date_mode = st.selectbox("۴) فیلتر تاریخ", ["همه تاریخ‌ها", "بازه زمانی", "تاریخ‌های خاص"], key="dm")
        selected_dates = []
        if date_mode == "بازه زمانی":
            all_dates = sorted(df_all[COL_DATE].unique())
            if all_dates:
                start_d, end_d = st.date_input("انتخاب بازه", [all_dates[0], all_dates[-1]])
                selected_dates = [start_d, end_d]
            else: st.info("تاریخی یافت نشد")
        elif date_mode == "تاریخ‌های خاص":
            all_dates = sorted(df_all[COL_DATE].unique())
            selected_dates = st.multiselect("انتخاب تاریخ‌ها", all_dates)
    with f5:
        days_val = st.slider("بازه (روز)", 1, 90, 30)
    # --- اعمال فیلترها با منطق تطبیق هوشمند ---
    df = df_all.copy()
    if sel_line != "همه خطوط": df = df[df[COL_LINE] == sel_line]
    if sel_unit != "همه واحدها": df = df[df[COL_UNIT] == sel_unit]
    # تطبیق هوشمند تجهیز (Substring Match)
    if sel_equip and "همه تجهیزات" not in sel_equip:
        # این بخش مشکل تو را حل می‌کند:
        # ما چک می‌کنیم اگر نام تجهیز انتخاب شده در متنِ ستون تجهیزات ارتعاشات وجود داشته باشد
        mask = df[COL_EQUIP].apply(lambda x: any(eq_name in str(x) for eq_name in sel_equip))
        df = df[mask]
    # فیلتر تاریخ
    if date_mode == "بازه زمانی" and selected_dates:
        df = df[(df[COL_DATE] >= selected_dates[0]) & (df[COL_DATE] <= selected_dates[1])]
    elif date_mode == "تاریخ‌های خاص" and selected_dates:
        df = df[df[COL_DATE].isin(selected_dates)]
    else:
        # فیلتر روزهای اخیر به عنوان پیش‌فرض اگر تاریخ خاص انتخاب نشده باشد
        start_limit = datetime.now().date() - timedelta(days=days_val-1)
        df = df[df[COL_DATE] >= start_limit]
    # --- نمایش نتایج ---
    st.markdown("---")
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1: st.metric("کل رکوردها", len(df))
    with m2: st.metric("بحرانی", len(df[df[COL_S] == 'بحرانی']))
    with m3: st.metric("هشدار", len(df[df[COL_S] == 'هشدار']))
    with m4: st.metric("میانگین دما", f"{df[COL_T].mean():.1f}°C" if not df.empty else "0")
    with m5: st.metric("وضعیت کلی", "⚠️ توجه" if len(df[df[COL_S] == 'بحرانی']) > 0 else "✅ عادی")
    tab1, tab2, tab3, tab4 = st.tabs(["📋 جدول داده‌ها", "📈 نمودارها", "📨 ارسال اعلان", "👥 کاربران"])
    with tab1:
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            st.download_button("⬇️ دانلود CSV", df.to_csv(index=False).encode('utf-8-sig'), "report.csv", "text/csv")
        else:
            st.warning("داده‌ای با این فیلترها یافت نشد.")
    with tab2:
        if not df.empty:
            fig = px.line(df, x=COL_DATE, y=[COL_H, COL_V, COL_A], title="روند ارتعاشات (mm/s)")
            st.plotly_chart(fig, use_container_width=True)
            if COL_T in df.columns:
                st.plotly_chart(px.line(df, x=COL_DATE, y=COL_T, title="روند دما"), use_container_width=True)
        else: st.info("داده‌ای برای نمودار موجود نیست.")
    with tab3:
        # بخش اعلان (همان منطق خودت)
        crit = df[df[COL_S] == 'بحرانی']
        if not crit.empty:
            st.error(f"⚠️ {len(crit)} مورد بحرانی یافت شد!")
            # ... (ادامه منطق ارسال اعلان)
        else:
            st.success("وضعیت بحرانی ثبت نشده است.")
    with tab4:
        # بخش مدیریت کاربران
        st.write("مدیریت کاربران...")
        st.dataframe(pd.DataFrame([{'نام': v['name'], 'ایمیل': k, 'نقش': v['role']} for k, v in USER_DB.items()]))
if name == "__main__":
    main()
