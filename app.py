import os
import streamlit as st
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field
from typing import List, Literal

# Load environment variables from .env
load_dotenv()

# --- 1. Comprehensive Legal & Workplace Schema ---
class FlagItem(BaseModel):
    category: Literal[
        "Scope Creep & Spec Work",
        "Toxic Culture & Burnout",
        "Payment & Financial Risk",
        "Predatory IP / Work-For-Hire",
        "Overreaching Non-Compete / Non-Solicit",
        "Uncapped Liability & Indemnity",
        "Unilateral Termination / Lock-in",
        "Jurisdiction & Dispute Traps",
        "Ambiguity & Bait-and-Switch"
    ]
    severity: Literal["Low", "Medium", "High", "Critical"]
    clause_excerpt: str = Field(description="The exact clause, sentence, or phrase triggering the warning")
    legal_or_practical_risk: str = Field(description="Plain-English explanation of why this clause exposes the user to risk or unfair liability")
    suggested_revision: str = Field(description="A redline replacement or negotiation counter-proposal for this specific clause")

class ScanResult(BaseModel):
    risk_score: int = Field(description="Overall risk rating from 0 (Safe/Standard) to 100 (Extremely Risky/Exploitative)")
    document_summary: str = Field(description="A clear 2-sentence executive summary of the document's posture")
    flags: List[FlagItem]
    negotiation_script: str = Field(description="A ready-to-send, professional email or negotiation response addressing the critical points")

# --- 2. Streamlit UI Config ---
st.set_page_config(
    page_title="Professional & Legal Red Flag Scanner",
    page_icon="⚖️",
    layout="wide"
)

st.title("⚖️ Professional & Legal Red Flag Scanner (Powered by Gemini)")
st.caption("AI-powered risk analysis for contracts, job postings, NDAs, and B2B agreements.")

# --- 3. Preset Templates ---
PRESETS = {
    "Select a preset sample...": ("", "Job Posting / Offer Letter"),
    
    "🚩 Job Post: Equity-Only & Excessive Roles": (
        "We are a high-velocity startup looking for a founding engineer. You will handle full-stack development, database architecture, DevOps, QA, and initial customer sales demos. Compensation is 100% equity-based until Series A closes. Must be willing to work late nights and weekends as we are a family here.",
        "Job Posting / Offer Letter"
    ),
    
    "🚩 Employment Contract: Universal IP Grab & Worldwide Non-Compete": (
        "The Employee agrees that all inventions, discoveries, designs, and code created during the term of employment—whether created during normal working hours, using Company resources, or created independently on personal time and personal equipment—shall be the sole property of the Company. Furthermore, the Employee agrees not to work for, advise, or consult with any entity operating in the software technology space worldwide for a period of 24 months following separation for any reason.",
        "Employment Agreement / Non-Compete"
    ),
    
    "🚩 Freelance SOW: Unlimited Scope & Delayed Payment Terms": (
        "Client shall pay Contractor Net-90 days following final written approval of all deliverables. Contractor agrees to provide unlimited revisions until Client is fully satisfied. In the event of project termination by Client at any time, Client shall not be liable for any unpaid milestone hours or work completed prior to termination.",
        "Freelance SOW / Master Services Agreement (MSA)"
    ),
    
    "🚩 NDA: Non-Expiring Confidentiality & Residuals Ban": (
        "Recipient's obligation to protect Confidential Information shall survive in perpetuity. Recipient agrees that any knowledge, concepts, or mental impressions retained by its personnel shall not be used in any future commercial endeavors, even if independently developed.",
        "NDA / Confidentiality Agreement"
    ),
    
    "🚩 Vendor / SaaS Agreement: Uncapped Indemnity & One-Sided Termination": (
        "Vendor shall indemnify, defend, and hold harmless Customer from and against any and all claims, losses, and damages arising out of the performance of the services, with no limitation on liability. Customer may terminate this agreement immediately without cause, whereas Vendor is bound to a 3-year minimum commitment.",
        "Vendor Contract / SaaS Terms of Service"
    )
}

# --- 4. Inputs Layout ---
col1, col2 = st.columns([1, 1])

with col1:
    selected_preset_key = st.selectbox("Load Sample Preset (Optional)", list(PRESETS.keys()))
    preset_text, preset_category = PRESETS[selected_preset_key]
    
    doc_types = [
        "Job Posting / Offer Letter",
        "Employment Agreement / Non-Compete",
        "Freelance SOW / Master Services Agreement (MSA)",
        "NDA / Confidentiality Agreement",
        "Vendor Contract / SaaS Terms of Service",
        "General B2B Commercial Agreement"
    ]
    
    selected_idx = doc_types.index(preset_category) if preset_category in doc_types else 0
    doc_type = st.selectbox("Document / Agreement Type", doc_types, index=selected_idx)

with col2:
    st.info("💡 Paste individual clauses, complete contracts, email threads, or job specs. The scanner identifies standard vs. predatory language.")

input_text = st.text_area(
    "Paste Text / Contract Clauses to Scan",
    value=preset_text,
    height=220,
    placeholder="Paste your agreement text, job post, or specific contract clause here..."
)

# --- 5. Analysis Trigger & Logic ---
if st.button("Run Comprehensive Scan", type="primary", use_container_width=True):
    api_key = os.getenv("GEMINI_API_KEY")
    
    if not input_text.strip():
        st.warning("Please paste text or select a preset to analyze.")
    elif not api_key:
        st.error("Missing `GEMINI_API_KEY`. Please set it in your `.env` file.")
    else:
        with st.spinner(f"Analyzing {doc_type} with Gemini..."):
            try:
                client = genai.Client(api_key=api_key)
                
                system_prompt = f"""
                You are a senior contract attorney, HR auditor, and commercial risk specialist.
                Conduct a rigorous analysis of the provided text, categorized as: '{doc_type}'.
                
                Inspect the text for:
                1. Overreaching IP ownership (e.g., claiming personal off-hours work).
                2. Unenforceable or restrictive non-compete/non-solicitation clauses.
                3. One-sided indemnity and uncapped liability provisions.
                4. Problematic payment terms (Net-90, indefinite revision loops, withholding payment).
                5. Toxic culture indicators, burnout risks, or vague job boundaries.
                6. Unfavorable termination rights or locked-in auto-renewals.
                
                Maintain legal objectivity. Deliver actionable redlines and negotiation text.
                """
                
                response = client.models.generate_content(
                    model="gemini-3.6-flash",
                    contents=f"{system_prompt}\n\nDocument to analyze:\n{input_text}",
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": ScanResult,
                    },
                )
                
                # Parse structured JSON output into ScanResult model
                result = ScanResult.model_validate_json(response.text)
                
                # --- 6. Render Output ---
                st.divider()
                
                score = result.risk_score
                if score < 30:
                    badge_color = "green"
                    risk_label = "Low Risk / Standard Terms"
                elif score < 65:
                    badge_color = "orange"
                    risk_label = "Moderate Risk / Negotiation Advised"
                else:
                    badge_color = "red"
                    risk_label = "High Risk / Predatory or Unbalanced"
                
                st.subheader(f"Risk Rating: :{badge_color}[{score}/100 — {risk_label}]")
                st.write(result.document_summary)
                
                st.markdown("### ⚠️ Flagged Clauses & Redlines")
                if not result.flags:
                    st.success("No predatory clauses or significant red flags detected.")
                else:
                    for i, flag in enumerate(result.flags, 1):
                        with st.expander(f"**#{i} [{flag.severity}] {flag.category}** — *\"{flag.clause_excerpt[:80]}...\"*"):
                            st.markdown(f"**Exact Flagged Text:**\n> {flag.clause_excerpt}")
                            st.markdown(f"**Legal / Practical Risk:**\n{flag.legal_or_practical_risk}")
                            st.markdown(f"**Suggested Counter-Draft / Redline:**")
                            st.code(flag.suggested_revision, language="markdown")
                
                st.markdown("### 💬 Ready-to-Send Negotiation Script")
                st.caption("Copy and customize this response to push back or request adjustments professionally:")
                st.code(result.negotiation_script, language="markdown")
                
            except Exception as e:
                st.error(f"Analysis failed: {str(e)}")