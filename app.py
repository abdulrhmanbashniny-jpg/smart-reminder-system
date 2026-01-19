import streamlit as st
from supabase import create_client
import pandas as pd

# --- الإعدادات ---
st.set_page_config(page_title="Smart Reminder System", layout="wide")

# الربط مع Supabase (المفاتيح تؤخذ من Secrets)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase = create_client(url, key)

st.title("🤖 نظام التذكيرات الذكي")

menu = ["📊 لوحة التحكم", "➕ إضافة معاملة", "👥 المستلمون", "📜 السجلات"]
choice = st.sidebar.selectbox("القائمة", menu)

if choice == "📊 لوحة التحكم":
    st.subheader("حالة المعاملات الحالية")
    res = supabase.table("items").select("title, expiry_date, workflow_status, departments(name)").execute()
    if res.data:
        df = pd.DataFrame(res.data)
        st.dataframe(df, use_container_width=True)

elif choice == "➕ إضافة معاملة":
    st.subheader("إضافة عقد أو معاملة جديدة")
    with st.form("add_form"):
        title = st.text_input("عنوان المعاملة")
        exp_date = st.date_input("تاريخ الانتهاء")
        
        # جلب البيانات المرجعية
        depts = supabase.table("departments").select("*").execute()
        rules = supabase.table("reminder_rules").select("*").execute()
        
        dept_id = st.selectbox("القسم", [d['name'] for d in depts.data])
        rule_id = st.selectbox("قاعدة التذكير", [r['name'] for r in rules.data])
        
        if st.form_submit_button("حفظ"):
            d_id = [d['id'] for d in depts.data if d['name'] == dept_id][0]
            r_id = [r['id'] for r in rules.data if r['name'] == rule_id][0]
            
            supabase.table("items").insert({
                "title": title, "expiry_date": str(exp_date),
                "department_id": d_id, "reminder_rule_id": r_id,
                "category_id": supabase.table("categories").select("id").limit(1).execute().data[0]['id']
            }).execute()
            st.success("تم الحفظ بنجاح!")

elif choice == "📜 السجلات":
    st.subheader("سجل الإشعارات المرسلة")
    logs = supabase.table("notification_log").select("*, items(title), recipients(name)").execute()
    if logs.data:
        st.write(logs.data)
