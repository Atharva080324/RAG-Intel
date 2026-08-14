import json
import os
import time
from collections.abc import Iterator

import requests
import streamlit as st

API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8002")
REQUEST_TIMEOUT = 120
SUGGESTIONS = [
    "Summarize the key points in this document.",
    "What are the most important facts or entities mentioned?",
    "What evidence in this document supports its main conclusion?",
]

st.set_page_config(
    page_title="Document Intelligence",
    page_icon=":material/find_in_page:",
    layout="wide",
)

st.title("Document intelligence")
st.caption("Upload a document, let the background worker index it, then ask grounded questions with source citations.")

if "token" not in st.session_state:
    st.session_state.token = None

for key, default in {
    "documents": [],
    "messages": [],
    "last_workflow": None,
    "last_citations": [],
    "last_elapsed": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

if st.session_state.token is None:
    token_from_url = st.query_params.get("token")
    if token_from_url:
        st.session_state.token = token_from_url
        st.query_params.clear()

def api_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}


def api_error(response: requests.Response) -> str:
    try:
        body = response.json()
        return str(body.get("detail", body))
    except ValueError:
        return response.text or response.reason


@st.cache_data(ttl=10, show_spinner=False)
def health_check():
    try:
        r = requests.get(f"{API_BASE}/health", timeout=10)
        return r.status_code, r.json() if r.content else None
    except Exception as e:
        return None, {"error": str(e)}


def load_documents() -> list[dict[str, object]]:
    if not st.session_state.token:
        return []
    try:
        response = requests.get(f"{API_BASE}/documents/", headers=api_headers(), timeout=20)
        if response.ok:
            return response.json().get("items", [])
        st.error(api_error(response), icon=":material/error:")
    except requests.RequestException as exc:
        st.error(f"Could not load documents: {exc}", icon=":material/error:")
    return []


def refresh_documents() -> None:
    st.session_state.documents = load_documents()


def status_badge(status: str) -> None:
    colors = {"completed": "green", "processing": "orange", "queued": "orange", "pending": "orange", "failed": "red"}
    st.badge(status.replace("_", " ").title(), color=colors.get(status, "gray"))


def stream_answer(document_id: int, question: str) -> Iterator[str]:
    st.session_state.last_workflow = None
    st.session_state.last_citations = []
    started_at = time.perf_counter()
    try:
        with requests.post(
            f"{API_BASE}/questions/stream",
            json={"document_id": document_id, "question": question},
            headers=api_headers(),
            timeout=REQUEST_TIMEOUT,
            stream=True,
        ) as response:
            if not response.ok:
                yield f"\n\n:red[Request failed: {api_error(response)}]"
                return
            event = None
            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("event: "):
                    event = line.removeprefix("event: ")
                    continue
                if not line.startswith("data: "):
                    continue
                try:
                    data = json.loads(line.removeprefix("data: "))
                except json.JSONDecodeError:
                    continue
                if event == "token":
                    yield data.get("text", "")
                elif event == "workflow":
                    st.session_state.last_workflow = data
                elif event == "citations":
                    st.session_state.last_citations = data
                elif event == "error":
                    yield f"\n\n:red[Answer generation failed: {data.get('detail', 'Unknown error')}]"
                    return
    except requests.RequestException as exc:
        yield f"\n\n:red[Could not reach the backend: {exc}]"
    finally:
        st.session_state.last_elapsed = round(time.perf_counter() - started_at, 1)


with st.sidebar:
    st.header("Workspace", divider="gray")
    status_code, payload = health_check()
    if status_code == 200:
        st.success("API connected", icon=":material/check_circle:")
    else:
        st.error("API unavailable", icon=":material/error:")
        st.caption(str(payload))

    if not st.session_state.token:
        auth_mode = st.segmented_control("Account", ["Sign in", "Create account"], default="Sign in")
        with st.form("auth_form", border=False):
            auth_email = st.text_input("Email")
            auth_password = st.text_input("Password", type="password")
            auth_submit = st.form_submit_button("Continue", icon=":material/login:")
        if auth_submit:
            try:
                if auth_mode == "Create account":
                    response = requests.post(f"{API_BASE}/auth/signup", json={"email": auth_email, "password": auth_password}, timeout=20)
                    if response.ok:
                        st.success("Account created. Sign in to continue.")
                    else:
                        st.error(api_error(response), icon=":material/error:")
                else:
                    response = requests.post(f"{API_BASE}/auth/token", data={"username": auth_email, "password": auth_password}, timeout=20)
                    if response.ok:
                        st.session_state.token = response.json().get("access_token")
                        refresh_documents()
                        st.rerun()
                    else:
                        st.error(api_error(response), icon=":material/error:")
            except requests.RequestException as exc:
                st.error(f"Authentication failed: {exc}", icon=":material/error:")
        st.link_button("Continue with Google", f"{API_BASE}/auth/google/login", icon=":material/account_circle:")
    else:
        st.success("Authenticated", icon=":material/verified_user:")
        if st.button("Sign out", icon=":material/logout:", width="stretch"):
            st.session_state.token = None
            st.session_state.documents = []
            st.session_state.messages = []
            st.rerun()
    st.caption("FastAPI · Redis · Celery · PostgreSQL/pgvector · LangGraph")


if not st.session_state.token:
    st.info("Sign in from the sidebar to begin.", icon=":material/login:")
    st.stop()

refresh_col, clear_col = st.columns(2, vertical_alignment="center")
with refresh_col:
    if st.button("Refresh documents", icon=":material/refresh:"):
        refresh_documents()
        st.rerun()
with clear_col:
    if st.button("Clear conversation", icon=":material/delete_sweep:"):
        st.session_state.messages = []
        st.rerun()

with st.container(border=True):
    st.subheader("Upload and index", divider="gray")
    uploaded_file = st.file_uploader("Choose a PDF, text, or Markdown file", type=["pdf", "txt", "md"])
    if uploaded_file is not None and st.button("Upload document", icon=":material/upload_file:", type="primary"):
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type or "application/octet-stream")}
        try:
            response = requests.post(f"{API_BASE}/documents/upload", files=files, headers=api_headers(), timeout=REQUEST_TIMEOUT)
            if response.ok:
                job = response.json()
                st.success(f"Upload queued. Job #{job['job_id']} is indexing in the background.", icon=":material/schedule:")
                refresh_documents()
            else:
                st.error(api_error(response), icon=":material/error:")
        except requests.RequestException as exc:
            st.error(f"Upload failed: {exc}", icon=":material/error:")

documents = st.session_state.documents or load_documents()
st.session_state.documents = documents
completed_documents = [document for document in documents if document.get("status") == "completed"]

with st.container(border=True):
    st.subheader("Your documents", divider="gray")
    if not documents:
        st.caption("No documents yet. Upload a file to start the asynchronous ingestion pipeline.")
    else:
        for document in documents:
            row = st.container(horizontal=True, horizontal_alignment="distribute", vertical_alignment="center")
            with row:
                st.write(f":material/description: **{document['filename']}**")
                status_badge(str(document["status"]))
                st.caption(f"ID {document['id']}")

if not completed_documents:
    st.info("A document must reach **Completed** before it can be queried. Refresh after the worker finishes.", icon=":material/pending:")
    st.stop()

document_options = {f"{item['filename']} · ID {item['id']}": int(item["id"]) for item in completed_documents}
selected_label = st.selectbox("Active document", options=list(document_options))
selected_document_id = document_options[selected_label]

st.subheader("Ask your document", divider="gray")
if not st.session_state.messages:
    suggestion = st.pills("Suggested questions", SUGGESTIONS, label_visibility="collapsed")
    if suggestion:
        st.session_state.messages.append({"role": "user", "content": suggestion})
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=":material/robot:" if message["role"] == "assistant" else None):
        st.markdown(message["content"])
        if message.get("citations"):
            with st.expander("Sources", icon=":material/format_quote:"):
                st.json(message["citations"])
        if message.get("workflow"):
            with st.expander("Retrieval details", icon=":material/query_stats:"):
                st.caption(f"Completed in {message.get('elapsed', 0)} seconds")
                st.json(message["workflow"])

prompt = st.chat_input("Ask a focused question about the selected document", submit_mode="disable")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar=":material/robot:"):
        with st.status("Retrieving evidence and generating an answer…", expanded=False) as status:
            answer = st.write_stream(stream_answer(selected_document_id, prompt))
            status.update(label=f"Answer completed in {st.session_state.last_elapsed}s", state="complete", expanded=False)
        if st.session_state.last_citations:
            with st.expander("Sources", icon=":material/format_quote:"):
                st.json(st.session_state.last_citations)
        if st.session_state.last_workflow:
            with st.expander("Retrieval details", icon=":material/query_stats:"):
                st.caption(f"Completed in {st.session_state.last_elapsed} seconds")
                st.json(st.session_state.last_workflow)
    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "citations": st.session_state.last_citations,
        "workflow": st.session_state.last_workflow,
        "elapsed": st.session_state.last_elapsed,
    })
