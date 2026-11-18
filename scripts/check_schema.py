import sqlite3

conn = sqlite3.connect("data/flowshark.db")
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [r[0] for r in c.fetchall()])
c.execute("PRAGMA table_info(classifications)")
cols = [r[1] for r in c.fetchall()]
print("Classifications columns:", cols)
c.execute("PRAGMA table_info(leads)")
print("Leads columns:", [r[1] for r in c.fetchall()])
c.execute("PRAGMA table_info(emails)")
print("Emails columns:", [r[1] for r in c.fetchall()])
