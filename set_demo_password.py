"""
Run once after loading seed_data.sql. Sets user_id=1's password to
'demo1234' so the grader can log in during the presentation without
having to register first.

    python set_demo_password.py
"""
from werkzeug.security import generate_password_hash
from config import Config
import mysql.connector

DEMO_USER_ID = 1
DEMO_PASSWORD = "demo1234"

conn = mysql.connector.connect(**Config.DB)
cur = conn.cursor()
cur.execute(
    "UPDATE Users SET password_hash=%s WHERE user_id=%s",
    (generate_password_hash(DEMO_PASSWORD), DEMO_USER_ID),
)
conn.commit()
cur.execute("SELECT username FROM Users WHERE user_id=%s", (DEMO_USER_ID,))
name = cur.fetchone()[0]
cur.close()
conn.close()
print(f"✓ User '{name}' (id={DEMO_USER_ID}) can now log in with password: {DEMO_PASSWORD}")