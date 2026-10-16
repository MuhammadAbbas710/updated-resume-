# ATS Resume Checker

A Streamlit app that scores a resume for ATS (Applicant Tracking System) friendliness and suggests concrete improvements, powered by Google Gemini Flash.

## Features

- Upload a resume as PDF, DOCX or TXT
- Optional job description for keyword matching
- Overall ATS score (0-100) with a breakdown: formatting, keywords, experience impact, skills, readability
- Strengths, missing keywords, prioritized improvements and example bullet rewrites

## Setup

1. Clone the repo and install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Get a free Gemini API key at https://aistudio.google.com/apikey

3. Provide the key in one of these ways:

   - Environment variable: `export GEMINI_API_KEY="your-key"` (Windows PowerShell: `$env:GEMINI_API_KEY="your-key"`)
   - Or create `.streamlit/secrets.toml` containing:

     ```toml
     GEMINI_API_KEY = "your-key"
     ```

   - Or paste it into the sidebar when the app runs.

4. Run the app:

   ```bash
   streamlit run app.py
   ```

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub (never commit your API key).
2. Go to https://share.streamlit.io and sign in with GitHub.
3. Click **Create app**, choose your repo, branch `main` and main file `app.py`.
4. Open **Advanced settings → Secrets** and add:

   ```toml
   GEMINI_API_KEY = "your-key"
   ```

5. Click **Deploy**.

## Notes

- Scanned or image-only PDFs cannot be read. Use a text-based PDF or DOCX.
- Scores are AI estimates, not the output of any real employer's ATS.
- The default model is `gemini-3.8-flash` (`DEFAULT_MODEL` at the top of `app.py`). To use a different one without editing code, set `GEMINI_MODEL` as an environment variable or in `.streamlit/secrets.toml`. Check https://ai.google.dev/gemini-api/docs/models for current model names.
- Never commit `.streamlit/secrets.toml` or your API key to GitHub.# updated-resume-
