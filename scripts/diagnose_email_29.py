import sqlite3
import os

def inspect_db(db_path: str):
    print(f"\n==========================================")
    print(f"Inspecting DB: {db_path}")
    print(f"Exists: {os.path.exists(db_path)}")
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row["name"] for row in cursor.fetchall()]
    print(f"Tables: {tables}")

    for tbl in ["mailboxes", "emails", "classifications", "classification_history", "contacts", "leads"]:
        if tbl in tables:
            cursor.execute(f"PRAGMA table_info({tbl});")
            cols = [c["name"] for c in cursor.fetchall()]
            cursor.execute(f"SELECT count(*) as count FROM {tbl};")
            count = cursor.fetchone()["count"]
            print(f"  Table '{tbl}' has {count} rows. Columns: {cols[:8]}... (total {len(cols)})")

    # If emails exist, inspect email 29 or any email
    if "emails" in tables:
        cursor.execute("SELECT * FROM emails WHERE id = 29;")
        e29 = cursor.fetchone()
        if e29:
            print(f"\n  Found Email 29 in {db_path}:")
            for k in e29.keys():
                if k not in ("body_text", "body_html", "raw_headers"):
                    print(f"    {k}: {e29[k]}")
        else:
            print(f"\n  Email 29 not found. Showing latest 3 emails:")
            cursor.execute("SELECT * FROM emails ORDER BY id DESC LIMIT 3;")
            for row in cursor.fetchall():
                print(f"    ID {row['id']}: subject='{row.get('subject')}'")

    if "classifications" in tables:
        cursor.execute("SELECT * FROM classifications WHERE email_id = 29;")
        c29 = cursor.fetchall()
        print(f"\n  Classifications for email_id = 29 in {db_path}: {len(c29)} rows")
        for row in c29:
            d = dict(row)
            print(f"    Classification row: {d}")

    conn.close()

if __name__ == "__main__":
    inspect_db(r"C:\Users\Lenovo\Downloads\anvayuOne\data\flowshark.db")
    inspect_db(r"C:\Users\Lenovo\Downloads\anvayuOne\gmail-fastapi-integration\data\flowshark.db")
