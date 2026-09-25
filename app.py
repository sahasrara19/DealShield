

import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader

# Page Setup
st.set_page_config(
    page_title="DealShield | AI Legal & Offer Auditor",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------- Custom Styling -----------------
st.markdown("""
<style>
    /* Global font & background polish */
    .main {
        background-color: #0e1117;
    }
    /* Metric Card Container */
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }
    .metric-title {
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05rem;
        color: #94a3b8;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        margin-top: 4px;
    }
    /* Custom clause comparison box */
    .redline-box {
        background: rgba(239, 68, 68, 0.08);
        border-left: 4px solid #ef4444;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 12px;
    }
    .safeline-box {
        background: rgba(34, 197, 94, 0.08);
        border-left: 4px solid #22c55e;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- Configure API Key -----------------
# REPLACE WITH THIS:
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = st.sidebar.text_input("Enter Gemini API Key:", type="password")
    if not api_key:
        st.info("💡 Add your GEMINI_API_KEY to .streamlit/secrets.toml or enter it above to proceed.")
        st.stop()

genai.configure(api_key=api_key)

# ----------------- Helper Functions -----------------
def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

SAMPLE_DOCS = {
    "Select a pre-loaded sample...": "",
    "Predatory Tech Internship Offer": """1. IP Rights: The Intern assigns all rights, titles, and interests in any intellectual property, invention, code, or side project developed at any time during the internship period, whether created on company equipment or personal time.
2. Non-Compete: For a period of 24 months following termination of this agreement, the Intern agrees not to work for, advise, or start any business in the software, web development, or tech industry worldwide.
3. Termination & Compensation: The Company reserves the right to withhold stipend payments if deliverables do not satisfy internal benchmarks. Either party may terminate with 60 days notice.""",
    "One-Sided Freelance Agreement": """1. Scope & Revisions: Contractor will provide unlimited revisions until Client provides written approval.
2. Payment: Invoices will be paid within 90 days of final project completion and live deployment.
3. Liability: Contractor assumes unlimited liability and indemnifies Client against any third-party claims, legal costs, or damages arising directly or indirectly from the project code."""
}

# ----------------- Sidebar -----------------
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shield.png", width=64)
    st.title("DealShield")
    st.caption("AI-Powered Contract & Offer Auditor")
    st.divider()

    doc_type = st.selectbox(
        "Document Type",
        [
            "Employment Offer / Internship",
            "Freelance / Independent Contractor",
            "Non-Disclosure Agreement (NDA)",
            "Software License / SaaS Agreement"
        ]
    )

    tone = st.select_slider(
        "Counter-Offer Email Tone",
        options=["Diplomatic & Friendly", "Balanced Professional", "Firm & Assertive"],
        value="Balanced Professional"
    )

    st.divider()
    st.markdown("### 🧪 Quick Samples")
    selected_sample = st.selectbox("Load Sample Agreement", list(SAMPLE_DOCS.keys()))

# ----------------- Header Section -----------------
st.title("🛡️ Legal Contract & Offer Auditor")
st.markdown("Spot hidden risks, evaluate predatory clauses, and generate fair counter-proposals before signing.")

# ----------------- Main Input Area -----------------
tab1, tab2 = st.tabs(["📄 Upload PDF Document", "✍️ Direct Text Paste"])

input_text = ""

with tab1:
    uploaded_file = st.file_uploader("Upload agreement or offer letter (PDF)", type=["pdf"])
    if uploaded_file:
        with st.spinner("Extracting contract text..."):
            input_text = extract_text_from_pdf(uploaded_file)
        st.success(f"Loaded '{uploaded_file.name}' ({len(input_text.split())} words detected)")

with tab2:
    default_text = SAMPLE_DOCS[selected_sample] if selected_sample != "Select a pre-loaded sample..." else ""
    pasted_text = st.text_area(
        "Or paste the legal terms directly:",
        value=default_text,
        height=220,
        placeholder="Paste offer clauses, NDA terms, or contract text here..."
    )
    if pasted_text:
        input_text = pasted_text

# ----------------- Prompt Formulation -----------------
def generate_analysis_prompt(text, doc_type, tone):
    return f"""
You are a senior contract attorney and negotiation strategist evaluating this document:

Document Type: {doc_type}
Preferred Negotiation Tone: {tone}

Document Text:
\"\"\"
{text}
\"\"\"

Please conduct an exhaustive, rigorous audit formatted in clean Markdown with the following specific sections:

## 1. Executive Summary & Risk Rating
- **Overall Safety Score**: Give a score from 0/100 to 100/100 (where 100 is completely fair and safe).
- **Risk Level**: (Low / Moderate / High / Severe Risk)
- **Bottom-Line Assessment**: 2-3 clear sentences summarizing the balance of power in this agreement.

## 2. Predatory Clauses & Safe Alternatives
For each flagged issue (e.g., broad non-competes, aggressive IP assignment, uncapped indemnification, unfair payment terms, punitive liquidated damages):
### 🚩 Clause: [Name of Issue, e.g. Overbroad Intellectual Property Assignment]
- **Original Wording / Issue**: Exact quote or summary of the clause.
- **Why It Harms You**: Practical impact in plain English.
- **Fair Replacement Language**: Ready-to-use standard balanced clause to substitute.

## 3. Ready-to-Send Counter-Proposal Email
Draft a complete, tactful counter-offer email to the sender incorporating the revised terms using the **{tone}** tone. Include standard placeholders like [Recipient Name] and [Your Name].
"""

# ----------------- Analysis Action -----------------
st.write("")
if st.button("🚀 Analyze Contract Risks", type="primary", use_container_width=True):
    if not input_text.strip():
        st.warning("Please upload a PDF or enter contract text to begin analysis.")
    else:
        with st.spinner("Scanning for predatory clauses, calculating risk balance, and generating revisions..."):
            try:
                model = genai.GenerativeModel("gemini-3.5-flash-lite")
                prompt = generate_analysis_prompt(input_text, doc_type, tone)
                response = model.generate_content(prompt)
                
                st.divider()
                st.subheader("📊 Audit Dossier")
                st.markdown(response.text)
                
            except Exception as e:
                st.error(f"Error communicating with Gemini: {e}")