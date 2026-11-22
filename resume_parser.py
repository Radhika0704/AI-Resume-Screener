import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel

load_dotenv()

mykey = os.getenv("GROQ_API_KEY")
if not mykey:
    raise ValueError("API KEY NOT FOUND")

client = Groq(api_key=mykey)

model = "openai/gpt-oss-120b"

job_description = """
We are looking for an experienced Software Development Engineer III (SDE-3) to join our engineering team and contribute to the design, development, and delivery of scalable, reliable, and high-performance software applications. The ideal candidate will have strong expertise in data structures, algorithms, object-oriented programming, system design, and modern software development practices. The role involves taking end-to-end ownership of complex engineering projects, designing and implementing robust backend services, developing RESTful APIs and microservices, optimizing application performance, and ensuring system scalability, security, and reliability. The candidate should have hands-on experience with programming languages such as Java, Python, C++, C#, or Go, along with a strong understanding of databases, SQL, NoSQL, distributed systems, cloud platforms, containerization, and CI/CD pipelines. Responsibilities include translating business requirements into technical solutions, participating in architectural discussions, conducting code reviews, identifying and resolving complex technical issues, improving existing systems, and maintaining high standards of code quality and engineering excellence. The SDE-3 will also collaborate closely with product managers, QA engineers, DevOps teams, and other stakeholders to deliver high-quality software within defined timelines. In addition to technical expertise, the candidate should demonstrate strong problem-solving abilities, effective communication, technical leadership, and the ability to mentor junior engineers, guide design decisions, and influence engineering best practices across teams. The ideal candidate should be comfortable working independently, managing technical challenges, making informed architectural decisions, and driving continuous improvements while contributing to the organization's long-term technology strategy.
"""


class JobDescription(BaseModel):
    role: str
    responsibilities: list[str] = []
    education_qualifications: list[str] = []
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    minimum_experience: float | None = None


jobd_schema = JobDescription.model_json_schema()

sys_prompt = (
    f"You are a helpful assistant that extracts structured information from job descriptions. "
    f"The extracted information MUST match this JSON schema: {jobd_schema}. "
    f"Return ONLY valid JSON, no commentary. "
    f"CRITICAL: NEVER return null or missing keys. For list fields return [] if nothing is found. "
    f"For minimum_experience return a number if mentioned, otherwise null."
)
user_prompt = f"Extract structured information from this job description:\n{job_description}"
msgs = [
    {"role": "system", "content": sys_prompt},
    {"role": "user", "content": user_prompt},
]

answer = client.chat.completions.create(
    model=model,
    messages=msgs,
    response_format={"type": "json_object"},
    temperature=0.1,
)
raw_json = answer.choices[0].message.content
job = JobDescription(**json.loads(raw_json))

print("=" * 60)
print("JOB ROLE:", job.role)
print("RESPONSIBILITIES:", job.responsibilities)
print("EDUCATION QUALS:", job.education_qualifications)
print("REQUIRED SKILLS:", job.required_skills)
print("PREFERRED SKILLS:", job.preferred_skills)
print("MIN EXPERIENCE:", job.minimum_experience)
print("=" * 60)


class MatchingCandidate(BaseModel):
    score: float  # 0-100
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


resume_schema = Resume.model_json_schema()


def final_score(job, resume):
    matching_candidate_schema = MatchingCandidate.model_json_schema()
    sys_prompt = f"""
You are an expert technical recruiter who evaluates resumes against a job description.

Return ONLY valid JSON matching this schema: {matching_candidate_schema}

Rules:
- "score" MUST be a NUMBER between 0 and 100 (e.g. 72.5). DO NOT return 0-1 values.
- "skill_gap": list of skills the JD requires that the candidate lacks or is weak in.
- "missing_requirements": list of JD requirements (experience/education/role responsibilities) not satisfied.
- "positive_features": list of strengths the candidate brings that match the JD.
- "final_verdict": one short sentence (max 20 words) explaining the fit.
- Never return null. Use [] for empty lists.

Weights: Skills 45%, Experience 30%, Education 15%, Overall Fit 10%.

JOB DESCRIPTION:
{job.model_dump_json(indent=1)}

RESUME:
{resume.model_dump_json(indent=1)}
""".strip()

    msgs = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": "Evaluate now and return JSON only."},
    ]

    answer = client.chat.completions.create(
        model=model,
        messages=msgs,
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    raw_json = answer.choices[0].message.content
    parsed = json.loads(raw_json)

    # Guard: LLM kabhi 0-1 bhej de to 0-100 me convert
    if parsed.get("score") is not None and parsed["score"] <= 1.0:
        parsed["score"] = round(parsed["score"] * 100, 1)

    return MatchingCandidate(**parsed)


def parse_resume(resume_text):
    sys_prompt = (
        f"You extract structured info from resumes. Return ONLY JSON matching schema: {resume_schema}. "
        f"NEVER return null for list fields — use []. "
        f"If total_experience_years is unknown, return null."
    )
    msgs = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": f"Resume text:\n{resume_text}"},
    ]

    answer = client.chat.completions.create(
        model=model,
        messages=msgs,
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    raw_json = answer.choices[0].message.content
    parsed = json.loads(raw_json)

    # LLM kabhi list fields null bhej de to [] kar do
    for k in ["education", "skills", "projects", "certifications"]:
        if parsed.get(k) is None:
            parsed[k] = []
    return Resume(**parsed)


from pypdf import PdfReader
from docx import Document


def read_pdf_resume(file_path):
    reader = PdfReader(file_path)
    return "".join((p.extract_text() or "") for p in reader.pages)


def read_docx_resume(file_path):
    doc = Document(file_path)
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


def read_resume(file_path):
    if file_path.suffix.lower() == ".pdf":
        return read_pdf_resume(file_path)
    elif file_path.suffix.lower() == ".docx":
        return read_docx_resume(file_path)
    return None


def pretty_candidate(rank, name, score, details: MatchingCandidate):
    print(f"\n{'─' * 60}")
    print(f"#{rank}  {name}")
    print(f"{'─' * 60}")
    print(f"  Score            : {score:.1f}%")
    print(f"  Verdict          : {details.final_verdict or '—'}")
    print(f"  Skill Gap        : {', '.join(details.skill_gap) if details.skill_gap else 'None'}")
    print(f"  Missing Reqs     : {', '.join(details.missing_requirements) if details.missing_requirements else 'None'}")
    print(f"  Positive Features: {', '.join(details.positive_features) if details.positive_features else '—'}")


resume_folder = Path("resumes")
all_results = []

for file_path in sorted(resume_folder.iterdir()):
    if file_path.suffix.lower() not in [".pdf", ".docx"]:
        continue
    print(f"\n▶ Processing resume: {file_path.name}")
    try:
        resume_text = read_resume(file_path) or ""
        if not resume_text.strip():
            print("   [skip] empty file")
            continue

        # truncate to save tokens
        resume_text = resume_text[:6000]

        parsed_resume = parse_resume(resume_text)
        time.sleep(6)
        result = final_score(job, parsed_resume)
        print(f"   ✓ Score: {result.score:.1f}%")
        all_results.append({
            "name": file_path.name,
            "score": result.score,
            "details": result,
        })
        time.sleep(6)
    except Exception as e:
        print(f"   ✗ Failed: {e}")
        continue


if not all_results:
    print("\nNo resumes successfully scored.")
elif len(all_results) == 1:
    # sirf 1 resume hai — sirf ek baar dikhao
    print("\n" + "=" * 60)
    print(" ONLY 1 CANDIDATE FOUND")
    print("=" * 60)
    pretty_candidate(1, all_results[0]["name"], all_results[0]["score"], all_results[0]["details"])
else:
    all_results.sort(key=lambda x: x["score"], reverse=True)

    print("\n" + "=" * 60)
    print(" TOP 2 CANDIDATES")
    print("=" * 60)
    for i, c in enumerate(all_results[:2], start=1):
        pretty_candidate(i, c["name"], c["score"], c["details"])

    print("\n" + "=" * 60)
    print(" BOTTOM 2 CANDIDATES")
    print("=" * 60)
    for i, c in enumerate(all_results[-2:], start=len(all_results) - 1):
        pretty_candidate(i, c["name"], c["score"], c["details"])