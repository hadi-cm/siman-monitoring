import streamlit as st
import pandas as pd

# --- DATA PREPARATION ---
# (Assuming the DataFrame 'df' is loaded here as in your previous version)
# df = pd.read_excel('your_file.xlsx')

# --- FILTER STRUCTURE DEFINITION ---
# ساختار سلسله‌مراتبی: خط تولید -> واحد -> تجهیزات
# خطوط ۱، ۲ و ۵ وجود ندارند
filter_structure = {
    # --- موارد مستقل (بدون خط تولید) ---
    "آسیاب سنگ شهدا": {
        "تجهیزات": ["آسیاب سنگ شهدا"]
    },
    "بارگیرخانه تهران": {
        "تجهیزات": ["بارگیرخانه تهران"]
    },
    "بارگیرخانه واحد ۶ یا ۸": {
        "تجهیزات": ["بارگیرخانه واحد ۶ یا ۸"]
    },

    # --- خط تولید ۳ ---
    "خط تولید ۳": {
        "آسیاب سنگ": ["آسیاب سنگ ۲", "آسیاب سنگ ۳"],
        "کوره": ["کوره ۳"],
        "آسیاب سیمان": ["آسیاب سیمان ۲", "آسیاب سیمان ۳"]
    },

    # --- خط تولید ۴ ---
    "خط تولید ۴": {
        "آسیاب سنگ": ["آسیاب سنگ ۴"],
        "آسیاب مواد": ["آسیاب مواد ۴"],
        "کوره": ["کوره ۴"],
        "آسیاب سیمان": ["آسیاب سیمان ۴"]
    },

    # --- خط تولید ۶ ---
    "خط تولید ۶": {
        "آسیاب سنگ": ["آسیاب سنگ ۴ یا ۶"],
        "آسیاب مواد": ["آسیاب مواد ۶"],
        "کوره": ["کوره ۶"],
        "آسیاب سیمان": ["آسیاب سیمان ۶-۱", "آسیاب سیمان ۶-۲"]
    },

    # --- خط تولید ۷ ---
    "خط تولید ۷": {
        "آسیاب سیمان": ["آسیاب سیمان ۷"]
    },

    # --- خط تولید ۸ ---
    "خط تولید ۸": {
        "آسیاب سنگ": ["آسیاب سنگ ۸"],
        "آسیاب مواد": ["آسیاب مواد ۸"],
        "کوره": ["کوره ۸"],
        "آسیاب سیمان": ["آسیاب سیمان ۸-۱", "آسیاب سیمان ۸-۲"]
    },

    # --- خط تولید ۹ ---
    "خط تولید ۹": {
        "آسیاب سنگ": ["آسیاب سنگ ۹"],
        "آسیاب مواد": ["آسیاب مواد ۹"],
        "کوره": ["کوره ۹"],
        "آسیاب سیمان": ["آسیاب سیمان ۹"]
    }
}

INDEPENDENT_ITEMS = ["آسیاب سنگ شهدا", "بارگیرخانه تهران", "بارگیرخانه واحد ۶ یا ۸"]

# --- STREAMLIT UI ---
st.set_page_config(layout="wide", page_title="سیستم فیلترینگ خطوط تولید")
st.title("📊 پنل مدیریت تجهیزات خطوط تولید")
st.sidebar.header("🔍 فیلترهای جستجو")

# 1) فیلتر خط تولید
line_options = ["همه خطوط"] + list(filter_structure.keys())
selected_line = st.sidebar.selectbox("انتخاب خط تولید", line_options)

selected_unit = None
selected_equipment = None

if selected_line == "همه خطوط":
    # جمع‌آوری تمام واحدها از همه بخش‌ها
    all_units = set()
    for section in filter_structure.values():
        all_units.update(section.keys())
    available_units = sorted(all_units)

    selected_unit = st.sidebar.selectbox("انتخاب واحد", ["همه واحدها"] + available_units)

    if selected_unit != "همه واحدها":
        all_equip = set()
        for section in filter_structure.values():
            if selected_unit in section:
                all_equip.update(section[selected_unit])
        available_equipment = sorted(all_equip)
        selected_equipment = st.sidebar.selectbox(
            "انتخاب تجهیزات", ["همه تجهیزات"] + available_equipment
        )
    else:
        selected_equipment = "همه تجهیزات"

else:
    section = filter_structure[selected_line]
    available_units = sorted(section.keys())

    # موارد مستقل: فقط یک کلید «تجهیزات» دارند
    if available_units == ["تجهیزات"]:
        available_equipment = sorted(section["تجهیزات"])
        selected_equipment = st.sidebar.selectbox("انتخاب تجهیزات", available_equipment)
        selected_unit = selected_line
    else:
        selected_unit = st.sidebar.selectbox("انتخاب واحد", available_units)
        available_equipment = sorted(section[selected_unit])
        selected_equipment = st.sidebar.selectbox("انتخاب تجهیزات", available_equipment)

# --- خلاصه فیلتر فعال ---
st.write(
    f"**فیلتر فعال:** {selected_line} ➔ "
    f"{selected_unit if selected_unit else ''} ➔ "
    f"{selected_equipment if selected_equipment else ''}"
)

# --- DATA FILTERING LOGIC (نمونه) ---
# df_filtered = df.copy()
# if selected_line != "همه خطوط":
#     df_filtered = df_filtered[df_filtered['خط تولید'] == selected_line]
# if selected_unit and selected_unit not in ("همه واحدها",) and selected_unit != selected_line:
#     df_filtered = df_filtered[df_filtered['واحد'] == selected_unit]
# if selected_equipment and selected_equipment != "همه تجهیزات":
#     df_filtered = df_filtered[df_filtered['تجهیزات'] == selected_equipment]
# st.dataframe(df_filtered, use_container_width=True)

st.info("اطلاعات فیلتر شده بر اساس داده‌های اکسل شما در این بخش نمایش داده می‌شود.")
