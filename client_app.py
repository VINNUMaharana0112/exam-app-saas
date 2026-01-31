import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import time
import os
import requests
import base64

# --- CONFIGURATION ---
# ⚠️ PASTE YOUR IMGBB KEY HERE
IMGBB_API_KEY = '2f8f92e37c4b9b9efc7279b226f648a0' 

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

# --- 2. HELPER: UPLOAD TO IMGBB ---
def upload_student_image(file_obj):
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
        return None
    except:
        return None

# --- 3. STATE MANAGEMENT ---
st.set_page_config(page_title="Student Exam Portal", layout="wide")

if 'exam_started' not in st.session_state:
    st.session_state['exam_started'] = False
if 'start_time' not in st.session_state:
    st.session_state['start_time'] = None
# We use this to store uploaded file URLs so they don't vanish on refresh
if 'uploaded_answers' not in st.session_state:
    st.session_state['uploaded_answers'] = {}

# --- 4. SIDEBAR ---
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

# --- 5. EXAM HALL ---
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
    
    # FETCH QUESTIONS
    docs = db.collection('questions').where('topic', '==', selected_topic).stream()
    questions = list(docs)
    
    if not questions:
        st.warning(f"No questions found for Subject: '{selected_topic}'.")
    else:
        # We use a container instead of a form for uploads to work smoother
        st.subheader(f"Subject: {selected_topic}")
        
        # Dictionary to capture final answers
        final_answers = {}

        for i, doc in enumerate(questions, 1):
            q = doc.to_dict()
            q_id = doc.id
            
            st.markdown(f"**Q{i}. {q.get('text')}** *({q.get('marks')} Marks)*")
            
            if "$" in q.get('text', ''):
                st.latex(q.get('text').replace('$', ''))
            
            if q.get('image_url'):
                st.image(q.get('image_url'), caption="Reference Figure", width=300)

            # --- INPUT LOGIC ---
            if q.get('type') == 'MCQ':
                options = q.get('options', [])
                # Store MCQ answer directly
                ans = st.radio(f"Select Answer for Q{i}", options, key=q_id)
                final_answers[q_id] = ans
            else:
                # LONG ANSWER: Text OR Image Upload
                st.markdown("Write answer below OR upload a photo of your paper:")
                text_ans = st.text_area(f"Text Answer Q{i}", height=100, key=f"text_{q_id}")
                
                # File Uploader
                uploaded_file = st.file_uploader(f"📷 Upload Photo for Q{i}", type=['png', 'jpg', 'jpeg'], key=f"file_{q_id}")
                
                # Handling Upload
                if uploaded_file:
                    # Check if we already uploaded this specific file to save bandwidth
                    if q_id not in st.session_state['uploaded_answers']:
                        with st.spinner(f"Uploading image for Q{i}..."):
                            url = upload_student_image(uploaded_file)
                            if url:
                                st.session_state['uploaded_answers'][q_id] = url
                                st.success("✅ Image Uploaded!")
                    
                    # Show preview of uploaded answer
                    if q_id in st.session_state['uploaded_answers']:
                        st.image(st.session_state['uploaded_answers'][q_id], width=200, caption="Your Answer Sheet")
                        final_answers[q_id] = st.session_state['uploaded_answers'][q_id]
                else:
                    # If no file, take the text
                    final_answers[q_id] = text_ans
            
            st.markdown("---")
        
        # SUBMIT BUTTON
        if st.button("🏁 Submit Exam & Upload Answers"):
            # Here we would save 'final_answers' to Firebase
            
            # 1. Save Submission to Firestore (New Feature)
            submission_data = {
                "student_name": name,
                "roll_no": roll_no,
                "topic": selected_topic,
                "answers": final_answers,
                "timestamp": firestore.SERVER_TIMESTAMP
            }
            db.collection('submissions').add(submission_data)
            
            st.balloons()
            st.success(f"Exam Submitted! We received {len(final_answers)} answers.")
            st.write("Receipt ID generated in Database.")
            st.stop()

else:
    st.title("🎓 Online Examination Portal")
    st.info("👈 Please Login from the Sidebar to start your test.")
