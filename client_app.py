import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import time
import os

# --- 1. ROBUST CONNECTION FUNCTION ---
@st.cache_resource
def get_db():
    if not firebase_admin._apps:
        # A. Local Mode
        if os.path.exists('serviceAccountKey.json'):
            cred = credentials.Certificate('serviceAccountKey.json')
        
        # B. Cloud Mode
        else:
            key_dict = {
                "type": st.secrets["firebase"]["type"],
                "project_id": st.secrets["firebase"]["project_id"],
                "private_key_id": st.secrets["firebase"]["private_key_id"],
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
    st.error(f"❌ Connection Error: {e}")
    st.stop()

# --- 2. CONFIGURATION & STATE ---
st.set_page_config(page_title="Student Exam Portal", layout="wide")

if 'exam_started' not in st.session_state:
    st.session_state['exam_started'] = False
if 'start_time' not in st.session_state:
    st.session_state['start_time'] = None

# --- 3. SIDEBAR: LOGIN ---
with st.sidebar:
    st.header("🔐 Candidate Login")
    name = st.text_input("Full Name")
    roll_no = st.text_input("Roll Number")
    
    st.divider()
    st.header("⚙️ Exam Settings")
    selected_topic = st.text_input("Enter Subject Code (Topic)", "Physics")
    exam_duration = st.number_input("Duration (Minutes)", value=30, min_value=5)
    
    if not st.session_state['exam_started']:
        if st.button("Start Exam"):
            if name and roll_no:
                st.session_state['exam_started'] = True
                st.session_state['start_time'] = time.time()
                st.rerun()
            else:
                st.warning("Please enter Name & Roll Number.")

# --- 4. EXAM HALL ---
if st.session_state['exam_started']:
    
    # TIMER
    elapsed = time.time() - st.session_state['start_time']
    remaining = (exam_duration * 60) - elapsed
    
    if remaining <= 0:
        st.error("⏰ TIME IS UP! Submitting automatically...")
        st.stop()
    else:
        mins, secs = divmod(int(remaining), 60)
        st.metric("Time Remaining", f"{mins:02d}:{secs:02d}")
        st.progress(max(0.0, remaining / (exam_duration * 60)))

    st.divider()
    
    # QUESTIONS
    docs = db.collection('questions').where('topic', '==', selected_topic).stream()
    questions = list(docs)
    
    if not questions:
        st.warning(f"No questions found for Subject: '{selected_topic}'.")
    else:
        with st.form("exam_sheet"):
            st.subheader(f"Subject: {selected_topic}")
            
            for i, doc in enumerate(questions, 1):
                q = doc.to_dict()
                q_id = doc.id
                
                st.markdown(f"**Q{i}. {q.get('text')}** *({q.get('marks')} Marks)*")
                
                if "$" in q.get('text', ''):
                    st.latex(q.get('text').replace('$', ''))
                
                if q.get('image_url'):
                    st.image(q.get('image_url'), caption="Reference Figure")

                if q.get('video_url'):
                    st.markdown(f"🎥 [Watch Video Reference]({q.get('video_url')})")

                if q.get('type') == 'MCQ':
                    options = q.get('options', [])
                    st.radio(f"Select Answer for Q{i}", options, key=q_id)
                else:
                    st.text_area(f"Your Answer for Q{i}", height=100, key=q_id)
                
                st.markdown("---")
            
            if st.form_submit_button("🏁 Submit Exam"):
                st.balloons()
                st.success(f"Exam Submitted by {name} ({roll_no})!")

else:
    st.title("🎓 Online Examination Portal")
    st.info("👈 Please Login from the Sidebar to start your test.")
