import streamlit as st
import os, json, time
from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel
from pypdf import PdfReader
from docx import Document

# -------------------------------------------------
# Setup (same .env, same venv as resume_Parser.py)
# -------------------------------------------------
load_dotenv()
mykey = os.getenv("GROQ_API_KEY")
if not mykey:
    raise ValueError("API KEY NOT FOUND — .env check karo")

client = Groq(api_key=mykey)
model = "openai/gpt-oss-120b"

# -------------------------------------------------
# Templates (same jaise resume_Parser.py mein the)
# -------------------------------------------------
class JobDescription(BaseModel):
    role: str
    responsibilities: list[str] = []
    education_qualifications: list[str] = []
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    minimum_experience: float | None = None

class MatchingCandidate(BaseModel):
    score: float
    skill_gap: list[str] = []
    missing_requirements: list[str] = []
    positive_features: list[str] = []
    final_verdict: str = ""

class Experience(BaseModel):
    company: str | None = None
    role: str | None = None
    duration: str | None = None
    description: str | None = None
    skills: list[str] = []

class Resume(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    total_experience_years: float | None = None
    education: list[str] = []
    experiences: list[Experience] | None = None
    skills: list[str] = []
    projects: list[str] = []
    certifications: list[str] = []

# -------------------------------------------------
# Helpers (same logic as resume_Parser.py)
# -------------------------------------------------
def read_pdf(file):
    reader = PdfReader(file)
    return "".join((p.extract_text() or "") for p in reader.pages)

def read_docx(file):
    doc = Document(file)
    text = ""
    for para in doc.paragraphs:
        if para.text.strip():
            text += para.text + "\n"
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    text += cell.text + "\n"
    return text

def parse_jd(jd_text):
    schema = JobDescription.model_json_schema()
    msgs = [
        {"role": "system", "content": (
            f"Extract structured info from JD. Return ONLY JSON matching: {schema}. "
            f"NEVER return null for list fields — use []. "
            f"minimum_experience: number if mentioned, else null."
        )},
        {"role": "user", "content": jd_text},
    ]
    a = client.chat.completions.create(
        model=model, messages=msgs,
        response_format={"type": "json_object"}, temperature=0.1,
    )
    return JobDescription(**json.loads(a.choices[0].message.content))

def parse_resume(text):
    schema = Resume.model_json_schema()
    msgs = [
        {"role": "system", "content": (
            f"Extract structured info from resume. Return ONLY JSON matching: {schema}. "
            f"NEVER return null for list fields — use []."
        )},
        {"role": "user", "content": f"Resume:\n{text[:6000]}"},
    ]
    a = client.chat.completions.create(
        model=model, messages=msgs,
        response_format={"type": "json_object"}, temperature=0.1,
    )
    parsed = json.loads(a.choices[0].message.content)
    for k in ["education", "skills", "projects", "certifications"]:
        if parsed.get(k) is None:
            parsed[k] = []
    return Resume(**parsed)

def score_resume(job, resume):
    schema = MatchingCandidate.model_json_schema()
    msgs = [
        {"role": "system", "content": (
            f"Expert recruiter. Return ONLY JSON matching: {schema}. "
            f"score MUST be 0-100 (e.g. 72.5), NOT 0-1. "
            f"skill_gap = JD skills candidate lacks. "
            f"missing_requirements = JD reqs not met. "
            f"positive_features = candidate strengths matching JD. "
            f"final_verdict = one short sentence. "
            f"Weights: Skills 45%, Exp 30%, Edu 15%, Fit 10%."
        )},
        {"role": "user", "content": (
            f"JOB: {job.model_dump_json(indent=1)}\n\n"
            f"RESUME: {resume.model_dump_json(indent=1)}"
        )},
    ]
    a = client.chat.completions.create(
        model=model, messages=msgs,
        response_format={"type": "json_object"}, temperature=0.1,
    )
    parsed = json.loads(a.choices[0].message.content)
    if parsed.get("score") is not None and parsed["score"] <= 1.0:
        parsed["score"] = round(parsed["score"] * 100, 1)
    return MatchingCandidate(**parsed)

# -------------------------------------------------
# Streamlit UI
# -------------------------------------------------
st.set_page_config(page_title="Resume Screener", page_icon="📄", layout="wide")
st.title("📄 AI Resume Screener")
st.caption("JD paste karo, resumes upload karo, ranked scores pao")

# Sidebar: JD
with st.sidebar:
    st.header("📋 Job Description")
    jd_text = st.text_area(
        "JD yahan paste karo",
        height=320,
        value="We need an SDE-3 with strong Java, Python, system design, "
              "databases, cloud, CI/CD, mentoring experience...",
    )
    run = st.button("🚀 Analyze", type="primary", use_container_width=True)

# Main: upload
uploaded = st.file_uploader(
    "Resumes upload karo (PDF / DOCX)",
    type=["pdf", "docx"],
    accept_multiple_files=True,
)

if run and uploaded:
    if not jd_text.strip():
        st.error("JD khali hai — pehle JD paste karo.")
        st.stop()

    # 1) Parse JD
    with st.spinner("JD padh raha hoon..."):
        try:
            job = parse_jd(jd_text)
        except Exception as e:
            st.error(f"JD parse fail: {e}")
            st.stop()

    with st.expander("🔍 Parsed JD (check karo)"):
        st.json(job.model_dump())

    # 2) Process resumes
    results = []
    progress = st.progress(0, text="Resumes process ho rahe hain...")

    for i, f in enumerate(uploaded):
        try:
            text = read_pdf(f) if f.name.lower().endswith(".pdf") else read_docx(f)
            if not text.strip():
                st.warning(f"{f.name} — empty file, skip")
                progress.progress((i + 1) / len(uploaded))
                continue
            r = parse_resume(text)
            time.sleep(4)
            s = score_resume(job, r)
            results.append({"name": f.name, "score": s.score, "details": s})
        except Exception as e:
            st.warning(f"{f.name} fail: {e}")
        progress.progress(
            (i + 1) / len(uploaded),
            text=f"{i+1}/{len(uploaded)} done",
        )
        time.sleep(4)

    progress.empty()

    # 3) Results
    if not results:
        st.error("Koi resume score nahi hua.")
        st.stop()

    results.sort(key=lambda x: x["score"], reverse=True)
    st.success(f"✅ {len(results)} resumes scored!")

    # Top 2
    st.header("🏆 Top Candidates")
    top_n = results[:2]
    cols = st.columns(len(top_n))
    for i, c in enumerate(top_n):
        with cols[i]:
            with st.container(border=True):
                st.subheader(f"#{i+1} {c['name']}")
                st.metric("Score", f"{c['score']:.1f}%")
                st.caption(f"**Verdict:** {c['details'].final_verdict or '—'}")
                st.write("**🎯 Skill Gap:**", ", ".join(c['details'].skill_gap) or "None")
                st.write("**❌ Missing Reqs:**", ", ".join(c['details'].missing_requirements) or "None")
                st.write("**✅ Strengths:**", ", ".join(c['details'].positive_features) or "—")

    # Bottom 2 (agar 2 se zyada results hain)
    if len(results) > 2:
        st.header("📉 Bottom Candidates")
        bottom_n = results[-2:]
        cols2 = st.columns(len(bottom_n))
        for i, c in enumerate(bottom_n):
            with cols2[i]:
                with st.container(border=True):
                    st.subheader(f"{c['name']}")
                    st.metric("Score", f"{c['score']:.1f}%")
                    st.caption(f"**Verdict:** {c['details'].final_verdict or '—'}")
                    st.write("**🎯 Skill Gap:**", ", ".join(c['details'].skill_gap) or "None")
                    st.write("**❌ Missing Reqs:**", ", ".join(c['details'].missing_requirements) or "None")
                    st.write("**✅ Strengths:**", ", ".join(c['details'].positive_features) or "—")

    # Full table
    st.header("📊 All Results")
    st.dataframe(
        [
            {
                "Rank": i + 1,
                "Name": r["name"],
                "Score (%)": round(r["score"], 1),
                "Verdict": r["details"].final_verdict,
            }
            for i, r in enumerate(results)
        ],
        use_container_width=True,
        hide_index=True,
    )