# 📄 AI Resume Screener

An AI-powered application that automatically screens and ranks resumes against a given Job Description (JD). Built using **Streamlit**, **Groq API**, and **Pydantic**.

🚀 **[Click here to view the Live App!](https://ai-resume-screener-eg9jffpgyxymeyayzdom.streamlit.app)**

## 🚀 Features

- **Automated Resume Parsing:** Extracts structured data (Name, Skills, Education, Experience, Projects) from PDF and DOCX files.
- **Smart Scoring:** Uses LLMs to evaluate candidates and generate a match score (0-100%) based on Job Description requirements.
- **Skill Gap Analysis:** Identifies exactly which required skills are missing from a candidate's profile.
- **Positive Features Extraction:** Highlights the candidate's strengths that align with the JD.
- **Top/Bottom Candidates:** Beautifully formatted UI cards to instantly view the best and worst matches.
- **Rate-Limit Friendly:** Built-in delays and token truncation to respect API rate limits.

## 🛠️ Tech Stack

- **Frontend:** Streamlit
- **AI/LLM:** Groq (Model: `openai/gpt-oss-120b`)
- **Data Validation:** Pydantic
- **File Parsing:** PyPDF, python-docx
- **Language:** Python 3.10+

## 📁 Project Structure

```text
├── app.py               # Streamlit frontend application
├── resume_Parser.py     # CLI version (Terminal based) for bulk processing
├── requirements.txt     # Python dependencies
├── .env                 # Environment variables (API keys - NOT pushed to Git)
├── .gitignore           # Git ignore file
└── resumes/             # Folder to store sample resumes

## 🌐 Live Demo
Check out the live app here: [AI Resume Screener]([https://ai-resume-screener-eg9jffpgyxymeyayzdom.streamlit.app])
