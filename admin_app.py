import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import requests
import base64
from fpdf import FPDF
import os

# --- CONFIGURATION ---
# ⚠️ PASTE YOUR IMGBB KEY HERE BEFORE UPLOADING TO GITHUB
IMGBB_API_KEY = '2f8f92e37c4b9b9efc7279b226f648a0' 

# --- 1. ROBUST CONNECTION FUNCTION ---
@st.cache_resource
def get_db():
    if not firebase_admin._apps:
        # A. Local Mode (Laptop)
        if os.path.exists('serviceAccountKey.json'):
            cred = credentials.Certificate('serviceAccountKey.json')
        
        # B. Cloud Mode (Streamlit Secrets)
        else:
            # We access the "firebase" section you defined in Secrets
            key_dict = {
                "type": st.secrets["firebase"]["type"],
                "project_id": st.secrets["firebase"]["project_id"],
                "private_key_id": st.secrets["firebase"]["private_key_id"],
                # Vital Fix: Replace escaped newlines with real newlines
                "private_key": st.secrets["firebase"]["private_key"].replace('\\n', '\n'),
                "client_email": st.secrets["firebase"]["client_email"],
                "client_id": st.secrets["firebase"]["client_id"],
                "auth_uri": st.secrets["firebase"]["auth_uri"],
                "token_uri": st.secrets["firebase"]["token_uri"],
                "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
                "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"],
            }
            cred = credentials.Certificate(key_dict)

        firebase_admin.initialize_app(cred)
    return firestore.client()

try:
    db = get_db()
except Exception as e:
    st.error(f"❌ Database Connection Error: {e}")
    st.stop()

# --- 2. HELPER FUNCTIONS ---

def upload_to_imgbb(file_obj):
    if not file_obj:
        return None
    try:
        payload = {
            "key": IMGBB_API_KEY,
            "image": base64.b64encode(file_obj.read())
        }
        response = requests.post("https://api.imgbb.com/1/upload", data=payload)
        data = response.json()
        if data['success']:
            return data['data']['url']
        else:
            st.error(f"ImgBB Error: {data['status']}")
            return None
    except Exception as e:
        st.error(f"Upload Error: {e}")
        return None

def generate_pdf(questions_list, exam_title):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Header
    pdf.set_font("Arial", style="B", size=16)
    pdf.cell(0, 10, txt=exam_title, ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 10, txt="Time: 60 Mins | Total Marks: 100", ln=True, align='C')
    pdf.ln(10)
    
    # Questions
    pdf.set_font("Arial", size=11)
    for i, q in enumerate(questions_list, 1):
        q_text = f"Q{i}. {q.get('text', '')}   [{q.get('marks')} Marks]"
        # Handle encoding
        q_text = q_text.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 7, txt=q_text)
        
        if q.get('type') == 'MCQ':
            opts = q.get('options', [])
            if opts:
                opt_str = f"    (A) {opts[0]}   (B) {opts[1]}   (C) {opts[2]}   (D) {opts[3]}"
                opt_str = opt_str.encode('latin-1', 'replace').decode('latin-1')
                pdf.cell(0, 7, txt=opt_str, ln=True)
        pdf.ln(5)

    return pdf.output(dest='S').encode('latin-1')

# --- 3. UI ---
st.set_page_config(page_title="Master Admin Panel", layout="wide")
st.title("🎓 Exam Controller: Question Bank")

tab1, tab2 = st.tabs(["➕ Add Question", "🖨️ Generate PDF"])

with tab1:
    with st.form("question_entry_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        topic = c1.text_input("Topic", placeholder="e.g. Physics")
        difficulty = c2.selectbox("Difficulty", ["Easy", "Medium", "Hard"])
        marks = c3.number_input("Marks", min_value=1, value=4)

        q_type = st.radio("Question Type", ["MCQ", "Long Answer"], horizontal=True)
        st.info("💡 Use LaTeX for Math: `$\int x^2 dx$`")
        question_text = st.text_area("Question Text", height=150)
        
        c4, c5 = st.columns(2)
        uploaded_img = c4.file_uploader("Attach Image", type=['png', 'jpg', 'jpeg'])
        video_link = c5.text_input("Attach Video Link (YouTube)")

        options = []
        correct_ans = ""
        if q_type == "MCQ":
            st.markdown("#### Options")
            ca, cb = st.columns(2)
            op1 = ca.text_input("Option A"); op2 = cb.text_input("Option B")
            op3 = ca.text_input("Option C"); op4 = cb.text_input("Option D")
            options = [op1, op2, op3, op4]
            correct_ans_index = st.selectbox("Correct Answer", ["A", "B", "C", "D"])
            mapping = {"A": 0, "B": 1, "C": 2, "D": 3}
            if options[0]: correct_ans = options[mapping[correct_ans_index]]

        submitted = st.form_submit_button("💾 Save Question")

        if submitted:
            if not topic or not question_text:
                st.error("Topic and Question Text are required.")
            else:
                with st.spinner("Processing..."):
                    image_url = None
                    if uploaded_img:
                        image_url = upload_to_imgbb(uploaded_img)
                    
                    question_data = {
                        "topic": topic,
                        "difficulty": difficulty,
                        "type": q_type,
                        "text": question_text,
                        "image_url": image_url,
                        "video_url": video_link,
                        "options": options,
                        "correct_answer": correct_ans,
                        "marks": marks,
                        "timestamp": firestore.SERVER_TIMESTAMP
                    }
                    db.collection("questions").add(question_data)
                    st.success("✅ Saved Successfully!")

with tab2:
    st.subheader("Offline Exam Paper Generator")
    col_p1, col_p2 = st.columns(2)
    pdf_topic = col_p1.text_input("Filter by Topic (Exact match)", "Physics")
    pdf_title = col_p2.text_input("Exam Title", "Weekly Mock Test")
    
    if st.button("📄 Generate PDF"):
        docs = db.collection('questions').where('topic', '==', pdf_topic).stream()
        q_list = [doc.to_dict() for doc in docs]
        
        if not q_list:
            st.warning(f"No questions found for topic: {pdf_topic}")
        else:
            pdf_bytes = generate_pdf(q_list, pdf_title)
            st.download_button(
                label="📥 Download PDF",
                data=pdf_bytes,
                file_name=f"{pdf_topic}_Exam.pdf",
                mime="application/pdf"
            )
