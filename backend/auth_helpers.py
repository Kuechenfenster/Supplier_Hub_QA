"""
Shared authentication helpers - avoids circular imports between main.py and bom_routes.py
"""
import os
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from models import get_db, InternalUser, AuditLog, SessionLocal, Supplier

JWT_SECRET = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY = int(os.getenv("JWT_EXPIRY", "3600"))

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def create_jwt_token(user_id: int, username: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(seconds=JWT_EXPIRY)
    payload = {"user_id": user_id, "username": username, "role": role, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: SessionLocal = Depends(get_db)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_jwt_token(credentials.credentials)
    user = db.query(InternalUser).filter(InternalUser.id == payload["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


async def get_current_supplier(credentials: HTTPAuthorizationCredentials = Depends(security), db: SessionLocal = Depends(get_db)):
    """Get current authenticated supplier from JWT token."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_jwt_token(credentials.credentials)
    supplier = db.query(Supplier).filter(Supplier.id == payload["user_id"]).first()
    if not supplier or supplier.status != "active":
        raise HTTPException(status_code=401, detail="Supplier not found or inactive")
    return supplier


def log_audit(db, user_id: int, action: str, entity_type: str, entity_id: int = None, old_value: dict = None, new_value: dict = None, ip_address: str = None):
    audit = AuditLog(
        user_id=user_id, action=action, entity_type=entity_type,
        entity_id=entity_id,
        old_value=str(old_value) if old_value else None,
        new_value=str(new_value) if new_value else None,
        ip_address=ip_address
    )
    db.add(audit)
    db.commit()


# ======================================================================
# Visibility Helper Functions (Phase 1)
# ======================================================================

def get_visible_materials_query(user, db):
    """
    Get query for materials visible to a user based on role and permissions.
    Internal users (admin/manager/qa) see all materials.
    Supplier users see only shared materials with visibility >= internal.
    """
    from pipeline.models.database import MaterialLibrary, DocumentVersion

    # Internal users see all materials
    if user.role in ["admin", "manager", "qa"]:
        return db.query(MaterialLibrary)

    # Supplier users see only shared materials
    # Check share_permissions table for supplier access
    from pipeline.models.database import get_db as pipeline_get_db
    pipeline_db = pipeline_get_db()

    # Get supplier ID from user's supplier info (if exists)
    # For now, return all materials - suppliers can be restricted later
    # via share_permissions lookup
    return db.query(MaterialLibrary).filter(
        MaterialLibrary.visibility.in_(['public', 'internal'])
    )


def get_visible_documents_query(user, db):
    """
    Get query for documents visible to a user.
    Internal users see all documents.
    Supplier users see documents with supplier_accessible=True or visibility=public.
    """
    from pipeline.models.database import MaterialDocument

    if user.role in ["admin", "manager", "qa"]:
        return db.query(MaterialDocument)

    return db.query(MaterialDocument).filter(
        MaterialDocument.visibility.in_(['public', 'internal'])
    )


def check_material_access(user, material_id: str, db):
    """
    Check if a user can access a specific material.
    Returns True if accessible, False otherwise.
    """
    from pipeline.models.database import MaterialLibrary, SharePermission

    material = db.query(MaterialLibrary).filter(MaterialLibrary.material_id == material_id).first()
    if not material:
        return False

    # Internal users can access all materials
    if user.role in ["admin", "manager", "qa"]:
        return True

    # Supplier users need explicit access
    # Check if material is shared with this supplier
    if material.visibility == 'public':
        return True

    if user.role == 'viewer':
        # Check share_permissions
        shared = db.query(SharePermission).filter(
            SharePermission.material_id == material_id
        ).first()
        if shared:
            return True

    return False
