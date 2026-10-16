"""ATS Resume Checker - Streamlit app powered by Google Gemini Flash."""

import io
import json
import os
import re

import streamlit as st
from docx import Document
from google import genai
from google.genai import types
from pypdf import PdfReader

# Default Gemini Flash model. Override with a GEMINI_MODEL secret or env variable
# if Google renames or retires it (see https://ai.google.dev/gemini-api/docs/models).
DEFAULT_MODEL = "gemini-3.8-flash"
MAX_RESUME_CHARS = 20000
MAX_JD_CHARS = 8000

SYSTEM_PROMPT = """You are an expert ATS (Applicant Tracking System) analyst and resume coach.
Evaluate the resume text provided. If a job description is included, also judge keyword
and skills match against it. Be honest, specific and practical. Never invent facts that
are not in the resume.

Return ONLY valid JSON with exactly this shape:
{
  "overall_score": <integer 0-100>,
  "breakdown": {
    "formatting": <integer 0-100>,
    "keywords": <integer 0-100>,
    "experience_impact": <integer 0-100>,
    "skills": <integer 0-100>,
    "readability": <integer 0-100>
  },
  "summary": "<2-3 sentence overall assessment>",
  "strengths": ["<short point>", "..."],
  "missing_keywords": ["<keyword>", "..."],
  "improvements": [
    {"priority": "High|Medium|Low", "issue": "<what is wrong>", "fix": "<how to fix it>"}
  ],
  "rewritten_examples": [
    {"original": "<weak bullet from resume>", "improved": "<stronger version>"}
  ]
}
Give 3-6 strengths, 5-10 improvements and up to 3 rewritten examples."""


# ---------- Helpers ----------

def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:
            raise ValueError("This PDF is password protected.")
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages)


def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    parts.append(cell.text)
    return "\n".join(parts)


def extract_resume_text(filename: str, file_bytes: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        text = extract_text_from_pdf(file_bytes)
    elif name.endswith(".docx"):
        text = extract_text_from_docx(file_bytes)
    elif name.endswith(".txt"):
        text = file_bytes.decode("utf-8", errors="ignore")
    else:
        raise ValueError("Unsupported file type. Upload a PDF, DOCX or TXT file.")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def parse_json_response(raw: str) -> dict:
    """Parse model output into a dict, tolerating markdown code fences."""
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.IGNORECASE)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def clamp_score(value) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def normalize_result(data: dict) -> dict:
    """Make sure every field exists and has the right type."""
    breakdown = data.get("breakdown") or {}
    keys = ["formatting", "keywords", "experience_impact", "skills", "readability"]
    return {
        "overall_score": clamp_score(data.get("overall_score")),
        "breakdown": {k: clamp_score(breakdown.get(k)) for k in keys},
        "summary": str(data.get("summary", "")),
        "strengths": [str(s) for s in (data.get("strengths") or [])],
        "missing_keywords": [str(s) for s in (data.get("missing_keywords") or [])],
        "improvements": [i for i in (data.get("improvements") or []) if isinstance(i, dict)],
        "rewritten_examples": [
            i for i in (data.get("rewritten_examples") or []) if isinstance(i, dict)
        ],
    }


def get_setting(name: str, default: str = "") -> str:
    """Read a setting from Streamlit secrets first, then environment variables."""
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return value or os.environ.get(name, "") or default


def get_api_key() -> str:
    return get_setting("GEMINI_API_KEY")


def get_model_name() -> str:
    return get_setting("GEMINI_MODEL", DEFAULT_MODEL)


def analyze_resume(api_key: str, resume_text: str, job_description: str = "") -> dict:
    client = genai.Client(api_key=api_key)
    prompt = f"RESUME:\n{resume_text[:MAX_RESUME_CHARS]}\n"
    if job_description.strip():
        prompt += f"\nJOB DESCRIPTION:\n{job_description[:MAX_JD_CHARS]}\n"
    else:
        prompt += "\n(No job description provided. Judge general ATS-friendliness.)\n"

    response = client.models.generate_content(
        model=get_model_name(),
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return normalize_result(parse_json_response(response.text))


def score_color(score: int) -> str:
    if score >= 80:
        return "green"
    if score >= 60:
        return "orange"
    return "red"


# ---------- UI ----------

def render_results(result: dict) -> None:
    score = result["overall_score"]
    st.subheader("Your ATS Score")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(f"## :{score_color(score)}[{score} / 100]")
        st.progress(score / 100)
    with col2:
        st.write(result["summary"])

    st.subheader("Score Breakdown")
    labels = {
        "formatting": "Formatting",
        "keywords": "Keywords",
        "experience_impact": "Experience impact",
        "skills": "Skills",
        "readability": "Readability",
    }
    cols = st.columns(len(labels))
    for col, (key, label) in zip(cols, labels.items()):
        col.metric(label, f"{result['breakdown'][key]}")

    if result["strengths"]:
        st.subheader("Strengths")
        for s in result["strengths"]:
            st.markdown(f"- {s}")

    if result["missing_keywords"]:
        st.subheader("Missing Keywords")
        st.write(", ".join(f"`{k}`" for k in result["missing_keywords"]))

    if result["improvements"]:
        st.subheader("Improvements")
        icons = {"high": "🔴", "medium": "🟠", "low": "🟢"}
        for item in result["improvements"]:
            prio = str(item.get("priority", "Medium"))
            icon = icons.get(prio.lower(), "🟠")
            with st.expander(f"{icon} {prio}: {item.get('issue', '')}"):
                st.write(item.get("fix", ""))

    if result["rewritten_examples"]:
        st.subheader("Example Rewrites")
        for ex in result["rewritten_examples"]:
            st.markdown(f"**Before:** {ex.get('original', '')}")
            st.markdown(f"**After:** {ex.get('improved', '')}")
            st.divider()


def main() -> None:
    st.set_page_config(page_title="ATS Resume Checker", page_icon="📄", layout="wide")
    st.title("📄 ATS Resume Checker")
    st.caption("Upload your resume to get an ATS score and tips to improve it.")

    api_key = get_api_key()
    if not api_key:
        with st.sidebar:
            st.header("Settings")
            api_key = st.text_input(
                "Gemini API key",
                type="password",
                help="Get a free key at https://aistudio.google.com/apikey",
            )
    if not api_key:
        st.info("Add your Gemini API key in the sidebar to begin.")

    uploaded = st.file_uploader("Upload resume (PDF, DOCX or TXT)", type=["pdf", "docx", "txt"])
    job_description = st.text_area(
        "Job description (optional, improves keyword matching)", height=150
    )

    if st.button("Analyze Resume", type="primary", disabled=uploaded is None or not api_key):
        try:
            with st.spinner("Reading your resume..."):
                text = extract_resume_text(uploaded.name, uploaded.getvalue())
            if len(text) < 50:
                st.error(
                    "Could not read enough text. If this is a scanned or image-based PDF, "
                    "ATS systems cannot read it either. Export a text-based PDF or DOCX."
                )
                return
            with st.spinner("Analyzing with Gemini..."):
                result = analyze_resume(api_key, text, job_description)
            st.session_state["result"] = result
        except ValueError as e:
            st.error(str(e))
            return
        except json.JSONDecodeError:
            st.error("The AI returned an unreadable response. Please try again.")
            return
        except Exception as e:
            st.error(f"Something went wrong: {e}")
            return

    if "result" in st.session_state:
        render_results(st.session_state["result"])

    st.markdown("---")
    st.caption("Scores are AI estimates, not the result of any real employer's ATS.")


if __name__ == "__main__":
    main()
