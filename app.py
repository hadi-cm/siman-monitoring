import pandas as pd
import streamlit as st
import base64
import plotly.graph_objects as go
import plotly.express as px
# ==============================================================================
# 0. تنظیمات صفحه
# ==============================================================================
st.set_page_config(page_title='داشبورد فنی ارتعاشات سیمان تهران', layout='wide')
# ==============================================================================
# 1. تنظیمات امنیتی و ورود
# ==============================================================================
USER_CREDENTIALS = {
    'alireza76ir@gmail.com': 'siman123',
    'vah.rezaei@gmail.com': 'siman123',
    'cm.zandiyeh@gmail.com': 'siman123',
    'm.babahasan@gmail.com': 'siman123',
    'freedocs.ir@gmail.com': 'siman123',
    'tehrancement@gmail.com': 'siman123',
    'masoud.sa.1989823@gmail.com': 'siman123',
}
def check_password():
    if 'authenticated' not in st.session_state:
        st.session_state['authenticated'] = False
    if not st.session_state['authenticated']:
        st.markdown('<h2 style="text-align: center;">🔐 ورود به سامانه هوشمند پایش وضعیت سیمان تهران</h2>', unsafe_allow_html=True)
        with st.form('login_form'):
            email = st.text_input('ایمیل کاربری:')
            password = st.text_input('رمز عبور:', type='password')
            if st.form_submit_button('ورود به داشبورد'):
                email_clean = email.strip().lower()
                found_email = next((k for k in USER_CREDENTIALS if k.strip().lower() == email_clean), None)
                if found_email and USER_CREDENTIALS[found_email].strip() == password.strip():
                    st.session_state['authenticated'] = True
                    st.rerun()
                else:
                    st.error('❌ ایمیل یا رمز عبور اشتباه است.')
        return False
    return True
if not check_password():
    st.stop()
# ==============================================================================
# 2. توابع کمکی
# ==============================================================================
def clean_text(text):
    if pd.isna(text): return ''
    text = str(text).strip()
    farsi_nums = '۰۱۲۳۴۵۶۷۸۹'
    arabic_nums = '٠١٢٣٤٥٦٧٨٩'
    english_nums = '0123456789'
    for f, e in zip(farsi_nums, english_nums): text = text.replace(f, e)
    for a, e in zip(arabic_nums, english_nums): text = text.replace(a, e)
    return ' '.join(text.split()).lower()
def get_image_base64(path):
    try:
        with open(path, 'rb') as image_file: return base64.b64encode(image_file.read()).decode()
    except: return ''
def smart_find_column(columns, keywords):
    if columns is None: return None
    for k in keywords:
        for c in columns:
            if k.lower() in str(c).strip().lower():
                return c
    return None
# ==============================================================================
# 3. هدر و لوگوها
# ==============================================================================
logo_siman_base64 = get_image_base64('client_logo.png')
logo_faz_fidar_base64 = get_image_base64('my_logo.png')
st.markdown(f'''
    <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; background-color: white; padding: 15px 30px; border-radius: 15px; box-shadow: 0 4px 8px rgba(0,0,0,0.1);'>
        <img src='data:image/png;base64,{logo_faz_fidar_base64}' style='width: 110px; height: auto;'>
        <div style='text-align: center; color: #1E3A8D; font-size: 26px; font-weight: bold; font-family: Tahoma;'>🛠️ سامانه پایش وضعیت تجهیزات سیمان تهران</div>
        <img src='data:image/png;base64,{logo_siman_base64}' style='width: 110px; height: auto;'>
    </div>
    ''', unsafe_allow_html=True)
# ==============================================================================
# 4. بارگذاری داده‌ها
# ==============================================================================
VIB_URL = 'https://docs.google.com/spreadsheets/d/1H4Yf3ilu72hI7YZns6EXNMpOfH-EII98_sEO_81uXrs/export?format=csv&gid=0'
ASSETS_URL = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vTI4vONsowudctVbskGkkSyQNqkkGZ8AuiykO9UKeE-8FSBZemWkR4q5DSAhpXEqwQkgsCUQy44Vvqx/pub?gid=1276803564&single=true&output=csv'
@st.cache_data(ttl=60)
def load_all_data():
    try:
        df_vib = pd.read_csv(VIB_URL)
        df_vib.columns = df_vib.columns.str.strip()
        title_col = smart_find_column(df_vib.columns, ['عنوان تجهیز', 'نام تجهیز'])
        if title_col:
            df_vib[title_col] = df_vib[title_col].replace(r'^\s*$', pd.NA, regex=True).ffill()
        df_vib = df_vib.astype(str).apply(lambda x: x.str.strip()).replace({'nan': '', 'None': ''})
        try:
            df_assets = pd.read_csv(ASSETS_URL)
            df_assets.columns = df_assets.columns.str.strip()
            df_assets = df_assets.astype(str).apply(lambda x: x.str.strip()).replace({'nan': '', 'None': ''})
        except: df_assets = None
        return df_vib, df_assets
    except Exception as e:
        st.error(f'❌ خطا در دریافت داده‌ها: {e}')
        return None, None
df, df_assets = load_all_data()
def get_point_guide(eq_name, eq_type):
    name = str(eq_name).lower()
    etype = str(eq_type).lower() if eq_type else ''
    if 'گیربکس' in name or 'گیربکس' in etype:
        return 'P1: انتهای موتور | P2: جلوی موتور | P3: محور ورودی گیربکس | P4: سمت آزاد محور ورودی | P5: سمت فیکس محور دوم | P6: سمت آزاد محور دوم | P7: سمت فیکس محور سوم | P8: سمت آزاد محور سوم | P9: بابیت اول سمت گیربکس | P10: بابیت دوم | P11: بابیت نزدیک پینیون آسیاب'
    if 'کراشر' in name or 'کراشر' in etype:
        return 'P1: انتهای موتور | P2: سر موتور | P3: یاتاقان سمت فیکس (پولی کوچک) | P4: یاتاقان سمت آزاد (پولی کوچک) | P5: یاتاقان فیکس (روتور) | P6: یاتاقان سمت آزاد (روتور)'
    if 'فن' in name or 'فن' in etype:
        return 'P1: انتهای موتور | P2: سر موتور | P3: یاتاقان فیکس | P4: یاتاقان آزاد'
    return 'راهنمای نقاط تعریف نشده است.'
# ==============================================================================
# 6. رابط کاربری و فیلترها
# ==============================================================================
if df is not None:
    col_line = smart_find_column(df.columns, ['خط تولید', 'خط'])
    col_unit = smart_find_column(df.columns, ['واحد'])
    col_title = smart_find_column(df.columns, ['عنوان تجهیز', 'نام تجهیز'])
    col_date = smart_find_column(df.columns, ['تاریخ'])
    point_col = smart_find_column(df.columns, ['نقطه', 'point'])
    with st.expander('🔍 سیستم جستجو و فیلتر پیشرفته', expanded=True):
        f1, f2, f3, f4, f5 = st.columns(5)
        with f1:
            sel_line = st.selectbox('📍 خط تولید:', ['همه'] + sorted([str(v) for v in df[col_line].unique() if pd.notna(v)]) if col_line else ['همه'])
        with f2:
            sel_unit = st.selectbox('🏢 واحد:', ['همه'] + sorted([str(v) for v in df[col_unit].unique() if pd.notna(v)]) if col_unit else ['همه'])
        with f3:
            search_eq = st.text_input('🔍 نام تجهیز:', '')
        with f4:
            selected_point = st.selectbox('📍 نقطه:', ['همه'] + [f'P{i}' for i in range(1, 13)])
        with f5:
            sel_date = st.selectbox('📅 تاریخ:', ['همه تاریخ‌ها'] + sorted([str(v) for v in df[col_date].unique() if pd.notna(v)], reverse=True) if col_date else ['همه تاریخ‌ها'])
    filtered_df = df.copy()
    if col_line and sel_line != 'همه':
        filtered_df = filtered_df[filtered_df[col_line].apply(clean_text) == clean_text(sel_line)]
    if col_unit and sel_unit != 'همه':
        filtered_df = filtered_df[filtered_df[col_unit].apply(clean_text) == clean_text(sel_unit)]
    if col_title and search_eq:
        search_clean = clean_text(search_eq)
        filtered_df = filtered_df[filtered_df[col_title].apply(lambda x: search_clean in clean_text(x))]
    if point_col and selected_point != 'همه':
        filtered_df = filtered_df[filtered_df[point_col].astype(str).str.upper().str.strip() == selected_point.upper()]
    if col_date and sel_date != 'همه تاریخ‌ها':
        filtered_df = filtered_df[filtered_df[col_date].apply(clean_text) == clean_text(sel_date)]
    if not filtered_df.empty:
        eq_name_val = filtered_df[col_title].iloc[0] if col_title else ''
        if df_assets is not None:
            asset_name_col = smart_find_column(df_assets.columns, ['نام تجهیز', 'نام', 'تجهیز'])
            if asset_name_col:
                target_clean = clean_text(eq_name_val)
                asset_rows = df_assets[df_assets[asset_name_col].apply(lambda x: target_clean in clean_text(x) or clean_text(x) in target_clean)].copy()
                if not asset_rows.empty:
                    first_row = asset_rows.iloc[0]
                    def get_val_safe(k_list):
                        col_found = smart_find_column(df_assets.columns, k_list)
                        if col_found:
                            v = str(first_row[col_found]).strip()
                            return v if v.lower() not in ['nan', 'none', ''] else '---'
                        return '---'
                    eq_type = get_val_safe(['نوع'])
                    st.markdown(f'''
                    <div style='background-color: #f0f7ff; padding: 20px; border-radius: 15px; border-right: 10px solid #1E3A8D; margin-bottom: 15px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);'>
                        <h3 style='color: #1E3A8D; margin-top: 0; font-family: Tahoma;'>🛠️ مشخصات فنی: {eq_name_val}</h3>
                        <div style='display: flex; justify-content: space-between; font-size: 16px; color: #333; flex-wrap: wrap; gap: 10px;'>
                            <span><b style='color: #1E3A8D;'>🔹 نوع:</b> {eq_type}</span>
                            <span><b style='color: #1E3A8D;'>🔹 دور:</b> {get_val_safe(['دور'])} RPM</span>
                            <span><b style='color: #1E3A8D;'>🔹 واحد:</b> {get_val_safe(['واحد'])}</span>
                        </div>
                        <div style='margin-top: 12px; font-size: 15px; color: #1E3A8D; background: #e6efff; padding: 8px 15px; border-radius: 8px; display: inline-block;'>
                            <b style='color: #1E3A8D;'>📍 راهنمای نقاط (P-Map):</b> {get_point_guide(eq_name_val, eq_type)}
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
                    pts = smart_find_column(df_assets.columns, ['نقطه'])
                    brg = smart_find_column(df_assets.columns, ['بیرینگ'])
                    bsh = smart_find_column(df_assets.columns, ['بوش'])
                    cols_to_show = [c for c in [pts, brg, bsh] if c is not None]
                    if cols_to_show:
                        logistics = asset_rows[cols_to_show].copy()
                        logistics = logistics.replace(['nan', 'None', ''], '---').fillna('---')
                        if brg and bsh: logistics = logistics[((logistics[brg] != '---') | (logistics[bsh] != '---'))]
                        elif brg: logistics = logistics[logistics[brg] != '---']
                        elif bsh: logistics = logistics[logistics[bsh] != '---']
                        rename_map = {pts: 'نقطه', brg: 'شماره بیرینگ', bsh: 'شماره بوش'}
                        logistics = logistics.rename(columns=rename_map)
                        if not logistics.empty:
                            with st.expander('📦 اطلاعات لجستیکی و قطعات', expanded=True):
                                st.dataframe(logistics, hide_index=True, use_container_width=True)
        
        # ==============================================================================
        # بخش اصلاح شده نمایش جدول با رنگ‌بندی
        # ==============================================================================
        
        def color_vibration_cells(val):
            try:
                # تبدیل مقدار به عدد برای مقایسه (تبدیل متون احتمالی به عدد)
                v = float(str(val).replace(',', '.')) 
                if v > 7.1:
                    return 'background-color: #ff4b4b; color: white' # قرمز
                elif v > 4.5:
                    return 'background-color: #ffa500; color: white' # زرد
                else:
                    return 'background-color: #2e7d32; color: white' # سبز
            except:
                return '' # اگر مقدار عدد نبود رنگ نده

        st.markdown('### 📋 جدول جزئیات پایش')
        
        # پیدا کردن ستون‌های ارتعاشی برای اعمال رنگ (عمودی، افقی، محوری)
        vib_cols = [c for c in filtered_df.columns if any(k in str(c) for k in ['عمودی', 'افقی', 'محوری'])]
        
        if vib_cols:
            # اعمال رنگ‌آمیزی فقط روی ستون‌های ارتعاشات
            styled_df = filtered_df.style.map(color_vibration_cells, subset=vib_cols)
            st.dataframe(styled_df, use_container_width=True)
        else:
            st.dataframe(filtered_df, use_container_width=True)

        # ==============================================================================
        # 7. بخش تحلیل‌های بصری و نمودارها
        # ==============================================================================
        st.markdown('---')
        st.markdown('## 📈 تحلیل‌های بصری و روند ارتعاشات')
        # پیدا کردن ستون‌های لرزش (افقی، عمودی، محوری)
        vib_cols = [c for c in df.columns if any(k in str(c) for k in ['عمودی', 'افقی', 'محوری'])]
        if vib_cols:
            tab1, tab2, tab3 = st.tabs(['📉 روند تغییرات نقطه', '📊 مقایسه نقاط', '🍩 وضعیت کلی تجهیزات'])
            with tab1:
                st.markdown('#### تحلیل روند ارتعاشات در یک نقطه')
                point_to_plot = st.selectbox('انتخاب نقطه برای تحلیل روند:', ['همه'] + [f'P{i}' for i in range(1, 13)])
                if point_to_plot != 'همه':
                    # فیلتر داده‌ها برای نقطه انتخابی و تجهیز انتخابی
                    trend_df = df.copy()
                    if col_title: trend_df = trend_df[trend_df[col_title] == eq_name_val]
                    if point_col: trend_df = trend_df[trend_df[point_col].astype(str).str.upper().str.strip() == point_to_plot.upper()]
                    if not trend_df.empty:
                        # تبدیل تاریخ برای مرتب سازی (ساده شده)
                        trend_df = trend_df.sort_values(by=col_date)
                        fig_trend = go.Figure()
                        for col in vib_cols:
                            fig_trend.add_trace(go.Scatter(x=trend_df[col_date], y=pd.to_numeric(trend_df[col], errors='coerce'), 
                                                         mode='lines+markers', name=col))
                        fig_trend.update_layout(title=f'روند ارتعاشات {point_to_plot} - {eq_name_val}', 
                                              xaxis_title='تاریخ', yaxis_title='مقدار (mm/s)', template='plotly_white')
                        st.plotly_chart(fig_trend, use_container_width=True)
                    else:
                        st.info('داده‌ای برای این نقطه در تاریخ‌های مختلف یافت نشد.')
                else:
                    st.info('لطفاً یک نقطه (مثلاً P1) را انتخاب کنید تا روند تغییرات آن را ببینید.')
            with tab2:
                st.markdown('#### مقایسه لرزش نقاط در تاریخ انتخاب شده')
                # استفاده از تاریخ انتخاب شده در فیلترهای بالا
                compare_df = df.copy()
                if col_title: compare_df = compare_df[compare_df[col_title] == eq_name_val]
                if col_date and sel_date != 'همه تاریخ‌ها':
                    compare_df = compare_df[compare_df[col_date].apply(clean_text) == clean_text(sel_date)]
                if not compare_df.empty and point_col:
                    # محاسبه میانگین لرزش در هر نقطه (از هر سه جهت)
                    compare_df['Average_Vib'] = compare_df[vib_cols].apply(pd.to_numeric, errors='coerce').mean(axis=1)
                    fig_bar = px.bar(compare_df, x=point_col, y='Average_Vib', 
                                    title=f'مقایسه شدت لرزش نقاط تجهیز {eq_name_val}',
                                    labels={'Average_Vib': 'میانگین لرزش (mm/s)', point_col: 'نقطه'},
                                    color='Average_Vib', color_continuous_scale='RdYlGn_r')
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info('برای نمایش مقایسه نقاط، لطفاً یک تاریخ مشخص را انتخاب کنید.')
            with tab3:
                st.markdown('#### وضعیت کلی سلامت تجهیزات (بر اساس آخرین داده)')
                # تحلیل وضعیت کلی
                if vib_cols:
                    # پیدا کردن بیشترین لرزش در هر ردیف
                    df['Max_Vib'] = df[vib_cols].apply(pd.to_numeric, errors='coerce').max(axis=1)
                    def categorize(val):
                        if pd.isna(val): return 'نامشخص'
                        if val > 7.1: return 'بحرانی'
                        if val > 4.5: return 'هشدار'
                        return 'سالم'
                    df['Status'] = df['Max_Vib'].apply(categorize)
                    status_counts = df['Status'].value_counts()
                    fig_pie = px.pie(values=status_counts.values, names=status_counts.index, 
                                   color=status_counts.index,
                                   color_discrete_map={'سالم': '#2e7d32', 'هشدار': '#ffa500', 'بحرانی': '#ff4b4b'},
                                   title='درصد وضعیت سلامت تجهیزات کارخانه')
                    st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info('🔎 هیچ داده‌ای با این فیلترها یافت نشد.')
    st.markdown('<div style="text-align:center; margin-top:20px; font-weight:bold;">طراحی و توسعه: مهندس هادی زندیه | شرکت فاز فیدار پارسیان</div>', unsafe_allow_html=True)
else:
    st.error('❌ خطا در دریافت داده‌ها. لطفاً اتصال اینترنت و لینک گوگل‌شیت را بررسی کنید.')
