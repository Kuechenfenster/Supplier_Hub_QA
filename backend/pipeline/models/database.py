"""
Compliance & Material Intelligence Pipeline — Database Schema
PostgreSQL Master Material Library

3-Tier Hierarchy: Manufacturer -> Supplier -> Material
Substance Breakdown + Compliance Checking
"""
import logging
from datetime import datetime, timezone
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text, Boolean,
    DateTime, ForeignKey, Date, LargeBinary, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

from pipeline.config import DATABASE_URL, DB_DIR

logger = logging.getLogger(__name__)
Base = declarative_base()


def utcnow():
    return datetime.now(timezone.utc)


# ======================================================================
# 1. Manufacturers — Raw Material / Substance Makers
# ======================================================================
class Manufacturer(Base):
    __tablename__ = "manufacturers"

    manufacturer_id = Column(String(50), primary_key=True)
    manufacturer_name = Column(String(200), nullable=False)
    manufacturer_code = Column(String(100))
    country = Column(String(100))
    website = Column(String(500))
    contact_email = Column(String(200))
    contact_phone = Column(String(50))
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    suppliers = relationship("Supplier", back_populates="manufacturer")


# ======================================================================
# 2. Suppliers — Our Material Suppliers (links to manufacturer)
# ======================================================================
class Supplier(Base):
    __tablename__ = "pipeline_suppliers"

    supplier_id = Column(String(50), primary_key=True)
    supplier_name = Column(String(200), nullable=False)
    supplier_material_id = Column(String(100))
    manufacturer_id = Column(String(50), ForeignKey("manufacturers.manufacturer_id"), index=True)
    contact_email = Column(String(200))
    contact_phone = Column(String(50))
    address = Column(Text)
    status = Column(String(20), default="active")
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    manufacturer = relationship("Manufacturer", back_populates="suppliers")
    materials = relationship("MaterialLibrary", back_populates="supplier")


# ======================================================================
# 3. Material_Library — Our Internal Material DNA
# ======================================================================
class MaterialLibrary(Base):
    __tablename__ = "material_library"

    material_id = Column(String(50), primary_key=True)
    material_name = Column(String(200), nullable=False)
    component_name = Column(String(200), nullable=False)
    supplier_id = Column(String(50), ForeignKey("pipeline_suppliers.supplier_id"), nullable=False, index=True)
    material_type = Column(String(20), default="mixture")  # substance / mixture / article
    category = Column(String(50))               # pigment / resin / solvent / packaging / additive
    physical_state = Column(String(20))         # solid / liquid / gas / paste
    cas_number = Column(String(50))
    ghs_classification = Column(String(200))
    en71_3_category = Column(String(10))        # I / II / III
    migration_limit_mg_kg = Column(Float)
    reach_regulation = Column(String(20))       # registered / pre-registered / exempt / svhc
    reach_svhc_candidate = Column(Boolean, default=False)
    reach_annex_xvii = Column(Boolean, default=False)
    toy_directive_compliant = Column(Boolean)
    internal_standard = Column(String(100))
    internal_status = Column(String(20), default="pending_review")  # approved / conditional / rejected / pending_review
    part_spec_name = Column(String(200))                 # Part specification name (required: manufacturer material name)
    part_drawing_path = Column(String(500))              # Path to part drawing attachment
    sub_supplier_id = Column(String(50))                  # Sub-supplier reference if bought through sub-supplier
    sds_path = Column(String(500))
    tds_path = Column(String(500))
    ai_verification_status = Column(String(20), default="unverified")  # unverified / verified / flagged / failed
    ai_verification_date = Column(DateTime)
    ai_verification_notes = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    supplier = relationship("Supplier", back_populates="materials")
    substance_breakdown = relationship("SubstanceBreakdown", back_populates="material", cascade="all, delete-orphan")
    documents = relationship("MaterialDocument", back_populates="material", cascade="all, delete-orphan")
    compliance_checks = relationship("ComplianceCheck", back_populates="material", cascade="all, delete-orphan")
    bom_records = relationship("BOMRecord", back_populates="material")
    risk_alerts = relationship("RiskAlert", back_populates="material")
    substance_tracking = relationship("SubstanceTracking", back_populates="material", cascade="all, delete-orphan")
    share_permissions = relationship("SharePermission", back_populates="material", cascade="all, delete-orphan")


# ======================================================================
# 4. Substance_Breakdown — CAS-Level Decomposition
# ======================================================================
class SubstanceBreakdown(Base):
    __tablename__ = "substance_breakdown"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(String(50), ForeignKey("material_library.material_id"), nullable=False, index=True)
    cas_number = Column(String(50), nullable=False, index=True)
    substance_name = Column(String(200), nullable=False)
    concentration_min = Column(Float)
    concentration_max = Column(Float)
    concentration_typical = Column(Float)
    is_impurity = Column(Boolean, default=False)
    source = Column(String(30))                # sds / tds / supplier_declaration / ai_extracted
    reach_status = Column(String(20))
    svhc = Column(Boolean, default=False)
    reach_annex_xvii_restricted = Column(Boolean, default=False)
    toy_safety_compliant = Column(Boolean)
    migration_limit_mg_kg = Column(Float)
    internal_limit_mg_kg = Column(Float)
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    material = relationship("MaterialLibrary", back_populates="substance_breakdown")


# ======================================================================
# 5. Material_Documents — Uploaded Files per Material
# ======================================================================
class MaterialDocument(Base):
    __tablename__ = "material_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(String(50), ForeignKey("material_library.material_id"), nullable=False, index=True)
    document_type = Column(String(30), nullable=False)  # sds / tds / coa / declaration / test_report / other
    file_name = Column(String(500), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_data = Column(LargeBinary)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    uploaded_by = Column(String(100))
    ai_extracted = Column(Boolean, default=False)
    ai_extraction_date = Column(DateTime)
    version = Column(String(20))
    valid_until = Column(Date)
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    material = relationship("MaterialLibrary", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")


# ======================================================================
# 6. Compliance_Checks — REACh / Toy Directive / Internal Results
# ======================================================================
class ComplianceCheck(Base):
    __tablename__ = "compliance_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(String(50), ForeignKey("material_library.material_id"), nullable=False, index=True)
    cas_number = Column(String(50), index=True)
    regulation = Column(String(30), nullable=False)    # reach / eu_toy_directive / en71_3 / internal
    check_type = Column(String(50), nullable=False)    # svhc_screening / annex_xvii / migration_test / substance_restrict / internal_standard
    result = Column(String(20), nullable=False)         # pass / fail / review / exempt
    limit_value = Column(Float)
    measured_value = Column(Float)
    unit = Column(String(20))
    details = Column(Text)
    source = Column(String(20))                        # ai_check / manual / test_report
    reference = Column(String(200))                     # e.g. REACh Article 57
    checked_at = Column(DateTime, default=utcnow)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    material = relationship("MaterialLibrary", back_populates="compliance_checks")


# ======================================================================
# 7. BOM_Records — Standardized BOM Entries
# ======================================================================
class BOMRecord(Base):
    __tablename__ = "bom_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bom_id = Column(String(50), nullable=False, index=True)
    sku = Column(String(50), nullable=False, index=True)
    product_name = Column(String(200))
    version = Column(String(20))
    material_id = Column(String(50), ForeignKey("material_library.material_id"), nullable=False, index=True)
    quantity = Column(Float)
    unit = Column(String(20))
    component_role = Column(String(50))
    is_sub_supplier = Column(Boolean, default=False)     # Tick: item bought from sub-supplier
    source_file = Column(String(500))
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    material = relationship("MaterialLibrary", back_populates="bom_records")


# ======================================================================
# 8. Risk_Alerts — Flagged Compliance Issues
# ======================================================================
class RiskAlert(Base):
    __tablename__ = "risk_alerts"

    alert_id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(String(50), ForeignKey("material_library.material_id"), index=True)
    cas_number = Column(String(50), index=True)
    sku = Column(String(50), index=True)
    bom_id = Column(String(50), index=True)
    alert_type = Column(String(50))            # svhc_found / reach_violation / toy_directive_fail / no_sds / expired_test / internal_standard_fail
    severity = Column(String(20))              # high / medium / low
    description = Column(Text)
    regulation_reference = Column(String(200)) # e.g. REACh Article 57
    resolved = Column(Boolean, default=False)
    resolved_by = Column(String(100))
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    material = relationship("MaterialLibrary", back_populates="risk_alerts")


# ======================================================================
# 9. Test_History — Lab Report Test Results
# ======================================================================
class TestHistory(Base):
    __tablename__ = "test_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(String(50), index=True)
    report_number = Column(String(100))
    report_date = Column(Date)
    lab_name = Column(String(200))
    test_standard = Column(String(100))
    test_type = Column(String(50))
    result = Column(String(20))
    measured_value = Column(Float)
    unit = Column(String(20))
    limit_value = Column(Float)
    sku = Column(String(50))
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow)


# ======================================================================
# 10. Document_Versions — Full History for Document Versioning
# ======================================================================
class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_document_id = Column(Integer, ForeignKey("material_documents.id"), index=True)
    version = Column(String(20), nullable=False)  # v1.0, v1.1, etc.
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    uploaded_by = Column(String(100))
    created_at = Column(DateTime, default=utcnow)
    is_current = Column(Boolean, default=True)
    notes = Column(Text)

    # Relationships
    document = relationship("MaterialDocument", back_populates="versions")


# ======================================================================
# 11. Share_Permissions — Material Access Control for Suppliers
# ======================================================================
class SharePermission(Base):
    __tablename__ = "share_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(String(50), ForeignKey("material_library.material_id"), index=True)
    supplier_id = Column(String(50), index=True)
    granted_by = Column(String(100))
    granted_at = Column(DateTime, default=utcnow)
    expires_at = Column(DateTime)
    access_level = Column(String(20), default="read")  # read, write, admin

    # Relationships
    material = relationship("MaterialLibrary", back_populates="share_permissions")


# ======================================================================
# 12. Product_Comparability — Compare Products by CAS Number
# ======================================================================
class ProductComparability(Base):
    __tablename__ = "product_comparability"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_sku = Column(String(50), nullable=False, index=True)
    material_id = Column(String(50), ForeignKey("material_library.material_id"), index=True)
    cas_number = Column(String(50), nullable=False, index=True)
    substance_name = Column(String(200), nullable=False)
    concentration_min = Column(Float)
    concentration_max = Column(Float)
    concentration_typical = Column(Float)
    comparison_group = Column(String(50), index=True)
    source = Column(String(30))  # bom_upload / lab_report / manual
    created_at = Column(DateTime, default=utcnow)


# ======================================================================
# 12. Substance_Tracking — CAS-Level Tracking Per Product SKU
# ======================================================================
class SubstanceTracking(Base):
    __tablename__ = "substance_tracking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    material_id = Column(String(50), ForeignKey("material_library.material_id"), index=True)
    product_sku = Column(String(50), nullable=False, index=True)
    bom_record_id = Column(Integer, ForeignKey("bom_records.id"))
    cas_number = Column(String(50), nullable=False, index=True)
    substance_name = Column(String(200), nullable=False)
    concentration_min = Column(Float)
    concentration_max = Column(Float)
    concentration_typical = Column(Float)
    unit = Column(String(20))
    trace_id = Column(String(50), index=True)  # Track substance flow through BOMs
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    material = relationship("MaterialLibrary", back_populates="substance_tracking")
    bom_record = relationship("BOMRecord", backref="substance_tracking")


# ======================================================================
# 13. Safety_Assessments — Product Safety Assessment Workflow
# ======================================================================
class SafetyAssessment(Base):
    __tablename__ = "safety_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_sku = Column(String(50), nullable=False, index=True)
    assessment_name = Column(String(200), nullable=False)
    version = Column(String(20), default="v1.0")
    status = Column(String(20), default="draft")  # draft, under_review, approved, rejected, archived
    created_by = Column(String(100))
    reviewed_by = Column(String(100))
    created_at = Column(DateTime, default=utcnow)
    reviewed_at = Column(DateTime)
    approval_date = Column(DateTime)
    notes = Column(Text)

    # Relationships
    checklist = relationship("AssessmentChecklist", back_populates="assessment", cascade="all, delete-orphan")
    results = relationship("AssessmentResult", back_populates="assessment", cascade="all, delete-orphan")


# ======================================================================
# 14. Assessment_Checklist — Safety Assessment Checklist Items
# ======================================================================
class AssessmentChecklist(Base):
    __tablename__ = "assessment_checklist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("safety_assessments.id"), index=True)
    checklist_item = Column(String(200), nullable=False)  # e.g., "Has SDS been reviewed?"
    category = Column(String(50))  # documentation, testing, regulatory
    required = Column(Boolean, default=True)
    is_complete = Column(Boolean, default=False)
    evidence_document_id = Column(Integer, ForeignKey("material_documents.id"))
    checked_by = Column(String(100))
    checked_at = Column(DateTime)
    notes = Column(Text)

    # Relationships
    assessment = relationship("SafetyAssessment", back_populates="checklist")


# ======================================================================
# 15. Assessment_Results — Test Results per Assessment
# ======================================================================
class AssessmentResult(Base):
    __tablename__ = "assessment_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(Integer, ForeignKey("safety_assessments.id"), index=True)
    cas_number = Column(String(50), index=True)
    substance_name = Column(String(200))
    test_required = Column(String(50))  # EN 71-3, REACh, GHS, internal
    check_type = Column(String(50))  # migration_test, svhc_screening, etc.
    result = Column(String(20))  # pass, fail, required, exempt, n/a
    measured_value = Column(Float)
    limit_value = Column(Float)
    unit = Column(String(20))
    details = Column(Text)
    reference = Column(String(200))  # e.g., REACh Article 57

    # Relationships
    assessment = relationship("SafetyAssessment", back_populates="results")


# ======================================================================
# 16. ECHA_Substances — ECHA / REACh Chemical Database
# ======================================================================
class ECHAChemical(Base):
    __tablename__ = "echa_chemicals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entry_no = Column(String(100), nullable=True, index=True)  # Unique identifier from source (ECHA registration no, CAS, etc.)
    name = Column(String(200), nullable=False, index=True)
    ec_number = Column(String(50), nullable=False, index=True)
    cas_number = Column(String(50), nullable=False, index=True)
    reach_status = Column(String(50))  # registered, pre-registered, exempt, restricted, svhc
    reach_listing = Column(String(200))  # e.g., Article 57 SVHC, Annex XIV, Annex XVII
    gh_code = Column(String(100))  # GHS classification code
    info_link = Column(String(500))  # Link to ECHA info page
    source_origin = Column(String(100))  # ECHA Website, Supplier SDS, Lab Report, etc.
    source_reference = Column(String(500))  # Document ID, Supplier Name, etc.
    verification_method = Column(String(50), default="AI Analysis")
    verified_at = Column(DateTime)
    category = Column(String(50), default="Substance")  # Substance, Mixture, Product
    added_by = Column(String(100))
    added_at = Column(DateTime, default=utcnow)
    history = Column(Text)  # JSON string of history changes

    # Relationships
    compliance_checks = relationship("ECHAComplianceCheck", back_populates="chemical", cascade="all, delete-orphan")


class ECHAComplianceCheck(Base):
    __tablename__ = "echa_compliance_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chemical_id = Column(Integer, ForeignKey("echa_chemicals.id"), index=True)
    regulation = Column(String(50), nullable=False)  # REACh, CLP, Toy Directive
    check_type = Column(String(100), nullable=False)
    result = Column(String(20), nullable=False)  # pass, fail, review
    limit_value = Column(Float)
    measured_value = Column(Float)
    unit = Column(String(20))
    details = Column(Text)
    checked_at = Column(DateTime, default=utcnow)

    # Relationships
    chemical = relationship("ECHAChemical", back_populates="compliance_checks")


# ======================================================================
# 17. SVHC_Substance — SVHC Database
# ======================================================================
class SVHCSubstance(Base):
    __tablename__ = "svhc_substances"

    id = Column(Integer, primary_key=True, autoincrement=True)
    substance_name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    ec_no = Column(String(50), nullable=False, index=True)
    cas_no = Column(String(50), nullable=False, index=True)
    reason_inclusion = Column(Text)  # Reason for inclusion in SVHC list
    date_inclusion = Column(Date)  # Date of inclusion in SVHC list
    decision = Column(String(50))  # Decision type: included, reviewed, removed, updated
    iuclid_dataset = Column(String(100))  # IUCLID dataset ID
    support_document = Column(String(200))  # Supporting document reference
    response_comments = Column(Text)  # Response to comments during review
    remarks = Column(Text)  # Additional remarks
    upload_type = Column(String(50))  # candidate_list, authorization_list, sunset_list, other
    last_updated = Column(DateTime, default=utcnow)
    uploaded_by = Column(String(100))
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    compliance_checks = relationship("SVHCComplianceCheck", back_populates="svhc", cascade="all, delete-orphan")


class SVHCComplianceCheck(Base):
    __tablename__ = "svhc_compliance_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    svhc_id = Column(Integer, ForeignKey("svhc_substances.id"), index=True)
    regulation = Column(String(50), nullable=False)  # REACh, CLP
    check_type = Column(String(100), nullable=False)
    result = Column(String(20), nullable=False)  # pass, fail, review
    limit_value = Column(Float)
    measured_value = Column(Float)
    unit = Column(String(20))
    details = Column(Text)
    checked_at = Column(DateTime, default=utcnow)

    # Relationships
    svhc = relationship("SVHCSubstance", back_populates="compliance_checks")


# ======================================================================
# Database Engine & Session Management
# ======================================================================
engine = None
SessionLocal = None


def init_engine(db_url: str = None):
    global engine, SessionLocal
    url = db_url or str(DATABASE_URL)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if "sqlite" in url else {}
    engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info(f"Database engine initialized: {url.split('@')[-1] if '@' in url else url}")
    return engine


def get_session():
    if SessionLocal is None:
        init_engine()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db(db_url: str = None):
    if engine is None or SessionLocal is None:
        init_engine(db_url)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")


def get_db():
    if SessionLocal is None:
        init_engine()
    return SessionLocal()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database initialized successfully")
    print(f"   URL: {DATABASE_URL}")
    print(f"   Tables: {[t.name for t in Base.metadata.sorted_tables]}")
