import os
from dotenv import load_dotenv

# reads the .env file so passwords are not written in the code
load_dotenv()


class Config:
    SECRET_KEY = os.environ.get(
        "FLASK_SECRET_KEY", "dev-only-secret-do-not-use-in-production"
    )
    # I kept these in one dict so db.py can pass them straight to the pool
    DB = {
        "host":     os.environ.get("DB_HOST", "localhost"),
        "port":     int(os.environ.get("DB_PORT", "3306")),
        "user":     os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "database": os.environ.get("DB_NAME", "cs2_marketplace"),
    }