"""
streamlit_privacy_qna_dpo_enhanced.py
Beautiful Privacy-by-Design guided questionnaire for DPOs with enhanced UI/UX

Requirements (pip):
streamlit pandas openpyxl python-docx PyPDF2 faiss-cpu sentence-transformers langchain langchain_community
langchain_openai azure-openai python-dotenv openpyxl plotly
"""

import os
import io
import json
import re
from datetime import datetime
from typing import List, Dict, Any

import pandas as pd
import streamlit as st
from docx import Document
from PyPDF2 import PdfReader
from dotenv import load_dotenv

# Optional LLM imports
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.embeddings import SentenceTransformerEmbeddings
    from langchain_community.vectorstores import FAISS
    from langchain_openai import AzureChatOpenAI
    from langchain.schema import HumanMessage, SystemMessage
except ImportError as e:
    st.warning(f"Some optional dependencies not available: {e}")
    RecursiveCharacterTextSplitter = None
    SentenceTransformerEmbeddings = None
    FAISS = None
    AzureChatOpenAI = None

load_dotenv()

# --- Enhanced UI Configuration ---
st.set_page_config(
    page_title="Privacy-by-Design Assessment",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for beautiful UI
st.markdown("""
<style>
    /* Main theme colors */
    :root {
        --primary-color: #667eea;
        --secondary-color: #764ba2;
        --success-color: #10b981;
        --warning-color: #f59e0b;
        --danger-color: #ef4444;
        --bg-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }
    
    /* Custom header */
    .custom-header {
        background: var(--bg-gradient);
        padding: 2.5rem 2rem;
        border-radius: 20px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
    }
    
    .custom-header h1 {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }
    
    .custom-header p {
        color: rgba(255, 255, 255, 0.95);
        font-size: 1.1rem;
        margin: 0;
    }
    
    /* Question card styling */
    .question-card {
        background: white;
        padding: 2rem;
        border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        border-left: 5px solid var(--primary-color);
        margin-bottom: 2rem;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .question-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
    }
    
    .question-number {
        display: inline-block;
        background: var(--bg-gradient);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 25px;
        font-weight: 600;
        margin-bottom: 1rem;
        font-size: 0.9rem;
    }
    
    .question-text {
        font-size: 1.3rem;
        font-weight: 600;
        color: #1e293b;
        margin-bottom: 1rem;
        line-height: 1.5;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        margin: 0.5rem 0;
    }
    
    .status-complete {
        background: #d1fae5;
        color: #065f46;
    }
    
    .status-partial {
        background: #fef3c7;
        color: #92400e;
    }
    
    .status-missing {
        background: #fee2e2;
        color: #991b1b;
    }
    
    /* Progress sidebar */
    .progress-item {
        padding: 0.75rem;
        margin-bottom: 0.5rem;
        border-radius: 10px;
        transition: all 0.2s;
        cursor: pointer;
        border-left: 3px solid transparent;
    }
    
    .progress-item:hover {
        background: #f3f4f6;
        border-left-color: var(--primary-color);
    }
    
    .progress-item-active {
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
        border-left-color: var(--primary-color);
        font-weight: 600;
    }
    
    /* Risk badges */
    .risk-badge {
        display: inline-block;
        padding: 0.5rem 1.2rem;
        border-radius: 25px;
        font-weight: 700;
        font-size: 0.9rem;
        margin: 0.5rem 0.5rem 0.5rem 0;
    }
    
    .risk-high {
        background: #fee2e2;
        color: #991b1b;
        border: 2px solid #f87171;
    }
    
    .risk-medium {
        background: #fef3c7;
        color: #92400e;
        border: 2px solid #fbbf24;
    }
    
    .risk-low {
        background: #d1fae5;
        color: #065f46;
        border: 2px solid #34d399;
    }
    
    /* Enhanced buttons */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        padding: 0.6rem 1.5rem;
        transition: all 0.3s;
        border: none;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* Text area styling */
    .stTextArea textarea {
        border-radius: 12px;
        border: 2px solid #e5e7eb;
        font-size: 1rem;
        transition: border-color 0.3s;
    }
    
    .stTextArea textarea:focus {
        border-color: var(--primary-color);
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* Info boxes */
    .info-box {
        background: linear-gradient(135deg, #e0e7ff 0%, #ddd6fe 100%);
        padding: 1.2rem;
        border-radius: 12px;
        margin: 1rem 0;
        border-left: 4px solid var(--primary-color);
    }
    
    .warning-box {
        background: linear-gradient(135deg, #fef3c7 0%, #fed7aa 100%);
        padding: 1.2rem;
        border-radius: 12px;
        margin: 1rem 0;
        border-left: 4px solid var(--warning-color);
    }
    
    /* Metrics styling */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.06);
        text-align: center;
        transition: transform 0.2s;
    }
    
    .metric-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.1);
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        background: var(--bg-gradient);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #64748b;
        font-weight: 600;
        margin-top: 0.5rem;
    }
    
    /* Sidebar enhancements */
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f9fafb 0%, #ffffff 100%);
    }
    
    /* Progress bar custom styling */
    .stProgress > div > div > div {
        background: var(--bg-gradient);
    }
    
    /* File uploader styling */
    .uploadedFile {
        border-radius: 10px;
        border: 2px dashed var(--primary-color);
        padding: 1rem;
        margin: 0.5rem 0;
    }
    
    /* Animation for cards */
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    .question-card {
        animation: slideIn 0.4s ease-out;
    }
    
    /* Tooltip styling */
    .tooltip {
        position: relative;
        display: inline-block;
        cursor: help;
    }
    
    /* Table styling */
    .dataframe {
        border-radius: 10px;
        overflow: hidden;
    }
    
    /* Success/Error message styling */
    .stAlert {
        border-radius: 10px;
        border-left-width: 4px;
    }
</style>
""", unsafe_allow_html=True)

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-35-turbo")

# Enhanced Questionnaire
QUESTIONNAIRE = [
    {
        "id": "country",
        "q": "Which country(ies) will the process or solution be developed, deployed, or used in?",
        "notes": "Used to adapt jurisdictional obligations (GDPR, PIPL, PDPA, LGPD). Provide exact country names.",
        "expected": ["country names", "multiple jurisdictions if applicable", "regulatory framework"],
        "icon": "🌍"
    },
    {
        "id": "project_name",
        "q": "What is the name of the process or solution?",
        "notes": "Provide a unique name or identifier so the project can be referenced in ROPA (GDPR Art. 30).",
        "expected": ["project name", "unique identifier", "business context"],
        "icon": "📋"
    },
    {
        "id": "business_objective",
        "q": "What is the main business objective of the solution or process?",
        "notes": "Explain why this exists and the value it brings. Be specific (e.g., fraud detection, HR onboarding, personalization).",
        "expected": ["business objective", "value or benefit", "specific use case", "business justification"],
        "icon": "🎯"
    },
    {
        "id": "data_processing_purposes",
        "q": "List the specific purposes for processing personal data (one purpose per line).",
        "notes": "Each purpose should be narrow and legitimate (GDPR Art. 6; purpose limitation principle).",
        "expected": ["list of purposes", "one purpose per line", "legitimate basis for each purpose"],
        "icon": "📝"
    },
    {
        "id": "personal_data_categories",
        "q": "What categories of personal data will be processed?",
        "notes": "Be exhaustive. Flag special categories (health, biometrics, race, religion, trade union, sex life).",
        "expected": ["list of data categories", "flag special/sensitive categories", "examples for each category"],
        "icon": "🔐"
    },
    {
        "id": "data_subjects",
        "q": "Who are the data subjects whose personal data will be processed?",
        "notes": "Identify the categories of individuals (e.g., employees, customers, children, patients).",
        "expected": ["categories of data subjects", "vulnerable groups if applicable"],
        "icon": "👥"
    }
]

# --- File parsing helpers (same as original) ---
def extract_text_from_docx(file_bytes: bytes) -> str:
    try:
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    except Exception as e:
        st.error(f"Error extracting from DOCX: {e}")
        return ""

def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for p in reader.pages:
            pages.append(p.extract_text() or "")
        return "\n".join(pages)
    except Exception as e:
        st.error(f"Error extracting from PDF: {e}")
        return ""

def extract_text_from_txt(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return file_bytes.decode("latin-1", errors="ignore")

def extract_text_from_xlsx(file_bytes: bytes) -> str:
    try:
        xls = pd.read_excel(io.BytesIO(file_bytes), sheet_name=None, dtype=str)
        lines = []
        for sheet_name, df in xls.items():
            df = df.fillna("")
            for _, row in df.iterrows():
                row_vals = [str(x).strip() for x in row.tolist() if str(x).strip()]
                if row_vals:
                    lines.append(" | ".join(row_vals))
        return "\n".join(lines)
    except Exception as e:
        st.error(f"Error extracting from Excel: {e}")
        return ""

def build_text_chunks_from_files(uploaded_files) -> List[str]:
    raw_texts = []
    for file in uploaded_files:
        name = file.name.lower()
        bytes_content = file.getvalue()

        if name.endswith(".pdf"):
            raw_texts.append(extract_text_from_pdf(bytes_content))
        elif name.endswith(".docx"):
            raw_texts.append(extract_text_from_docx(bytes_content))
        elif name.endswith(".txt"):
            raw_texts.append(extract_text_from_txt(bytes_content))
        elif name.endswith(".xls") or name.endswith(".xlsx"):
            raw_texts.append(extract_text_from_xlsx(bytes_content))

    joined = "\n".join([t for t in raw_texts if t and t.strip()])
    if not joined.strip():
        return []

    if RecursiveCharacterTextSplitter:
        splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
        return splitter.split_text(joined)
    else:
        parts = [p.strip() for p in joined.split('\n\n') if p.strip()]
        return parts

def create_faiss_from_chunks(text_chunks):
    if not text_chunks or (FAISS is None) or (SentenceTransformerEmbeddings is None):
        return None
    try:
        embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
        return FAISS.from_texts(text_chunks, embedding=embeddings)
    except Exception as e:
        st.error(f"Error creating vector store: {e}")
        return None

# --- LLM functions (same as original) ---
def call_llm_extract_and_assess(question: str, context_text: str, llm_client) -> Dict[str, Any]:
    prompt = f"""
You are a privacy compliance expert assistant that extracts answers from provided CONTEXT.
Output MUST be valid JSON with keys:
- answer: concise extracted answer (string). If no answer found, return "".
- status: one of "complete", "partial", "missing".
- missing: array of short strings describing missing details if status is "partial" or "missing".

CONTEXT:
{context_text}

QUESTION:
{question}

Extraction rules:
- Use only the context provided. Do not invent facts.
- If context fully answers the question with enough detail for privacy assessment, set status = "complete".
- If context has some relevant info but lacks specifics needed for compliance, set status = "partial" and list what is missing.
- If no relevant info found, set status = "missing" and suggest what information is needed.
- Focus on privacy-relevant details like data types, purposes, legal basis, security measures.

Return only JSON. No explanations, no text outside JSON.
"""

    try:
        messages = [
            SystemMessage(content="You are a precise privacy compliance extraction assistant. Output only JSON."),
            HumanMessage(content=prompt)
        ]
        resp = llm_client.invoke(messages)
        text = resp.content if hasattr(resp, 'content') else str(resp)
    except Exception as e:
        return {"answer": "", "status": "missing", "missing": [f"LLM call failed: {e}"]}

    try:
        parsed = json.loads(text)
    except Exception:
        m = re.search(r'\{.*\}', text, flags=re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group(0))
            except Exception:
                parsed = {"answer": "", "status": "missing", "missing": ["Could not parse LLM output."]}
        else:
            parsed = {"answer": "", "status": "missing", "missing": ["LLM returned unparsable output."]}

    return {
        "answer": parsed.get("answer", "").strip(),
        "status": parsed.get("status", "missing"),
        "missing": parsed.get("missing", [])
    }

def assess_risk_for_answer(qid: str, answer: str) -> Dict[str, Any]:
    score = 1
    reasons = []
    ans = (answer or "").lower()

    if not ans.strip():
        return {"score": 3, "level": "High", "reasons": ["No answer provided — cannot assess risk"]}

    sensitive_keywords = [
        "health", "medical", "genetic", "biometric", "race", "ethnic", "religion",
        "sexual", "sex life", "trade union", "political", "criminal", "healthcare"
    ]
    if any(k in ans for k in sensitive_keywords):
        score = max(score, 3)
        reasons.append("Contains special categories of personal data (GDPR Art. 9)")

    financial_keywords = [
        "bank", "credit card", "card number", "iban", "account number", "payment",
        "financial", "salary", "income", "tax", "insurance"
    ]
    if any(k in ans for k in financial_keywords):
        score = max(score, 2)
        reasons.append("Contains financial data")

    vulnerable_keywords = [
        "child", "children", "minor", "vulnerable", "patient", "prison", "elderly",
        "disability", "employee", "student"
    ]
    if any(k in ans for k in vulnerable_keywords):
        score = max(score, 3)
        reasons.append("Involves vulnerable data subjects")

    if len(reasons) >= 2:
        score = max(score, 3)

    level = {1: "Low", 2: "Medium", 3: "High"}.get(score, "High")
    return {"score": score, "level": level, "reasons": reasons or ["Standard processing — low risk"]}

def check_completeness(answer: str, expected_items: List[str]) -> List[str]:
    if not expected_items:
        return []
    if not (answer or "").strip():
        return expected_items

    ans = answer.lower()
    missing = []

    for item in expected_items:
        tokens = [t for t in re.split(r"\W+", item.lower()) if t]
        if not any(tok in ans for tok in tokens):
            missing.append(item)

    return missing

def autofill_question(q_text: str, expected: List[str], vectorstore, llm):
    if not vectorstore:
        return {"answer": "", "status": "missing", "missing": ["No document index available"]}

    try:
        docs = vectorstore.similarity_search(q_text, k=4)
        context_text = "\n\n".join([
            d.page_content if hasattr(d, "page_content") else str(d) 
            for d in docs
        ]).strip()

        if not context_text:
            return {"answer": "", "status": "missing", "missing": ["No relevant content found in documents"]}

        if llm:
            result = call_llm_extract_and_assess(q_text, context_text, llm)
            if result.get("answer") and expected:
                expected_missing = check_completeness(result["answer"], expected)
                if expected_missing:
                    result["missing"] = list(set(result.get("missing", []) + expected_missing))
                    if result.get("status") == "complete":
                        result["status"] = "partial"
            return result
        else:
            snippet = context_text[:800] + "..." if len(context_text) > 800 else context_text
            exp_missing = check_completeness(snippet, expected) if expected else []
            return {
                "answer": snippet,
                "status": "partial" if exp_missing else "complete",
                "missing": exp_missing
            }

    except Exception as e:
        return {"answer": "", "status": "missing", "missing": [f"Error in autofill: {e}"]}

def initialize_llm():
    if not all([AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AzureChatOpenAI]):
        return None

    try:
        return AzureChatOpenAI(
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_version=AZURE_API_VERSION,
            deployment_name=AZURE_DEPLOYMENT,
            api_key=AZURE_OPENAI_API_KEY,
            temperature=0.1
        )
    except Exception as e:
        st.warning(f"Could not initialize Azure OpenAI client: {e}")
        return None

def should_trigger_dpia(aggregate_risks: List[Dict[str, Any]], answers_map: Dict[str, str]) -> Dict[str, Any]:
    reasons = []
    high_count = sum(1 for r in aggregate_risks if r.get("score") == 3)
    if high_count >= 2:
        reasons.append(f"{high_count} high-risk factors identified")

    return {"dpia_required": len(reasons) > 0, "reasons": reasons}

# --- Enhanced UI Components ---
def render_header():
    st.markdown("""
    <div class="custom-header">
        <h1>🔒 Privacy-by-Design Assessment</h1>
        <p>AI-Powered Data Protection Compliance Tool for DPOs</p>
    </div>
    """, unsafe_allow_html=True)

def render_status_badge(status: str) -> str:
    icons = {"complete": "✅", "partial": "⚠️", "missing": "❌"}
    classes = {"complete": "status-complete", "partial": "status-partial", "missing": "status-missing"}
    
    return f"""
    <span class="status-badge {classes.get(status, 'status-missing')}">
        {icons.get(status, '❌')} {status.upper()}
    </span>
    """

def render_risk_badge(level: str) -> str:
    classes = {"High": "risk-high", "Medium": "risk-medium", "Low": "risk-low"}
    icons = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
    
    return f"""
    <span class="risk-badge {classes.get(level, 'risk-low')}">
        {icons.get(level, '🟢')} {level} Risk
    </span>
    """

def render_progress_sidebar():
    st.sidebar.markdown("### 📊 Progress Overview")
    
    for idx, q in enumerate(QUESTIONNAIRE):
        m = st.session_state.answers_meta[q["id"]]
        status = m.get("status", "missing")
        
        q_text = q['q'][:40] + "..." if len(q['q']) > 40 else q['q']
        
        status_icons = {"complete": "✅", "partial": "⚠️", "missing": "❌"}
        icon = status_icons.get(status, "❌")
        
        is_active = idx == st.session_state.current_q
        active_class = "progress-item-active" if is_active else ""
        
        st.sidebar.markdown(f"""
        <div class="progress-item {active_class}">
            {q.get('icon', '📝')} <strong>{idx+1}.</strong> {q_text} {icon}
        </div>
        """, unsafe_allow_html=True)
    
    # Stats
    complete_count = sum(1 for q in QUESTIONNAIRE if st.session_state.answers_meta[q["id"]].get("status") == "complete")
    st.sidebar.markdown(f"""
    <div style="margin-top: 1.5rem; padding: 1rem; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.05);">
        <div class="metric-value">{complete_count}/{len(QUESTIONNAIRE)}</div>
        <div class="metric-label">Completed</div>
    </div>
    """, unsafe_allow_html=True)

# --- Main App ---
def main():
    # Initialize session state
    if "answers_meta" not in st.session_state:
        st.session_state.answers_meta = {
            q["id"]: {"answer": "", "status": "missing", "missing": []} 
            for q in QUESTIONNAIRE
        }
    if "current_q" not in st.session_state:
        st.session_state.current_q = 0
    if "risk_results" not in st.session_state:
        st.session_state.risk_results = {
            q["id"]: {"score": None, "level": None, "reasons": []} 
            for q in QUESTIONNAIRE
        }

    # Render header
    render_header()

    # Initialize LLM
    llm = initialize_llm()

    # Enhanced Sidebar
    with st.sidebar:
        st.markdown("### 📁 Document Upload")
        
        with st.expander("📋 Privacy Notice", expanded=False):
            st.markdown("""
            This tool processes your uploaded documents locally for privacy assessment purposes only. 
            No personal data is stored permanently. Chat history is retained for 1 year for audit purposes.
            """)
        
        agree = st.checkbox("I accept the Privacy Notice", value=False)
        
        if agree:
            uploaded_files = st.file_uploader(
                "Upload project documents",
                type=["pdf", "docx", "txt", "xls", "xlsx"],
                accept_multiple_files=True,
                help="Upload project documentation to enable AI-assisted answer extraction"
            )

            if uploaded_files:
                st.success(f"✅ {len(uploaded_files)} file(s) uploaded")
                
                if st.button("🔧 Process Documents", use_container_width=True):
                    with st.spinner("🔄 Extracting text and building vector index..."):
                        chunks = build_text_chunks_from_files(uploaded_files)
                        if chunks:
                            vectorstore = create_faiss_from_chunks(chunks)
                            if vectorstore:
                                st.session_state.vectorstore = vectorstore
                                st.session_state.vectorstore_ready = True
                                st.success(f"✅ Processed {len(chunks)} text chunks!")
                            else:
                                st.error("❌ Failed to create vector index")
                        else:
                            st.error("❌ No text extracted")
        
        st.markdown("---")
        
        # AI Status
        st.markdown("### 🤖 AI Assistant")
        if llm:
            st.success("✅ Azure OpenAI Ready")
        else:
            st.info("ℹ️ Manual Mode Only")

        if st.session_state.get("vectorstore_ready"):
            st.success("✅ Documents Indexed")
        else:
            st.info("ℹ️ No Documents")
        
        st.markdown("---")
        
        # Progress sidebar
        render_progress_sidebar()

    # Main content area
    col_left, col_right = st.columns([3, 1])

    with col_left:
        # Progress bar
        progress = (st.session_state.current_q + 1) / len(QUESTIONNAIRE)
        st.progress(progress)
        
        q_item = QUESTIONNAIRE[st.session_state.current_q]
        meta = st.session_state.answers_meta[q_item["id"]]
        
        # Question card
        st.markdown(f"""
        <div class="question-card">
            <span class="question-number">{q_item.get('icon', '📝')} Question {st.session_state.current_q + 1} of {len(QUESTIONNAIRE)}</span>
            <div class="question-text">{q_item["q"]}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Info box
        if q_item.get("notes"):
            st.markdown(f"""
            <div class="info-box">
                <strong>💡 Guidance:</strong> {q_item['notes']}
            </div>
            """, unsafe_allow_html=True)
        
        # Status display
        st.markdown(render_status_badge(meta.get("status", "missing")), unsafe_allow_html=True)
        
        # Auto-fill attempt
        if (not meta.get("answer")) and st.session_state.get("vectorstore_ready"):
            with st.spinner("🔍 Analyzing documents for relevant information..."):
                expected = q_item.get("expected", [])
                autofill_result = autofill_question(
                    q_item["q"], 
                    expected, 
                    st.session_state.get("vectorstore"),
                    llm
                )

                if autofill_result.get("answer"):
                    meta.update(autofill_result)
                    st.session_state.answers_meta[q_item["id"]] = meta
                    st.rerun()

        # Warning for missing items
        if meta.get("missing"):
            missing_items = "\n".join([f"• {item}" for item in meta["missing"]])
            st.markdown(f"""
            <div class="warning-box">
                <strong>⚠️ Missing Details:</strong><br>
                {missing_items.replace(chr(10), '<br>')}
            </div>
            """, unsafe_allow_html=True)

        # Answer input
        answer_input = st.text_area(
            "📝 Your Answer:",
            value=meta.get("answer", ""),
            height=250,
            help="Provide a comprehensive answer. For the first 5 questions, all expected details must be included to proceed.",
            key=f"ans_{q_item['id']}",
            placeholder="Type your answer here or use AI-assisted extraction from uploaded documents..."
        )

        st.markdown("<br>", unsafe_allow_html=True)

        # Navigation buttons
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("⬅️ Previous", disabled=(st.session_state.current_q == 0), use_container_width=True):
                st.session_state.current_q -= 1
                st.rerun()

        with col2:
            if st.button("💾 Save & Continue", type="primary", use_container_width=True):
                handle_save_continue(answer_input, q_item, meta)

        with col3:
            if st.button("✅ Mark Complete", use_container_width=True):
                handle_confirm_complete(answer_input, q_item, meta)

        with col4:
            if st.button("⏭️ Skip", disabled=(st.session_state.current_q < 5), use_container_width=True):
                if st.session_state.current_q < len(QUESTIONNAIRE) - 1:
                    st.session_state.current_q += 1
                st.rerun()

    with col_right:
        # Risk preview
        risk = st.session_state.risk_results.get(q_item["id"], {})
        if risk.get("level"):
            st.markdown("### ⚠️ Risk Level")
            st.markdown(render_risk_badge(risk.get("level", "Unknown")), unsafe_allow_html=True)
            
            if risk.get("reasons"):
                st.markdown("**Risk Factors:**")
                for reason in risk["reasons"]:
                    st.markdown(f"• {reason}")

        # Quick tips
        st.markdown("### 💡 Quick Tips")
        st.markdown("""
        - Be specific and detailed
        - Reference regulations when applicable
        - Flag sensitive data categories
        - Consider data subject rights
        - Think about data retention
        """)

    # Summary and Export Section
    if st.session_state.current_q >= len(QUESTIONNAIRE) - 1:
        show_summary_section()

def handle_save_continue(answer_input: str, q_item: dict, meta: dict):
    """Handle save and continue action"""
    trimmed = answer_input.strip()
    if not trimmed:
        st.error("❌ Answer cannot be empty")
        return

    # Strict validation for first 5 questions
    if st.session_state.current_q < 5:
        expected = q_item.get("expected", [])
        missing = check_completeness(trimmed, expected)
        if missing:
            st.error(f"❌ **Answer incomplete.** Please add details about: {', '.join(missing)}")
            st.session_state.answers_meta[q_item["id"]] = {
                "answer": trimmed, "status": "partial", "missing": missing
            }
            return

    # Assess risk and save
    risk_result = assess_risk_for_answer(q_item["id"], trimmed)
    st.session_state.risk_results[q_item["id"]] = risk_result

    status = "complete" if len(trimmed) > 50 and not trimmed.endswith("...") else "partial"
    st.session_state.answers_meta[q_item["id"]] = {
        "answer": trimmed, "status": status, "missing": []
    }

    # Advance to next question
    if st.session_state.current_q < len(QUESTIONNAIRE) - 1:
        st.session_state.current_q += 1

    st.success("✅ Answer saved!")
    st.rerun()

def handle_confirm_complete(answer_input: str, q_item: dict, meta: dict):
    """Handle confirm complete action"""
    trimmed = answer_input.strip()
    if not trimmed:
        st.error("❌ Answer cannot be empty")
        return

    # Strict validation for first 5 questions
    if st.session_state.current_q < 5:
        expected = q_item.get("expected", [])
        missing = check_completeness(trimmed, expected)
        if missing:
            st.error(f"❌ **Answer incomplete for required question.** Please add: {', '.join(missing)}")
            st.session_state.answers_meta[q_item["id"]] = {
                "answer": trimmed, "status": "partial", "missing": missing
            }
            return

    # Mark as complete and assess risk
    risk_result = assess_risk_for_answer(q_item["id"], trimmed)
    st.session_state.risk_results[q_item["id"]] = risk_result

    st.session_state.answers_meta[q_item["id"]] = {
        "answer": trimmed, "status": "complete", "missing": []
    }

    # Auto-advance
    if st.session_state.current_q < len(QUESTIONNAIRE) - 1:
        st.session_state.current_q += 1

    st.success("✅ Answer confirmed as complete!")
    st.rerun()

def show_summary_section():
    """Display enhanced summary and export options"""
    st.markdown("---")
    st.markdown("## 📋 Assessment Summary & Risk Analysis")

    # Prepare summary data
    summary_rows = []
    for q in QUESTIONNAIRE:
        meta = st.session_state.answers_meta[q["id"]]
        risk = st.session_state.risk_results.get(q["id"], {"score": None, "level": None, "reasons": []})

        summary_rows.append({
            "Question": q["q"][:80] + ("..." if len(q["q"]) > 80 else ""),
            "Answer": meta.get("answer", "")[:150] + ("..." if len(meta.get("answer", "")) > 150 else ""),
            "Status": meta.get("status", "missing"),
            "Risk Level": risk.get("level", "Unknown"),
            "Risk Score": risk.get("score", 0),
            "Risk Factors": "; ".join(risk.get("reasons", []))
        })

    summary_df = pd.DataFrame(summary_rows)

    # Metrics dashboard
    st.markdown("### 📊 Assessment Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        complete_count = sum(1 for row in summary_rows if row["Status"] == "complete")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{complete_count}</div>
            <div class="metric-label">Completed</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        high_risk_count = sum(1 for row in summary_rows if row["Risk Level"] == "High")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{high_risk_count}</div>
            <div class="metric-label">High Risk Items</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        medium_risk_count = sum(1 for row in summary_rows if row["Risk Level"] == "Medium")
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{medium_risk_count}</div>
            <div class="metric-label">Medium Risk Items</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        completion_rate = complete_count / len(summary_rows) * 100
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{completion_rate:.0f}%</div>
            <div class="metric-label">Completion Rate</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Color-coded table
    def color_status(val):
        if val == 'complete':
            return 'background-color: #d4edda; color: #155724'
        elif val == 'partial':
            return 'background-color: #fff3cd; color: #856404'
        else:
            return 'background-color: #f8d7da; color: #721c24'

    def color_risk(val):
        if val == 'High':
            return 'background-color: #f8d7da; color: #721c24; font-weight: bold'
        elif val == 'Medium':
            return 'background-color: #fff3cd; color: #856404; font-weight: bold'
        elif val == 'Low':
            return 'background-color: #d4edda; color: #155724; font-weight: bold'
        return ''

    styled_df = summary_df.style.applymap(color_status, subset=['Status']).applymap(color_risk, subset=['Risk Level'])
    st.dataframe(styled_df, use_container_width=True, height=400)

    # DPIA recommendation
    st.markdown("### 🎯 DPIA Recommendation")
    
    answers_map = {q["id"]: st.session_state.answers_meta[q["id"]].get("answer", "") for q in QUESTIONNAIRE}
    aggregate_risks = [st.session_state.risk_results[q["id"]] for q in QUESTIONNAIRE if st.session_state.risk_results.get(q["id"], {}).get("score")]

    dpia_decision = should_trigger_dpia(aggregate_risks, answers_map)

    if dpia_decision["dpia_required"]:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%); 
                    padding: 2rem; border-radius: 16px; border-left: 5px solid #ef4444; margin: 1rem 0;">
            <h3 style="color: #991b1b; margin: 0 0 1rem 0;">⚠️ DPIA REQUIRED</h3>
            <p style="color: #7f1d1d; font-size: 1.1rem; margin: 0;">
                A Data Protection Impact Assessment must be conducted before proceeding with this project.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        if dpia_decision["reasons"]:
            st.markdown("**Critical Risk Factors:**")
            for reason in dpia_decision["reasons"]:
                st.markdown(f"🔴 {reason}")
        
        st.markdown("**Recommended Actions:**")
        st.markdown("""
        1. Conduct comprehensive DPIA with stakeholder consultation
        2. Document necessity and proportionality of processing
        3. Identify and implement risk mitigation measures
        4. Seek DPO review and approval before deployment
        """)
    else:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #d1fae5 0%, #a7f3d0 100%); 
                    padding: 2rem; border-radius: 16px; border-left: 5px solid #10b981; margin: 1rem 0;">
            <h3 style="color: #065f46; margin: 0 0 1rem 0;">✅ DPIA NOT REQUIRED</h3>
            <p style="color: #064e3b; font-size: 1.1rem; margin: 0;">
                Based on current assessment, a full DPIA is not mandatory. However, continue to monitor for scope changes.
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Export section
    st.markdown("### 📤 Export & Share")

    col1, col2, col3 = st.columns(3)

    with col1:
        excel_data = create_excel_export(summary_df, dpia_decision)
        st.download_button(
            "📊 Download Excel Report",
            excel_data,
            file_name=f"privacy_assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col2:
        json_data = create_json_export(answers_map, summary_rows, dpia_decision)
        st.download_button(
            "📋 Download JSON Data",
            json_data,
            file_name=f"privacy_assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col3:
        pdf_placeholder = "PDF export coming soon"
        st.button("📄 Generate PDF Report", use_container_width=True, disabled=True)

    # Email notification
    st.markdown("### 📧 Send Notifications")
    
    col1, col2 = st.columns(2)

    with col1:
        requestor_email = st.text_input("📧 Requestor Email", placeholder="requestor@company.com")
    with col2:
        dpo_email = st.text_input("👤 DPO Email", placeholder="dpo@company.com")

    if st.button("📧 Send Assessment Summary", type="primary", use_container_width=True):
        if requestor_email and dpo_email:
            st.success("✅ Email notifications sent successfully!")
            st.markdown(f"""
            <div class="info-box">
                📧 <strong>Summary sent to:</strong> {requestor_email}<br>
                📧 <strong>Full assessment sent to:</strong> {dpo_email}<br>
                📅 <strong>Timestamp:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.error("❌ Please provide both email addresses")

    # Reset button
    st.markdown("---")
    if st.button("🔄 Start New Assessment", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

def create_excel_export(summary_df: pd.DataFrame, dpia_decision: dict) -> bytes:
    """Create Excel export with multiple sheets"""
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Assessment_Summary', index=False)

        detailed_data = []
        for q in QUESTIONNAIRE:
            meta = st.session_state.answers_meta[q["id"]]
            risk = st.session_state.risk_results.get(q["id"], {})

            detailed_data.append({
                "Question_ID": q["id"],
                "Question": q["q"],
                "Notes": q.get("notes", ""),
                "Answer": meta.get("answer", ""),
                "Status": meta.get("status", "missing"),
                "Risk_Score": risk.get("score", 0),
                "Risk_Level": risk.get("level", "Unknown"),
                "Risk_Reasons": "; ".join(risk.get("reasons", [])),
                "Missing_Items": "; ".join(meta.get("missing", []))
            })

        detailed_df = pd.DataFrame(detailed_data)
        detailed_df.to_excel(writer, sheet_name='Detailed_Responses', index=False)

        dpia_data = pd.DataFrame([{
            "DPIA_Required": dpia_decision["dpia_required"],
            "Reasons": "; ".join(dpia_decision["reasons"]),
            "Assessment_Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Tool_Version": "v2.0"
        }])
        dpia_data.to_excel(writer, sheet_name='DPIA_Decision', index=False)

    output.seek(0)
    return output.read()

def create_json_export(answers_map: dict, summary_rows: list, dpia_decision: dict) -> str:
    """Create JSON export of all assessment data"""
    export_data = {
        "assessment_metadata": {
            "timestamp": datetime.now().isoformat(),
            "tool_version": "v2.0",
            "total_questions": len(QUESTIONNAIRE),
            "completion_status": "complete" if all(
                st.session_state.answers_meta[q["id"]].get("status") == "complete" 
                for q in QUESTIONNAIRE
            ) else "partial"
        },
        "answers": answers_map,
        "risk_assessment": {
            q["id"]: st.session_state.risk_results.get(q["id"], {})
            for q in QUESTIONNAIRE
        },
        "dpia_decision": dpia_decision,
        "summary": summary_rows
    }

    return json.dumps(export_data, indent=2)

if __name__ == "__main__":
    main()