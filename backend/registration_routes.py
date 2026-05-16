import os
import json
import uuid
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, validator
from sqlalchemy.orm import Session

from models import (
    SessionLocal, get_db, Supplier, SupplierRegistration,
    MaterialRegistration, SupplierDocument
)
from auth_helpers import get_current_supplier

router = APIRouter(prefix="/api/registration", tags=["Supplier Registration"])

BASE_DIR = os.path.dirname(__file__)
UPLOAD_BASE = os.getenv("REGISTRATION_UPLOAD_DIR", os.path.join(BASE_DIR, "data", "registrations"))

os.makedirs(UPLOAD_BASE, exist_ok=True)

ALLOWED_CONTENT_TYPES = {"application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ISO_COUNTRIES = {
    "AF", "AL", "DZ", "AD", "AO", "AG", "AR", "AM", "AU", "AT", "AZ", "BS", "BH", "BD", "BB",
    "BY", "BE", "BZ", "BJ", "BT", "BO", "BA", "BW", "BR", "BN", "BG", "BF", "BI", "CV", "KH",
    "CM", "CA", "CF", "TD", "CL", "CN", "CO", "KM", "CG", "CR", "HR", "CU", "CY", "CZ", "DK",
    "DJ", "DM", "DO", "EC", "EG", "SV", "GQ", "ER", "EE", "SZ", "ET", "FJ", "FI", "FR", "GA",
    "GM", "GE", "DE", "GH", "GR", "GD", "GT", "GN", "GW", "GY", "HT", "HN", "HK", "HU", "IS",
    "IN", "ID", "IR", "IQ", "IE", "IL", "IT", "JM", "JP", "JO", "KZ", "KE", "KI", "KP", "KR",
    "KW", "KG", "LA", "LV", "LB", "LS", "LR", "LY", "LI", "LT", "LU", "MG", "MW", "MY", "MV",
    "ML", "MT", "MH", "MR", "MU", "MX", "FM", "MD", "MC", "MN", "ME", "MA", "MZ", "MM", "NA",
    "NR", "NP", "NL", "NZ", "NI", "NE", "NG", "MK", "NO", "OM", "PK", "PW", "PS", "PA", "PG",
    "PY", "PE", "PH", "PL", "PT", "QA", "RO", "RU", "RW", "KN", "LC", "VC", "WS", "SM", "ST",
    "SA", "SN", "RS", "SC", "SL", "SG", "SK", "SI", "SB", "SO", "ZA", "SS", "ES", "LK", "SD",
    "SR", "SE", "CH", "SY", "TW", "TJ", "TZ", "TH", "TL", "TG", "TO", "TT", "TN", "TR", "TM",
    "TV", "UG", "UA", "AE", "GB", "US", "UY", "UZ", "VU", "VA", "VE", "VN", "YE", "ZM", "ZW"
}

SDS_LANGUAGES = ["English", "German", "French", "Traditional Chinese", "Simplified Chinese", "Other"]
TDS_PHYSICAL_STATES = ["Liquid", "Powder", "Granules", "Pellets", "Solid"]


def validate_file(file: UploadFile):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail=f"File '{file.filename}' must be a PDF. Received: {file.content_type}")
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File '{file.filename}' exceeds 10 MB limit.")


def save_upload_file(upload: UploadFile, registration_id: int, doc_type: str) -> dict:
    ext = os.path.splitext(upload.filename or "document.pdf")[1] or ".pdf"
    safe_name = f"{registration_id}_{doc_type}_{uuid.uuid4().hex[:8]}{ext}"
    dest_dir = os.path.join(UPLOAD_BASE, str(registration_id))
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, safe_name)
    content = upload.file.read()
    with open(dest_path, "wb") as f:
        f.write(content)
    return {
        "file_path": dest_path,
        "original_filename": upload.filename or safe_name,
        "file_size_bytes": len(content),
    }


def check_sds_expiry(issue_date: date, today: Optional[date] = None) -> bool:
    ref = today or date.today()
    age_years = ref.year - issue_date.year - ((ref.month, ref.day) < (issue_date.month, issue_date.day))
    return age_years > 3


# ──────────────────────────── Pydantic Schemas ────────────────────────────

class ContactProfile(BaseModel):
    full_name: str
    email: str
    phone: str

    @validator("full_name")
    def name_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Contact name is required")
        return v.strip()

    @validator("email")
    def email_valid(cls, v):
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v.strip()

    @validator("phone")
    def phone_has_digits(cls, v):
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) < 7:
            raise ValueError("Phone number must contain at least 7 digits")
        return v.strip()


class SupplierProfileSchema(BaseModel):
    name_en: str
    name_cn: Optional[str] = None
    material_origin: str
    sales_contact: ContactProfile
    qm_contact: Optional[ContactProfile] = None
    facility_address: str

    @validator("name_en")
    def name_en_length(cls, v):
        if len(v.strip()) < 2 or len(v.strip()) > 255:
            raise ValueError("Supplier name (English) must be 2-255 characters")
        return v.strip()

    @validator("material_origin")
    def valid_iso_code(cls, v):
        if v.strip().upper() not in ISO_COUNTRIES:
            raise ValueError(f"Invalid ISO 2-letter country code: {v}")
        return v.strip().upper()

    @validator("facility_address")
    def address_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Facility address is required")
        return v.strip()


class MaterialIdentifierSchema(BaseModel):
    commercial_material_name: str
    internal_factory_material_code: str
    supplier_material_code: str
    is_food_contact: bool = False

    @validator("commercial_material_name")
    def commercial_name_required(cls, v):
        if not v or not v.strip():
            raise ValueError("Commercial material name is required")
        return v.strip()

    @validator("internal_factory_material_code")
    def internal_code_required(cls, v):
        if not v or not v.strip():
            raise ValueError("Internal factory material code is required")
        return v.strip()

    @validator("supplier_material_code")
    def supplier_code_required(cls, v):
        if not v or not v.strip():
            raise ValueError("Supplier material code is required")
        return v.strip()


# ──────────────────────────── Routes ────────────────────────────

@router.get("/countries")
async def list_countries():
    return sorted(ISO_COUNTRIES)


@router.get("/metadata/lookup")
async def lookup_metadata():
    return {
        "sds_languages": SDS_LANGUAGES,
        "physical_states": TDS_PHYSICAL_STATES,
        "countries": sorted(ISO_COUNTRIES),
    }


@router.get("/draft")
async def get_draft(
    supplier: Supplier = Depends(get_current_supplier),
    db: Session = Depends(get_db),
):
    reg = db.query(SupplierRegistration).filter(
        SupplierRegistration.supplier_id == supplier.id
    ).first()
    if not reg:
        return {"exists": False, "registration": None}

    materials_data = []
    for mat in reg.materials:
        docs_data = {}
        for d in mat.documents:
            docs_data[d.document_type] = {
                "id": d.id,
                "original_filename": d.original_filename,
                "file_size_bytes": d.file_size_bytes,
                "sds_language": d.sds_language,
                "sds_issue_date": d.sds_issue_date.isoformat() if d.sds_issue_date else None,
                "sds_expiry_warning": d.sds_expiry_warning,
                "tds_physical_state": d.tds_physical_state,
                "coa_test_date": d.coa_test_date.isoformat() if d.coa_test_date else None,
            }
        materials_data.append({
            "id": mat.id,
            "commercial_material_name": mat.commercial_material_name,
            "internal_factory_material_code": mat.internal_factory_material_code,
            "supplier_material_code": mat.supplier_material_code,
            "is_food_contact": mat.is_food_contact,
            "documents": docs_data,
        })

    return {
        "exists": True,
        "registration": {
            "id": reg.id,
            "status": reg.registration_status,
            "name_en": reg.name_en,
            "name_cn": reg.name_cn,
            "material_origin": reg.material_origin,
            "sales_contact": {
                "full_name": reg.sales_contact_name,
                "email": reg.sales_contact_email,
                "phone": reg.sales_contact_phone,
            },
            "qm_contact": {
                "full_name": reg.qm_contact_name,
                "email": reg.qm_contact_email,
                "phone": reg.qm_contact_phone,
            },
            "facility_address": reg.facility_address,
            "materials": materials_data,
            "created_at": reg.created_at.isoformat() if reg.created_at else None,
            "submitted_at": reg.submitted_at.isoformat() if reg.submitted_at else None,
        },
    }


@router.post("/step1-profile")
async def save_step1_profile(
    name_en: str = Form(..., min_length=2, max_length=255),
    name_cn: str = Form(""),
    material_origin: str = Form(..., min_length=2, max_length=2),
    sales_contact_name: str = Form(...),
    sales_contact_email: str = Form(...),
    sales_contact_phone: str = Form(...),
    qm_contact_name: str = Form(""),
    qm_contact_email: str = Form(""),
    qm_contact_phone: str = Form(""),
    facility_address: str = Form(...),
    supplier: Supplier = Depends(get_current_supplier),
    db: Session = Depends(get_db),
):
    profile = SupplierProfileSchema(
        name_en=name_en,
        name_cn=name_cn or None,
        material_origin=material_origin,
        sales_contact=ContactProfile(
            full_name=sales_contact_name,
            email=sales_contact_email,
            phone=sales_contact_phone,
        ),
        qm_contact=ContactProfile(
            full_name=qm_contact_name,
            email=qm_contact_email,
            phone=qm_contact_phone,
        ) if qm_contact_name.strip() else None,
        facility_address=facility_address,
    )

    reg = db.query(SupplierRegistration).filter(
        SupplierRegistration.supplier_id == supplier.id
    ).first()

    if not reg:
        reg = SupplierRegistration(supplier_id=supplier.id)
        db.add(reg)

    reg.name_en = profile.name_en
    reg.name_cn = profile.name_cn
    reg.material_origin = profile.material_origin
    reg.sales_contact_name = profile.sales_contact.full_name
    reg.sales_contact_email = profile.sales_contact.email
    reg.sales_contact_phone = profile.sales_contact.phone

    if profile.qm_contact:
        reg.qm_contact_name = profile.qm_contact.full_name
        reg.qm_contact_email = profile.qm_contact.email
        reg.qm_contact_phone = profile.qm_contact.phone
    else:
        reg.qm_contact_name = profile.sales_contact.full_name
        reg.qm_contact_email = profile.sales_contact.email
        reg.qm_contact_phone = profile.sales_contact.phone

    reg.facility_address = profile.facility_address
    reg.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(reg)

    return {"id": reg.id, "status": reg.registration_status, "step": 1, "message": "Supplier profile saved."}


@router.post("/step2-materials")
async def save_step2_materials(
    payload: str = Form(..., description="JSON array of material objects"),
    supplier: Supplier = Depends(get_current_supplier),
    db: Session = Depends(get_db),
):
    try:
        materials_data = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload for materials")

    if not isinstance(materials_data, list) or len(materials_data) == 0:
        raise HTTPException(status_code=400, detail="At least one material is required")

    reg = db.query(SupplierRegistration).filter(
        SupplierRegistration.supplier_id == supplier.id
    ).first()
    if not reg:
        raise HTTPException(status_code=400, detail="Complete Step 1 (Supplier Profile) first.")

    validated = []
    for item in materials_data:
        validated.append(MaterialIdentifierSchema(**item))

    existing_materials = {m.supplier_material_code: m for m in reg.materials}
    kept_ids = set()

    for mat_schema in validated:
        if mat_schema.supplier_material_code in existing_materials:
            mat = existing_materials[mat_schema.supplier_material_code]
            mat.commercial_material_name = mat_schema.commercial_material_name
            mat.internal_factory_material_code = mat_schema.internal_factory_material_code
            mat.is_food_contact = mat_schema.is_food_contact
            mat.updated_at = datetime.utcnow()
        else:
            mat = MaterialRegistration(
                registration_id=reg.id,
                commercial_material_name=mat_schema.commercial_material_name,
                internal_factory_material_code=mat_schema.internal_factory_material_code,
                supplier_material_code=mat_schema.supplier_material_code,
                is_food_contact=mat_schema.is_food_contact,
            )
            db.add(mat)
        db.flush()
        kept_ids.add(mat.id)

    reg.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(reg)

    return {
        "id": reg.id,
        "step": 2,
        "material_count": len(reg.materials),
        "message": "Materials saved.",
    }


@router.post("/step3-documents")
async def save_step3_documents(
    material_id: int = Form(...),
    is_food_contact: bool = Form(False),

    sds_file: UploadFile = File(...),
    sds_language: str = Form(...),
    sds_issue_date: str = Form(...),

    tds_file: UploadFile = File(...),
    tds_physical_state: str = Form(...),

    coa_file: UploadFile = File(...),
    coa_test_date: str = Form(...),

    reach_rohs_file: UploadFile = File(...),

    food_contact_doc_file: Optional[UploadFile] = File(None),

    supplier: Supplier = Depends(get_current_supplier),
    db: Session = Depends(get_db),
):
    reg = db.query(SupplierRegistration).filter(
        SupplierRegistration.supplier_id == supplier.id
    ).first()
    if not reg:
        raise HTTPException(status_code=400, detail="Complete Step 1 (Supplier Profile) first.")

    material = db.query(MaterialRegistration).filter(
        MaterialRegistration.id == material_id,
        MaterialRegistration.registration_id == reg.id,
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    if sds_language not in SDS_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Invalid SDS language. Options: {SDS_LANGUAGES}")
    if tds_physical_state not in TDS_PHYSICAL_STATES:
        raise HTTPException(status_code=400, detail=f"Invalid physical state. Options: {TDS_PHYSICAL_STATES}")

    try:
        sds_date = date.fromisoformat(sds_issue_date)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid SDS issue date format (YYYY-MM-DD).")

    try:
        coa_date = date.fromisoformat(coa_test_date)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid CoA test date format (YYYY-MM-DD).")

    expiry_warning = check_sds_expiry(sds_date)

    if is_food_contact and not food_contact_doc_file:
        raise HTTPException(status_code=400, detail="Food Contact DoC file is required when Food Contact Material is checked.")

    all_files = {
        "sds": sds_file,
        "tds": tds_file,
        "coa": coa_file,
        "reach_rohs": reach_rohs_file,
    }
    if is_food_contact and food_contact_doc_file:
        all_files["food_contact_doc"] = food_contact_doc_file

    for key, f in all_files.items():
        if f:
            validate_file(f)

    for key in ["sds", "tds", "coa", "reach_rohs"]:
        if key in all_files:
            existing = db.query(SupplierDocument).filter(
                SupplierDocument.material_id == material.id,
                SupplierDocument.document_type == key,
            ).first()
            if existing:
                try:
                    os.remove(existing.file_path)
                except OSError:
                    pass
                db.delete(existing)

        file_info = save_upload_file(all_files[key], reg.id, key)
        doc = SupplierDocument(
            registration_id=reg.id,
            material_id=material.id,
            document_type=key,
            file_path=file_info["file_path"],
            original_filename=file_info["original_filename"],
            file_size_bytes=file_info["file_size_bytes"],
        )
        if key == "sds":
            doc.sds_language = sds_language
            doc.sds_issue_date = sds_date
            doc.sds_expiry_warning = expiry_warning
        elif key == "tds":
            doc.tds_physical_state = tds_physical_state
        elif key == "coa":
            doc.coa_test_date = coa_date
        db.add(doc)

    if is_food_contact and "food_contact_doc" in all_files:
        existing_fcd = db.query(SupplierDocument).filter(
            SupplierDocument.material_id == material.id,
            SupplierDocument.document_type == "food_contact_doc",
        ).first()
        if existing_fcd:
            try:
                os.remove(existing_fcd.file_path)
            except OSError:
                pass
            db.delete(existing_fcd)

        fc_info = save_upload_file(food_contact_doc_file, reg.id, "food_contact_doc")
        doc = SupplierDocument(
            registration_id=reg.id,
            material_id=material.id,
            document_type="food_contact_doc",
            file_path=fc_info["file_path"],
            original_filename=fc_info["original_filename"],
            file_size_bytes=fc_info["file_size_bytes"],
        )
        db.add(doc)

    material.is_food_contact = is_food_contact
    material.updated_at = datetime.utcnow()
    reg.updated_at = datetime.utcnow()
    db.commit()

    warnings = []
    if expiry_warning:
        warnings.append("Warning: This SDS exceeds the 3-year compliance lifecycle guideline.")

    return {
        "id": reg.id,
        "material_id": material.id,
        "step": 3,
        "sds_expiry_warning": expiry_warning,
        "warnings": warnings,
        "message": "Documents uploaded successfully.",
    }


@router.post("/step3-documents/single")
async def upload_single_document(
    material_id: int = Form(...),
    document_type: str = Form(...),

    sds_language: Optional[str] = Form(None),
    sds_issue_date: Optional[str] = Form(None),
    tds_physical_state: Optional[str] = Form(None),
    coa_test_date: Optional[str] = Form(None),
    is_food_contact: bool = Form(False),

    file: UploadFile = File(...),

    supplier: Supplier = Depends(get_current_supplier),
    db: Session = Depends(get_db),
):
    reg = db.query(SupplierRegistration).filter(
        SupplierRegistration.supplier_id == supplier.id
    ).first()
    if not reg:
        raise HTTPException(status_code=400, detail="Complete Step 1 first.")

    material = db.query(MaterialRegistration).filter(
        MaterialRegistration.id == material_id,
        MaterialRegistration.registration_id == reg.id,
    ).first()
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    if document_type not in ("sds", "tds", "coa", "reach_rohs", "food_contact_doc"):
        raise HTTPException(status_code=400, detail=f"Unknown document type: {document_type}")

    validate_file(file)

    existing = db.query(SupplierDocument).filter(
        SupplierDocument.material_id == material.id,
        SupplierDocument.document_type == document_type,
    ).first()
    if existing:
        try:
            os.remove(existing.file_path)
        except OSError:
            pass
        db.delete(existing)

    file_info = save_upload_file(file, reg.id, document_type)
    doc = SupplierDocument(
        registration_id=reg.id,
        material_id=material.id,
        document_type=document_type,
        file_path=file_info["file_path"],
        original_filename=file_info["original_filename"],
        file_size_bytes=file_info["file_size_bytes"],
    )

    warnings = []
    if document_type == "sds":
        if not sds_language or sds_language not in SDS_LANGUAGES:
            raise HTTPException(status_code=400, detail="SDS language is required.")
        if not sds_issue_date:
            raise HTTPException(status_code=400, detail="SDS issue date is required.")
        try:
            sds_date = date.fromisoformat(sds_issue_date)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid SDS issue date format.")
        doc.sds_language = sds_language
        doc.sds_issue_date = sds_date
        doc.sds_expiry_warning = check_sds_expiry(sds_date)
        if doc.sds_expiry_warning:
            warnings.append("Warning: This SDS exceeds the 3-year compliance lifecycle guideline.")
    elif document_type == "tds":
        if not tds_physical_state or tds_physical_state not in TDS_PHYSICAL_STATES:
            raise HTTPException(status_code=400, detail="Physical state is required.")
        doc.tds_physical_state = tds_physical_state
    elif document_type == "coa":
        if not coa_test_date:
            raise HTTPException(status_code=400, detail="CoA test date is required.")
        try:
            doc.coa_test_date = date.fromisoformat(coa_test_date)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid CoA test date format.")

    material.is_food_contact = is_food_contact
    material.updated_at = datetime.utcnow()

    db.add(doc)
    reg.updated_at = datetime.utcnow()
    db.commit()

    return {
        "id": doc.id,
        "document_type": document_type,
        "original_filename": doc.original_filename,
        "warnings": warnings,
        "message": f"{document_type.upper()} uploaded successfully.",
    }


@router.post("/submit")
async def submit_registration(
    supplier: Supplier = Depends(get_current_supplier),
    db: Session = Depends(get_db),
):
    reg = db.query(SupplierRegistration).filter(
        SupplierRegistration.supplier_id == supplier.id
    ).first()
    if not reg:
        raise HTTPException(status_code=400, detail="No registration draft found. Complete all steps first.")

    if reg.registration_status not in ("draft", "rejected"):
        raise HTTPException(status_code=400, detail=f"Cannot submit a registration in '{reg.registration_status}' status.")

    required_checks = []

    # Check profile fields
    if not reg.name_en or not reg.material_origin:
        required_checks.append("Step 1: Supplier profile is incomplete (name_en, material_origin required).")
    if not reg.sales_contact_name or not reg.sales_contact_email:
        required_checks.append("Step 1: Sales contact is incomplete.")
    if not reg.facility_address:
        required_checks.append("Step 1: Facility address is required.")

    # Check materials
    if not reg.materials:
        required_checks.append("Step 2: At least one material is required.")

    for mat in reg.materials:
        docs_by_type = {d.document_type: d for d in mat.documents}
        for req_type in ["sds", "tds", "coa", "reach_rohs"]:
            if req_type not in docs_by_type:
                required_checks.append(f"Step 3: '{req_type.upper()}' missing for material '{mat.commercial_material_name}'.")
        if mat.is_food_contact and "food_contact_doc" not in docs_by_type:
            required_checks.append(f"Step 3: 'Food Contact DoC' missing for material '{mat.commercial_material_name}'.")

    if required_checks:
        return JSONResponse(
            status_code=400,
            content={"detail": "Registration incomplete.", "checks": required_checks},
        )

    # Check for hard-block SDS warnings: block if SDS > 3 years
    blocked_sds = []
    for mat in reg.materials:
        for doc in mat.documents:
            if doc.document_type == "sds" and doc.sds_expiry_warning:
                blocked_sds.append(
                    f"Material '{mat.commercial_material_name}': SDS issue date "
                    f"({doc.sds_issue_date.isoformat() if doc.sds_issue_date else 'unknown'}) exceeds 3-year limit."
                )

    if blocked_sds:
        return JSONResponse(
            status_code=400,
            content={"detail": "SDS compliance block: expired documents detected.", "blocked_sds": blocked_sds},
        )

    reg.registration_status = "submitted"
    reg.submitted_at = datetime.utcnow()
    reg.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(reg)

    return {
        "id": reg.id,
        "status": reg.registration_status,
        "submitted_at": reg.submitted_at.isoformat(),
        "message": "Registration submitted for review.",
    }


@router.get("/document/{document_id}/download")
async def download_document(
    document_id: int,
    supplier: Supplier = Depends(get_current_supplier),
    db: Session = Depends(get_db),
):
    doc = db.query(SupplierDocument).filter(SupplierDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    reg = db.query(SupplierRegistration).filter(
        SupplierRegistration.id == doc.registration_id,
        SupplierRegistration.supplier_id == supplier.id,
    ).first()
    if not reg:
        raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(doc.file_path, filename=doc.original_filename, media_type="application/pdf")


@router.delete("/document/{document_id}")
async def delete_document(
    document_id: int,
    supplier: Supplier = Depends(get_current_supplier),
    db: Session = Depends(get_db),
):
    doc = db.query(SupplierDocument).filter(SupplierDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    reg = db.query(SupplierRegistration).filter(
        SupplierRegistration.id == doc.registration_id,
        SupplierRegistration.supplier_id == supplier.id,
    ).first()
    if not reg:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        os.remove(doc.file_path)
    except OSError:
        pass

    db.delete(doc)
    db.commit()

    return {"message": "Document deleted."}


@router.delete("/material/{material_id}")
async def delete_material(
    material_id: int,
    supplier: Supplier = Depends(get_current_supplier),
    db: Session = Depends(get_db),
):
    mat = db.query(MaterialRegistration).filter(MaterialRegistration.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")

    reg = db.query(SupplierRegistration).filter(
        SupplierRegistration.id == mat.registration_id,
        SupplierRegistration.supplier_id == supplier.id,
    ).first()
    if not reg:
        raise HTTPException(status_code=403, detail="Access denied")

    for doc in mat.documents:
        try:
            os.remove(doc.file_path)
        except OSError:
            pass

    db.delete(mat)
    reg.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Material and associated documents deleted."}
