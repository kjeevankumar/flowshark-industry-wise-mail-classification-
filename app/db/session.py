"""Database engine, session management, and initialization.

Configures SQLAlchemy engine (SQLite by default, PostgreSQL ready),
provides session dependency for FastAPI, and initializes database schema.
"""

import os
from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config import get_settings

settings = get_settings()

# Normalize connection string (Render provides postgres:// which SQLAlchemy 2.0 requires as postgresql://)
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Ensure local data directory exists for SQLite
if db_url.startswith("sqlite"):
    # Extract path if file-based sqlite
    db_path = db_url.replace("sqlite:///", "")
    if db_path and db_path != ":memory:":
        parent_dir = Path(db_path).resolve().parent
        parent_dir.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all registered database tables if they do not already exist."""
    # Import all models so metadata knows about them
    import app.models.tenant_model  # noqa: F401
    import app.models.organization_model  # noqa: F401
    import app.models.mailbox_model  # noqa: F401
    import app.models.email_model  # noqa: F401
    import app.models.conversation_model  # noqa: F401
    import app.models.classification_model  # noqa: F401
    import app.models.sync_model  # noqa: F401
    import app.models.contact_model  # noqa: F401
    import app.models.lead_model  # noqa: F401
    import app.models.task_model  # noqa: F401
    import app.models.commercial_event_model  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Lightweight migration for SQLite tables
    if db_url.startswith("sqlite"):
        try:
            from sqlalchemy import text
            from app.core.security import encrypt_credential

            with engine.connect() as conn:
                # 0. Bootstrap default tenant if table exists and empty
                tenant_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(tenants)")).fetchall()]
                default_tenant_id = 1
                if tenant_cols:
                    t_row = conn.execute(text("SELECT id FROM tenants WHERE slug = 'default' LIMIT 1")).fetchone()
                    if not t_row:
                        t_cursor = conn.execute(
                            text("INSERT INTO tenants (name, slug, created_at, updated_at) VALUES ('FlowShark Default', 'default', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
                        )
                        default_tenant_id = t_cursor.lastrowid
                        conn.commit()
                    else:
                        default_tenant_id = t_row[0]

                # 1. sync_state columns
                sync_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(sync_state)")).fetchall()]
                if sync_cols:
                    if "mailbox_id" not in sync_cols:
                        conn.execute(text("ALTER TABLE sync_state ADD COLUMN mailbox_id INTEGER REFERENCES mailboxes(id)"))
                    if "new_emails_last_sync" not in sync_cols:
                        conn.execute(text("ALTER TABLE sync_state ADD COLUMN new_emails_last_sync INTEGER DEFAULT 0"))
                    if "worker_status" not in sync_cols:
                        conn.execute(text("ALTER TABLE sync_state ADD COLUMN worker_status VARCHAR(50) DEFAULT 'stopped'"))

                # 2. mailboxes columns
                mb_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(mailboxes)")).fetchall()]
                if mb_cols:
                    if "tenant_id" not in mb_cols:
                        conn.execute(text("ALTER TABLE mailboxes ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)"))
                        conn.execute(text("UPDATE mailboxes SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": default_tenant_id})

                # 3. emails columns
                email_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(emails)")).fetchall()]
                if email_cols:
                    if "tenant_id" not in email_cols:
                        conn.execute(text("ALTER TABLE emails ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)"))
                        conn.execute(text("UPDATE emails SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": default_tenant_id})
                    if "mailbox_id" not in email_cols:
                        conn.execute(text("ALTER TABLE emails ADD COLUMN mailbox_id INTEGER REFERENCES mailboxes(id)"))
                    if "organization_id" not in email_cols:
                        conn.execute(text("ALTER TABLE emails ADD COLUMN organization_id INTEGER REFERENCES organizations(id)"))
                    if "contact_id" not in email_cols:
                        conn.execute(text("ALTER TABLE emails ADD COLUMN contact_id INTEGER REFERENCES contacts(id)"))
                    if "lead_id" not in email_cols:
                        conn.execute(text("ALTER TABLE emails ADD COLUMN lead_id INTEGER REFERENCES leads(id)"))
                    if "cc" not in email_cols:
                        conn.execute(text("ALTER TABLE emails ADD COLUMN cc VARCHAR(500)"))
                    if "bcc" not in email_cols:
                        conn.execute(text("ALTER TABLE emails ADD COLUMN bcc VARCHAR(500)"))

                # 4. conversations columns
                conv_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(conversations)")).fetchall()]
                if conv_cols:
                    if "mailbox_id" not in conv_cols:
                        conn.execute(text("ALTER TABLE conversations ADD COLUMN mailbox_id INTEGER REFERENCES mailboxes(id)"))
                    if "contact_id" not in conv_cols:
                        conn.execute(text("ALTER TABLE conversations ADD COLUMN contact_id INTEGER REFERENCES contacts(id)"))
                    if "lead_id" not in conv_cols:
                        conn.execute(text("ALTER TABLE conversations ADD COLUMN lead_id INTEGER REFERENCES leads(id)"))

                # 5. classifications columns
                class_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(classifications)")).fetchall()]
                if class_cols:
                    if "tenant_id" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)"))
                        conn.execute(text("UPDATE classifications SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": default_tenant_id})
                    if "mailbox_id" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN mailbox_id INTEGER REFERENCES mailboxes(id)"))
                    if "organization_id" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN organization_id INTEGER REFERENCES organizations(id)"))
                    if "contact_id" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN contact_id INTEGER REFERENCES contacts(id)"))
                    if "lead_id" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN lead_id INTEGER REFERENCES leads(id)"))
                    if "context_used" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN context_used TEXT"))
                    if "sender_industry" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN sender_industry VARCHAR(100) DEFAULT 'Unknown'"))
                    if "customer_org_industry" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN customer_org_industry VARCHAR(100) DEFAULT 'Unknown'"))
                    if "target_industry" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN target_industry VARCHAR(100) DEFAULT 'Unknown'"))
                    if "requested_solution_domain" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN requested_solution_domain VARCHAR(100) DEFAULT 'Unknown'"))
                    if "sub_industry" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN sub_industry VARCHAR(100)"))
                    if "business_activity" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN business_activity TEXT"))
                    if "industry_confidence" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN industry_confidence FLOAT DEFAULT 0.0"))
                    if "industry_reason" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN industry_reason TEXT"))
                    if "industry_evidence" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN industry_evidence JSON"))
                    if "industry_requires_review" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN industry_requires_review BOOLEAN DEFAULT 0"))
                    if "relevance_category" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN relevance_category VARCHAR(50) DEFAULT 'business_enquiry'"))
                    if "is_business_relevant" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN is_business_relevant BOOLEAN DEFAULT 1"))
                    if "pipeline_category" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN pipeline_category VARCHAR(50)"))
                    if "commercial_intent" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN commercial_intent VARCHAR(50) DEFAULT 'none'"))
                    if "supporting_evidence" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN supporting_evidence JSON"))
                    if "executive_explanation" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN executive_explanation TEXT"))
                    if "priority_score" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN priority_score FLOAT DEFAULT 0.5"))
                    if "priority_level" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN priority_level VARCHAR(50) DEFAULT 'warm'"))
                    if "action_urgency" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN action_urgency VARCHAR(50) DEFAULT 'medium'"))
                    if "business_potential" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN business_potential VARCHAR(50) DEFAULT 'medium'"))
                    if "information_completeness" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN information_completeness VARCHAR(50) DEFAULT 'partial'"))
                    if "review_reasons" not in class_cols:
                        conn.execute(text("ALTER TABLE classifications ADD COLUMN review_reasons JSON"))

                # 6. contacts columns
                contact_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(contacts)")).fetchall()]
                if contact_cols:
                    if "tenant_id" not in contact_cols:
                        conn.execute(text("ALTER TABLE contacts ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)"))
                        conn.execute(text("UPDATE contacts SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": default_tenant_id})
                    if "organization_id" not in contact_cols:
                        conn.execute(text("ALTER TABLE contacts ADD COLUMN organization_id INTEGER REFERENCES organizations(id)"))
                    if "industry" not in contact_cols:
                        conn.execute(text("ALTER TABLE contacts ADD COLUMN industry VARCHAR(100) DEFAULT 'Unknown'"))
                    if "sub_industry" not in contact_cols:
                        conn.execute(text("ALTER TABLE contacts ADD COLUMN sub_industry VARCHAR(100)"))

                # 7. leads columns
                lead_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(leads)")).fetchall()]
                if lead_cols:
                    if "tenant_id" not in lead_cols:
                        conn.execute(text("ALTER TABLE leads ADD COLUMN tenant_id INTEGER REFERENCES tenants(id)"))
                        conn.execute(text("UPDATE leads SET tenant_id = :tid WHERE tenant_id IS NULL"), {"tid": default_tenant_id})
                    if "organization_id" not in lead_cols:
                        conn.execute(text("ALTER TABLE leads ADD COLUMN organization_id INTEGER REFERENCES organizations(id)"))
                    if "target_industry" not in lead_cols:
                        conn.execute(text("ALTER TABLE leads ADD COLUMN target_industry VARCHAR(100) DEFAULT 'Unknown'"))
                    if "sub_industry" not in lead_cols:
                        conn.execute(text("ALTER TABLE leads ADD COLUMN sub_industry VARCHAR(100)"))
                    if "requested_solution_domain" not in lead_cols:
                        conn.execute(text("ALTER TABLE leads ADD COLUMN requested_solution_domain VARCHAR(100) DEFAULT 'Unknown'"))
                    if "priority" not in lead_cols:
                        conn.execute(text("ALTER TABLE leads ADD COLUMN priority VARCHAR(50) DEFAULT 'warm'"))
                    if "assigned_to" not in lead_cols:
                        conn.execute(text("ALTER TABLE leads ADD COLUMN assigned_to VARCHAR(255)"))

                # 8. classification_history columns
                hist_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(classification_history)")).fetchall()]
                if hist_cols:
                    if "mailbox_id" not in hist_cols:
                        conn.execute(text("ALTER TABLE classification_history ADD COLUMN mailbox_id INTEGER REFERENCES mailboxes(id)"))
                    if "email_id" not in hist_cols:
                        conn.execute(text("ALTER TABLE classification_history ADD COLUMN email_id INTEGER REFERENCES emails(id)"))

                conn.commit()

                # 9. Bootstrap default active mailbox from settings if available and mailboxes table is empty
                if settings.GMAIL_ADDRESS:
                    account_addr = settings.GMAIL_ADDRESS.strip().lower()
                    existing_mb = conn.execute(
                        text("SELECT id, is_active FROM mailboxes WHERE lower(email_address) = :addr"),
                        {"addr": account_addr},
                    ).fetchone()

                    active_id = None
                    if not existing_mb:
                        enc_pwd = encrypt_credential(settings.clean_app_password or "")
                        cursor = conn.execute(
                            text(
                                "INSERT INTO mailboxes (tenant_id, email_address, encrypted_app_password, is_active, imap_host, imap_port, smtp_host, smtp_port, created_at, updated_at) "
                                "VALUES (:tid, :email, :pwd, 1, :ihost, :iport, :shost, :sport, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                            ),
                            {
                                "tid": default_tenant_id,
                                "email": account_addr,
                                "pwd": enc_pwd,
                                "ihost": settings.IMAP_HOST,
                                "iport": settings.IMAP_PORT,
                                "shost": settings.SMTP_HOST,
                                "sport": settings.SMTP_PORT,
                            },
                        )
                        active_id = cursor.lastrowid
                        conn.commit()
                    else:
                        active_id = existing_mb[0]

                    # Backfill mailbox_id for legacy unassigned rows
                    if active_id:
                        conn.execute(text("UPDATE emails SET mailbox_id = :mid WHERE mailbox_id IS NULL"), {"mid": active_id})
                        conn.execute(text("UPDATE conversations SET mailbox_id = :mid WHERE mailbox_id IS NULL"), {"mid": active_id})
                        conn.execute(text("UPDATE classifications SET mailbox_id = :mid WHERE mailbox_id IS NULL"), {"mid": active_id})
                        conn.execute(text("UPDATE sync_state SET mailbox_id = :mid WHERE mailbox_id IS NULL"), {"mid": active_id})
                        conn.commit()
        except Exception as e:
            pass
    elif "postgresql" in db_url or "postgres" in db_url:
        try:
            from sqlalchemy import text
            with engine.connect() as conn:
                for col_stmt in [
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS relevance_category VARCHAR(50) DEFAULT 'business_enquiry'",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS is_business_relevant BOOLEAN DEFAULT TRUE",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS pipeline_category VARCHAR(50)",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS commercial_intent VARCHAR(50) DEFAULT 'none'",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS supporting_evidence JSON",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS executive_explanation TEXT",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS priority_score FLOAT DEFAULT 0.5",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS priority_level VARCHAR(50) DEFAULT 'warm'",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS action_urgency VARCHAR(50) DEFAULT 'medium'",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS business_potential VARCHAR(50) DEFAULT 'medium'",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS information_completeness VARCHAR(50) DEFAULT 'partial'",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS customer_org_industry VARCHAR(100) DEFAULT 'Unknown'",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS requested_solution_domain VARCHAR(100) DEFAULT 'Unknown'",
                    "ALTER TABLE classifications ADD COLUMN IF NOT EXISTS review_reasons JSON",
                    "ALTER TABLE emails ADD COLUMN IF NOT EXISTS cc VARCHAR(500)",
                    "ALTER TABLE emails ADD COLUMN IF NOT EXISTS bcc VARCHAR(500)",
                    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS priority VARCHAR(50) DEFAULT 'warm'",
                    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS requested_solution_domain VARCHAR(100) DEFAULT 'Unknown'",
                    "ALTER TABLE leads ADD COLUMN IF NOT EXISTS assigned_to VARCHAR(255)",
                ]:
                    try:
                        conn.execute(text(col_stmt))
                    except Exception:
                        pass
                conn.commit()
        except Exception:
            pass

