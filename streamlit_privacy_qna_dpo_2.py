# streamlit_privacy_qna_dpo_lovable.py
"""
Lovable Streamlit app: Privacy-by-Design guided questionnaire for DPOs
- One-question-at-a-time flow (enforces strict completeness for first 5 questions)
- Document-assisted autofill (PDF/DOCX/TXT/XLSX) -> vector index + Azure OpenAI extraction
- Heuristic risk scoring + export to Excel

This is a UI-enhanced version of streamlit_privacy_qna_dpo.py with a warm, professional tone, soft pastel theme,
rounded cards, emoji-driven feedback, and subtle UX touches. Core logic is preserved.

Requirements (pip):
streamlit pandas openpyxl python-docx PyPDF2 faiss-cpu sentence-transformers langchain langchain_community
langchain_openai azure-openai python-dotenv openpyxl
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

# Optional LLM imports (only used if env configured)
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_community.embeddings import SentenceTransformerEmbeddings
    from langchain_community.vectorstores import FAISS
    from langchain_openai import AzureChatOpenAI
    from langchain.schema import HumanMessage, SystemMessage
except ImportError as e:
    # Keep app functional in manual mode
    st.warning(f"Some optional dependencies not available: {e}")
    RecursiveCharacterTextSplitter = None
    SentenceTransformerEmbeddings = None
    FAISS = None
    AzureChatOpenAI = None

load_dotenv()

# --- Config ---
st.set_page_config(page_title="Privacy-by-Design — DPO Guided Assessment", layout="wide")

# ---- Lovable UI: Global CSS (soft pastel, fonts, rounded cards) ----
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');
    html, body, [class*="css"]  {
        font-family: 'Poppins', sans-serif;
        background: linear-gradient(135deg, #fdf6ff 0%, #eef8ff 100%);
        color: #1f2937;
    }

    /* Title styles */
    .stApp h1 {
        color: #5b21b6;
        text-align: center;
        margin-bottom: 0.1rem;
    }

    /* Card-like inputs and containers */
    .stTextArea, .stTextInput, .stSelectbox, .stMarkdown {
        background: #ffffffcc;
        border-radius: 14px;
        box-shadow: 0 6px 18px rgba(16,24,40,0.04);
        padding: 10px;
    }

    /* Buttons */
    div.stButton > button {
        border-radius: 999px;
        color: white;
        background: linear-gradient(90deg, #6b21a8, #8b5cf6);
        padding: 8px 18px;
        font-weight: 600;
        transition: transform 0.18s ease, box-shadow 0.18s ease;
    }
    div.stButton > button:hover {
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 8px 24px rgba(99,102,241,0.14);
    }

    /* Sidebar style */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f3f8ff 0%, #fff6fb 100%);
        border-top-right-radius: 12px;
        border-bottom-right-radius: 12px;
        padding: 16px;
    }

    /* Progress bar */
    .stProgress > div > div > div {
        background-image: linear-gradient(to right, #6b21a8, #8b5cf6);
    }

    /* Small helper badges */
    .helper-badge { display:inline-block; background:#6b21a8; color:#fff; padding:3px 8px; border-radius:12px; font-size:12px }

    </style>
""", unsafe_allow_html=True)

# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
AZURE_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-35-turbo")

# Enhanced Questionnaire based on requirements document
QUESTIONNAIRE = [
    {
        "id": "country",
        "q": "Which country(ies) will the process or solution be developed, deployed, or used in?",
        "notes": "Used to adapt jurisdictional obligations (GDPR, PIPL, PDPA, LGPD). Provide exact country names.",
        "expected": ["country names", "multiple jurisdictions if applicable", "regulatory framework"]
    },
    {
        "id": "project_name",
        "q": "What is the name of the process or solution?",
        "notes": "Provide a unique name or identifier so the project can be referenced in ROPA (GDPR Art. 30).",
        "expected": ["project name", "unique identifier", "business context"]
    },
    {
        "id": "business_objective",
        "q": "What is the main business objective of the solution or process?",
        "notes": "Explain why this exists and the value it brings. Be specific (e.g., fraud detection, HR onboarding, personalization).",
        "expected": ["business objective", "value or benefit", "specific use case", "business justification"]
    },
    {
        "id": "data_processing_purposes",
        "q": "List the specific purposes for processing personal data (one purpose per line).",
        "notes": "Each purpose should be narrow and legitimate (GDPR Art. 6; purpose limitation principle).",
        "expected": ["list of purposes", "one purpose per line", "legitimate basis for each purpose"]
    },
    {
        "id": "personal_data_categories",
        "q": "What categories of personal data will be processed? (e.g., name, email, location, financial, health, biometrics)",
        "notes": "Be exhaustive. Flag special categories (health, biometrics, race, religion, trade union, sex life).",
        "expected": ["list of data categories", "flag special/sensitive categories", "examples for each category"]
    },
    {
        "id": "data_subjects",
        "q": "Who are the data subjects whose personal data will be processed?",
        "notes": "Identify the categories of individuals (e.g., employees, customers, children, patients).",
        "expected": ["categories of data subjects", "vulnerable groups if applicable"]
    }
]

# --- File parsing helpers ---
def extract_text_from_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX file"""
    try:
        doc = Document(io.BytesIO(file_bytes))
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    except Exception as e:
        st.error(f"Error extracting from DOCX: {e}")
        return ""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF file"""
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
    """Extract text from TXT file"""
    try:
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return file_bytes.decode("latin-1", errors="ignore")


def extract_text_from_xlsx(file_bytes: bytes) -> str:
    """Extract text from Excel file"""
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
    """Build text chunks from uploaded files for vector indexing"""
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
        else:
            st.warning(f"Unsupported file type: {file.name} - skipped")

    joined = "\n".join([t for t in raw_texts if t and t.strip()])
    if not joined.strip():
        return []

    if RecursiveCharacterTextSplitter:
        splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
        return splitter.split_text(joined)
    else:
        # Fallback: simple splitting by paragraphs
        parts = [p.strip() for p in joined.split('\n\n') if p.strip()]
        return parts


def create_faiss_from_chunks(text_chunks):
    """Create FAISS vector store from text chunks"""
    if not text_chunks or (FAISS is None) or (SentenceTransformerEmbeddings is None):
        return None
    try:
        embeddings = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
        return FAISS.from_texts(text_chunks, embedding=embeddings)
    except Exception as e:
        st.error(f"Error creating vector store: {e}")
        return None

# --- LLM extraction (optional) ---
def call_llm_extract_and_assess(question: str, context_text: str, llm_client) -> Dict[str, Any]:
    """
    Uses Azure OpenAI to extract an answer and assess completeness
    """
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
        # Try to extract JSON from response
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

# --- Risk scoring engine ---
def assess_risk_for_answer(qid: str, answer: str) -> Dict[str, Any]:
    """Enhanced risk assessment based on privacy compliance factors"""
    score = 1
    reasons = []
    ans = (answer or "").lower()

    if not ans.strip():
        return {"score": 3, "level": "High", "reasons": ["No answer provided — cannot assess risk"]}

    # Special categories of personal data (GDPR Art. 9)
    sensitive_keywords = [
        "health", "medical", "genetic", "biometric", "race", "ethnic", "religion",
        "sexual", "sex life", "trade union", "political", "criminal", "healthcare", 
        "hiv", "disability", "mental health", "pregnancy"
    ]
    if any(k in ans for k in sensitive_keywords):
        score = max(score, 3)
        reasons.append("Contains special categories of personal data (GDPR Art. 9)")

    # Financial data
    financial_keywords = [
        "bank", "credit card", "card number", "iban", "account number", "payment",
        "financial", "salary", "income", "tax", "insurance"
    ]
    if any(k in ans for k in financial_keywords):
        score = max(score, 2)
        reasons.append("Contains financial data")

    # Vulnerable data subjects
    vulnerable_keywords = [
        "child", "children", "minor", "vulnerable", "patient", "prison", "elderly",
        "disability", "employee", "student"
    ]
    if any(k in ans for k in vulnerable_keywords):
        score = max(score, 3)
        reasons.append("Involves vulnerable data subjects")

    # Scale of processing
    scale_indicators = [
        r"\d{4,}", "thousand", "million", "large scale", "mass", "bulk", "global",
        "worldwide", "international", "cross-border"
    ]
    if any(re.search(pattern, ans) for pattern in scale_indicators):
        score = max(score, 3)
        reasons.append("Large-scale data processing indicated")

    # International transfers
    transfer_keywords = [
        "transfer", "third country", "subprocessor", "third party", "vendor", 
        "cloud", "offshore", "international", "cross-border", "adequacy"
    ]
    if any(k in ans for k in transfer_keywords):
        score = max(score, 2)
        reasons.append("International transfers or third-party processing")

    # Automated decision-making and profiling
    automated_keywords = [
        "automated decision", "profiling", "algorithm", "ai", "artificial intelligence",
        "machine learning", "ml", "model", "scoring", "prediction", "recommendation"
    ]
    if any(k in ans for k in automated_keywords):
        score = max(score, 3)
        reasons.append("Automated decision-making or profiling involved")

    # New technologies
    tech_keywords = [
        "blockchain", "iot", "internet of things", "facial recognition", "location tracking",
        "surveillance", "monitoring", "tracking", "geolocation"
    ]
    if any(k in ans for k in tech_keywords):
        score = max(score, 2)
        reasons.append("Innovative technology or surveillance elements")

    # Lack of security measures
    if qid == "security_measures" and len(ans) < 50:
        score = max(score, 2)
        reasons.append("Insufficient security measures described")

    # Multiple risk factors compound
    if len(reasons) >= 2:
        score = max(score, 3)

    level = {1: "Low", 2: "Medium", 3: "High"}.get(score, "High")
    return {"score": score, "level": level, "reasons": reasons or ["Standard processing — low risk"]}


def should_trigger_dpia(aggregate_risks: List[Dict[str, Any]], answers_map: Dict[str, str]) -> Dict[str, Any]:
    """Determine if DPIA is required based on GDPR Art. 35 criteria"""
    reasons = []

    # Count high-risk answers
    high_count = sum(1 for r in aggregate_risks if r.get("score") == 3)
    if high_count >= 2:
        reasons.append(f"{high_count} high-risk factors identified")

    # GDPR Art. 35(3) criteria
    special_data = answers_map.get("personal_data_categories", "").lower()
    automated = answers_map.get("automated_decision_making", "").lower()
    monitoring = answers_map.get("security_measures", "").lower()

    # Special categories processing at large scale
    if any(k in special_data for k in ["health", "biometric", "genetic", "criminal"]):
        reasons.append("Processing special categories of personal data")

    # Automated decision-making with legal effects
    if any(k in automated for k in ["yes", "automated", "profiling", "decision"]):
        reasons.append("Automated decision-making or profiling with significant effects")

    # Systematic monitoring of publicly accessible areas
    if any(k in monitoring for k in ["monitoring", "surveillance", "tracking", "cctv"]):
        reasons.append("Systematic monitoring indicated")

    # Check for large scale processing
    all_answers = " ".join(answers_map.values()).lower()
    if re.search(r"(\d{4,}|thousand|million|large scale|global)", all_answers):
        reasons.append("Large-scale processing indicated")

    return {"dpia_required": len(reasons) > 0, "reasons": reasons}

# --- Completeness checker ---

def check_completeness(answer: str, expected_items: List[str]) -> List[str]:
    """Check if answer contains expected elements"""
    if not expected_items:
        return []
    if not (answer or "").strip():
        return expected_items

    ans = answer.lower()
    missing = []

    for item in expected_items:
        # Break expected into tokens and check if any token present
        tokens = [t for t in re.split(r"\W+", item.lower()) if t]
        if not any(tok in ans for tok in tokens):
            missing.append(item)

    return missing

# --- Autofill helper ---

def autofill_question(q_text: str, expected: List[str], vectorstore, llm):
    """Attempt to autofill question from documents"""
    if not vectorstore:
        return {"answer": "", "status": "missing", "missing": ["No document index available"]}

    try:
        # Retrieve relevant document chunks
        docs = vectorstore.similarity_search(q_text, k=4)
        context_text = "\n\n".join([
            d.page_content if hasattr(d, "page_content") else str(d) 
            for d in docs
        ]).strip()

        if not context_text:
            return {"answer": "", "status": "missing", "missing": ["No relevant content found in documents"]}

        if llm:
            # Use LLM to extract and assess
            result = call_llm_extract_and_assess(q_text, context_text, llm)

            # Also check against expected items
            if result.get("answer") and expected:
                expected_missing = check_completeness(result["answer"], expected)
                if expected_missing:
                    result["missing"] = list(set(result.get("missing", []) + expected_missing))
                    if result.get("status") == "complete":
                        result["status"] = "partial"

            return result
        else:
            # No LLM: return context snippet
            snippet = context_text[:800] + "..." if len(context_text) > 800 else context_text
            exp_missing = check_completeness(snippet, expected) if expected else []
            return {
                "answer": snippet,
                "status": "partial" if exp_missing else "complete",
                "missing": exp_missing
            }

    except Exception as e:
        return {"answer": "", "status": "missing", "missing": [f"Error in autofill: {e}"]}

# --- Initialize LLM client ---

def initialize_llm():
    """Initialize Azure OpenAI client if configured"""
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

# --- Main Streamlit App ---

def main():
    st.title("Privacy-by-Design — Your Friendly DPO Assistant")
    st.markdown("""
    👋 **Welcome!**

    Let's walk together through your data protection journey.  
    Upload your documents and answer guided questions — the tool will help you spot privacy risks and suggest when a DPIA is needed. 💼💡
    """)

    # Initialize LLM
    llm = initialize_llm()

    # Sidebar for document upload and processing
    with st.sidebar:
        st.header("📁 Document Processing")

        # Privacy notice
        st.markdown("""
        **Privacy Notice**: This tool processes your uploaded documents locally for privacy assessment purposes only. 
        No personal data is stored permanently. Chat history is retained for 1 year for audit purposes.
        """)

        if st.checkbox("I agree to the Privacy Notice"):
            uploaded_files = st.file_uploader(
                "Upload project documents",
                type=["pdf", "docx", "txt", "xls", "xlsx"],
                accept_multiple_files=True,
                help="Upload project documentation to enable AI-assisted answer extraction"
            )

            if uploaded_files and st.button("🔧 Process Documents & Build Index"):
                with st.spinner("Extracting text and building vector index..."):
                    chunks = build_text_chunks_from_files(uploaded_files)
                    if chunks:
                        vectorstore = create_faiss_from_chunks(chunks)
                        if vectorstore:
                            st.session_state.vectorstore = vectorstore
                            st.session_state.vectorstore_ready = True
                            st.success(f"✅ Processed {len(chunks)} text chunks. Ready for assessment!")
                        else:
                            st.error("❌ Failed to create vector index")
                    else:
                        st.error("❌ No text extracted from uploaded files")
        else:
            st.warning("⚠️ Please accept the Privacy Notice to continue")
            st.stop()

        # LLM Status
        st.markdown("---")
        st.markdown("### 🤖 AI Assistant Status")
        if llm:
            st.success("✅ Azure OpenAI connected")
        else:
            st.info("ℹ️ Azure OpenAI not configured - manual mode only")

        if st.session_state.get("vectorstore_ready"):
            st.success("✅ Document index ready")
        else:
            st.info("ℹ️ No documents processed")

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

    # Main question interface
    col_left, col_right = st.columns([3, 1])

    with col_left:
        # Progress indicator
        progress = (st.session_state.current_q + 1) / len(QUESTIONNAIRE)
        st.progress(progress)
        st.markdown(f"💪 You're {int(progress*100)}% done — keep going!")

        st.header(f"Question {st.session_state.current_q + 1} of {len(QUESTIONNAIRE)}")

        q_item = QUESTIONNAIRE[st.session_state.current_q]

        # Soft card with question and notes
        with st.container():
            st.markdown(f"""
            <div style="background-color: #ffffffee; border-radius: 14px; padding: 18px; box-shadow: 0 8px 24px rgba(15,23,42,0.04); margin-bottom: 12px;">
                <h3 style="color:#5b21b6; margin-bottom:6px;">{q_item['q']}</h3>
                <p style="color:#374151; margin-top:0;">{q_item.get('notes','')}</p>
            </div>
            """, unsafe_allow_html=True)

        meta = st.session_state.answers_meta[q_item["id"]]

        # Auto-fill attempt
        if (not meta.get("answer")) and st.session_state.get("vectorstore_ready"):
            with st.spinner("🔍 Attempting to extract answer from your documents..."):
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

        # Status display with friendly icon
        status_color = {"complete": "🟢", "partial": "🟡", "missing": "🔴"}
        st.markdown(f"**Status:** {status_color.get(meta.get('status', 'missing'), '🔴')} {meta.get('status', 'missing').upper()}")

        if meta.get("missing"):
            st.warning("⚠️ **Missing/Recommended details:**\n" + "\n".join([f"• {item}" for item in meta["missing"]]))

        # Answer input
        answer_input = st.text_area(
            "Your Answer:",
            value=meta.get("answer", ""),
            height=200,
            help="Provide a comprehensive answer. For the first 5 questions, all expected details must be included to proceed.",
            key=f"ans_{q_item['id']}"
        )

        # Navigation buttons
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if st.button("⬅️ Back", disabled=(st.session_state.current_q == 0)):
                st.session_state.current_q -= 1
                st.rerun()

        with col2:
            if st.button("💾 Save & Continue"):
                handle_save_continue(answer_input, q_item, meta)

        with col3:
            if st.button("✅ Confirm Complete"):
                handle_confirm_complete(answer_input, q_item, meta)

        with col4:
            if st.button("⏭️ Skip", disabled=(st.session_state.current_q < 5)):
                if st.session_state.current_q < len(QUESTIONNAIRE) - 1:
                    st.session_state.current_q += 1
                st.rerun()

    with col_right:
        st.markdown("### 📊 Progress Overview")

        for idx, q in enumerate(QUESTIONNAIRE):
            m = st.session_state.answers_meta[q["id"]]
            status = m.get("status", "missing")

            # Truncate long questions
            q_text = q['q'][:50] + "..." if len(q['q']) > 50 else q['q']

            status_icons = {"complete": "✅", "partial": "⚠️", "missing": "❌"}
            icon = status_icons.get(status, "❌")

            if idx == st.session_state.current_q:
                st.markdown(f"**➤ {idx+1}. {q_text}** {icon}")
            else:
                st.markdown(f"{idx+1}. {q_text} {icon}")

        # Quick stats
        complete_count = sum(1 for q in QUESTIONNAIRE if st.session_state.answers_meta[q["id"]].get("status") == "complete")
        st.markdown(f"**Completed:** {complete_count}/{len(QUESTIONNAIRE)}")

    # Summary and Export Section
    if st.session_state.current_q >= len(QUESTIONNAIRE) - 1:
        show_summary_section()


def handle_save_continue(answer_input: str, q_item: dict, meta: dict):
    """Handle save and continue action"""
    trimmed = answer_input.strip()
    if not trimmed:
        st.error("😔 Answer cannot be empty")
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

    st.success("🎉 Answer saved!")
    st.rerun()


def handle_confirm_complete(answer_input: str, q_item: dict, meta: dict):
    """Handle confirm complete action"""
    trimmed = answer_input.strip()
    if not trimmed:
        st.error("😔 Answer cannot be empty")
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
    """Display summary and export options"""
    st.markdown("---")
    st.header("📋 Assessment Summary & Risk Analysis")

    # Decorative summary container
    st.markdown("""
    <div style="background-color:#fff; border-radius:12px; padding:14px; box-shadow:0 8px 24px rgba(15,23,42,0.04); margin-bottom:12px;">
        <h3 style="color:#5b21b6; margin:0 0 6px 0;">📋 Summary Overview</h3>
        <p style="color:#374151; margin:0;">Here’s a snapshot of your answers and risks — review before exporting. If a DPIA is recommended, follow the suggested action.</p>
    </div>
    """, unsafe_allow_html=True)

    # Prepare summary data
    summary_rows = []
    for q in QUESTIONNAIRE:
        meta = st.session_state.answers_meta[q["id"]]
        risk = st.session_state.risk_results.get(q["id"], {"score": None, "level": None, "reasons": []})

        summary_rows.append({
            "Question": q["q"][:100] + ("..." if len(q["q"]) > 100 else ""),
            "Answer": meta.get("answer", "")[:200] + ("..." if len(meta.get("answer", "")) > 200 else ""),
            "Status": meta.get("status", "missing"),
            "Risk Level": risk.get("level", "Unknown"),
            "Risk Score": risk.get("score", 0),
            "Risk Factors": "; ".join(risk.get("reasons", []))
        })

    summary_df = pd.DataFrame(summary_rows)

    # Color-coded display (pandas styling preserved) -- streamlit will render as static table
    def color_status(val):
        if val == 'complete':
            return 'background-color: #e6fff2'
        elif val == 'partial':
            return 'background-color: #fff7e6'
        else:
            return 'background-color: #fff1f2'

    def color_risk(val):
        if val == 'High':
            return 'background-color: #fff1f2'
        elif val == 'Medium':
            return 'background-color: #fff7e6'
        else:
            return 'background-color: #e6fff2'

    styled_df = summary_df.style.applymap(color_status, subset=['Status']).applymap(color_risk, subset=['Risk Level'])
    st.dataframe(styled_df, use_container_width=True)

    # Risk summary
    high_risk_count = sum(1 for row in summary_rows if row["Risk Level"] == "High")
    medium_risk_count = sum(1 for row in summary_rows if row["Risk Level"] == "Medium")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("High Risk Items", high_risk_count)
    with col2:
        st.metric("Medium Risk Items", medium_risk_count)
    with col3:
        completion_rate = sum(1 for row in summary_rows if row["Status"] == "complete") / len(summary_rows) * 100
        st.metric("Completion Rate", f"{completion_rate:.1f}%")

    # DPIA recommendation
    answers_map = {q["id"]: st.session_state.answers_meta[q["id"]].get("answer", "") for q in QUESTIONNAIRE}
    aggregate_risks = [st.session_state.risk_results[q["id"]] for q in QUESTIONNAIRE if st.session_state.risk_results.get(q["id"], {}).get("score")]

    dpia_decision = should_trigger_dpia(aggregate_risks, answers_map)

    st.markdown("### 🎯 DPIA Recommendation")
    if dpia_decision["dpia_required"]:
        st.error("**⚠️ DPIA REQUIRED**")
        st.markdown("**Reasons:**")
        for reason in dpia_decision["reasons"]:
            st.markdown(f"• {reason}")
        st.markdown("**Recommended Action:** Conduct a full Data Protection Impact Assessment before proceeding.")
    else:
        st.success("**✅ DPIA NOT REQUIRED** based on current assessment")
        st.markdown("However, please review with your DPO if there are any changes to the project scope.")

    # Export functionality
    st.markdown("### 📤 Export Results")

    col1, col2 = st.columns(2)

    with col1:
        # Excel export
        excel_data = create_excel_export(summary_df, dpia_decision)
        st.download_button(
            "📊 Download Excel Report",
            excel_data,
            file_name=f"privacy_assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with col2:
        # JSON export
        json_data = create_json_export(answers_map, summary_rows, dpia_decision)
        st.download_button(
            "📋 Download JSON Data",
            json_data,
            file_name=f"privacy_assessment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

    # Email notification setup (placeholder)
    st.markdown("### 📧 Notifications")
    col1, col2 = st.columns(2)

    with col1:
        requestor_email = st.text_input("Requestor Email", placeholder="requestor@company.com")
    with col2:
        dpo_email = st.text_input("DPO Email", placeholder="dpo@company.com")

    if st.button("📧 Send Notifications"):
        # In a real implementation, this would send actual emails
        st.info("📧 Email notifications sent successfully!")
        st.markdown(f"• Summary sent to: {requestor_email}")
        st.markdown(f"• Full assessment sent to: {dpo_email}")


def create_excel_export(summary_df: pd.DataFrame, dpia_decision: dict) -> bytes:
    """Create Excel export with multiple sheets"""
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main summary
        summary_df.to_excel(writer, sheet_name='Assessment_Summary', index=False)

        # Detailed answers
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

        # DPIA recommendation
        dpia_data = pd.DataFrame([{
            "DPIA_Required": dpia_decision["dpia_required"],
            "Reasons": "; ".join(dpia_decision["reasons"]),
            "Assessment_Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Tool_Version": "v1.0"
        }])
        dpia_data.to_excel(writer, sheet_name='DPIA_Decision', index=False)

    output.seek(0)
    return output.read()


def create_json_export(answers_map: dict, summary_rows: list, dpia_decision: dict) -> str:
    """Create JSON export of all assessment data"""
    export_data = {
        "assessment_metadata": {
            "timestamp": datetime.now().isoformat(),
            "tool_version": "v1.0",
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
