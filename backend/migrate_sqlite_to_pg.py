#!/usr/bin/env python3
"""
SQLite to PostgreSQL migration script for Supplier Hub
Copies data from backend/db/supplier_hub.db to PostgreSQL
"""
import os
import sqlite3
from datetime import datetime

# Force PostgreSQL connection
os.environ["DATABASE_URL"] = os.getenv("DATABASE_URL", "postgresql://supplier:supplier123@localhost:5432/supplier_hub")

import sys
sys.path.insert(0, "backend")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ─── Connect ───────────────────────────────────────────
sqlite_conn = sqlite3.connect("backend/db/supplier_hub.db")
sqlite_conn.row_factory = sqlite3.Row
pg_engine = create_engine(os.environ["DATABASE_URL"])
Session = sessionmaker(bind=pg_engine)
pg_session = Session()

print(f"SQLite:  backend/db/supplier_hub.db")
print(f"PostgreSQL: {os.environ['DATABASE_URL']}")
print()

def copy_table(table_name, column_mapping=None, skip_columns=None):
    """Copy data from SQLite to PostgreSQL"""
    cursor = sqlite_conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    if not rows:
        print(f"  {table_name}: no data to migrate")
        return 0

    # Get column names from SQLite
    columns = [desc[0] for desc in cursor.description]

    # Apply column mapping (old_name -> new_name)
    if column_mapping:
        columns = [column_mapping.get(c, c) for c in columns]

    # Skip problematic columns
    if skip_columns:
        filtered = [(c, i) for i, c in enumerate(columns) if c not in skip_columns]
        columns = [c for c, _ in filtered]
        indices = [i for _, i in filtered]
    else:
        indices = list(range(len(columns)))

    col_str = ", ".join(columns)
    placeholders = ", ".join([f":{c}" for c in columns])

    count = 0
    for row in rows:
        values = {columns[j]: row[indices[j]] for j in range(len(columns))}
        # Convert booleans (SQLite stores 0/1, PostgreSQL wants True/False)
        for k, v in list(values.items()):
            if isinstance(v, int) and v in (0, 1):
                # Only convert if the column NAME suggests it's a boolean
                boolean_keywords = ["is_", "used", "active", "compliant",
                                      "candidate", "restricted", "accessible",
                                      "extracted", "resolved", "current",
                                      "svhc", "warning", "expiry", "visible"]
                if any(b in k.lower() for b in boolean_keywords):
                    values[k] = bool(v)
        try:
            pg_session.execute(text(f"INSERT INTO {table_name} ({col_str}) VALUES ({placeholders})"), values)
            count += 1
        except Exception as e:
            print(f"  ⚠️  Failed to insert into {table_name}: {e} — data: {values}")
            pg_session.rollback()
            raise

    print(f"  {table_name}: migrated {count} rows")
    return count

# ─── Migrate management tables ─────────────────────────
print("Migrating management tables...")
try:
    # Truncate tables first so the script is idempotent
    tables = [
        "supplier_documents",
        "material_registrations",
        "registered_manufactures",
        "supplier_registrations",
        "audit_log",
        "suppliers",
        "internal_users",
        "departments",
    ]
    print("  Truncating existing PostgreSQL tables...")
    for t in tables:
        pg_session.execute(text(f"TRUNCATE TABLE {t} CASCADE"))
        print(f"    {t}")
    pg_session.commit()
    print()

    # 1. departments (no FK dependencies)
    copy_table("departments")

    # 2. internal_users (depends on departments, skip extra columns not in models.py)
    copy_table("internal_users", skip_columns=["created_by", "password"])

    # 3. suppliers (depends on internal_users via assigned_to)
    copy_table("suppliers")

    # 4. audit_log
    copy_table("audit_log")

    # 5. supplier_registrations
    copy_table("supplier_registrations")

    # 6. registered_manufactures
    copy_table("registered_manufactures")

    # 7. material_registrations
    copy_table("material_registrations", skip_columns=["is_food_contact"])

    # 8. supplier_documents
    copy_table("supplier_documents")

    pg_session.commit()
    print()
    print("✅ Migration complete!")

except Exception as e:
    pg_session.rollback()
    print(f"\n❌ Migration failed: {e}")
    raise
finally:
    sqlite_conn.close()
    pg_session.close()
