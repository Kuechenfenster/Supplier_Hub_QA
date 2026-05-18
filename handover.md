# Handover — Supplier Material Registration Module

**Date**: 2026-05-18  
**Scope**: Full implementation of a "Raw Material & Supplier Registration Module" for the Supplier Hub platform, including database schema, backend API, and frontend wizard.

---

## Original Request Summary

Build a standalone supplier self-registration portal where external factories register themselves and their raw materials, collecting technical metadata for EU regulatory compliance (REACH, RoHS, SVHC).

Key requirements:
1. **Supplier & Commercial Profile** (Name, Country, Sales/QM Contacts, Facility Address)
2. **Raw Material Identifiers** (Commercial name, internal SKU, supplier code)
3. **Document Upload Vault** (SDS, TDS, CoA, REACH/RoHS, Food Contact DoC) with metadata and 3-year SDS expiry check
4. **4-step wizard UX** ([1.Profile] → [2.Materials] → [3.Documents] → [4.Review & Submit])

---

## Files Changed

| File | Action | Description |
|---|---|---|
| `backend/models.py` | **Modified** | Added `SupplierRegistration`, `MaterialRegistration`, `SupplierDocument` ORM models |
| `backend/registration_routes.py` | **New** | 11 API endpoints under `/api/registration/` |
| `backend/main.py` | **Modified** | Registered router, added `/supplier-registration` frontend route, added startup column migrations |
| `backend/migrate.py` | **Modified** | Added CREATE TABLE + ALTER COLUMN migrations for PostgreSQL |
| `backend/entrypoint.sh` | **Modified** | Added `python backend/migrate.py` before `init_db.py` |
| `static/supplier-registration.html` | **New** | 4-step wizard SPA with drag-drop file upload |
| `static/supplier-dashboard.html` | **Modified** | Wired "Material Suppliers" sidebar panel to registration API |
| `postgres-init/02-registration-fix.sql` | **New** | Standalone SQL migration for manual production fix |

---

## Database Schema (3 new tables)

### `supplier_registrations`
- `id` SERIAL PK, `supplier_id` FK → suppliers(unique)
- **Profile**: `name_en` VARCHAR(255) NOT NULL, `name_cn` VARCHAR(255), `material_origin` VARCHAR(100), `facility_address` TEXT NOT NULL
- **Sales Contact** (all nullable): `sales_contact_name/email/phone`
- **QM Contact** (all nullable): `qm_contact_name/email/phone`
- `registration_status` VARCHAR(20): draft → submitted → under_review → approved → rejected

### `material_registrations`
- `id` SERIAL PK, `registration_id` FK → supplier_registrations
- `commercial_material_name` VARCHAR(255) NOT NULL
- `internal_factory_material_code` VARCHAR(100) NOT NULL (our SKU)
- `supplier_material_code` VARCHAR(100) NOT NULL (vendor's catalog ID)
- `is_food_contact` BOOLEAN DEFAULT FALSE
- UNIQUE INDEX on `(registration_id, supplier_material_code)`

### `supplier_documents`
- `id` SERIAL PK, `registration_id` FK, `material_id` FK
- `document_type` VARCHAR(30): sds / tds / coa / reach_rohs / food_contact_doc
- `file_path`, `original_filename`, `file_size_bytes`
- **Type-specific columns**: `sds_language`, `sds_issue_date`, `sds_expiry_warning`, `tds_physical_state`, `coa_test_date`

---

## API Endpoints (`/api/registration/`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/metadata/lookup` | GET | Returns country names, SDS languages, physical state options |
| `/draft` | GET | Loads supplier's current draft with nested materials & documents |
| `/step1-profile` | POST | Saves supplier profile (FormData) |
| `/step2-materials` | POST | Saves material identifiers (JSON payload) |
| `/step3-documents` | POST | Bulk document upload with metadata |
| `/step3-documents/single` | POST | Single document upload with type-specific metadata |
| `/submit` | POST | Validates and submits registration (blocks if SDS > 3 years) |
| `/document/{id}/download` | GET | Download uploaded file (supplier-scoped access) |
| `/document/{id}` | DELETE | Remove document + file from disk |
| `/material/{id}` | DELETE | Remove material + all associated documents |

---

## Revisions from User Feedback

### 1. Material Origin → Full Country Names, Optional
- Changed from ISO 2-letter codes (`CN`, `DE`) to full country names (`China`, `Germany`)
- Column widened from `VARCHAR(2)` to `VARCHAR(100)`
- Made nullable (not mandatory)
- **Migration**: `ALTER TABLE supplier_registrations ALTER COLUMN material_origin TYPE VARCHAR(100)`

### 2. Sales Contact → Optional
- All three `sales_contact_*` columns made nullable
- Frontend validation removed (email/phone checks only run if value provided)
- **Migration**: `ALTER TABLE ... ALTER COLUMN sales_contact_* DROP NOT NULL`

### 3. Document Uploads → All Optional
- All `File(...)` params changed to `File(None)`
- Submit validation no longer requires SDS/TDS/CoA/REACH-RoHS documents
- Only Food Contact DoC remains conditional (required when FCM checkbox is checked)
- Frontend: removed "MISSING" warnings, changed to `—` for absent docs

### 4. Dashboard Improvements
- Changed from inline card view to **table view** with columns: Material Name, Internal Code, Supplier Code, Food Contact, Docs count
- **Edit** button per material → opens registration wizard in new window
- **Deactivate** button → confirms then calls `DELETE /api/registration/material/{id}`
- **"Register New Supplier"** button → opens `/supplier-registration` in **new browser tab** (`window.open(..., '_blank')`)
- **"+ Add New Material"** button (green) → appears when registration already exists, also opens wizard in new tab

### 5. PostgreSQL Column Migration Fix
- Production DB had `material_origin VARCHAR(2)` → inserts of full country names failed with `DataError`
- Root cause: SQLAlchemy `create_all()` doesn't ALTER existing columns; `migrate.py` wasn't called in `entrypoint.sh`
- **Fix**: Added `ALTER TABLE` statements directly in `main.py` startup (runs synchronously with app on every deploy)

### 6. JS Syntax Error Fix (Dashboard)
- Edit produced duplicate/orphaned code (87 lines of repeated function body after `escHtml`)
- Caused `SyntaxError: Unexpected token '}'` → entire page failed to load
- Removed duplicates; validated with `node --check`

---

## Known Caveats

1. **Production deployment requires the app to restart** for the `ALTER TABLE` statements in `main.py` startup to execute. If the column was already `VARCHAR(2)`, the migration widens it to `VARCHAR(100)`.
2. **File storage is local filesystem** (`backend/data/registrations/`). No cloud storage (S3, etc.) configured.
3. **Local dev uses SQLite by default**. Set `DATABASE_URL=postgresql://supplier:supplier123@localhost:5432/supplier_hub` to use the Docker PostgreSQL.
4. **Food Contact DoC is the only document that blocks submission** when the FCM checkbox is checked. All other documents (SDS, TDS, CoA, REACH/RoHS) are advisory.

---

## Frontend Locations

- **Registration Wizard**: `/supplier-registration`
- **Dashboard Material Suppliers Panel**: `/supplier-dashboard` → sidebar "Material Suppliers"
- **Supplier Login**: `/supplier-login`