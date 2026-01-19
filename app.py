import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px
from datetime import datetime, date

# --- إعدادات الصفحة والهوية ---
st.set_page_config(page_title="Expiry Sentinel Pro", page_icon="🛡️", layout="wide")

# CSS مخصص لتحسين المظهر (تم تصحيح السطر أدناه)
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 20px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    div[data-testid="stExpander"] { border: none; box-shadow: 0 2px 4px rgba(0,0,0,0.05); background-color: white; }
    </style>
    """, unsafe_allow_html=True)


# --- الاتصال بـ Supabase ---
@st.cache_resource
def get_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = get_client()

# --- القائمة الجانبية الاحترافية ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/559/559343.png", width=80)
    st.title("Sentinel Pro")
    st.markdown("---")
    menu = st.radio("القائمة الرئيسية", ["📊 لوحة التحكم", "📦 إدارة العناصر", "👥 المستلمون", "📨 قوالب الرسائل", "⚙️ الإعدادات"])

# --- 1. لوحة التحكم (Dashboard) ---
if menu == "📊 لوحة التحكم":
    st.title("📊 الرؤية الشاملة")
    
    # مقاييس سريعة
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total = supabase.table("items").select("id", count="exact").execute().count
        st.metric("إجمالي العناصر", total)
    with col2:
        critical = supabase.table("items").select("id", count="exact").lte("expiry_date", str(date.today())).execute().count
        st.metric("منتهية الصلاحية", critical, delta_color="inverse")
    with col3:
        sent = supabase.table("notification_log").select("id", count="exact").eq("status", "sent").execute().count
        st.metric("تنبيهات ناجحة", sent)
    with col4:
        rate = (sent / total * 100) if total > 0 else 0
        st.metric("كفاءة التغطية", f"{int(rate)}%")

    st.markdown("---")
    
    # رسوم بيانية
    c1, c2 = st.columns([2, 1])
    with c1:
        st.subheader("📈 جدول الإرسال الأسبوعي")
        logs = supabase.table("notification_log").select("sent_at, status").execute()
        if logs.data:
            ldf = pd.DataFrame(logs.data)
            ldf['sent_at'] = pd.to_datetime(ldf['sent_at']).dt.date
            fig = px.area(ldf.groupby('sent_at').count().reset_index(), x='sent_at', y='status', title="نشاط التنبيهات")
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        st.subheader("📂 توزيع الأقسام")
        items = supabase.table("items").select("departments(name)").execute()
        if items.data:
            idf = pd.DataFrame([i['departments']['name'] for i in items.data], columns=['Department'])
            fig = px.pie(idf, names='Department', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

# --- 2. إدارة العناصر (Items Management) ---
elif menu == "📦 إدارة العناصر":
    st.title("📦 مستودع المعاملات")
    
    tab1, tab2 = st.tabs(["🔍 عرض الكل", "➕ إضافة جديد"])
    
    with tab1:
        search = st.text_input("بحث بالاسم أو الرقم المرجعي...")
        query = supabase.table("items").select("*, departments(name), reminder_rules(name)")
        if search: query = query.ilike("title", f"%{search}%")
        data = query.execute().data
        
        if data:
            df = pd.DataFrame(data)
            # تجميل الجدول
            df['القسم'] = df['departments'].apply(lambda x: x['name'])
            df['القاعدة'] = df['reminder_rules'].apply(lambda x: x['name'])
            st.dataframe(df[['ref_number', 'title', 'expiry_date', 'القسم', 'القاعدة', 'workflow_status']], use_container_width=True)
        else:
            st.info("لا توجد بيانات مطابقة")

    with tab2:
        with st.form("pro_add_form"):
            c1, c2 = st.columns(2)
            title = c1.text_input("اسم المعاملة/العقد")
            expiry = c2.date_input("تاريخ الانتهاء")
            
            depts = supabase.table("departments").select("*").execute().data
            rules = supabase.table("reminder_rules").select("*").execute().data
            
            dept = c1.selectbox("القسم المسؤل", [d['name'] for d in depts])
            rule = c2.selectbox("نظام التذكير", [r['name'] for r in rules])
            
            recipients = supabase.table("recipients").select("*").execute().data
            selected_recs = st.multiselect("المستلمون (واتساب/تيليجرام)", [r['name'] for r in recipients])
            
            if st.form_submit_button("🛡️ تأمين وحفظ"):
                d_id = next(d['id'] for d in depts if d['name'] == dept)
                r_id = next(r['id'] for r in rules if r['name'] == rule)
                
                # إدخال العنصر
                new_item = supabase.table("items").insert({
                    "title": title, "expiry_date": str(expiry),
                    "department_id": d_id, "reminder_rule_id": r_id,
                    "category_id": supabase.table("categories").select("id").limit(1).execute().data[0]['id']
                }).execute()
                
                # ربط المستلمين
                if new_item.data and selected_recs:
                    item_id = new_item.data[0]['id']
                    recs_ids = [r['id'] for r in recipients if r['name'] in selected_recs]
                    for rid in recs_ids:
                        supabase.table("item_recipients").insert({"item_id": item_id, "recipient_id": rid}).execute()
                st.success("تمت الإضافة بنجاح!")

# --- 3. إدارة المستلمين (Recipients) ---
elif menu == "👥 المستلمون":
    st.title("👥 إدارة جهات الاتصال")
    with st.expander("➕ إضافة مستلم جديد"):
        name = st.text_input("الاسم الكامل")
        c1, c2 = st.columns(2)
        wa = c1.text_input("رقم الواتساب (مثال: +9665...)")
        tg = c2.text_input("ID تيليجرام")
        if st.button("حفظ المستلم"):
            supabase.table("recipients").insert({"name": name, "whatsapp_number": wa, "telegram_id": tg}).execute()
            st.success("تم الحفظ")
            st.rerun()
            
    res = supabase.table("recipients").select("*").execute()
    if res.data:
        st.table(pd.DataFrame(res.data)[['name', 'whatsapp_number', 'telegram_id']])

# --- 4. قوالب الرسائل (Templates) ---
elif menu == "📨 قوالب الرسائل":
    st.title("📨 تخصيص الرسائل")
    st.info("استخدم الرموز: {{recipient_name}}, {{item_title}}, {{days_left}}")
    
    tab_wa, tab_tg = st.tabs(["WhatsApp Template", "Telegram Template"])
    with tab_wa:
        current_wa = "عزيزي {{recipient_name}}، نذكرك بأن {{item_title}} ينتهي بعد {{days_left}} أيام."
        new_wa = st.text_area("نص رسالة الواتساب", value=current_wa, height=150)
        if st.button("تحديث قالب واتساب"):
            st.success("تم التحديث")
