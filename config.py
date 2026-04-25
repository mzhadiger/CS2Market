"""
config.py — Centralizes configuration. Reads from .env so secrets stay
out of source control.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # Loads .env in the current working directory.


class Config:
    SECRET_KEY = os.environ.get(
        "FLASK_SECRET_KEY", "dev-only-secret-do-not-use-in-production"
    )
    # Grouped so db.py can splat this straight into MySQLConnectionPool(**DB).
    DB = {
        "host":     os.environ.get("DB_HOST", "localhost"),
        "port":     int(os.environ.get("DB_PORT", "3306")),
        "user":     os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "database": os.environ.get("DB_NAME", "cs2_marketplace"),
    }