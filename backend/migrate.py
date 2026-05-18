#!/usr/bin/env python3
"""Database migration script for Supplier Hub"""
import os
import time
from sqlalchemy import create_engine, text, exc

# Single Database URL - supports both SQLite and PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///backend/db/supplier_hub.db")

# Connection retry settings
max_retries = 30
retry_delay = 2


def get_engine():
    """Get database engine with retry."""
    for attempt in range(max_retries):
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                print(f"✅ Database connection successful! URL: {DATABASE_URL}")
                return engine
        except exc.OperationalError as e:
            if attempt < max_retries - 1:
                print(f"⏳ Waiting for database... (attempt {attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                print(f"❌ Could not connect to database after {max_retries} attempts")
                raise


# ======================================================================
# All Database Migrations (Management + Pipeline in one database)
# ======================================================================

migrations = [
    # ==================================================================
    # Management Portal Tables
    # ==================================================================

    # Internal Users table
    """CREATE TABLE IF NOT EXISTS internal_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        password_hash VARCHAR(255),
        full_name VARCHAR(100) NOT NULL,
        invitation_code VARCHAR(50) UNIQUE NOT NULL,
        invitation_used BOOLEAN DEFAULT 0,
        invitation_expires DATETIME NOT NULL,
        role VARCHAR(20) NOT NULL DEFAULT 'viewer',
        department_id INTEGER,
        supervisor_id INTEGER,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_login DATETIME,
        created_by INTEGER
    )""",

    # Departments table
    """CREATE TABLE IF NOT EXISTS departments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(50) NOT NULL,
        code VARCHAR(10) UNIQUE NOT NULL,
        description TEXT,
        manager_id INTEGER,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Audit Log table
    """CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action VARCHAR(50) NOT NULL,
        entity_type VARCHAR(50) NOT NULL,
        entity_id INTEGER,
        old_value TEXT,
        new_value TEXT,
        ip_address VARCHAR(45),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Suppliers table (management portal)
    """CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR NOT NULL,
        email VARCHAR UNIQUE NOT NULL,
        code VARCHAR UNIQUE NOT NULL,
        password VARCHAR NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        assigned_to INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # ==================================================================
    # Pipeline Database Tables
    # ==================================================================

    # Manufacturers table
    """CREATE TABLE IF NOT EXISTS manufacturers (
        manufacturer_id VARCHAR(50) PRIMARY KEY,
        manufacturer_name VARCHAR(200) NOT NULL,
        manufacturer_code VARCHAR(100),
        country VARCHAR(100),
        website VARCHAR(500),
        contact_email VARCHAR(200),
        contact_phone VARCHAR(50),
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Pipeline Suppliers table (different from management suppliers)
    """CREATE TABLE IF NOT EXISTS suppliers (
        supplier_id VARCHAR(50) PRIMARY KEY,
        supplier_name VARCHAR(200) NOT NULL,
        supplier_material_id VARCHAR(100),
        manufacturer_id VARCHAR(50),
        contact_email VARCHAR(200),
        contact_phone VARCHAR(50),
        address TEXT,
        status VARCHAR(20) DEFAULT 'active',
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Material Library table
    """CREATE TABLE IF NOT EXISTS material_library (
        material_id VARCHAR(50) PRIMARY KEY,
        material_name VARCHAR(200) NOT NULL,
        component_name VARCHAR(200),
        supplier_id VARCHAR(50) NOT NULL,
        material_type VARCHAR(20) DEFAULT 'mixture',
        category VARCHAR(50),
        physical_state VARCHAR(20),
        cas_number VARCHAR(50),
        ghs_classification VARCHAR(200),
        en71_3_category VARCHAR(10),
        migration_limit_mg_kg FLOAT,
        reach_regulation VARCHAR(20),
        reach_svhc_candidate BOOLEAN DEFAULT 0,
        reach_annex_xvii BOOLEAN DEFAULT 0,
        toy_directive_compliant BOOLEAN,
        internal_standard VARCHAR(100),
        internal_status VARCHAR(20) DEFAULT 'pending_review',
        part_spec_name VARCHAR(200),
        part_drawing_path VARCHAR(500),
        sub_supplier_id VARCHAR(50),
        sds_path VARCHAR(500),
        tds_path VARCHAR(500),
        ai_verification_status VARCHAR(20) DEFAULT 'unverified',
        ai_verification_date DATETIME,
        ai_verification_notes TEXT,
        visibility VARCHAR(20) DEFAULT 'internal',
        published_to_supplier DATETIME,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Substance Breakdown table
    """CREATE TABLE IF NOT EXISTS substance_breakdown (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_id VARCHAR(50) NOT NULL,
        cas_number VARCHAR(50) NOT NULL,
        substance_name VARCHAR(200) NOT NULL,
        concentration_min FLOAT,
        concentration_max FLOAT,
        concentration_typical FLOAT,
        is_impurity BOOLEAN DEFAULT 0,
        source VARCHAR(30),
        reach_status VARCHAR(20),
        svhc BOOLEAN DEFAULT 0,
        reach_annex_xvii_restricted BOOLEAN DEFAULT 0,
        toy_safety_compliant BOOLEAN,
        migration_limit_mg_kg FLOAT,
        internal_limit_mg_kg FLOAT,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Material Documents table
    """CREATE TABLE IF NOT EXISTS material_documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_id VARCHAR(50) NOT NULL,
        document_type VARCHAR(30) NOT NULL,
        file_name VARCHAR(500) NOT NULL,
        file_path VARCHAR(500) NOT NULL,
        file_data BLOB,
        file_size INTEGER,
        mime_type VARCHAR(100),
        uploaded_by VARCHAR(100),
        ai_extracted BOOLEAN DEFAULT 0,
        ai_extraction_date DATETIME,
        version VARCHAR(20),
        valid_until DATE,
        visibility VARCHAR(20) DEFAULT 'internal',
        supplier_accessible BOOLEAN DEFAULT 0,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Document Versions table
    """CREATE TABLE IF NOT EXISTS document_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_document_id INTEGER NOT NULL,
        version VARCHAR(20) NOT NULL,
        file_path VARCHAR(500) NOT NULL,
        file_size INTEGER,
        uploaded_by VARCHAR(100),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        is_current BOOLEAN DEFAULT 1,
        notes TEXT,
        FOREIGN KEY (material_document_id) REFERENCES material_documents(id)
    )""",

    # Compliance Checks table
    """CREATE TABLE IF NOT EXISTS compliance_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_id VARCHAR(50) NOT NULL,
        cas_number VARCHAR(50),
        regulation VARCHAR(30) NOT NULL,
        check_type VARCHAR(50) NOT NULL,
        result VARCHAR(20) NOT NULL,
        limit_value FLOAT,
        measured_value FLOAT,
        unit VARCHAR(20),
        details TEXT,
        source VARCHAR(20),
        reference VARCHAR(200),
        checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # BOM Records table
    """CREATE TABLE IF NOT EXISTS bom_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bom_id VARCHAR(50) NOT NULL,
        sku VARCHAR(50) NOT NULL,
        product_name VARCHAR(200),
        version VARCHAR(20),
        material_id VARCHAR(50) NOT NULL,
        quantity FLOAT,
        unit VARCHAR(20),
        component_role VARCHAR(50),
        is_sub_supplier BOOLEAN DEFAULT 0,
        supplier_visible BOOLEAN DEFAULT 1,
        source_file VARCHAR(500),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Risk Alerts table
    """CREATE TABLE IF NOT EXISTS risk_alerts (
        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_id VARCHAR(50),
        cas_number VARCHAR(50),
        sku VARCHAR(50),
        bom_id VARCHAR(50),
        alert_type VARCHAR(50),
        severity VARCHAR(20),
        description TEXT,
        regulation_reference VARCHAR(200),
        resolved BOOLEAN DEFAULT 0,
        resolved_by VARCHAR(100),
        resolved_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Test History table
    """CREATE TABLE IF NOT EXISTS test_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_id VARCHAR(50),
        report_number VARCHAR(100),
        report_date DATE,
        lab_name VARCHAR(200),
        test_standard VARCHAR(100),
        test_type VARCHAR(50),
        result VARCHAR(20),
        measured_value FLOAT,
        unit VARCHAR(20),
        limit_value FLOAT,
        sku VARCHAR(50),
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Share Permissions table
    """CREATE TABLE IF NOT EXISTS share_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_id VARCHAR(50),
        supplier_id VARCHAR(50),
        granted_by VARCHAR(100),
        granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        expires_at DATETIME,
        access_level VARCHAR(20) DEFAULT 'read'
    )""",

    # Visibility Settings table
    """CREATE TABLE IF NOT EXISTS visibility_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setting_key VARCHAR(100) UNIQUE NOT NULL,
        setting_value VARCHAR(20) DEFAULT 'internal',
        updated_by VARCHAR(100),
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Product Comparability table
    """CREATE TABLE IF NOT EXISTS product_comparability (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_sku VARCHAR(50) NOT NULL,
        material_id VARCHAR(50) NOT NULL,
        cas_number VARCHAR(50) NOT NULL,
        substance_name VARCHAR(200) NOT NULL,
        concentration_min FLOAT,
        concentration_max FLOAT,
        concentration_typical FLOAT,
        comparison_group VARCHAR(50),
        source VARCHAR(30),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Substance Tracking table
    """CREATE TABLE IF NOT EXISTS substance_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        material_id VARCHAR(50),
        product_sku VARCHAR(50) NOT NULL,
        bom_record_id INTEGER,
        cas_number VARCHAR(50) NOT NULL,
        substance_name VARCHAR(200) NOT NULL,
        concentration_min FLOAT,
        concentration_max FLOAT,
        concentration_typical FLOAT,
        unit VARCHAR(20),
        trace_id VARCHAR(50),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # Safety Assessments table
    """CREATE TABLE IF NOT EXISTS safety_assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_sku VARCHAR(50) NOT NULL,
        assessment_name VARCHAR(200) NOT NULL,
        version VARCHAR(20) DEFAULT 'v1.0',
        status VARCHAR(20) DEFAULT 'draft',
        created_by VARCHAR(100),
        reviewed_by VARCHAR(100),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        reviewed_at DATETIME,
        approval_date DATETIME,
        notes TEXT
    )""",

    # Assessment Checklist table
    """CREATE TABLE IF NOT EXISTS assessment_checklist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id INTEGER NOT NULL,
        checklist_item VARCHAR(200) NOT NULL,
        category VARCHAR(50),
        required BOOLEAN DEFAULT 1,
        is_complete BOOLEAN DEFAULT 0,
        evidence_document_id INTEGER,
        checked_by VARCHAR(100),
        checked_at DATETIME,
        notes TEXT,
        FOREIGN KEY (assessment_id) REFERENCES safety_assessments(id)
    )""",

    # Assessment Results table
    """CREATE TABLE IF NOT EXISTS assessment_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id INTEGER NOT NULL,
        cas_number VARCHAR(50),
        substance_name VARCHAR(200),
        test_required VARCHAR(50),
        check_type VARCHAR(50),
        result VARCHAR(20),
        measured_value FLOAT,
        limit_value FLOAT,
        unit VARCHAR(20),
        details TEXT,
        reference VARCHAR(200),
        FOREIGN KEY (assessment_id) REFERENCES safety_assessments(id)
    )""",

    # ECHA / REACh Chemicals table
    """CREATE TABLE IF NOT EXISTS echa_chemicals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_no VARCHAR(100),
        name VARCHAR(200) NOT NULL,
        ec_number VARCHAR(50) NOT NULL,
        cas_number VARCHAR(50) NOT NULL,
        reach_status VARCHAR(50),
        reach_listing VARCHAR(200),
        gh_code VARCHAR(100),
        info_link VARCHAR(500),
        source_origin VARCHAR(100),
        source_reference VARCHAR(500),
        verification_method VARCHAR(50) DEFAULT 'AI Analysis',
        verified_at DATETIME,
        category VARCHAR(50) DEFAULT 'Substance',
        added_by VARCHAR(100),
        added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        history TEXT
    )""",

    # ECHA / REACh Compliance Checks table
    """CREATE TABLE IF NOT EXISTS echa_compliance_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chemical_id INTEGER NOT NULL,
        regulation VARCHAR(50) NOT NULL,
        check_type VARCHAR(100) NOT NULL,
        result VARCHAR(20) NOT NULL,
        limit_value FLOAT,
        measured_value FLOAT,
        unit VARCHAR(20),
        details TEXT,
        checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chemical_id) REFERENCES echa_chemicals(id)
    )""",

    # SVHC Substances table
    """CREATE TABLE IF NOT EXISTS svhc_substances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        substance_name VARCHAR(200) NOT NULL,
        description TEXT,
        ec_no VARCHAR(50) NOT NULL,
        cas_no VARCHAR(50) NOT NULL,
        reason_inclusion TEXT,
        date_inclusion DATE,
        decision VARCHAR(50),
        iuclid_dataset VARCHAR(100),
        support_document VARCHAR(200),
        response_comments TEXT,
        remarks TEXT,
        upload_type VARCHAR(50),
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
        uploaded_by VARCHAR(100),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""",

    # SVHC Compliance Checks table
    """CREATE TABLE IF NOT EXISTS svhc_compliance_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        svhc_id INTEGER NOT NULL,
        regulation VARCHAR(50) NOT NULL,
        check_type VARCHAR(100) NOT NULL,
        result VARCHAR(20) NOT NULL,
        limit_value FLOAT,
        measured_value FLOAT,
        unit VARCHAR(20),
        details TEXT,
        checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (svhc_id) REFERENCES svhc_substances(id)
    )""",

    # ==================================================================
    # Indexes
    # ==================================================================

    # Management Portal Indexes
    """CREATE INDEX IF NOT EXISTS idx_internal_users_username ON internal_users(username)""",
    """CREATE INDEX IF NOT EXISTS idx_internal_users_email ON internal_users(email)""",
    """CREATE INDEX IF NOT EXISTS idx_internal_users_invitation ON internal_users(invitation_code)""",
    """CREATE INDEX IF NOT EXISTS idx_internal_users_department ON internal_users(department_id)""",
    """CREATE INDEX IF NOT EXISTS idx_internal_users_supervisor ON internal_users(supervisor_id)""",
    """CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC)""",

    # Pipeline Indexes
    """CREATE INDEX IF NOT EXISTS idx_materials_supplier ON material_library(supplier_id)""",
    """CREATE INDEX IF NOT EXISTS idx_materials_cas ON material_library(cas_number)""",
    """CREATE INDEX IF NOT EXISTS idx_substance_material ON substance_breakdown(material_id)""",
    """CREATE INDEX IF NOT EXISTS idx_compliance_material ON compliance_checks(material_id)""",
    """CREATE INDEX IF NOT EXISTS idx_bom_records_material ON bom_records(material_id)""",
    """CREATE INDEX IF NOT EXISTS idx_risk_alerts_material ON risk_alerts(material_id)""",
    """CREATE INDEX IF NOT EXISTS idx_test_history_material ON test_history(material_id)""",

    # New Feature Indexes
    """CREATE INDEX IF NOT EXISTS idx_document_versions_doc ON document_versions(material_document_id)""",
    """CREATE INDEX IF NOT EXISTS idx_document_versions_version ON document_versions(version)""",
    """CREATE INDEX IF NOT EXISTS idx_share_permissions_material ON share_permissions(material_id)""",
    """CREATE INDEX IF NOT EXISTS idx_product_comp_sku ON product_comparability(product_sku)""",
    """CREATE INDEX IF NOT EXISTS idx_product_comp_cas ON product_comparability(cas_number)""",
    """CREATE INDEX IF NOT EXISTS idx_product_comp_group ON product_comparability(comparison_group)""",
    """CREATE INDEX IF NOT EXISTS idx_substance_tracking_sku ON substance_tracking(product_sku)""",
    """CREATE INDEX IF NOT EXISTS idx_substance_tracking_cas ON substance_tracking(cas_number)""",
    """CREATE INDEX IF NOT EXISTS idx_substance_tracking_trace ON substance_tracking(trace_id)""",
    """CREATE INDEX IF NOT EXISTS idx_safety_assessment_sku ON safety_assessments(product_sku)""",
    """CREATE INDEX IF NOT EXISTS idx_safety_assessment_status ON safety_assessments(status)""",
"""CREATE INDEX IF NOT EXISTS idx_assessment_checklist_assessment ON assessment_checklist(assessment_id)""",
    """CREATE INDEX IF NOT EXISTS idx_assessment_result_assessment ON assessment_results(assessment_id)""",

    # ==================================================================
    # Registration Module Tables (Create)
    # ==================================================================
    """CREATE TABLE IF NOT EXISTS supplier_registrations (
        id SERIAL PRIMARY KEY,
        supplier_id INTEGER NOT NULL,
        registration_status VARCHAR(20) DEFAULT 'draft',
        name_en VARCHAR(255) NOT NULL,
        name_cn VARCHAR(255),
        material_origin VARCHAR(100),
        sales_contact_name VARCHAR(255),
        sales_contact_email VARCHAR(255),
        sales_contact_phone VARCHAR(50),
        qm_contact_name VARCHAR(255),
        qm_contact_email VARCHAR(255),
        qm_contact_phone VARCHAR(50),
        facility_address TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        submitted_at TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS registered_manufactures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        registration_id INTEGER NOT NULL,
        manufacture_name VARCHAR(255) NOT NULL,
        supply_type VARCHAR(30) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (registration_id) REFERENCES supplier_registrations(id)
    )""",
    """CREATE TABLE IF NOT EXISTS material_registrations (
        id SERIAL PRIMARY KEY,
        registration_id INTEGER NOT NULL,
        commercial_material_name VARCHAR(255) NOT NULL,
        internal_factory_material_code VARCHAR(100) NOT NULL,
        supplier_material_code VARCHAR(100) NOT NULL,
        manufacture_id INTEGER DEFAULT 1,
        supply_type VARCHAR(30) DEFAULT 'tier2',
        is_food_contact BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (registration_id) REFERENCES supplier_registrations(id),
        FOREIGN KEY (manufacture_id) REFERENCES registered_manufactures(id)
    )""",
    """CREATE TABLE IF NOT EXISTS supplier_documents (
        id SERIAL PRIMARY KEY,
        registration_id INTEGER NOT NULL,
        material_id INTEGER NOT NULL,
        document_type VARCHAR(30) NOT NULL,
        file_path VARCHAR(500) NOT NULL,
        original_filename VARCHAR(255) NOT NULL,
        file_size_bytes INTEGER NOT NULL,
        sds_language VARCHAR(50),
        sds_issue_date DATE,
        sds_expiry_warning BOOLEAN DEFAULT FALSE,
        tds_physical_state VARCHAR(30),
        coa_test_date DATE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (registration_id) REFERENCES supplier_registrations(id),
        FOREIGN KEY (material_id) REFERENCES material_registrations(id)
    )""",

    # ==================================================================
    # Registration Module Migration Fixes (Alter existing columns)
    # ==================================================================
    """ALTER TABLE supplier_registrations ALTER COLUMN material_origin TYPE VARCHAR(100)""",
    """ALTER TABLE supplier_registrations ALTER COLUMN sales_contact_name DROP NOT NULL""",
    """ALTER TABLE supplier_registrations ALTER COLUMN sales_contact_email DROP NOT NULL""",
    """ALTER TABLE supplier_registrations ALTER COLUMN sales_contact_phone DROP NOT NULL""",

    # Registration Indexes
    """CREATE INDEX IF NOT EXISTS idx_supplier_reg_supplier ON supplier_registrations(supplier_id)""",
    """CREATE INDEX IF NOT EXISTS idx_supplier_reg_status ON supplier_registrations(registration_status)""",
    """CREATE INDEX IF NOT EXISTS idx_material_reg_registration ON material_registrations(registration_id)""",
    """CREATE INDEX IF NOT EXISTS idx_material_reg_supplier_code ON material_registrations(registration_id, supplier_material_code)""",
    """CREATE INDEX IF NOT EXISTS idx_supplier_doc_registration ON supplier_documents(registration_id)""",
    """CREATE INDEX IF NOT EXISTS idx_supplier_doc_material ON supplier_documents(material_id)""",
    """CREATE INDEX IF NOT EXISTS idx_supplier_doc_type ON supplier_documents(document_type)""",
    """CREATE INDEX IF NOT EXISTS idx_mfg_registration ON registered_manufactures(registration_id)""",
    """CREATE INDEX IF NOT EXISTS idx_mfg_name_reg ON registered_manufactures(registration_id, manufacture_name)""",
    """CREATE INDEX IF NOT EXISTS idx_material_reg_mfg ON material_registrations(manufacture_id)""",

    # ==================================================================
    # Registration Module Migration Fixes (Add/alter columns)
    # ==================================================================
    # PostgreSQL-style add column (skip on SQLite)
    """ALTER TABLE material_registrations ADD COLUMN IF NOT EXISTS manufacture_id INTEGER DEFAULT 1""",
    """ALTER TABLE material_registrations ADD COLUMN IF NOT EXISTS supply_type VARCHAR(30) DEFAULT 'tier2'""",
    # SQLite-style add column (executed via try/except)
    """ALTER TABLE material_registrations ADD COLUMN manufacture_id INTEGER DEFAULT 1""",
    """ALTER TABLE material_registrations ADD COLUMN supply_type VARCHAR(30) DEFAULT 'tier2'""",
    # Registered Manufacture contact columns
    """ALTER TABLE registered_manufactures ADD COLUMN IF NOT EXISTS sales_contact_name VARCHAR(100)""",
    """ALTER TABLE registered_manufactures ADD COLUMN IF NOT EXISTS sales_contact_email VARCHAR(200)""",
    """ALTER TABLE registered_manufactures ADD COLUMN IF NOT EXISTS sales_contact_phone VARCHAR(50)""",
    """ALTER TABLE registered_manufactures ADD COLUMN IF NOT EXISTS tech_contact_name VARCHAR(100)""",
    """ALTER TABLE registered_manufactures ADD COLUMN IF NOT EXISTS tech_contact_email VARCHAR(200)""",
    """ALTER TABLE registered_manufactures ADD COLUMN IF NOT EXISTS tech_contact_phone VARCHAR(50)""",
    """ALTER TABLE registered_manufactures ADD COLUMN sales_contact_name VARCHAR(100)""",
    """ALTER TABLE registered_manufactures ADD COLUMN sales_contact_email VARCHAR(200)""",
    """ALTER TABLE registered_manufactures ADD COLUMN sales_contact_phone VARCHAR(50)""",
    """ALTER TABLE registered_manufactures ADD COLUMN tech_contact_name VARCHAR(100)""",
    """ALTER TABLE registered_manufactures ADD COLUMN tech_contact_email VARCHAR(200)""",
    """ALTER TABLE registered_manufactures ADD COLUMN tech_contact_phone VARCHAR(50)""",
]

print("=" * 60)
print("Running database migrations...")
print("=" * 60)

try:
    with get_engine().connect() as conn:
        for i, sql in enumerate(migrations, 1):
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"  [{i}/{len(migrations)}] ✓ Migration {i} completed")
            except Exception as e:
                error_msg = str(e)[:80]
                print(f"  [{i}/{len(migrations)}] ⚠ Migration {i} skipped or already exists: {error_msg}")

    print("\n" + "=" * 60)
    print("✅ Database migrations completed!")
    print("=" * 60)

except Exception as e:
    print(f"\n❌ Migration failed: {e}")
    raise
