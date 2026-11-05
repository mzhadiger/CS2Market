# Sets the password demo1234 for the first 4 users so we can log in as
# different people during the presentation.
# Run it once after loading seed_data.sql:  py setup_demo_users.py
from werkzeug.security import generate_password_hash
from config import Config
import mysql.connector

# user ids from seed_data.sql:
# 1 is s1mple_fan_99 (buyer)
# 2 is ZywOo_GOAT (seller)
# 3 is device_CPH (trader)
# 4 is NiKo_G2 (renter)
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
    print(f"id={uid:2d}  {name:<20s}  password: {pw}")
conn.commit()
cur.close()
conn.close()
print("\nAll demo users ready. Passwords are 'demo1234'.")