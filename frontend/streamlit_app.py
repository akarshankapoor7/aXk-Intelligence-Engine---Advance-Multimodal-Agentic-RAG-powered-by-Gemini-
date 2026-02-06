import streamlit as st
import requests
import json
import os
import time
import uuid

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="aXk – Intelligence Engine",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main {
        background-color: #f9f9f9;
    }
    .stChatInput {
        border-radius: 20px;
    }
    .stButton button {
        background-color: #4CAF50;
        color: white;
        border-radius: 10px;
        width: 100%;
        height: 50px;
        font-weight: bold;
    }
    .success-box {
        padding: 20px;
        background-color: #000000;
        color: white;
        border-left: 5px solid #4CAF50;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONSTANTS ---
API_URL = "http://localhost:8050/query"

# --- SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "data_processed" not in st.session_state:
    st.session_state.data_processed = False

if "files_info" not in st.session_state:
    st.session_state.files_info = ""

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

# --- SIDEBAR: KNOWLEDGE BASE ---
with st.sidebar:
    st.title("🧩 Knowledge Base")
    st.markdown("Configure the brain of your engine here.")
    
    st.divider()
    
    st.subheader("🌐 Web Sources")
    urls = st.text_area(
        "Target URLs", 
        height=120, 
        placeholder="https://example.com/article\nhttps://arxiv.org/abs/...",
        help="Enter one URL per line."
    )
    
    st.subheader("kT Upload Documents")
    uploaded_files = st.file_uploader(
        "Supported: PDF, TXT, CSV, DOCX, PNG, JPG", 
        type=["pdf", "txt", "csv", "docx", "png", "jpg", "jpeg"], 
        accept_multiple_files=True
    )
    
    st.divider()
    
    col1, col2 = st.columns([1, 1])
    
    process_btn = st.button("🚀 Initialize Engine", type="primary")
    
    if process_btn:
        with st.spinner("Processing Knowledge Base..."):
            # Simulate processing time for UX
            time.sleep(1.5) 
            
            # Count inputs
            url_count = len([u for u in urls.split("\n") if u.strip()])
            file_count = len(uploaded_files) if uploaded_files else 0
            
            if url_count == 0 and file_count == 0:
                st.warning("⚠️ Please provide at least one URL or File.")
            else:
                st.session_state.data_processed = True
                
                # Construct greeting message details
                details = []
                if file_count > 0:
                    details.append(f"{file_count} document{'s' if file_count > 1 else ''}")
                if url_count > 0:
                    details.append(f"{url_count} web link{'s' if url_count > 1 else ''}")
                
                st.session_state.files_info = " and ".join(details)
                st.toast("System Initialized Successfully!", icon="✅")


    st.divider()
    
    col_n1, col_n2 = st.columns([2, 1])
    if col_n1.button("➕ New Chat", type="primary"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.context_sent = False
        st.session_state.data_processed = False
        st.session_state.files_info = ""
        st.rerun()

    # History List (Max 5)
    st.caption("📜 Recent Sessions (Max 5)")
    try:
         hist_resp = requests.get(f"http://localhost:8050/sessions")
         if hist_resp.status_code == 200:
             sessions = hist_resp.json().get("sessions", [])
             
             for sess in sessions:
                 # Clean ID for display
                 label = sess[:8]
                 if sess == st.session_state.session_id:
                     label += " (Current)"
                     
                 if st.button(f"💬 {label}", key=f"sess_{sess}"):
                     # Load History
                     st.session_state.session_id = sess
                     
                     # Fetch messages
                     h_resp = requests.get(f"http://localhost:8050/history/{sess}")
                     if h_resp.status_code == 200:
                         st.session_state.messages = h_resp.json().get("history", [])
                         st.session_state.data_processed = True # Assume processed if loading old chat
                         st.rerun()
    except:
        st.error("Backend offline")

    with st.expander("⚙️ Advanced Settings"):
        st.checkbox("Enable Deep Web Search", value=True)
        st.checkbox("Show Reasoning Trace", value=False)
        st.selectbox("Model", ["Gemini 2.0 Flash", "Gemini 1.5 Pro"])

# --- MAIN CONTENT ---

# Header Section
col_logo, col_title = st.columns([1, 5])
with col_logo:
    st.markdown("# 🧠") 
with col_title:
    st.markdown("# aXk – Intelligence Engine")
    st.caption("Powered by **Gemini 2.0 Flash** | Agentic RAG System")

st.markdown("---")

# Welcome / Status Section
if not st.session_state.data_processed:
    st.info("👋 **Welcome!** Please add your URLs or Documents in the sidebar and click **'Initialize Engine'** to begin.")
    
    # Hero/Placeholder graphic (optional text based)
    st.markdown("""
    ### 🚀 What can I do?
    - **Summarize** complex PDF research papers.
    - **Extract** insights from live websites.
    - **Synthesize** information across multiple sources.
    """)

else:
    # Professional Activity Notification
    st.markdown(f"""
    <div class="success-box">
        <h3>✅ System Active</h3>
        <p>The <b>{st.session_state.files_info}</b> have been successfully received and indexed by the engine.</p>
        <p><b>I am ready. What would you like to know about this data?</b></p>
    </div>
    """, unsafe_allow_html=True)

    # Pre-fill initial greeting in chat if empty
    if not st.session_state.messages:
        greeting = f"Hi! I've analyzed the {st.session_state.files_info} you provided. You can ask me to summarize them, find specific details, or explain complex concepts. What's on your mind?"
        st.session_state.messages.append({"role": "assistant", "content": greeting})


# --- CHAT INTERFACE ---
for message in st.session_state.messages:
    avatar = "🧑‍💻" if message["role"] == "user" else "🤖"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# --- CHAT INPUT HANDLING ---

# Check for suggestion auto-submit
if "suggestion_msg" in st.session_state and st.session_state.suggestion_msg:
    prompt = st.session_state.suggestion_msg
    st.session_state.suggestion_msg = None # Clear it immediately
else:
    prompt = st.chat_input("Ask aXk Engine...")

if prompt:
    # User Message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)

    # API Logic
    url_list = [u.strip() for u in urls.split("\n") if u.strip()]
    
    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        
        with st.spinner("Thinking..."):
            try:
                # Prepare Payload
                # Prepare Payload
                # Optimization: Only send files/URLs if they haven't been sent yet for this session.
                # However, currently the API appends context to history.
                # We need to track if we've sent context variables.
                
                context_already_sent = st.session_state.get("context_sent", False)
                
                payload_urls = []
                files_payload = []
                
                if not context_already_sent:
                     # First turn - send everything
                     payload_urls = url_list
                     if uploaded_files:
                        for f in uploaded_files:
                            f.seek(0) 
                            files_payload.append(("files", (f.name, f, f.type)))
                     st.session_state.context_sent = True
                
                data = {
                    "query": prompt, 
                    "urls": payload_urls,
                    "session_id": st.session_state.session_id
                }
                
                # POST Request
                response = requests.post(API_URL, data=data, files=files_payload)
                
                if response.status_code == 200:
                    result = response.json()
                    answer = result.get("answer", "No answer generated.")
                    sources = result.get("sources", [])
                    metrics = result.get("metrics", {})
                    
                    # Stream output (simulated for now, text is static)
                    message_placeholder.markdown(answer)
                    
                    # Graphviz Visualization Support
                    import re
                    # Regex to find ```graphviz ... ``` blocks
                    graphviz_blocks = re.findall(r'```graphviz\n(.*?)\n```', answer, re.DOTALL)
                    if graphviz_blocks:
                        for graph in graphviz_blocks:
                            try:
                                st.graphviz_chart(graph)
                            except Exception as e:
                                st.error(f"Failed to render workflow diagram: {e}")

                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    
                    # Sources & Metrics area
                    if sources or metrics:
                        with st.status("📚 References & Metrics", expanded=False):
                            tab_src, tab_met = st.tabs(["Sources", "System Metrics"])
                            
                            with tab_src:
                                if sources:
                                    for s in sources:
                                        st.markdown(f"**🔗 {s.get('title', 'Unknown Source')}**")
                                        st.caption(f"URL: {s.get('url', 'N/A')}")
                                        st.text(s.get('content_snippet', ''))
                                        st.divider()
                                else:
                                    st.write("No external sources cited used.")

                            with tab_met:
                                col_a, col_b, col_c = st.columns(3)
                                col_a.metric("Latency", f"{metrics.get('latency', 0):.2f}s")
                                col_b.metric("Tokens", metrics.get('tokens_used', 0))
                                col_c.metric("Confidence", f"{metrics.get('grounding_score', 0.0) * 100:.0f}%")
                    
                    # Suggestions (Proactive)
                    with st.container():
                        st.markdown("---")
                        st.caption("✨ **Suggested Next Steps:**")
                        c1, c2, c3 = st.columns(3)
                        
                    # Suggestions (Proactive)
                    with st.container():
                        st.markdown("---")
                        st.caption("✨ **Suggested Next Steps:**")
                        c1, c2, c3 = st.columns(3)
                        
                        # Get last answer snippet for context
                        last_ans = answer[:200].replace("\n", " ") + "..."
                        
                        # Callback function to set prompt
                        def set_suggestion(msg):
                            st.session_state.suggestion_msg = msg
                        
                        if c1.button("🔍 Deep Dive", key=f"sugg_1_{len(st.session_state.messages)}"):
                            st.session_state.suggestion_msg = f"Deep Dive: Explain the technical details of this: '{last_ans}'"
                            st.rerun()
                            
                        if c2.button("📝 Summarize", key=f"sugg_2_{len(st.session_state.messages)}"):
                            st.session_state.suggestion_msg = f"Summarize the key points of this in 3 bullets: '{last_ans}'"
                            st.rerun()
                            
                        if c3.button("🔄 Check Accuracy", key=f"sugg_3_{len(st.session_state.messages)}"):
                             st.session_state.suggestion_msg = f"Verify these claims with a strict web search: '{last_ans}'"
                             st.rerun()

                else:
                    error_msg = f"❌ **Error {response.status_code}**: {response.text}"
                    message_placeholder.markdown(error_msg)
            
            except Exception as e:
                message_placeholder.error(f"⚠️ Connection Error: {str(e)}")

    # Footer Stats (Persistent)
    st.sidebar.divider()
    st.sidebar.caption(f"🆔 Session: {st.session_state.session_id[-8:]}")
    
    # Footer Stats (Persistent)
    st.sidebar.divider()
    st.sidebar.caption(f"🆔 Session: {st.session_state.session_id[-8:]}")
    st.sidebar.caption("v2.1 | Local & Private")
