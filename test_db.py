import db

print("Testing database...")

conn = db.get_connection()

print("Connected!")

before = conn.execute(
    "SELECT COUNT(*) AS count FROM opportunities"
).fetchone()["count"]

print("Opportunities before init:", before)

conn.close()

print("Running init_db()...")

db.init_db()

print("init_db() finished!")

conn = db.get_connection()

students = conn.execute(
    "SELECT COUNT(*) AS count FROM students"
).fetchone()["count"]

opportunities = conn.execute(
    "SELECT COUNT(*) AS count FROM opportunities"
).fetchone()["count"]

skills = conn.execute(
    "SELECT COUNT(*) AS count FROM skills"
).fetchone()["count"]

print("Students:", students)
print("Opportunities:", opportunities)
print("Skills:", skills)

conn.close()