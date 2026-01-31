import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import time
import os
import json

# --- 1. HYBRID CONNECTION FUNCTION (Local & Cloud) ---
@st.cache_resource
def get_db():
    if not firebase_admin._apps:
        # A. Try Local File
        if os.path.exists('serviceAccountKey.json'):
            cred = credentials.Certificate('serviceAccountKey.json')
        # B. Try Secrets
        else:
            key_dict = json.loads(st.secrets["FIREBASE_KEY"])
            cred = credentials.Certificate(key_dict)

        firebase_admin.initialize_app(cred)
    return firestore.client()

try:
    db = get_db()
except Exception as e:
    st.error("System Error: Could not connect to Exam Database.")
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
    # In a real app, these would be locked/hidden
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
    
    # TIMER LOGIC
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
    
    # FETCH QUESTIONS
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
                
                # Question Header
                st.markdown(f"**Q{i}. {q.get('text')}** *({q.get('marks')} Marks)*")
                
                # Render LaTeX
                if "$" in q.get('text', ''):
                    st.latex(q.get('text').replace('$', ''))
                
                # Render Image (ImgBB)
                if q.get('image_url'):
                    st.image(q.get('image_url'), caption="Reference Figure")

                # Render Video
                if q.get('video_url'):
                    st.markdown(f"🎥 [Watch Video Reference]({q.get('video_url')})")

                # Answer Input
                if q.get('type') == 'MCQ':
                    options = q.get('options', [])
                    st.radio(f"Select Answer for Q{i}", options, key=q_id)
                else:
                    st.text_area(f"Your Answer for Q{i}", height=100, key=q_id)
                
                st.markdown("---")
            
            # SUBMIT
            if st.form_submit_button("🏁 Submit Exam"):
                st.balloons()
                st.success(f"Exam Submitted by {name} ({roll_no})!")
                # Here you would save answers to Firebase 'submissions' collection
else:
    # LANDING PAGE
    st.title("🎓 Online Examination Portal")
    st.info("👈 Please Login from the Sidebar to start your test.")
    st.markdown("""
    **Instructions:**
    1. Ensure stable internet connection.
    2. Do not refresh the page once the exam starts.
    3. Keep an eye on the timer at the top.
    """)