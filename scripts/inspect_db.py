import sqlite3
import json

conn = sqlite3.connect('data/flowshark.db')
c = conn.cursor()

tables = [t[0] for t in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)

for t in tables:
    cols = [col[1] for col in c.execute(f"PRAGMA table_info({t})").fetchall()]
    print(f"\n--- {t} ({len(cols)} cols) ---")
    print(", ".join(cols))
    count = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"Total rows: {count}")
    if count > 0 and t in ['mailboxes', 'sync_state', 'leads', 'contacts']:
        rows = c.execute(f"SELECT * FROM {t} LIMIT 5").fetchall()
        for r in rows:
            print("  ", r)

print("\n--- Recent 10 Emails ---")
emails = c.execute("SELECT id, mailbox_id, sender, subject, received_at FROM emails ORDER BY id DESC LIMIT 10").fetchall()
for e in emails:
    print("  ", e)

print("\n--- Classifications on Non-business or Security / Google emails ---")
sec_emails = c.execute("SELECT e.id, e.sender, e.subject, cl.relationship, cl.intent, cl.lead_stage, cl.sender_industry, cl.target_industry, cl.confidence, cl.classification_reason FROM emails e LEFT JOIN classifications cl ON e.id = cl.email_id WHERE e.sender LIKE '%google%' OR e.subject LIKE '%security%' OR e.subject LIKE '%verification%' OR e.subject LIKE '%alert%'").fetchall()
for se in sec_emails:
    print("  Security/Google email:", se)

print("\n--- All distinct intent & relationship combos ---")
combos = c.execute("SELECT relationship, intent, lead_stage, count(*) FROM classifications GROUP BY relationship, intent, lead_stage").fetchall()
for cb in combos:
    print("  ", cb)
