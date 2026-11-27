import os
import sqlite3
from django.apps import AppConfig
from django.conf import settings

class AssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'assistant'

    def ready(self):
        # Clear previous chat sessions on server startup so chat starts fresh
        try:
            db_path = settings.DATABASES["default"]["NAME"]
            if os.path.exists(db_path):
                with sqlite3.connect(db_path) as conn:
                    conn.execute("DELETE FROM django_session;")
        except Exception:
            pass
