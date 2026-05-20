"""
Substance Library API Routes — CRUD + search for 5 libraries and symbol references.
"""
import os
import json
import shutil
from datetime import datetime
from typing import Optional, List, Union
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query, Form
from pydantic import BaseModel
from sqlalchemy import or_, text

try:
    import pandas as pd
except ImportError:
    pd = None

from pipeline.models.database import (
    init_db as pipeline_init_db,
    get_db as pipeline_get_db,
    SubstanceLibrary, CMRSubstance, ECHASubstance,
    CLPClassification, GHSClassification, SymbolReference,
    utcnow
)
from auth_helpers import get_current_user, log_audit, verify_password
from models import InternalUser, SessionLocal

router = APIRouter(prefix="/api/substances", tags=["Substance Library"])

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
IMPORT_DIR = os.path.join(BASE_DIR, "data", "substance_imports")
os.makedirs(IMPORT_DIR, exist_ok=True)


# ======================================================================
# Pydantic Schemas
# ======================================================================

class PaginationResponse(BaseModel):
    data: list
    pagination: dict


class SubstanceCreate(BaseModel):
    name: str
    cas_number: Optional[str] = None
    ec_number: Optional[str] = None
    iupac_name: Optional[str] = None
    molecular_formula: Optional[str] = None
    registration_status: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None


class SubstanceUpdate(BaseModel):
    name: Optional[str] = None
    cas_number: Optional[str] = None
    ec_number: Optional[str] = None
    iupac_name: Optional[str] = None
    molecular_formula: Optional[str] = None
    registration_status: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None


class CMRCreate(BaseModel):
    substance_id: Optional[int] = None
    cas_number: Optional[str] = None
    ec_number: Optional[str] = None
    name: str
    cmr_type: Optional[str] = None
    cmr_category: Optional[str] = None
    hazard_class: Optional[str] = None
    hazard_statements: Optional[str] = None
    clp_notes: Optional[str] = None
    atp_reference: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None


class CMRUpdate(BaseModel):
    substance_id: Optional[int] = None
    cas_number: Optional[str] = None
    ec_number: Optional[str] = None
    name: Optional[str] = None
    cmr_type: Optional[str] = None
    cmr_category: Optional[str] = None
    hazard_class: Optional[str] = None
    hazard_statements: Optional[str] = None
    clp_notes: Optional[str] = None
    atp_reference: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None


class ECHACreate(BaseModel):
    substance_id: Optional[int] = None
    cas_number: Optional[str] = None
    ec_number: Optional[str] = None
    name: str
    reach_status: Optional[str] = None
    tonnage_band: Optional[str] = None
    registration_type: Optional[str] = None
    index_number: Optional[str] = None
    clp_notes: Optional[str] = None
    atp_reference: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None


class ECHAUpdate(BaseModel):
    substance_id: Optional[int] = None
    cas_number: Optional[str] = None
    ec_number: Optional[str] = None
    name: Optional[str] = None
    reach_status: Optional[str] = None
    tonnage_band: Optional[str] = None
    registration_type: Optional[str] = None
    index_number: Optional[str] = None
    clp_notes: Optional[str] = None
    atp_reference: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None


class CLPCreate(BaseModel):
    substance_id: Optional[int] = None
    cas_number: Optional[str] = None
    ec_number: Optional[str] = None
    name: str
    hazard_class: Optional[str] = None
    hazard_category: Optional[str] = None
    hazard_statement_code: Optional[str] = None
    hazard_statement: Optional[str] = None
    p_statements: Optional[str] = None
    signal_word: Optional[str] = None
    pictograms: Optional[str] = None
    concentration_limit: Optional[str] = None
    m_factor: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None


class CLPUpdate(BaseModel):
    substance_id: Optional[int] = None
    cas_number: Optional[str] = None
    ec_number: Optional[str] = None
    name: Optional[str] = None
    hazard_class: Optional[str] = None
    hazard_category: Optional[str] = None
    hazard_statement_code: Optional[str] = None
    hazard_statement: Optional[str] = None
    p_statements: Optional[str] = None
    signal_word: Optional[str] = None
    pictograms: Optional[str] = None
    concentration_limit: Optional[str] = None
    m_factor: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None


class GHSCreate(BaseModel):
    substance_id: Optional[int] = None
    cas_number: Optional[str] = None
    ec_number: Optional[str] = None
    name: str
    ghs_hazard_class: Optional[str] = None
    ghs_category: Optional[str] = None
    pictogram_codes: Optional[str] = None
    signal_word: Optional[str] = None
    hazard_statements: Optional[str] = None
    precautionary_statements: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None


class GHSUpdate(BaseModel):
    substance_id: Optional[int] = None
    cas_number: Optional[str] = None
    ec_number: Optional[str] = None
    name: Optional[str] = None
    ghs_hazard_class: Optional[str] = None
    ghs_category: Optional[str] = None
    pictogram_codes: Optional[str] = None
    signal_word: Optional[str] = None
    hazard_statements: Optional[str] = None
    precautionary_statements: Optional[str] = None
    source_url: Optional[str] = None
    notes: Optional[str] = None


class SymbolCreate(BaseModel):
    symbol_code: str
    name: str
    description: Optional[str] = None
    emoji: Optional[str] = None
    regulation_source: Optional[str] = None
    image_url: Optional[str] = None


class SymbolUpdate(BaseModel):
    symbol_code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    emoji: Optional[str] = None
    regulation_source: Optional[str] = None
    image_url: Optional[str] = None


class BatchDeleteRequest(BaseModel):
    ids: List[int]
    password: str


# ======================================================================
# Helpers
# ======================================================================

def _paginate(query, page: int, limit: int):
    total = query.count()
    if limit == -1:
        items = query.all()
        return items, {"page": 1, "limit": "all", "total": total, "totalPages": 1}
    offset = (page - 1) * limit
    items = query.offset(offset).limit(limit).all()
    total_pages = (total + limit - 1) // limit if limit else 1
    return items, {"page": page, "limit": limit, "total": total, "totalPages": total_pages}


def _verify_admin_password(current_user, password: str):
    app_db = SessionLocal()
    try:
        user = app_db.query(InternalUser).filter(InternalUser.id == current_user.id).first()
        if not user or not verify_password(password, user.password_hash or ""):
            raise HTTPException(status_code=401, detail="Invalid admin password")
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admin can perform this action")
    finally:
        app_db.close()


def _substance_to_dict(s):
    return {
        "id": s.id,
        "name": s.name,
        "cas_number": s.cas_number,
        "ec_number": s.ec_number,
        "iupac_name": s.iupac_name,
        "molecular_formula": s.molecular_formula,
        "registration_status": s.registration_status,
        "source_url": s.source_url,
        "notes": s.notes,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


def _cmr_to_dict(c):
    return {
        "id": c.id,
        "substance_id": c.substance_id,
        "cas_number": c.cas_number,
        "ec_number": c.ec_number,
        "name": c.name,
        "cmr_type": c.cmr_type,
        "cmr_category": c.cmr_category,
        "hazard_class": c.hazard_class,
        "hazard_statements": c.hazard_statements,
        "clp_notes": c.clp_notes,
        "atp_reference": c.atp_reference,
        "source_url": c.source_url,
        "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _echa_to_dict(e):
    return {
        "id": e.id,
        "substance_id": e.substance_id,
        "cas_number": e.cas_number,
        "ec_number": e.ec_number,
        "name": e.name,
        "reach_status": e.reach_status,
        "tonnage_band": e.tonnage_band,
        "registration_type": e.registration_type,
        "index_number": e.index_number,
        "clp_notes": e.clp_notes,
        "atp_reference": e.atp_reference,
        "source_url": e.source_url,
        "notes": e.notes,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }


def _clp_to_dict(c):
    return {
        "id": c.id,
        "substance_id": c.substance_id,
        "cas_number": c.cas_number,
        "ec_number": c.ec_number,
        "name": c.name,
        "hazard_class": c.hazard_class,
        "hazard_category": c.hazard_category,
        "hazard_statement_code": c.hazard_statement_code,
        "hazard_statement": c.hazard_statement,
        "p_statements": c.p_statements,
        "signal_word": c.signal_word,
        "pictograms": c.pictograms,
        "concentration_limit": c.concentration_limit,
        "m_factor": c.m_factor,
        "source_url": c.source_url,
        "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _ghs_to_dict(g):
    return {
        "id": g.id,
        "substance_id": g.substance_id,
        "cas_number": g.cas_number,
        "ec_number": g.ec_number,
        "name": g.name,
        "ghs_hazard_class": g.ghs_hazard_class,
        "ghs_category": g.ghs_category,
        "pictogram_codes": g.pictogram_codes,
        "signal_word": g.signal_word,
        "hazard_statements": g.hazard_statements,
        "precautionary_statements": g.precautionary_statements,
        "source_url": g.source_url,
        "notes": g.notes,
        "created_at": g.created_at.isoformat() if g.created_at else None,
        "updated_at": g.updated_at.isoformat() if g.updated_at else None,
    }


def _symbol_to_dict(s):
    return {
        "id": s.id,
        "symbol_code": s.symbol_code,
        "name": s.name,
        "description": s.description,
        "emoji": s.emoji,
        "regulation_source": s.regulation_source,
        "image_url": s.image_url,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# ======================================================================
# Substance Library (Master)
# ======================================================================

# ======================================================================
# Substance Library (Master)
# ======================================================================

@router.get("")
async def list_substances(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    q: Optional[str] = Query(None),
    current_user: InternalUser = Depends(get_current_user)
):
    db = pipeline_get_db()
    try:
        query = db.query(SubstanceLibrary)
        if q:
            search = f"%{q}%"
            query = query.filter(
                or_(
                    SubstanceLibrary.name.ilike(search),
                    SubstanceLibrary.cas_number.ilike(search),
                    SubstanceLibrary.ec_number.ilike(search),
                    SubstanceLibrary.iupac_name.ilike(search),
                )
            )
        items, pagination = _paginate(query.order_by(SubstanceLibrary.name), page, limit)
        return {"data": [_substance_to_dict(i) for i in items], "pagination": pagination}
    finally:
        db.close()


@router.get("/search")
async def search_substances(q: Optional[str] = Query(None), current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    try:
        query = db.query(SubstanceLibrary)
        if q:
            search = f"%{q}%"
            query = query.filter(
                or_(
                    SubstanceLibrary.name.ilike(search),
                    SubstanceLibrary.cas_number.ilike(search),
                    SubstanceLibrary.ec_number.ilike(search),
                    SubstanceLibrary.iupac_name.ilike(search),
                )
            )
        items = query.order_by(SubstanceLibrary.name).limit(100).all()
        return {"data": [_substance_to_dict(i) for i in items]}
    finally:
        db.close()


@router.post("")
async def create_substance(data: SubstanceCreate, current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        s = SubstanceLibrary(**data.dict(exclude_unset=True))
        db.add(s)
        db.commit()
        db.refresh(s)
        log_audit(audit_db, current_user.id, "create", "substance_library", s.id, new_value=data.dict())
        return _substance_to_dict(s)
    finally:
        db.close()
        audit_db.close()


@router.put("/{substance_id}")
async def update_substance(substance_id: int, data: SubstanceUpdate, current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        s = db.query(SubstanceLibrary).filter(SubstanceLibrary.id == substance_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Substance not found")
        for key, value in data.dict(exclude_unset=True).items():
            setattr(s, key, value)
        s.updated_at = utcnow()
        db.commit()
        db.refresh(s)
        log_audit(audit_db, current_user.id, "update", "substance_library", s.id, new_value=data.dict(exclude_unset=True))
        return _substance_to_dict(s)
    finally:
        db.close()
        audit_db.close()


@router.delete("/{substance_id}")
async def delete_substance(substance_id: int, current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        s = db.query(SubstanceLibrary).filter(SubstanceLibrary.id == substance_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Substance not found")
        db.delete(s)
        db.commit()
        log_audit(audit_db, current_user.id, "delete", "substance_library", substance_id)
        return {"message": "Substance deleted", "id": substance_id}
    finally:
        db.close()
        audit_db.close()


# ======================================================================
# CMR Library
# ======================================================================

@router.get("/cmr")
async def list_cmr(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    q: Optional[str] = Query(None),
    current_user: InternalUser = Depends(get_current_user)
):
    db = pipeline_get_db()
    try:
        query = db.query(CMRSubstance)
        if q:
            search = f"%{q}%"
            query = query.filter(
                or_(
                    CMRSubstance.name.ilike(search),
                    CMRSubstance.cas_number.ilike(search),
                    CMRSubstance.ec_number.ilike(search),
                )
            )
        items, pagination = _paginate(query.order_by(CMRSubstance.name), page, limit)
        return {"data": [_cmr_to_dict(i) for i in items], "pagination": pagination}
    finally:
        db.close()


@router.post("/cmr")
async def create_cmr(data: CMRCreate, current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        c = CMRSubstance(**data.dict(exclude_unset=True))
        db.add(c)
        db.commit()
        db.refresh(c)
        log_audit(audit_db, current_user.id, "create", "cmr_substance", c.id, new_value=data.dict())
        return _cmr_to_dict(c)
    finally:
        db.close()
        audit_db.close()


@router.put("/cmr/{cmr_id}")
async def update_cmr(cmr_id: int, data: CMRUpdate, current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        c = db.query(CMRSubstance).filter(CMRSubstance.id == cmr_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="CMR entry not found")
        for key, value in data.dict(exclude_unset=True).items():
            setattr(c, key, value)
        c.updated_at = utcnow()
        db.commit()
        db.refresh(c)
        log_audit(audit_db, current_user.id, "update", "cmr_substance", c.id, new_value=data.dict(exclude_unset=True))
        return _cmr_to_dict(c)
    finally:
        db.close()
        audit_db.close()


@router.post("/cmr/batch")
async def delete_cmr_batch(data: BatchDeleteRequest, current_user: InternalUser = Depends(get_current_user)):
    _verify_admin_password(current_user, data.password)
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        deleted = 0
        for cid in data.ids:
            c = db.query(CMRSubstance).filter(CMRSubstance.id == cid).first()
            if c:
                db.delete(c)
                deleted += 1
        db.commit()
        log_audit(audit_db, current_user.id, "batch_delete", "cmr_substance", None, old_value={"ids": data.ids})
        return {"message": f"Deleted {deleted} CMR entries", "deleted": deleted}
    finally:
        db.close()
        audit_db.close()


# ======================================================================
# ECHA Library
# ======================================================================

@router.get("/echa")
async def list_echa(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    q: Optional[str] = Query(None),
    current_user: InternalUser = Depends(get_current_user)
):
    db = pipeline_get_db()
    try:
        query = db.query(ECHASubstance)
        if q:
            search = f"%{q}%"
            query = query.filter(
                or_(
                    ECHASubstance.name.ilike(search),
                    ECHASubstance.cas_number.ilike(search),
                    ECHASubstance.ec_number.ilike(search),
                )
            )
        items, pagination = _paginate(query.order_by(ECHASubstance.name), page, limit)
        return {"data": [_echa_to_dict(i) for i in items], "pagination": pagination}
    finally:
        db.close()


@router.post("/echa")
async def create_echa(data: ECHACreate, current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        e = ECHASubstance(**data.dict(exclude_unset=True))
        db.add(e)
        db.commit()
        db.refresh(e)
        log_audit(audit_db, current_user.id, "create", "echa_substance", e.id, new_value=data.dict())
        return _echa_to_dict(e)
    finally:
        db.close()
        audit_db.close()


@router.put("/echa/{echa_id}")
async def update_echa(echa_id: int, data: ECHAUpdate, current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        e = db.query(ECHASubstance).filter(ECHASubstance.id == echa_id).first()
        if not e:
            raise HTTPException(status_code=404, detail="ECHA entry not found")
        for key, value in data.dict(exclude_unset=True).items():
            setattr(e, key, value)
        e.updated_at = utcnow()
        db.commit()
        db.refresh(e)
        log_audit(audit_db, current_user.id, "update", "echa_substance", e.id, new_value=data.dict(exclude_unset=True))
        return _echa_to_dict(e)
    finally:
        db.close()
        audit_db.close()


@router.post("/echa/batch")
async def delete_echa_batch(data: BatchDeleteRequest, current_user: InternalUser = Depends(get_current_user)):
    _verify_admin_password(current_user, data.password)
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        deleted = 0
        for eid in data.ids:
            e = db.query(ECHASubstance).filter(ECHASubstance.id == eid).first()
            if e:
                db.delete(e)
                deleted += 1
        db.commit()
        log_audit(audit_db, current_user.id, "batch_delete", "echa_substance", None, old_value={"ids": data.ids})
        return {"message": f"Deleted {deleted} ECHA entries", "deleted": deleted}
    finally:
        db.close()
        audit_db.close()


# ======================================================================
# CLP Library
# ======================================================================

@router.get("/clp")
async def list_clp(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    q: Optional[str] = Query(None),
    current_user: InternalUser = Depends(get_current_user)
):
    db = pipeline_get_db()
    try:
        query = db.query(CLPClassification)
        if q:
            search = f"%{q}%"
            query = query.filter(
                or_(
                    CLPClassification.name.ilike(search),
                    CLPClassification.cas_number.ilike(search),
                    CLPClassification.ec_number.ilike(search),
                )
            )
        items, pagination = _paginate(query.order_by(CLPClassification.name), page, limit)
        return {"data": [_clp_to_dict(i) for i in items], "pagination": pagination}
    finally:
        db.close()


@router.post("/clp")
async def create_clp(data: CLPCreate, current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        c = CLPClassification(**data.dict(exclude_unset=True))
        db.add(c)
        db.commit()
        db.refresh(c)
        log_audit(audit_db, current_user.id, "create", "clp_classification", c.id, new_value=data.dict())
        return _clp_to_dict(c)
    finally:
        db.close()
        audit_db.close()


@router.put("/clp/{clp_id}")
async def update_clp(clp_id: int, data: CLPUpdate, current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        c = db.query(CLPClassification).filter(CLPClassification.id == clp_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="CLP entry not found")
        for key, value in data.dict(exclude_unset=True).items():
            setattr(c, key, value)
        c.updated_at = utcnow()
        db.commit()
        db.refresh(c)
        log_audit(audit_db, current_user.id, "update", "clp_classification", c.id, new_value=data.dict(exclude_unset=True))
        return _clp_to_dict(c)
    finally:
        db.close()
        audit_db.close()


@router.post("/clp/batch")
async def delete_clp_batch(data: BatchDeleteRequest, current_user: InternalUser = Depends(get_current_user)):
    _verify_admin_password(current_user, data.password)
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        deleted = 0
        for cid in data.ids:
            c = db.query(CLPClassification).filter(CLPClassification.id == cid).first()
            if c:
                db.delete(c)
                deleted += 1
        db.commit()
        log_audit(audit_db, current_user.id, "batch_delete", "clp_classification", None, old_value={"ids": data.ids})
        return {"message": f"Deleted {deleted} CLP entries", "deleted": deleted}
    finally:
        db.close()
        audit_db.close()


# ======================================================================
# GHS Library
# ======================================================================

@router.get("/ghs")
async def list_ghs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1),
    q: Optional[str] = Query(None),
    current_user: InternalUser = Depends(get_current_user)
):
    db = pipeline_get_db()
    try:
        query = db.query(GHSClassification)
        if q:
            search = f"%{q}%"
            query = query.filter(
                or_(
                    GHSClassification.name.ilike(search),
                    GHSClassification.cas_number.ilike(search),
                    GHSClassification.ec_number.ilike(search),
                )
            )
        items, pagination = _paginate(query.order_by(GHSClassification.name), page, limit)
        return {"data": [_ghs_to_dict(i) for i in items], "pagination": pagination}
    finally:
        db.close()


@router.post("/ghs")
async def create_ghs(data: GHSCreate, current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        g = GHSClassification(**data.dict(exclude_unset=True))
        db.add(g)
        db.commit()
        db.refresh(g)
        log_audit(audit_db, current_user.id, "create", "ghs_classification", g.id, new_value=data.dict())
        return _ghs_to_dict(g)
    finally:
        db.close()
        audit_db.close()


@router.put("/ghs/{ghs_id}")
async def update_ghs(ghs_id: int, data: GHSUpdate, current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        g = db.query(GHSClassification).filter(GHSClassification.id == ghs_id).first()
        if not g:
            raise HTTPException(status_code=404, detail="GHS entry not found")
        for key, value in data.dict(exclude_unset=True).items():
            setattr(g, key, value)
        g.updated_at = utcnow()
        db.commit()
        db.refresh(g)
        log_audit(audit_db, current_user.id, "update", "ghs_classification", g.id, new_value=data.dict(exclude_unset=True))
        return _ghs_to_dict(g)
    finally:
        db.close()
        audit_db.close()


@router.post("/ghs/batch")
async def delete_ghs_batch(data: BatchDeleteRequest, current_user: InternalUser = Depends(get_current_user)):
    _verify_admin_password(current_user, data.password)
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        deleted = 0
        for gid in data.ids:
            g = db.query(GHSClassification).filter(GHSClassification.id == gid).first()
            if g:
                db.delete(g)
                deleted += 1
        db.commit()
        log_audit(audit_db, current_user.id, "batch_delete", "ghs_classification", None, old_value={"ids": data.ids})
        return {"message": f"Deleted {deleted} GHS entries", "deleted": deleted}
    finally:
        db.close()
        audit_db.close()


# ======================================================================
# Symbol References
# ======================================================================

@router.get("/symbols")
async def list_symbols(current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    try:
        items = db.query(SymbolReference).order_by(SymbolReference.symbol_code).all()
        return {"data": [_symbol_to_dict(i) for i in items]}
    finally:
        db.close()


@router.post("/symbols")
async def create_symbol(data: SymbolCreate, current_user: InternalUser = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can add symbols")
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        s = SymbolReference(**data.dict(exclude_unset=True))
        db.add(s)
        db.commit()
        db.refresh(s)
        log_audit(audit_db, current_user.id, "create", "symbol_reference", s.id, new_value=data.dict())
        return _symbol_to_dict(s)
    finally:
        db.close()
        audit_db.close()


@router.put("/symbols/{symbol_id}")
async def update_symbol(symbol_id: int, data: SymbolUpdate, current_user: InternalUser = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can update symbols")
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        s = db.query(SymbolReference).filter(SymbolReference.id == symbol_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Symbol not found")
        for key, value in data.dict(exclude_unset=True).items():
            setattr(s, key, value)
        db.commit()
        db.refresh(s)
        log_audit(audit_db, current_user.id, "update", "symbol_reference", s.id, new_value=data.dict(exclude_unset=True))
        return _symbol_to_dict(s)
    finally:
        db.close()
        audit_db.close()


@router.delete("/symbols/{symbol_id}")
async def delete_symbol(symbol_id: int, current_user: InternalUser = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can delete symbols")
    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        s = db.query(SymbolReference).filter(SymbolReference.id == symbol_id).first()
        if not s:
            raise HTTPException(status_code=404, detail="Symbol not found")
        db.delete(s)
        db.commit()
        log_audit(audit_db, current_user.id, "delete", "symbol_reference", symbol_id)
        return {"message": "Symbol deleted", "id": symbol_id}
    finally:
        db.close()
        audit_db.close()


# ======================================================================
# Cross-Regulation Linking (by CAS)
# ======================================================================

@router.get("/{substance_id}/related")
async def get_related(substance_id: int, current_user: InternalUser = Depends(get_current_user)):
    db = pipeline_get_db()
    try:
        master = db.query(SubstanceLibrary).filter(SubstanceLibrary.id == substance_id).first()
        if not master:
            raise HTTPException(status_code=404, detail="Substance not found")
        cas = master.cas_number
        if not cas:
            return {"cmr": [], "echa": [], "clp": [], "ghs": []}
        return {
            "cmr": [_cmr_to_dict(c) for c in db.query(CMRSubstance).filter(CMRSubstance.cas_number == cas).all()],
            "echa": [_echa_to_dict(e) for e in db.query(ECHASubstance).filter(ECHASubstance.cas_number == cas).all()],
            "clp": [_clp_to_dict(c) for c in db.query(CLPClassification).filter(CLPClassification.cas_number == cas).all()],
            "ghs": [_ghs_to_dict(g) for g in db.query(GHSClassification).filter(GHSClassification.cas_number == cas).all()],
        }
    finally:
        db.close()


# ======================================================================
# Import (CSV/Excel) — generic per library
# ======================================================================

@router.post("/import/{library}")
async def import_library_file(
    library: str,
    file: UploadFile = File(...),
    current_user: InternalUser = Depends(get_current_user)
):
    if library not in {"substance", "cmr", "echa", "clp", "ghs"}:
        raise HTTPException(status_code=400, detail="Library must be one of: substance, cmr, echa, clp, ghs")

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in {".xlsx", ".xls", ".csv"}:
        raise HTTPException(status_code=400, detail="Only .xlsx, .xls, .csv allowed")

    if pd is None:
        raise HTTPException(status_code=500, detail="pandas not installed")

    file_path = os.path.join(IMPORT_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    db = pipeline_get_db()
    audit_db = SessionLocal()
    try:
        df = pd.read_excel(file_path) if file_ext in {".xlsx", ".xls"} else pd.read_csv(file_path)
        imported = 0
        skipped = 0

        for _, row in df.iterrows():
            row_dict = {str(k).strip().lower(): (str(v).strip() if pd.notna(v) else None) for k, v in row.items()}

            if library == "substance":
                obj = _build_substance_from_row(row_dict)
                if obj:
                    db.add(SubstanceLibrary(**obj))
                    imported += 1
                else:
                    skipped += 1
            elif library == "cmr":
                obj = _build_cmr_from_row(row_dict)
                if obj:
                    db.add(CMRSubstance(**obj))
                    imported += 1
                else:
                    skipped += 1
            elif library == "echa":
                obj = _build_echa_from_row(row_dict)
                if obj:
                    db.add(ECHASubstance(**obj))
                    imported += 1
                else:
                    skipped += 1
            elif library == "clp":
                obj = _build_clp_from_row(row_dict)
                if obj:
                    db.add(CLPClassification(**obj))
                    imported += 1
                else:
                    skipped += 1
            elif library == "ghs":
                obj = _build_ghs_from_row(row_dict)
                if obj:
                    db.add(GHSClassification(**obj))
                    imported += 1
                else:
                    skipped += 1

        db.commit()
        log_audit(audit_db, current_user.id, "import", f"{library}_library", None, new_value={"imported": imported, "skipped": skipped})
        return {"message": f"Imported {imported} {library} records", "imported": imported, "skipped": skipped}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import error: {str(e)}")
    finally:
        db.close()
        audit_db.close()


def _build_substance_from_row(row):
    name = _find_value(row, ["name", "substance_name", "chemical_name"])
    if not name:
        return None
    return {
        "name": name,
        "cas_number": _find_value(row, ["cas_number", "cas", "cas_no"]),
        "ec_number": _find_value(row, ["ec_number", "ec", "ec_no"]),
        "iupac_name": _find_value(row, ["iupac_name", "iupac"]),
        "molecular_formula": _find_value(row, ["molecular_formula", "formula"]),
        "registration_status": _find_value(row, ["registration_status", "status"]),
        "source_url": _find_value(row, ["source_url", "url", "link"]),
    }


def _build_cmr_from_row(row):
    name = _find_value(row, ["name", "substance_name"])
    if not name:
        return None
    return {
        "name": name,
        "cas_number": _find_value(row, ["cas_number", "cas", "cas_no"]),
        "ec_number": _find_value(row, ["ec_number", "ec", "ec_no"]),
        "cmr_type": _find_value(row, ["cmr_type", "type"]),
        "cmr_category": _find_value(row, ["cmr_category", "category"]),
        "hazard_class": _find_value(row, ["hazard_class"]),
        "hazard_statements": _find_value(row, ["hazard_statements", "h_statements"]),
        "clp_notes": _find_value(row, ["clp_notes", "notes"]),
        "atp_reference": _find_value(row, ["atp_reference", "atp"]),
    }


def _build_echa_from_row(row):
    name = _find_value(row, ["name", "substance_name"])
    if not name:
        return None
    return {
        "name": name,
        "cas_number": _find_value(row, ["cas_number", "cas", "cas_no"]),
        "ec_number": _find_value(row, ["ec_number", "ec", "ec_no"]),
        "reach_status": _find_value(row, ["reach_status", "status"]),
        "tonnage_band": _find_value(row, ["tonnage_band", "tonnage"]),
        "registration_type": _find_value(row, ["registration_type"]),
        "index_number": _find_value(row, ["index_number"]),
        "clp_notes": _find_value(row, ["clp_notes", "notes"]),
        "atp_reference": _find_value(row, ["atp_reference", "atp"]),
    }


def _build_clp_from_row(row):
    name = _find_value(row, ["name", "substance_name"])
    if not name:
        return None
    return {
        "name": name,
        "cas_number": _find_value(row, ["cas_number", "cas", "cas_no"]),
        "ec_number": _find_value(row, ["ec_number", "ec", "ec_no"]),
        "hazard_class": _find_value(row, ["hazard_class"]),
        "hazard_category": _find_value(row, ["hazard_category", "category"]),
        "hazard_statement_code": _find_value(row, ["hazard_statement_code", "h_code"]),
        "hazard_statement": _find_value(row, ["hazard_statement"]),
        "p_statements": _find_value(row, ["p_statements", "precautionary_statements"]),
        "signal_word": _find_value(row, ["signal_word"]),
        "pictograms": _find_value(row, ["pictograms", "pictogram_codes"]),
        "concentration_limit": _find_value(row, ["concentration_limit"]),
        "m_factor": _find_value(row, ["m_factor"]),
    }


def _build_ghs_from_row(row):
    name = _find_value(row, ["name", "substance_name"])
    if not name:
        return None
    return {
        "name": name,
        "cas_number": _find_value(row, ["cas_number", "cas", "cas_no"]),
        "ec_number": _find_value(row, ["ec_number", "ec", "ec_no"]),
        "ghs_hazard_class": _find_value(row, ["ghs_hazard_class", "hazard_class"]),
        "ghs_category": _find_value(row, ["ghs_category", "category"]),
        "pictogram_codes": _find_value(row, ["pictogram_codes", "pictograms"]),
        "signal_word": _find_value(row, ["signal_word"]),
        "hazard_statements": _find_value(row, ["hazard_statements"]),
        "precautionary_statements": _find_value(row, ["precautionary_statements"]),
    }


def _find_value(row, columns):
    for col in columns:
        if col in row and row[col]:
            return row[col]
    return None


# ======================================================================
# Export / Download — CSV/Excel for each library
# ======================================================================

EXPORT_COLUMNS = {
    "substance": ["id", "name", "cas_number", "ec_number", "iupac_name", "molecular_formula", "registration_status", "source_url", "notes"],
    "cmr": ["id", "substance_id", "cas_number", "ec_number", "name", "cmr_type", "cmr_category", "hazard_class", "hazard_statements", "clp_notes", "atp_reference", "source_url"],
    "echa": ["id", "substance_id", "cas_number", "ec_number", "name", "reach_status", "tonnage_band", "registration_type", "index_number", "clp_notes", "atp_reference", "source_url"],
    "clp": ["id", "substance_id", "cas_number", "ec_number", "name", "hazard_class", "hazard_category", "hazard_statement_code", "hazard_statement", "p_statements", "signal_word", "pictograms", "concentration_limit", "m_factor"],
    "ghs": ["id", "substance_id", "cas_number", "ec_number", "name", "ghs_hazard_class", "ghs_category", "pictogram_codes", "signal_word", "hazard_statements", "precautionary_statements"],
}


@router.get("/export/{library}")
async def export_library(
    library: str,
    format: str = Query("csv"),
    current_user: InternalUser = Depends(get_current_user)
):
    if library not in EXPORT_COLUMNS:
        raise HTTPException(status_code=400, detail="Library must be one of: substance, cmr, echa, clp, ghs")

    if pd is None:
        raise HTTPException(status_code=500, detail="pandas not installed")

    from fastapi.responses import StreamingResponse
    import io

    db = pipeline_get_db()
    try:
        model_map = {
            "substance": SubstanceLibrary,
            "cmr": CMRSubstance,
            "echa": ECHASubstance,
            "clp": CLPClassification,
            "ghs": GHSClassification,
        }
        Model = model_map[library]
        items = db.query(Model).all()

        columns = EXPORT_COLUMNS[library]
        data = []
        for item in items:
            row = {}
            for col in columns:
                val = getattr(item, col, None)
                if val is None:
                    row[col] = ""
                elif isinstance(val, datetime):
                    row[col] = val.isoformat()
                else:
                    row[col] = str(val)
            data.append(row)

        df = pd.DataFrame(data, columns=columns)
        buffer = io.BytesIO()

        if format.lower() == "xlsx":
            df.to_excel(buffer, index=False, engine="openpyxl")
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"{library}_export.xlsx"
        else:
            df.to_csv(buffer, index=False)
            media_type = "text/csv"
            filename = f"{library}_export.csv"

        buffer.seek(0)
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            buffer,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    finally:
        db.close()


# ======================================================================
# Scraper / Auto-Sync Endpoints
# ======================================================================

class SyncRequest(BaseModel):
    datasets: Optional[List[str]] = None
    dry_run: bool = False

@router.post("/sync")
async def sync_echa_data(
    body: SyncRequest,
    current_user: InternalUser = Depends(get_current_user)
):
    """Manually trigger ECHA data sync. Admin only."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can trigger ECHA sync")

    try:
        from echa_scraper import run_scraper, ECHA_DOWNLOADS
    except ImportError:
        from backend.echa_scraper import run_scraper, ECHA_DOWNLOADS

    valid_keys = list(ECHA_DOWNLOADS.keys())
    if body.datasets:
        invalid = [d for d in body.datasets if d not in valid_keys]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid datasets: {invalid}. Valid: {valid_keys}")

    try:
        results = run_scraper(datasets=body.datasets or valid_keys, dry_run=body.dry_run)
        return {
            "message": "ECHA sync completed",
            "dry_run": body.dry_run,
            "results": results
        }
    except Exception as e:
        logger.error(f"ECHA sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/sync/status")
async def sync_status(current_user: InternalUser = Depends(get_current_user)):
    """Get available datasets and scraper status."""
    try:
        from echa_scraper import ECHA_DOWNLOADS
    except ImportError:
        from backend.echa_scraper import ECHA_DOWNLOADS

    return {
        "datasets": [
            {
                "key": k,
                "name": v["name"],
                "format": v.get("format", "unknown"),
                "has_url": v.get("url") is not None or v.get("fallback_url") is not None,
                "source_url": v.get("source_url"),
            }
            for k, v in ECHA_DOWNLOADS.items()
        ],
        "scheduler_running": False,  # Will be updated by main.py
        "next_run": "Sundays 02:00 UTC"
    }
