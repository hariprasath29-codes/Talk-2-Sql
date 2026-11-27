import json
import os
import re
import sqlite3
import pandas as pd
import requests
from django.conf import settings
from django.db import connection
from django.shortcuts import render

MODELS = [
    {
        "id": "groq",
        "name": "Groq (GPT-OSS 120B)",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key": os.getenv("GROQ_API_KEY", ""),
        "model": "openai/gpt-oss-120b",
    },
    {
        "id": "gemini",
        "name": "Google (Gemini 3.8 Flash)",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key": os.getenv("GEMINI_API_KEY", ""),
        "model": "gemini-3.8-flash",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter (Free)",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key": os.getenv("OPENROUTER_API_KEY", ""),
        "model": "openrouter/free",
    },
]


def ask_llm(prompt, preferred_id="groq"):
    """Put the user-selected model first, and fall back to others on quota/rate errors."""
    ordered_models = MODELS.copy()
    if preferred_id:
        ordered_models.sort(key=lambda m: 0 if m["id"] == preferred_id else 1)

    fallback_reason = ""
    last_error = "No API keys configured in .env"

    for idx, provider in enumerate(ordered_models):
        if not provider["key"]:
            if idx == 0:
                fallback_reason = f"{provider['name']} key missing"
            continue

        headers = {
            "Authorization": f"Bearer {provider['key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": provider["model"],
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        }

        try:
            response = requests.post(
                provider["url"], headers=headers, json=payload, timeout=30
            )

            # Catch 400/401/402/403/404/429/5xx so it cleanly switches to the next provider
            if response.status_code != 200:
                last_error = f"{provider['name']} error ({response.status_code})"
                if idx == 0:
                    fallback_reason = last_error
                continue

            reply = response.json()["choices"][0]["message"]["content"].strip()
            label = provider["name"]
            if fallback_reason:
                label = f"{provider['name']} (Fallback: {fallback_reason})"
            return reply, label

        except requests.RequestException:
            last_error = f"{provider['name']} failed"
            if idx == 0:
                fallback_reason = last_error
            continue

    raise RuntimeError(f"All models exhausted or failed. Last error: {last_error}")


def ensure_default_datasets():
    """Ensure student.json and teacher.json are always in sync with SQLite."""
    base_dir = settings.BASE_DIR
    db_path = settings.DATABASES["default"]["NAME"]

    defaults = [
        ("student.json", "assistant_student"),
        ("teacher.json", "assistant_teacher"),
    ]

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            for filename, table_name in defaults:
                filepath = os.path.join(base_dir, filename)
                if os.path.exists(filepath):
                    with open(filepath, "r", encoding="utf-8") as f:
                        raw_data = json.load(f)
                    df = pd.json_normalize(raw_data)
                    df.columns = [
                        re.sub(r"\W+", "_", c.strip().lower()) for c in df.columns
                    ]

                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
                        (table_name,),
                    )
                    exists = cursor.fetchone()
                    need_update = True
                    if exists:
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                        cnt = cursor.fetchone()[0]
                        if cnt == len(df):
                            cursor.execute(f"PRAGMA table_info({table_name});")
                            existing_cols = [c[1] for c in cursor.fetchall()]
                            if sorted(existing_cols) == sorted(df.columns.tolist()):
                                need_update = False

                    if need_update:
                        df.to_sql(table_name, conn, if_exists="replace", index=False)
    except Exception:
        pass


def get_db_schema():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND name LIKE 'assistant_%';"
        )
        tables = cursor.fetchall()
    return "\n".join([f"{name}: {sql}" for name, sql in tables])


def is_safe_select_query(sql_query):
    cleaned = sql_query.strip().upper()
    if not cleaned.startswith("SELECT"):
        return False
    forbidden = r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|REPLACE|CREATE|GRANT|REVOKE)\b"
    return not bool(re.search(forbidden, cleaned))


def index(request):
    ensure_default_datasets()

    chat_history = request.session.get("chat_history", [])
    selected_model = request.session.get("selected_model", "groq")
    if selected_model == "auto":
        selected_model = "groq"

    if request.method == "POST":
        if request.POST.get("clear_chat"):
            request.session["chat_history"] = []
            return render(
                request,
                "assistant/index.html",
                {"chat_history": [], "selected_model": selected_model},
            )

        selected_model = request.POST.get("selected_model", "groq")
        request.session["selected_model"] = selected_model

        question = request.POST.get("question", "").strip()
        uploaded_files = request.FILES.getlist("dataset_file")

        import_messages = []
        if uploaded_files:
            db_path = settings.DATABASES["default"]["NAME"]
            with sqlite3.connect(db_path) as conn:
                for f in uploaded_files:
                    try:
                        ext = os.path.splitext(f.name)[1].lower()
                        if ext == ".json":
                            raw_data = json.load(f)
                            df = pd.json_normalize(raw_data)
                        elif ext == ".csv":
                            df = pd.read_csv(f)
                        else:
                            import_messages.append(
                                f"Skipped '{f.name}': only .json and .csv files are supported."
                            )
                            continue

                        df.columns = [
                            re.sub(r"\W+", "_", c.strip().lower()) for c in df.columns
                        ]
                        base_name = os.path.splitext(f.name)[0]
                        clean_name = re.sub(r"\W+", "_", base_name.strip().lower())
                        table_name = f"assistant_{clean_name}"

                        df.to_sql(table_name, conn, if_exists="replace", index=False)
                        cols_str = ", ".join(df.columns.tolist()[:6])
                        if len(df.columns) > 6:
                            cols_str += f", +{len(df.columns) - 6} more"
                        import_messages.append(
                            f"Imported '{f.name}' ({len(df)} records) into table '{table_name}'. Columns: [{cols_str}]"
                        )
                    except Exception as e:
                        import_messages.append(f"Failed to import '{f.name}': {str(e)}")

        # If user uploaded file with no text question
        if uploaded_files and not question:
            file_names = ", ".join(f.name for f in uploaded_files)
            chat_history.append(
                {
                    "user": f"Uploaded dataset: {file_names}",
                    "sql": "",
                    "columns": [],
                    "rows": [],
                    "model_used": "",
                    "info": "<br>".join(import_messages),
                    "error": "",
                }
            )
            request.session["chat_history"] = chat_history
            return render(
                request,
                "assistant/index.html",
                {"chat_history": chat_history, "selected_model": selected_model},
            )

        if question:
            schema = get_db_schema()
            prompt = (
                f"You are a SQLite expert assisting with a database.\n"
                f"Database Schema:\n{schema}\n\n"
                f"Write a single valid SQLite SELECT query to answer: '{question}'.\n\n"
                "College Database Rules:\n"
                "1. Student table: assistant_student\n"
                "   - Columns: student_id, name, branch, artificial_intelligence, machine_learning, python, deep_learning, maths, total_marks, cgpa, status, failed_subjects.\n"
                "   - 4 Branches: 'AI & DS', 'IT', 'CSE', 'AI & ML'. Handle variations (e.g. 'aids' -> 'AI & DS', 'aiml' -> 'AI & ML').\n"
                "   - 5 Subjects: artificial_intelligence, machine_learning, python, deep_learning, maths.\n"
                "   - CGPA: float from 0.0 to 10.0.\n"
                "   - Status: 'Pass' means the student passed ALL 5 subjects (every subject >= 50). 'Fail' means failed in at least one subject (< 50).\n"
                "   - Query Logic:\n"
                "     * If user asks 'pass in all subject', 'passed all subjects', or 'who passed in all subjects':\n"
                "       SELECT student_id, name, branch, cgpa, status FROM assistant_student WHERE status = 'Pass';\n"
                "     * If user asks 'who failed' or 'failed students':\n"
                "       SELECT student_id, name, branch, failed_subjects, status FROM assistant_student WHERE status = 'Fail';\n"
                "     * If user asks for performance/marks in a specific subject (e.g. 'who passed in python', 'failed in maths'):\n"
                "       SELECT student_id, name, branch, python FROM assistant_student WHERE python >= 50;\n"
                "     * If user asks for 'student details' or 'all students':\n"
                "       SELECT student_id, name, branch, artificial_intelligence, machine_learning, python, deep_learning, maths, total_marks, cgpa, status FROM assistant_student;\n"
                "2. Teacher table: assistant_teacher\n"
                "   - Columns: teacher_id, name, subject, department, hod_name, experience_years.\n"
                "   - Always include the hod_name column when displaying teacher details (e.g. SELECT teacher_id, name, subject, department, hod_name, experience_years FROM assistant_teacher).\n"
                "   - If the user asks for HODs (e.g. 'who is the HOD of CSE', 'list all HODs', 'HOD of AI & DS'):\n"
                "     SELECT DISTINCT department, hod_name FROM assistant_teacher WHERE lower(trim(department)) = ...\n"
                "3. Any imported tables starting with assistant_ are available to query directly as well.\n"
                "4. ONLY query tables that actually exist in the schema above.\n"
                "5. If the user asks about a table or topic not in the schema, return: "
                "SELECT 'Table not found in database' AS message;\n"
                "6. Return ONLY the raw SQL query with no markdown, no backticks, and no explanation."
            )

            generated_sql = ""
            columns = []
            rows = []
            used_model = ""
            error = ""

            try:
                raw_sql, used_model = ask_llm(prompt, preferred_id=selected_model)
                raw_sql = raw_sql.replace("```sql", "").replace("```", "").strip()
                generated_sql = raw_sql

                if not is_safe_select_query(raw_sql):
                    error = "Blocked: Only read-only SELECT queries are allowed."
                else:
                    with connection.cursor() as cursor:
                        cursor.execute(raw_sql)
                        columns = [col[0] for col in cursor.description]
                        rows = cursor.fetchall()
            except Exception as e:
                error = f"Error: {str(e)}"

            user_text = question
            if uploaded_files:
                user_text = f"📎 [{', '.join(f.name for f in uploaded_files)}] {question}"

            chat_history.append(
                {
                    "user": user_text,
                    "sql": generated_sql,
                    "columns": columns,
                    "rows": rows,
                    "model_used": used_model,
                    "info": "<br>".join(import_messages) if import_messages else "",
                    "error": error,
                }
            )
            request.session["chat_history"] = chat_history

    return render(
        request,
        "assistant/index.html",
        {"chat_history": chat_history, "selected_model": selected_model},
    )