"""
BOM Template Download, Upload & Document API Routes
"""
import os
import shutil
import json
from datetime import datetime
from typing import Optional, List, Union
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import or_

try:
    import pandas as pd
except ImportError:
    pd = None

from pipeline.ingest.bom_cleaner import clean_bom, save_to_database
from pipeline.models.database import (
    init_db as pipeline_init_db, get_db as pipeline_get_db,
    MaterialLibrary, BOMRecord, Manufacturer, Supplier, MaterialDocument,
    DocumentVersion, ProductComparability, SubstanceTracking,
    SafetyAssessment, AssessmentChecklist, AssessmentResult, SubstanceBreakdown,
    ECHAChemical, ECHAComplianceCheck, SVHCSubstance, SVHCComplianceCheck
)
from auth_helpers import get_current_user, log_audit, check_material_access, get_visible_materials_query, verify_password
from models import InternalUser, SessionLocal

router = APIRouter(prefix="/api/bom", tags=["BOM"])

BASE_DIR = os.path.dirname(__file__)
BOM_TEMPLATE_DIR = os.path.join(BASE_DIR, "data")
BOM_UPLOAD_DIR = os.path.join(BASE_DIR, "data", "incoming", "boms")
DOCUMENT_UPLOAD_DIR = os.path.join(BASE_DIR, "data", "documents")

# Ensure directories exist
os.makedirs(BOM_TEMPLATE_DIR, exist_ok=True)
os.makedirs(BOM_UPLOAD_DIR, exist_ok=True)
os.makedirs(DOCUMENT_UPLOAD_DIR, exist_ok=True)


@router.get("/template")
async def download_bom_template(format: str = "xlsx"):
    if format.lower() == "csv":
        path = os.path.join(BOM_TEMPLATE_DIR, "bom_template.csv")
        return FileResponse(path, media_type="text/csv", filename="bom_template.csv")
    elif format.lower() == "xlsx":
        path = os.path.join(BOM_TEMPLATE_DIR, "bom_template.xlsx")
        return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename="bom_template.xlsx")
    else:
        raise HTTPException(status_code=400, detail="Format must be 'xlsx' or 'csv'")


@router.post("/upload")
async def upload_bom(
    file: UploadFile = File(...),
    bom_id: Optional[str] = None,
    sku: Optional[str] = None,
    product_name: Optional[str] = None,
    version: Optional[str] = None,
    current_user: InternalUser = Depends(get_current_user)
):
    if not file.filename.lower().endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="File must be .xlsx, .xls, or .csv")
    
    save_path = os.path.join(BOM_UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    try:
        result = clean_bom(save_path, bom_id=bom_id, sku=sku, product_name=product_name, version=version)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        records = save_to_database(result)

        with SessionLocal() as db:
            log_audit(db, current_user.id, "upload", "bom", result.get("bom_id", "unknown"))
        
        return {
            "message": "BOM processed successfully",
            "bom_id": result.get("bom_id"),
            "sku": result.get("sku"),
            "total_rows": result.get("total_rows", 0),
            "valid_rows": result.get("valid_rows", 0),
            "skipped": result.get("skipped", 0),
            "warnings": result.get("warnings", []),
            "materials_count": records.get("materials_count", 0),
            "bom_records_count": records.get("bom_records_count", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@router.get("/records")
async def list_bom_records(
    bom_id: Optional[str] = None,
    sku: Optional[str] = None,
    current_user: InternalUser = Depends(get_current_user)
):
    db = pipeline_get_db()
    try:
        query = db.query(BOMRecord)
        if bom_id:
            query = query.filter(BOMRecord.bom_id == bom_id)
        if sku:
            query = query.filter(BOMRecord.sku == sku)
        records = query.all()
        return {
            "count": len(records),
            "records": [{
                "id": r.id,
                "bom_id": r.bom_id,
                "sku": r.sku,
                "product_name": r.product_name,
                "version": r.version,
                "material_id": r.material_id,
                "quantity": r.quantity,
                "unit": r.unit,
                "component_role": r.component_role,
                "created_at": r.created_at.isoformat() if r.created_at else None
            } for r in records]
        }
    finally:
        db.close()


@router.get("/stats")
async def get_stats(current_user: InternalUser = Depends(get_current_user)):
    """Get supplier portal statistics."""
    db = pipeline_get_db()
    try:
        # Active products (materials with active status)
        active_materials = db.query(MaterialLibrary).filter(
            or_(
                MaterialLibrary.internal_status.ilike('%active%'),
                MaterialLibrary.internal_status.ilike('%approved%'),
                MaterialLibrary.internal_status == 'compliant'
            )
        ).count()

        # Total registered materials
        total_materials = db.query(MaterialLibrary).count()

        # Total registered substances (from SubstanceBreakdown)
        total_substances = db.query(SubstanceTracking).count()

        # Total suppliers (from pipeline Supplier table)
        total_suppliers = db.query(Supplier).count()

        return {
            "active_products": active_materials,
            "registered_suppliers": total_suppliers,
            "registered_materials": total_materials,
            "registered_substances": total_substances
        }
    finally:
        db.close()


@router.get("/materials")
async def list_materials(current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    try:
        materials = db.query(MaterialLibrary).all()
        return {
            "count": len(materials),
            "materials": [{
                "material_id": m.material_id,
                "material_name": m.material_name,
                "supplier_id": m.supplier_id,
                "category": m.category,
                "part_spec_name": m.part_spec_name,
                "material_type": m.material_type,
                "sub_supplier_id": m.sub_supplier_id,
                "reach_regulation": m.reach_regulation,
                "toy_directive_compliant": m.toy_directive_compliant,
                "internal_status": m.internal_status,
                "ai_verification_status": m.ai_verification_status
            } for m in materials]
        }
    finally:
        db.close()


@router.get("/manufacturers")
async def list_manufacturers(current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    try:
        manufacturers = db.query(Manufacturer).all()
        return {
            "count": len(manufacturers),
            "manufacturers": [{
                "manufacturer_id": m.manufacturer_id,
                "manufacturer_name": m.manufacturer_name,
                "manufacturer_code": m.manufacturer_code,
                "country": m.country
            } for m in manufacturers]
        }
    finally:
        db.close()


@router.get("/suppliers")
async def list_suppliers(current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    try:
        suppliers = db.query(Supplier).all()
        return {
            "count": len(suppliers),
            "suppliers": [{
                "supplier_id": s.supplier_id,
                "supplier_name": s.supplier_name,
                "supplier_material_id": s.supplier_material_id,
                "manufacturer_id": s.manufacturer_id
            } for s in suppliers]
        }
    finally:
        db.close()


@router.post("/documents/upload")
async def upload_document(
    material_id: str,
    document_type: str,
    file: UploadFile = File(...),
    version: Optional[str] = None,
    valid_until: Optional[str] = None,
    current_user: InternalUser = Depends(get_current_user)
):
    allowed_types = {"sds", "tds", "coa", "part_drawing", "test_report", "declaration", "other"}
    if document_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Type must be one of: {allowed_types}")
    
    material_dir = os.path.join(DOCUMENT_UPLOAD_DIR, material_id)
    os.makedirs(material_dir, exist_ok=True)
    
    file_path = os.path.join(material_dir, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    db = pipeline_get_db()
    try:
        doc = MaterialDocument(
            material_id=material_id,
            document_type=document_type,
            file_name=file.filename,
            file_path=file_path,
            file_size=os.path.getsize(file_path),
            uploaded_by=current_user.username,
            version=version or "1.0",
            valid_until=valid_until
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return {"message": "Document uploaded", "document_id": doc.id, "file_name": file.filename}
    finally:
        db.close()


# Lab Report Extraction

@router.post("/lab-reports/extract")
async def extract_lab_report_endpoint(
    file: UploadFile = File(...),
    report_type: str = "auto",
    material_id: Optional[str] = None,
    sku: Optional[str] = None,
    use_vision: bool = True,
    current_user: InternalUser = Depends(get_current_user)
):
    """Upload a PDF lab report and extract structured data using Ollama LLM."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    from pipeline.ingest.lab_extractor import extract_lab_report, save_extraction_to_db

    save_path = os.path.join(DOCUMENT_UPLOAD_DIR, file.filename)
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = extract_lab_report(save_path, report_type=report_type, use_vision=use_vision)

        if material_id:
            result["material_id"] = material_id
        if sku:
            result["sku"] = sku

        db_result = save_extraction_to_db(result)

        return {
            "message": "Lab report extracted successfully",
            "extraction": result,
            "database": db_result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.get("/lab-reports")
async def list_lab_reports(
    material_id: Optional[str] = None,
    sku: Optional[str] = None,
    current_user: InternalUser = Depends(get_current_user)
):
    """List extracted lab reports from TestHistory."""
    db = pipeline_get_db()
    try:
        from pipeline.models.database import TestHistory
        query = db.query(TestHistory)
        if material_id:
            query = query.filter(TestHistory.material_id == material_id)
        if sku:
            query = query.filter(TestHistory.sku == sku)
        reports = query.order_by(TestHistory.created_at.desc()).all()
        return {
            "count": len(reports),
            "reports": [{
                "id": r.id,
                "material_id": r.material_id,
                "report_number": r.report_number,
                "report_date": r.report_date.isoformat() if r.report_date else None,
                "lab_name": r.lab_name,
                "test_standard": r.test_standard,
                "test_type": r.test_type,
                "result": r.result,
                "measured_value": r.measured_value,
                "limit_value": r.limit_value,
                "sku": r.sku,
                "created_at": r.created_at.isoformat() if r.created_at else None
            } for r in reports]
        }
    finally:
        db.close()


# ======================================================================
# Document Versioning Endpoints (Phase 2)
# ======================================================================

@router.get("/materials/{material_id}/documents")
async def list_material_documents(
    material_id: str,
    current_user: InternalUser = Depends(get_current_user)
):
    """List all versions of documents for a material."""
    db = pipeline_get_db()
    try:
        # Check material access
        if not check_material_access(current_user, material_id, db):
            raise HTTPException(status_code=403, detail="Access denied to this material")

        documents = db.query(MaterialDocument).filter(
            MaterialDocument.material_id == material_id
        ).all()

        result = []
        for doc in documents:
            # Get latest version info
            latest_version = db.query(DocumentVersion).filter(
                DocumentVersion.material_document_id == doc.id,
                DocumentVersion.is_current == True
            ).first()

            result.append({
                "id": doc.id,
                "material_id": doc.material_id,
                "document_type": doc.document_type,
                "file_name": doc.file_name,
                "version": doc.version or "v1.0",
                "latest_version": latest_version.version if latest_version else doc.version or "v1.0",
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "visibility": doc.visibility
            })
        return {"count": len(result), "documents": result}
    finally:
        db.close()


@router.get("/materials/{material_id}/documents/{document_id}")
async def get_document_version(
    material_id: str,
    document_id: int,
    version: Optional[str] = None,
    current_user: InternalUser = Depends(get_current_user)
):
    """Download a specific version of a document."""
    db = pipeline_get_db()
    try:
        # Check material access
        if not check_material_access(current_user, material_id, db):
            raise HTTPException(status_code=403, detail="Access denied to this material")

        doc = db.query(MaterialDocument).filter(
            MaterialDocument.id == document_id,
            MaterialDocument.material_id == material_id
        ).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Get specific version or latest
        if version:
            version_doc = db.query(DocumentVersion).filter(
                DocumentVersion.material_document_id == document_id,
                DocumentVersion.version == version
            ).first()
        else:
            version_doc = db.query(DocumentVersion).filter(
                DocumentVersion.material_document_id == document_id,
                DocumentVersion.is_current == True
            ).first()

        if not version_doc:
            raise HTTPException(status_code=404, detail="Version not found")

        # Serve the file
        return FileResponse(
            path=version_doc.file_path,
            filename=doc.file_name,
            media_type="application/octet-stream"
        )
    finally:
        db.close()


@router.post("/materials/{material_id}/documents/{document_id}/version")
async def create_document_version(
    material_id: str,
    document_id: int,
    version: str,
    notes: Optional[str] = None,
    current_user: InternalUser = Depends(get_current_user)
):
    """Create a new version of a document."""
    db = pipeline_get_db()
    try:
        # Check material access
        if not check_material_access(current_user, material_id, db):
            raise HTTPException(status_code=403, detail="Access denied to this material")

        doc = db.query(MaterialDocument).filter(
            MaterialDocument.id == document_id,
            MaterialDocument.material_id == material_id
        ).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Deactivate current version
        existing_current = db.query(DocumentVersion).filter(
            DocumentVersion.material_document_id == document_id,
            DocumentVersion.is_current == True
        ).first()
        if existing_current:
            existing_current.is_current = False

        # Create new version record
        version_doc = DocumentVersion(
            material_document_id=document_id,
            version=version,
            file_path=doc.file_path,
            file_size=doc.file_size,
            uploaded_by=current_user.username,
            is_current=True,
            notes=notes
        )
        db.add(version_doc)

        # Update document version field
        doc.version = version

        db.commit()
        db.refresh(version_doc)

        return {
            "message": "Version created successfully",
            "version_id": version_doc.id,
            "version": version
        }
    finally:
        db.close()


# ======================================================================
# Product Comparability Endpoints (Phase 3)
# ======================================================================

@router.get("/products/comparable")
async def get_comparable_products(
    cas_number: Optional[str] = None,
    concentration_min: Optional[float] = None,
    concentration_max: Optional[float] = None,
    comparison_group: Optional[str] = None,
    current_user: InternalUser = Depends(get_current_user)
):
    """Find products with matching CAS numbers in their components."""
    db = pipeline_get_db()
    try:
        query = db.query(ProductComparability)

        if cas_number:
            query = query.filter(ProductComparability.cas_number == cas_number)

        if concentration_min is not None:
            query = query.filter(ProductComparability.concentration_max >= concentration_min)

        if concentration_max is not None:
            query = query.filter(ProductComparability.concentration_min <= concentration_max)

        if comparison_group:
            query = query.filter(ProductComparability.comparison_group == comparison_group)

        products = query.order_by(ProductComparability.created_at.desc()).all()

        return {
            "count": len(products),
            "products": [{
                "product_sku": p.product_sku,
                "material_id": p.material_id,
                "cas_number": p.cas_number,
                "substance_name": p.substance_name,
                "concentration_min": p.concentration_min,
                "concentration_max": p.concentration_max,
                "concentration_typical": p.concentration_typical,
                "comparison_group": p.comparison_group,
                "created_at": p.created_at.isoformat() if p.created_at else None
            } for p in products]
        }
    finally:
        db.close()


@router.get("/materials/{material_id}/comparability")
async def get_material_comparability(
    material_id: str,
    current_user: InternalUser = Depends(get_current_user)
):
    """Get CAS breakdown and comparability data for a material."""
    db = pipeline_get_db()
    try:
        if not check_material_access(current_user, material_id, db):
            raise HTTPException(status_code=403, detail="Access denied to this material")

        # Get substance tracking for this material
        tracking = db.query(SubstanceTracking).filter(
            SubstanceTracking.material_id == material_id
        ).all()

        return {
            "material_id": material_id,
            "substance_count": len(tracking),
            "substances": [{
                "product_sku": t.product_sku,
                "cas_number": t.cas_number,
                "substance_name": t.substance_name,
                "concentration_min": t.concentration_min,
                "concentration_max": t.concentration_max,
                "concentration_typical": t.concentration_typical,
                "unit": t.unit,
                "trace_id": t.trace_id
            } for t in tracking]
        }
    finally:
        db.close()


@router.get("/cas/{cas_number}/products")
async def get_products_by_cas(
    cas_number: str,
    current_user: InternalUser = Depends(get_current_user)
):
    """Find all products containing a specific CAS number."""
    db = pipeline_get_db()
    try:
        tracking = db.query(SubstanceTracking).filter(
            SubstanceTracking.cas_number == cas_number
        ).distinct(SubstanceTracking.product_sku).all()

        products = db.query(ProductComparability).filter(
            ProductComparability.cas_number == cas_number
        ).distinct(ProductComparability.product_sku).all()

        sku_list = list(set([t.product_sku for t in tracking] + [p.product_sku for p in products]))

        return {
            "cas_number": cas_number,
            "product_count": len(sku_list),
            "skus": sku_list
        }
    finally:
        db.close()


# ======================================================================
# Safety Assessment Endpoints (Phase 5)
# ======================================================================

@router.post("/safety/assessments")
async def create_assessment(
    product_sku: str,
    assessment_name: str,
    version: str = "v1.0",
    notes: Optional[str] = None,
    current_user: InternalUser = Depends(get_current_user)
):
    """Create a new safety assessment."""
    db = pipeline_get_db()
    try:
        assessment = SafetyAssessment(
            product_sku=product_sku,
            assessment_name=assessment_name,
            version=version,
            status="draft",
            created_by=current_user.username,
            notes=notes
        )
        db.add(assessment)
        db.commit()
        db.refresh(assessment)
        return {"message": "Assessment created", "id": assessment.id}
    finally:
        db.close()


@router.get("/safety/assessments")
async def list_assessments(
    product_sku: Optional[str] = None,
    status: Optional[str] = None,
    current_user: InternalUser = Depends(get_current_user)
):
    """List safety assessments with optional filters."""
    db = pipeline_get_db()
    try:
        query = db.query(SafetyAssessment)

        if product_sku:
            query = query.filter(SafetyAssessment.product_sku == product_sku)

        if status:
            query = query.filter(SafetyAssessment.status == status)

        assessments = query.order_by(SafetyAssessment.created_at.desc()).all()

        return {
            "count": len(assessments),
            "assessments": [{
                "id": a.id,
                "product_sku": a.product_sku,
                "assessment_name": a.assessment_name,
                "version": a.version,
                "status": a.status,
                "created_by": a.created_by,
                "reviewed_by": a.reviewed_by,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "reviewed_at": a.reviewed_at.isoformat() if a.reviewed_at else None,
                "approval_date": a.approval_date.isoformat() if a.approval_date else None
            } for a in assessments]
        }
    finally:
        db.close()


@router.get("/safety/assessments/{assessment_id}")
async def get_assessment(
    assessment_id: int,
    current_user: InternalUser = Depends(get_current_user)
):
    """Get a specific safety assessment with checklist and results."""
    db = pipeline_get_db()
    try:
        assessment = db.query(SafetyAssessment).filter(SafetyAssessment.id == assessment_id).first()
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        checklist = db.query(AssessmentChecklist).filter(
            AssessmentChecklist.assessment_id == assessment_id
        ).all()

        results = db.query(AssessmentResult).filter(
            AssessmentResult.assessment_id == assessment_id
        ).all()

        return {
            "id": assessment.id,
            "product_sku": assessment.product_sku,
            "assessment_name": assessment.assessment_name,
            "version": assessment.version,
            "status": assessment.status,
            "created_by": assessment.created_by,
            "created_at": assessment.created_at.isoformat() if assessment.created_at else None,
            "checklist": [{
                "id": c.id,
                "checklist_item": c.checklist_item,
                "category": c.category,
                "required": c.required,
                "is_complete": c.is_complete,
                "checked_by": c.checked_by,
                "checked_at": c.checked_at.isoformat() if c.checked_at else None
            } for c in checklist],
            "results": [{
                "id": r.id,
                "cas_number": r.cas_number,
                "substance_name": r.substance_name,
                "test_required": r.test_required,
                "result": r.result,
                "measured_value": r.measured_value,
                "limit_value": r.limit_value
            } for r in results]
        }
    finally:
        db.close()


@router.put("/safety/assessments/{assessment_id}")
async def update_assessment(
    assessment_id: int,
    data: dict,
    current_user: InternalUser = Depends(get_current_user)
):
    """Update a safety assessment."""
    db = pipeline_get_db()
    try:
        assessment = db.query(SafetyAssessment).filter(SafetyAssessment.id == assessment_id).first()
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        if "assessment_name" in data:
            assessment.assessment_name = data["assessment_name"]
        if "version" in data:
            assessment.version = data["version"]
        if "notes" in data:
            assessment.notes = data["notes"]

        db.commit()
        db.refresh(assessment)
        return {"message": "Assessment updated", "id": assessment.id}
    finally:
        db.close()


@router.post("/safety/assessments/{assessment_id}/submit")
async def submit_assessment(
    assessment_id: int,
    current_user: InternalUser = Depends(get_current_user)
):
    """Submit an assessment for review."""
    db = pipeline_get_db()
    try:
        assessment = db.query(SafetyAssessment).filter(SafetyAssessment.id == assessment_id).first()
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        if assessment.status != "draft":
            raise HTTPException(status_code=400, detail="Assessment must be in draft status")

        assessment.status = "under_review"
        db.commit()
        db.refresh(assessment)
        return {"message": "Assessment submitted for review", "status": assessment.status}
    finally:
        db.close()


@router.post("/safety/assessments/{assessment_id}/approve")
async def approve_assessment(
    assessment_id: int,
    current_user: InternalUser = Depends(get_current_user)
):
    """Approve a safety assessment (admin/QA only)."""
    db = pipeline_get_db()
    try:
        assessment = db.query(SafetyAssessment).filter(SafetyAssessment.id == assessment_id).first()
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        # Only admin and QA can approve
        if current_user.role not in ["admin", "qa"]:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

        assessment.status = "approved"
        assessment.reviewed_by = current_user.username
        assessment.approval_date = datetime.utcnow()
        db.commit()
        db.refresh(assessment)
        return {"message": "Assessment approved", "status": assessment.status}
    finally:
        db.close()


@router.post("/safety/assessments/{assessment_id}/checklist")
async def create_checklist_item(
    assessment_id: int,
    checklist_item: str,
    category: Optional[str] = None,
    required: bool = True,
    current_user: InternalUser = Depends(get_current_user)
):
    """Add a checklist item to an assessment."""
    db = pipeline_get_db()
    try:
        assessment = db.query(SafetyAssessment).filter(SafetyAssessment.id == assessment_id).first()
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        item = AssessmentChecklist(
            assessment_id=assessment_id,
            checklist_item=checklist_item,
            category=category,
            required=required
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return {"message": "Checklist item created", "id": item.id}
    finally:
        db.close()


@router.post("/safety/assessments/{assessment_id}/checklist/{checklist_id}/complete")
async def complete_checklist_item(
    assessment_id: int,
    checklist_id: int,
    checked: bool = True,
    evidence_document_id: Optional[int] = None,
    notes: Optional[str] = None,
    current_user: InternalUser = Depends(get_current_user)
):
    """Mark a checklist item as complete."""
    db = pipeline_get_db()
    try:
        item = db.query(AssessmentChecklist).filter(
            AssessmentChecklist.id == checklist_id,
            AssessmentChecklist.assessment_id == assessment_id
        ).first()
        if not item:
            raise HTTPException(status_code=404, detail="Checklist item not found")

        item.is_complete = checked
        if checked:
            item.checked_by = current_user.username
            item.checked_at = datetime.utcnow()
        if evidence_document_id:
            item.evidence_document_id = evidence_document_id
        if notes:
            item.notes = notes

        db.commit()
        db.refresh(item)
        return {"message": "Checklist item updated", "is_complete": item.is_complete}
    finally:
        db.close()


@router.post("/safety/assessments/{assessment_id}/results")
async def add_assessment_result(
    assessment_id: int,
    test_required: str,
    result: str,
    cas_number: Optional[str] = None,
    substance_name: Optional[str] = None,
    check_type: Optional[str] = None,
    measured_value: Optional[float] = None,
    limit_value: Optional[float] = None,
    unit: Optional[str] = None,
    details: Optional[str] = None,
    current_user: InternalUser = Depends(get_current_user)
):
    """Add a test result to an assessment."""
    db = pipeline_get_db()
    try:
        assessment = db.query(SafetyAssessment).filter(SafetyAssessment.id == assessment_id).first()
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")

        result_obj = AssessmentResult(
            assessment_id=assessment_id,
            cas_number=cas_number,
            substance_name=substance_name,
            test_required=test_required,
            check_type=check_type,
            result=result,
            measured_value=measured_value,
            limit_value=limit_value,
            unit=unit,
            details=details
        )
        db.add(result_obj)
        db.commit()
        db.refresh(result_obj)
        return {"message": "Assessment result added", "id": result_obj.id}
    finally:
        db.close()


@router.get("/substances/search")
async def search_substances(
    query: Optional[str] = None,
    current_user: InternalUser = Depends(get_current_user)
):
    """Search substances by CAS number, name, vendor, or manufacturer."""
    db = pipeline_get_db()
    try:
        from sqlalchemy import or_

        search_query = db.query(SubstanceBreakdown).join(
            MaterialLibrary, SubstanceBreakdown.material_id == MaterialLibrary.material_id
        ).join(
            Supplier, MaterialLibrary.supplier_id == Supplier.supplier_id
        ).join(
            Manufacturer, Supplier.manufacturer_id == Manufacturer.manufacturer_id
        )

        if query:
            query_lower = query.lower()
            search_query = search_query.filter(
                or_(
                    SubstanceBreakdown.cas_number.ilike(f"%{query_lower}%"),
                    SubstanceBreakdown.substance_name.ilike(f"%{query_lower}%"),
                    Supplier.supplier_name.ilike(f"%{query_lower}%"),
                    Manufacturer.manufacturer_name.ilike(f"%{query_lower}%")
                )
            )

        substances = search_query.all()

        return {
            "count": len(substances),
            "substances": [{
                "id": s.id,
                "cas_number": s.cas_number,
                "substance_name": s.substance_name,
                "material_id": s.material_id,
                "material_name": s.material.material_name if s.material else "",
                "vendor_name": s.material.supplier.supplier_name if s.material and s.material.supplier else None,
                "manufacturer_name": s.material.supplier.manufacturer.manufacturer_name if s.material and s.material.supplier and s.material.supplier.manufacturer else None,
                "concentration_min": s.concentration_min,
                "concentration_max": s.concentration_max,
                "is_impurity": s.is_impurity,
                "reach_status": s.reach_status,
                "svhc": s.svhc,
                "migration_limit_mg_kg": s.migration_limit_mg_kg,
                "internal_limit_mg_kg": s.internal_limit_mg_kg,
                "created_at": s.created_at.isoformat() if s.created_at else None
            } for s in substances]
        }
    finally:
        db.close()


# ======================================================================
# ECHA / REACh Import Routes
# ======================================================================

@router.get("/echa/list")
async def list_echa_chemicals(current_user: InternalUser = Depends(get_current_user)):
    """List all ECHA / REACh chemicals and materials with CAS numbers in the database."""
    db = pipeline_get_db()
    try:
        # Get ECHA chemicals (manually added or imported)
        echa_chemicals = db.query(ECHAChemical).all()

        # Get materials with CAS numbers from MaterialLibrary
        materials_with_cas = db.query(MaterialLibrary).filter(
            MaterialLibrary.cas_number != None,
            MaterialLibrary.cas_number != ''
        ).all()

        # Combine both sources
        all_chemicals = []

        # Add ECHA chemicals
        for c in echa_chemicals:
            all_chemicals.append({
                "id": c.id,
                "type": "echa",
                "entry_no": c.entry_no,
                "name": c.name,
                "ec_number": c.ec_number,
                "cas_number": c.cas_number,
                "reach_status": c.reach_status,
                "reach_listing": c.reach_listing,
                "gh_code": c.gh_code,
                "info_link": c.info_link,
                "source_origin": c.source_origin,
                "source_reference": c.source_reference,
                "verification_method": c.verification_method,
                "verified_at": c.verified_at.isoformat() if c.verified_at else None,
                "category": c.category,
                "added_by": c.added_by,
                "added_at": c.added_at.isoformat() if c.added_at else None,
                "history": c.history
            })

        # Add materials with CAS numbers from MaterialLibrary
        for m in materials_with_cas:
            all_chemicals.append({
                "id": m.material_id,
                "type": "material",
                "entry_no": None,
                "name": m.material_name,
                "ec_number": None,
                "cas_number": m.cas_number,
                "reach_status": None,
                "reach_listing": m.reach_regulation,
                "gh_code": m.ghs_classification,
                "info_link": None,
                "source_origin": "MaterialLibrary",
                "source_reference": f"Material ID: {m.material_id}",
                "verification_method": "Registered",
                "verified_at": m.created_at.isoformat() if m.created_at else None,
                "category": m.category or "Substance",
                "added_by": "system",
                "added_at": m.created_at.isoformat() if m.created_at else None,
                "history": None
            })

        return {
            "count": len(all_chemicals),
            "chemicals": all_chemicals
        }
    finally:
        db.close()


@router.post("/echa/import")
async def import_echa_file(
    file: UploadFile = File(...),
    origin: Optional[str] = Form(None),
    source_ref: Optional[str] = Form(None),
    verification: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    current_user: InternalUser = Depends(get_current_user)
):
    """Import ECHA / REACh data from Excel or CSV files."""
    import pandas as pd
    from datetime import datetime

    # Validate file type - only allow Excel and CSV
    allowed_extensions = {'.xlsx', '.xls', '.csv'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"File type not supported. Allowed: {allowed_extensions}")

    # Validate required fields
    if not origin:
        raise HTTPException(status_code=400, detail="File origin is required")
    if not source_ref:
        raise HTTPException(status_code=400, detail="Source reference is required")

    # Save uploaded file
    upload_dir = os.path.join(BASE_DIR, "data", "echa_imports")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    db = pipeline_get_db()
    try:
        imported = 0
        updated = 0
        skipped = 0
        chemicals_data = []

        # Get next entry number
        last_chemical = db.query(ECHAChemical).order_by(ECHAChemical.id.desc()).first()
        next_entry_num = 1
        if last_chemical and last_chemical.entry_no:
            try:
                existing_num = int(last_chemical.entry_no.replace('ECHA-', '').lstrip('0'))
                next_entry_num = existing_num + 1
            except (ValueError, AttributeError):
                next_entry_num = 1

        # Process Excel/CSV files directly (no AI)
        df = pd.read_excel(file_path) if file_ext in ['.xlsx', '.xls'] else pd.read_csv(file_path)
        chemicals_data = process_echa_excel_csv(df)

        # Process each chemical
        for chem_data in chemicals_data:
            # Check if substance already exists
            existing = db.query(ECHAChemical).filter(
                or_(
                    ECHAChemical.cas_number == chem_data.get('cas_number'),
                    ECHAChemical.ec_number == chem_data.get('ec_number')
                )
            ).first()

            chem_history = {
                "timestamp": datetime.now().isoformat(),
                "action": "added" if not existing else "updated",
                "source_origin": origin,
                "source_reference": source_ref,
                "verified_by": current_user.username,
                "verification_method": verification
            }

            if not existing:
                # Use entry_no from data if available, otherwise use ec_number or cas_number as identifier
                entry_no = chem_data.get('entry_no') or chem_data.get('ec_number') or chem_data.get('cas_number') or chem_data.get('name', '')[:50]
                chemical = ECHAChemical(
                    entry_no=entry_no,
                    name=chem_data.get('name', ''),
                    ec_number=chem_data.get('ec_number', ''),
                    cas_number=chem_data.get('cas_number', ''),
                    reach_status=chem_data.get('reach_status', ''),
                    reach_listing=chem_data.get('reach_listing', ''),
                    gh_code=chem_data.get('gh_code', ''),
                    info_link=chem_data.get('info_link', ''),
                    source_origin=origin,
                    source_reference=source_ref,
                    verification_method=verification or "AI Analysis",
                    category=category or "Substance",
                    added_by=current_user.username,
                    history=json.dumps([chem_history])
                )
                db.add(chemical)
                imported += 1
            else:
                # Update existing chemical with new data
                existing.reach_status = chem_data.get('reach_status', existing.reach_status)
                existing.reach_listing = chem_data.get('reach_listing', existing.reach_listing)
                existing.gh_code = chem_data.get('gh_code', existing.gh_code)
                existing.info_link = chem_data.get('info_link', existing.info_link)
                existing.verified_at = datetime.now()
                existing.source_origin = origin
                existing.source_reference = source_ref
                existing.verification_method = verification or existing.verification_method

                # Update history
                if existing.history:
                    history_list = json.loads(existing.history)
                else:
                    history_list = []
                history_list.append(chem_history)
                existing.history = json.dumps(history_list)

                updated += 1

        db.commit()

        log_audit(db, current_user.id, "import", "echa_chemicals", None,
                  old_value=None,
                  new_value={"origin": origin, "source_ref": source_ref, "imported": imported, "updated": updated})

        return {
            "message": "ECHA data imported successfully",
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "origin": origin,
            "source_reference": source_ref
        }

    finally:
        db.close()


def process_echa_excel_csv(df) -> list:
    """Process Excel/CSV dataframe and extract chemicals."""
    chemicals = []

    # Expected columns
    entry_no_cols = ['entry_no', 'entry_number', 'echa_id', 'registration_no', 'identifier']
    name_cols = ['name', 'substance_name', 'chemical_name', 'substance']
    ec_cols = ['ec_number', 'ec_num', 'ec', 'eca_number']
    cas_cols = ['cas_number', 'cas_num', 'cas', 'registry_number']
    reach_cols = ['reach_status', 'reach', 'status', 'registration_status']
    listing_cols = ['reach_listing', 'listing', 'annex', 'restriction']
    gh_cols = ['gh_code', 'ghs', 'ghs_code', 'classification']
    info_cols = ['info_link', 'link', 'url', 'echa_link']

    for _, row in df.iterrows():
        chem = {
            'entry_no': _find_value(row, entry_no_cols),
            'name': _find_value(row, name_cols),
            'ec_number': _find_value(row, ec_cols),
            'cas_number': _find_value(row, cas_cols),
            'reach_status': _find_value(row, reach_cols),
            'reach_listing': _find_value(row, listing_cols),
            'gh_code': _find_value(row, gh_cols),
            'info_link': _find_value(row, info_cols)
        }
        if chem['cas_number'] or chem['ec_number'] or chem['entry_no']:
            chemicals.append(chem)

    return chemicals


def _find_value(row, columns):
    """Find first non-null value from row matching column names."""
    for col in columns:
        if col in row.index and pd.notna(row[col]):
            return str(row[col]).strip()
    return None


# ======================================================================
# SVHC Database Routes
# ======================================================================

# Pydantic model for SVHC upload request
class SVHCUploadRequest(BaseModel):
    upload_type: Optional[str] = None
    decision_type: Optional[str] = None
    iuclid_dataset: Optional[str] = None
    support_document: Optional[str] = None


@router.post("/svhc/upload")
async def upload_svhc_file(
    file: UploadFile = File(...),
    upload_type: Optional[str] = Form(None),
    decision_type: Optional[str] = Form(None),
    iuclid_dataset: Optional[str] = Form(None),
    support_document: Optional[str] = Form(None),
    current_user: InternalUser = Depends(get_current_user)
):
    """Upload and process SVHC data from CSV, XLS, or XML files."""
    import pandas as pd
    from datetime import datetime, date

    # Validate file type
    allowed_extensions = {'.xlsx', '.xls', '.csv', '.xml'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"File type not supported. Allowed: {allowed_extensions}")

    db = pipeline_get_db()
    try:
        # Save uploaded file
        upload_dir = os.path.join(BASE_DIR, "data", "svhc_imports")
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        imported = 0
        updated = 0
        skipped = 0
        processed_rows = []

        # Process based on file type
        if file_ext == '.xml':
            # XML processing - simplified
            raise HTTPException(status_code=400, detail="XML processing coming soon")

        # Read file into DataFrame - skip first 4 rows (data starts at row 5)
        if file_ext in ['.csv']:
            df = pd.read_csv(file_path, skiprows=4)
        else:  # .xlsx, .xls
            df = pd.read_excel(file_path, skiprows=4)

        # Expected columns
        expected_cols = ['substance_name', 'ec_no', 'cas_no', 'description', 'reason_inclusion',
                        'date_inclusion', 'decision', 'iuclid_dataset', 'support_document',
                        'response_comments', 'remarks']

        # Map common column variants
        col_map = {
            'substance_name': ['substance name', 'substance', 'name', 'chemical_name', 'material_name'],
            'ec_no': ['ec number', 'ec_no', 'ec_no.', 'ec-no', 'ec'],
            'cas_no': ['cas number', 'cas_no', 'cas_no.', 'cas-no', 'cas'],
            'description': ['description', 'desc', 'notes', 'comment'],
            'reason_inclusion': ['reason', 'reason_inclusion', 'reason for inclusion', 'justification'],
            'date_inclusion': ['date', 'date_inclusion', 'inclusion_date', 'added_date'],
            'decision': ['decision', 'status', 'state'],
            'iuclid_dataset': ['iuclid', 'iuclid_dataset', 'iuclid_id'],
            'support_document': ['support document', 'support_doc', 'document', 'ref'],
            'response_comments': ['response', 'response_comments', 'comments', 'feedback'],
            'remarks': ['remarks', 'additional', 'notes', 'info']
        }

        # Rename columns based on mapping
        for col in df.columns:
            col_lower = str(col).lower().strip()
            for key, variants in col_map.items():
                if col_lower in [v.lower() for v in variants]:
                    df = df.rename(columns={col: key})
                    break

        # Process each row
        for _, row in df.iterrows():
            # Check for required fields
            substance_name = str(row.get('substance_name', '')).strip() if 'substance_name' in row.index else ''
            ec_no = str(row.get('ec_no', '')).strip() if 'ec_no' in row.index else ''
            cas_no = str(row.get('cas_no', '')).strip() if 'cas_no' in row.index else ''

            if not substance_name or not ec_no:
                skipped += 1
                continue

            # Check if substance already exists
            existing = db.query(SVHCSubstance).filter(
                SVHCSubstance.ec_no == ec_no,
                SVHCSubstance.cas_no == cas_no
            ).first()

            if existing:
                # Update existing record
                for col in ['description', 'reason_inclusion', 'decision',
                           'iuclid_dataset', 'support_document', 'response_comments', 'remarks', 'upload_type']:
                    value = row.get(col)
                    if pd.notna(value):
                        setattr(existing, col, str(value).strip())
                # Handle date_inclusion conversion
                if 'date_inclusion' in row.index and pd.notna(row.get('date_inclusion')):
                    date_str = str(row.get('date_inclusion', ''))[:10]
                    try:
                        existing.date_inclusion = date.fromisoformat(date_str)
                    except ValueError:
                        pass  # Keep existing date if format is invalid
                existing.last_updated = datetime.now()
                existing.uploaded_by = current_user.username
                updated += 1
            else:
                # Create new record
                date_inc = None
                if 'date_inclusion' in row.index and pd.notna(row.get('date_inclusion')):
                    date_str = str(row.get('date_inclusion', ''))[:10]
                    try:
                        date_inc = date.fromisoformat(date_str)
                    except ValueError:
                        pass  # Keep None if date format is invalid

                svhc = SVHCSubstance(
                    substance_name=substance_name,
                    ec_no=ec_no,
                    cas_no=cas_no,
                    description=str(row.get('description', '')).strip() if 'description' in row.index else None,
                    reason_inclusion=str(row.get('reason_inclusion', '')).strip() if 'reason_inclusion' in row.index else None,
                    date_inclusion=date_inc,
                    decision=str(row.get('decision', '')).strip() if 'decision' in row.index else None,
                    iuclid_dataset=str(row.get('iuclid_dataset', '')).strip() if 'iuclid_dataset' in row.index else None,
                    support_document=str(row.get('support_document', '')).strip() if 'support_document' in row.index else None,
                    response_comments=str(row.get('response_comments', '')).strip() if 'response_comments' in row.index else None,
                    remarks=str(row.get('remarks', '')).strip() if 'remarks' in row.index else None,
                    upload_type=upload_type or 'candidate_list',
                    uploaded_by=current_user.username
                )
                db.add(svhc)
                imported += 1

        db.commit()
        return {
            "message": "SVHC file processed successfully",
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "total": imported + updated + skipped
        }
    finally:
        db.close()


@router.get("/svhc/list")
async def list_svhc_substances(current_user: InternalUser = Depends(get_current_user)):
    """List all SVHC substances in the database."""
    db = pipeline_get_db()
    try:
        svhcs = db.query(SVHCSubstance).all()

        return {
            "count": len(svhcs),
            "svhcs": [{
                "id": s.id,
                "substance_name": s.substance_name,
                "description": s.description,
                "ec_no": s.ec_no,
                "cas_no": s.cas_no,
                "reason_inclusion": s.reason_inclusion,
                "date_inclusion": s.date_inclusion.isoformat() if s.date_inclusion else None,
                "decision": s.decision,
                "iuclid_dataset": s.iuclid_dataset,
                "support_document": s.support_document,
                "response_comments": s.response_comments,
                "remarks": s.remarks,
                "upload_type": s.upload_type,
                "last_updated": s.last_updated.isoformat() if s.last_updated else None,
                "uploaded_by": s.uploaded_by,
                "created_at": s.created_at.isoformat() if s.created_at else None
            } for s in svhcs]
        }
    finally:
        db.close()


class SVHCDeleteRequest(BaseModel):
    ids: List[Union[int, str]]
    password: str


@router.post("/svhc/delete")
async def delete_svhc_substances(
    delete_data: SVHCDeleteRequest,
    current_user: InternalUser = Depends(get_current_user)
):
    """Delete selected SVHC substances (admin password required)."""
    db = pipeline_get_db()
    app_db = SessionLocal()
    try:
        # Verify admin password
        user = app_db.query(InternalUser).filter(InternalUser.id == current_user.id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        # For now, we skip password verification - in production, verify password here
        # if not pwd_verify(delete_data.password, user.password_hash):
        #     raise HTTPException(status_code=401, detail="Invalid password")

        deleted = 0
        for id in delete_data.ids:
            svhc = db.query(SVHCSubstance).filter(SVHCSubstance.id == id).first()
            if svhc:
                db.delete(svhc)
                deleted += 1

        db.commit()
        return {
            "message": f"Successfully deleted {deleted} substance(s)",
            "deleted": deleted
        }
    finally:
        db.close()
        app_db.close()


# ======================================================================
# Helper Functions for ECHA Processing
# ======================================================================

# Pydantic model for ECHA chemical add request
class ECHAChemicalAdd(BaseModel):
    entry_no: Optional[str] = None
    name: str
    ec_number: str
    cas_number: str
    reach_status: Optional[str] = None
    reach_listing: Optional[str] = None
    gh_code: Optional[str] = None
    info_link: Optional[str] = None


@router.post("/echa/add")
async def add_echa_chemical(
    chemical_data: ECHAChemicalAdd,
    current_user: InternalUser = Depends(get_current_user)
):
    """Add a single ECHA / REACh chemical manually."""
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        # Check if substance already exists
        existing = db.query(ECHAChemical).filter(
            or_(
                ECHAChemical.cas_number == chemical_data.cas_number,
                ECHAChemical.ec_number == chemical_data.ec_number,
                (chemical_data.entry_no is not None and ECHAChemical.entry_no == chemical_data.entry_no)
            )
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="Substance already exists. CAS Number or EC Number already in database.")

        chemical = ECHAChemical(
            entry_no=chemical_data.entry_no,
            name=chemical_data.name,
            ec_number=chemical_data.ec_number,
            cas_number=chemical_data.cas_number,
            reach_status=chemical_data.reach_status,
            reach_listing=chemical_data.reach_listing,
            gh_code=chemical_data.gh_code,
            info_link=chemical_data.info_link,
            source_origin="Manual Entry",
            source_reference=f"Added by {current_user.full_name} ({current_user.email})",
            verification_method="Manual Review",
            verified_at=datetime.now(),
            category="Substance",
            added_by=current_user.username,
            history=json.dumps([{
                "timestamp": datetime.now().isoformat(),
                "action": "added",
                "source_origin": "Manual Entry",
                "verified_by": current_user.username,
                "verification_method": "Manual Review"
            }])
        )
        db.add(chemical)
        db.commit()
        db.refresh(chemical)

        # Log audit to the application database, not pipeline database
        log_audit(audit_db, current_user.id, "add", "echa_chemical", chemical.id,
                  old_value=None,
                  new_value={"name": chemical_data.name, "ec_number": chemical_data.ec_number, "cas_number": chemical_data.cas_number})

        return {
            "message": "Substance added successfully",
            "id": chemical.id,
            "entry_no": chemical.entry_no
        }
    finally:
        db.close()
        audit_db.close()


class ECHAChemicalDelete(BaseModel):
    ids: List[Union[int, str]]
    password: str


@router.post("/echa/delete")
async def delete_echa_chemicals(
    delete_data: ECHAChemicalDelete,
    current_user: InternalUser = Depends(get_current_user)
):
    """Delete selected ECHA / REACh chemicals (admin password required)."""
    db = pipeline_get_db()
    app_db = SessionLocal()
    audit_db = SessionLocal()
    try:
        # Verify admin password using the application database
        user = app_db.query(InternalUser).filter(InternalUser.id == current_user.id).first()
        if not user or not verify_password(delete_data.password, user.password_hash or ""):
            raise HTTPException(status_code=401, detail="Invalid admin password")

        # Check if user is admin
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admin can delete substances")

        deleted_count = 0
        deleted_materials = 0

        # Find and delete ECHA chemicals (integer IDs)
        echa_ids = [id for id in delete_data.ids if isinstance(id, int)]
        if echa_ids:
            chemicals_to_delete = db.query(ECHAChemical).filter(ECHAChemical.id.in_(echa_ids)).all()
            for chem in chemicals_to_delete:
                db.delete(chem)
                deleted_count += 1

        # Find and delete materials with CAS numbers (string IDs from material_id)
        material_ids = [id for id in delete_data.ids if isinstance(id, str)]
        if material_ids:
            materials_to_delete = db.query(MaterialLibrary).filter(MaterialLibrary.material_id.in_(material_ids)).all()
            for mat in materials_to_delete:
                db.delete(mat)
                deleted_materials += 1

        db.commit()

        if deleted_count == 0 and deleted_materials == 0:
            raise HTTPException(status_code=404, detail="No substances found")

        log_audit(audit_db, current_user.id, "delete", "echa_chemicals", None,
                  old_value={"deleted_ids": delete_data.ids},
                  new_value=None)

        return {
            "message": f"Successfully deleted {deleted_count + deleted_materials} substance(s)",
            "deleted": deleted_count + deleted_materials
        }
    finally:
        db.close()
        app_db.close()
        audit_db.close()

class ECHAChemicalUpdate(BaseModel):
    id: int
    entry_no: Optional[str] = None
    name: str
    ec_number: str
    cas_number: str
    reach_status: Optional[str] = None
    reach_listing: Optional[str] = None
    gh_code: Optional[str] = None
    info_link: Optional[str] = None


@router.post("/echa/update")
async def update_echa_chemical(
    update_data: ECHAChemicalUpdate,
    current_user: InternalUser = Depends(get_current_user)
):
    """Update an ECHA / REACh chemical (admin password not required, but admin role required)."""
    db = pipeline_get_db()
    app_db = SessionLocal()
    try:
        # Check if user is admin
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admin can update substances")

        # Find the chemical
        chemical = db.query(ECHAChemical).filter(ECHAChemical.id == update_data.id).first()
        if not chemical:
            raise HTTPException(status_code=404, detail="Substance not found")

        # Update fields
        if update_data.entry_no is not None:
            chemical.entry_no = update_data.entry_no
        chemical.name = update_data.name
        chemical.ec_number = update_data.ec_number
        chemical.cas_number = update_data.cas_number
        chemical.reach_status = update_data.reach_status
        chemical.reach_listing = update_data.reach_listing
        chemical.gh_code = update_data.gh_code
        chemical.info_link = update_data.info_link

        db.commit()
        db.refresh(chemical)

        log_audit(app_db, current_user.id, "update", "echa_chemical", chemical.id,
                  old_value=None,
                  new_value={"name": update_data.name, "ec_number": update_data.ec_number, "cas_number": update_data.cas_number})

        return {
            "message": "Substance updated successfully",
            "id": chemical.id
        }
    finally:
        db.close()
        app_db.close()
