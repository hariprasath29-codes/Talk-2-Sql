# Talk2SQL – AI Database Assistant

A full-stack conversational database web application built with **Python**, **Django**, and **SQLite** that translates plain-English questions into safe, read-only `SELECT` SQL queries and renders live tabular results.

## Key Features

- **Natural Language to SQL:** Converts plain-English user prompts into accurate SQLite queries using schema-aware Prompt Engineering (`sqlite_master` table inspection).
- **Multi-Model AI Fallback Routing:** Integrates **Groq API**, **Google GenAI (Gemini API)**, and **OpenRouter API** with automatic fallback routing so queries continue seamlessly if one provider hits a rate limit.
- **Read-Only Security Guardrails:** Enforces regex validation to allow only `SELECT` statements and block destructive commands (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`).
- **Dynamic `.json` & `.csv` Dataset Uploads:** Uses **Pandas** and **SQLite** to normalize columns and create queryable database tables on the fly (includes sample `student.json` and `teacher.json` datasets).
- **Clean Web Interface:** Responsive frontend built with **HTML5**, **CSS3**, and **JavaScript** for interactive querying and instant table display.

## Tech Stack

- **Backend:** Python, Django
- **Database & Data Processing:** SQLite, Pandas
- **Generative AI:** Groq API, Google GenAI (Gemini API), OpenRouter API
- **Frontend:** HTML5, CSS3, JavaScript

## Project Structure

```text
Talk-2-Sql/
├── assistant/              # Main Django app (views, models, templates, SQL guardrails)
├── core/                   # Project settings and URL routing
├── manage.py               # Django CLI utility
├── student.json            # Sample student dataset for JSON-to-SQL testing
└── teacher.json            # Sample teacher dataset for JSON-to-SQL testing
