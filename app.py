

import streamlit as st
from google import genai
from google.genai import types
from pypdf import PdfReader
from pydantic import BaseModel
from enum import Enum
from html import escape as h
from urllib.parse import quote

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

client = genai.Client(api_key=api_key)

# ----------------- Helper Functions -----------------
def extract_text_from_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

# ----------------- Structured Output Schema -----------------
# Asking the model for a free-form 0-100 score makes it re-invent a number
# from scratch on every call, so the same contract can score differently
# each time. Instead we ask for categorical facts (fixed, discrete choices)
# and compute the score ourselves in Python, so the same facts always
# produce the same score.

class ClauseCategory(str, Enum):
    non_compete = "non_compete"
    ip_assignment = "ip_assignment"
    indemnification_liability = "indemnification_liability"
    payment_terms = "payment_terms"
    termination = "termination"
    confidentiality = "confidentiality"
    other = "other"

class Severity(str, Enum):
    low = "low"
    moderate = "moderate"
    high = "high"
    severe = "severe"

class FlaggedClause(BaseModel):
    issue_name: str
    category: ClauseCategory
    severity: Severity
    original_text: str
    why_it_harms_you: str
    fair_replacement: str

class ContractAnalysis(BaseModel):
    bottom_line_assessment: str
    flagged_clauses: list[FlaggedClause]
    negotiation_email: str

RUBRIC_GUIDE = """
Category definitions:
- non_compete: restricts where, for whom, or how long the person can work after leaving.
- ip_assignment: claims ownership over inventions, code, or personal side projects.
- indemnification_liability: makes the person responsible for the other party's legal costs or damages, or imposes uncapped liability.
- payment_terms: unfavorable timing, withholding, or scope of payment (e.g. long payment delays, unlimited free revisions).
- termination: unbalanced terms around how the agreement can be ended.
- confidentiality: what must be kept secret, and for how long.
- other: any other clause that is harmful to the person signing and does not fit the above.

Severity guide — apply these consistently so the same type of clause always
gets the same severity label regardless of exact wording:
- severe: extreme terms far outside any standard agreement (e.g. a worldwide non-compete over 12 months, IP assignment over personal time/projects, fully uncapped indemnification).
- high: clearly disadvantageous and outside common practice, but not the most extreme version.
- moderate: somewhat unfavorable, within the range sometimes seen in real contracts, but still worth negotiating.
- low: a minor asymmetry most people would accept without much concern.
"""

# Fixed point-deduction table. This is what actually determines the score —
# the model only chooses which category and severity apply, from a fixed
# set of options, so the same input always maps to the same score.
CATEGORY_MAX_DEDUCTION = {
    ClauseCategory.non_compete: 25,
    ClauseCategory.ip_assignment: 20,
    ClauseCategory.indemnification_liability: 20,
    ClauseCategory.payment_terms: 15,
    ClauseCategory.termination: 10,
    ClauseCategory.confidentiality: 10,
    ClauseCategory.other: 10,
}
SEVERITY_MULTIPLIER = {
    Severity.low: 0.25,
    Severity.moderate: 0.5,
    Severity.high: 0.75,
    Severity.severe: 1.0,
}

def compute_safety_score(flagged_clauses):
    score = 100
    for clause in flagged_clauses:
        max_deduction = CATEGORY_MAX_DEDUCTION.get(clause.category, 10)
        multiplier = SEVERITY_MULTIPLIER.get(clause.severity, 0.5)
        score -= max_deduction * multiplier
    return max(0, round(score))

def risk_level_from_score(score):
    if score >= 80:
        return "Low Risk", "#22c55e"
    elif score >= 60:
        return "Moderate Risk", "#eab308"
    elif score >= 35:
        return "High Risk", "#f97316"
    else:
        return "Severe Risk", "#ef4444"

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
    st.markdown("###  Quick Samples")
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
You are a senior contract attorney and negotiation strategist evaluating this document.

Document Type: {doc_type}
Preferred Negotiation Tone: {tone}

{RUBRIC_GUIDE}

Document Text:
\"\"\"
{text}
\"\"\"

Identify every clause that is unusually unfavorable to the person signing (the
intern, employee, freelancer, or contractor — not the company). For each one,
classify it using the category and severity definitions above exactly as
given, quote or closely summarize the original wording, explain the
practical impact in plain English, and draft ready-to-use fair replacement
wording.

Also write a complete negotiation email in the {tone} tone that proposes the
replacement terms, addressed to the sender, with placeholders like
[Recipient Name] and [Your Name].

Also write a 2-3 sentence bottom-line assessment of the overall balance of
power in this agreement.
"""

# ----------------- Analysis Action -----------------
@st.cache_data(show_spinner=False)
def run_contract_audit(contract_text, doc_type, tone):
    prompt = generate_analysis_prompt(contract_text, doc_type, tone)
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.0,
            seed=42,
            thinking_config=types.ThinkingConfig(thinking_level="high"),
            response_mime_type="application/json",
            response_schema=ContractAnalysis,
        ),
    )
    return response.text
st.write("")
if st.button("🚀 Analyze Contract Risks", type="primary", use_container_width=True):
    if not input_text.strip():
        st.warning("Please upload a PDF or enter contract text to begin analysis.")
    else:
        with st.spinner("Scanning for predatory clauses, calculating risk balance, and generating revisions..."):
            try:
                prompt = generate_analysis_prompt(input_text, doc_type, tone)
                result_text = run_contract_audit(input_text, doc_type, tone)
                analysis: ContractAnalysis = ContractAnalysis.model_validate_json(result_text)

                st.divider()
                st.subheader("📊 Audit Dossier")

                if analysis is None:
                  st.error("Couldn't parse a structured response from the model. Raw output below.")
                  st.markdown(result_text)   
                else:
                    score = compute_safety_score(analysis.flagged_clauses)
                    risk_level, risk_color = risk_level_from_score(score)

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-title">Safety Score</div>
                            <div class="metric-value" style="color:{risk_color}">{score}/100</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col2:
                        st.markdown(f"""
                        <div class="metric-card">
                            <div class="metric-title">Risk Level</div>
                            <div class="metric-value" style="color:{risk_color}">{risk_level}</div>
                        </div>
                        """, unsafe_allow_html=True)

                    st.write("")
                    st.progress(score / 100)
                    st.markdown(f"**Bottom line:** {analysis.bottom_line_assessment}")

                    st.write("")
                    st.markdown("### 🚩 Flagged Clauses & Fair Alternatives")
                    if not analysis.flagged_clauses:
                        st.success("No significant red flags detected in this document.")
                    for clause in analysis.flagged_clauses:
                        st.markdown(f"""
                        <div class="redline-box">
                            <strong>{h(clause.issue_name)}</strong>
                            &nbsp;—&nbsp;<em>{clause.severity.value.title()} · {clause.category.value.replace('_', ' ').title()}</em><br><br>
                            <strong>Original:</strong> {h(clause.original_text)}<br><br>
                            <strong>Why it harms you:</strong> {h(clause.why_it_harms_you)}
                        </div>
                        <div class="safeline-box">
                            <strong>Fair replacement:</strong> {h(clause.fair_replacement)}
                        </div>
                        """, unsafe_allow_html=True)

                    st.write("")
                    st.markdown("### ✉️ Ready-to-Send Counter Proposal")
                    st.text_area("Negotiation email", value=analysis.negotiation_email, height=250)

                    mailto_link = (
                        "mailto:?subject=" + quote("Regarding the proposed terms")
                        + "&body=" + quote(analysis.negotiation_email)
                    )
                    st.link_button("📧 Open in Email Client", mailto_link)

            except Exception as e:
                st.error(f"Error communicating with Gemini: {e}")