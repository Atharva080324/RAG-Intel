import os
import streamlit as st
import requests

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

st.set_page_config(page_title="RAG Backend Tester", page_icon="📄", layout="wide")

st.title("RAG Backend Tester")
st.caption("A simple local UI for testing auth, documents, jobs, and questions")

if "token" not in st.session_state:
    st.session_state.token = None

if st.session_state.token is None:
    token_from_url = st.query_params.get("token")
    if token_from_url:
        st.session_state.token = token_from_url
        st.query_params.clear()

@st.cache_data(show_spinner=False)
def health_check():
    try:
        r = requests.get(f"{API_BASE}/health", timeout=10)
        return r.status_code, r.json() if r.content else None
    except Exception as e:
        return None, {"error": str(e)}


st.subheader("System")
status_code, payload = health_check()
if status_code == 200:
    st.success(f"Backend healthy: {payload}")
else:
    st.error(f"Backend check failed: {payload}")

st.divider()

st.subheader("Authentication")
with st.form("signup_form"):
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    submitted = st.form_submit_button("Sign up")
    if submitted:
        try:
            r = requests.post(
                f"{API_BASE}/auth/signup",
                json={"email": email, "password": password},
                timeout=20,
            )
            st.write(r.status_code)
            st.json(r.json() if r.content else {})
        except Exception as e:
            st.error(str(e))

with st.form("login_form"):
    login_email = st.text_input("Login Email", key="login_email")
    login_password = st.text_input("Login Password", type="password", key="login_password")
    submitted_login = st.form_submit_button("Log in")
    if submitted_login:
        try:
            r = requests.post(
                f"{API_BASE}/auth/token",
                data={"username": login_email, "password": login_password},
                timeout=20,
            )
            if r.ok:
                st.session_state.token = r.json().get("access_token")
                st.success("Logged in")
            st.json(r.json() if r.content else {})
        except Exception as e:
            st.error(str(e))

if st.session_state.token:
    st.success("Token stored in session")
    st.code(st.session_state.token)

st.divider()

st.subheader("Google OAuth")
st.markdown("Open the backend's Google login endpoint in a browser to start the OAuth flow.")
st.link_button("Open Google login", f"{API_BASE}/auth/google/login")

st.divider()

st.subheader("Documents")
uploaded_file = st.file_uploader("Upload a document", type=["pdf", "txt", "md"])
if uploaded_file is not None and st.session_state.token:
    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "application/octet-stream")}
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    try:
        r = requests.post(f"{API_BASE}/documents/upload", files=files, headers=headers, timeout=120)
        st.json(r.json() if r.content else {})
    except Exception as e:
        st.error(str(e))

if st.button("List documents"):
    headers = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}
    try:
        r = requests.get(f"{API_BASE}/documents/", headers=headers, timeout=20)
        st.json(r.json() if r.content else {})
    except Exception as e:
        st.error(str(e))

st.divider()

st.subheader("Questions")
question = st.text_area("Question")
if st.button("Analyze question") and question:
    payload = {"question": question}
    headers = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}
    try:
        r = requests.post(f"{API_BASE}/questions/analyze", json=payload, headers=headers, timeout=120)
        st.json(r.json() if r.content else {})
    except Exception as e:
        st.error(str(e))
