"""
setup_demo_users.py — sets simple passwords for multiple demo users so you
can log in as different people during the presentation.

Run once:  py setup_demo_users.py
"""
from werkzeug.security import generate_password_hash
from config import Config
import mysql.connector

# (user_id, password) — matches usernames from seed_data:
# id 1 = s1mple_fan_99   (buyer)
# id 2 = ZywOo_GOAT      (seller)
# id 3 = device_CPH      (trader)
# id 4 = NiKo_G2         (renter)
DEMO_ACCOUNTS = [
    (1, "demo1234"),
    (2, "demo1234"),
    (3, "demo1234"),
    (4, "demo1234"),
]

conn = mysql.connector.connect(**Config.DB)
cur  = conn.cursor()
for uid, pw in DEMO_ACCOUNTS:
    cur.execute(
        "UPDATE Users SET password_hash=%s WHERE user_id=%s",
        (generate_password_hash(pw), uid),
    )
    cur.execute("SELECT username FROM Users WHERE user_id=%s", (uid,))
    name = cur.fetchone()[0]
    print(f"✓ id={uid:2d}  {name:<20s}  password: {pw}")
conn.commit()
cur.close()
conn.close()
print("\nAll demo users ready. Passwords are 'demo1234'.")