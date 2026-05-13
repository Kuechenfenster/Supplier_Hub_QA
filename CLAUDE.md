# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Supplier Hub is a supplier management system for cosmetic raw materials compliance. It includes:
- **Management Portal** - Admin dashboard for user, supplier, and compliance management
- **Supplier Portal** - Factory/supplier registration and materials submission
- **Pipeline** - BOM processing and lab report extraction with AI/LLM

## Architecture

### Two-Database Setup

1. **supplier_hub** - Application database (users, departments, suppliers, audit log)
2. **hti_pipeline** - Material library database (manufacturers, materials, BOM records, compliance checks)

### Key Relationships

```
Manufacturer → Supplier → Material (3-tier hierarchy)
InternalUser → Department (one-to-many)
InternalUser → AuditLog (one-to-many)
```

## Directory Structure

```
backend/
├── main.py              # FastAPI app entry point
├── models.py            # Application database models (supplier_hub)
├── auth_helpers.py      # JWT, password hashing, audit logging
├── bom_routes.py        # BOM upload and lab extraction endpoints
├── init_db.py           # Database initialization
├── migrate.py           # Database migration script
└── pipeline/            # Material intelligence pipeline
    ├── config.py        # Configuration, column mappings, compliance rules
    ├── database.py      # Pipeline database models (hti_pipeline)
    ├── models/
    │   ├── schemas.py   # Pydantic validation schemas
    │   └── database.py  # Pipeline database models (alias)
    └── ingest/          # Data ingestion modules
        ├── bom_cleaner.py
        └── lab_extractor.py
static/                  # Static HTML frontend files
```

## Getting Started

### Running Locally (without Docker)

```bash
# Install dependencies
pip install -r backend/requirements.txt
pip install pandas openpyxl requests pymupdf

# Initialize database and start server
python run.py
```

The server will run on **http://localhost:9000**

### Docker Commands

```bash
# Start services
docker compose up -d --build

# Stop services
docker compose down

# View logs
docker compose logs -f web
docker compose logs -f db

# Access database
docker compose exec db psql -U supplier -d supplier_hub
docker compose exec db psql -U supplier -d hti_pipeline

# Reset (deletes data!)
docker compose down -v
```

### Admin Setup

1. Login at http://localhost:9000/management-login
2. Admin credentials: `admin` / `master1312` (change after first login)

**Note for Local Development:** The application uses SQLite by default (`backend/db/supplier_hub.db` and `backend/db/hti_pipeline.db`). For Docker deployment, PostgreSQL is used.

### Environment Variables

```yaml
# Application Database
DATABASE_URL: postgresql://supplier:supplier123@db:5432/supplier_hub

# Pipeline Database
PIPELINE_DATABASE_URL: postgresql://supplier:supplier123@db:5432/hti_pipeline

# Authentication
JWT_SECRET: change-this-secret-in-production
JWT_EXPIRY: "3600"

# AI/LLM (Lab Report Extraction)
OLLAMA_HOST: http://host.docker.internal:11434
OLLAMA_MODEL: qwen3.5:4b
```

## API Endpoints

### Authentication
- `POST /api/auth/login` - Login (returns JWT token)
- `GET /api/auth/me` - Get current user info

### User Management (Admin/Manager)
- `GET /api/admin/users` - List users
- `POST /api/admin/users` - Create user
- `PUT /api/admin/users/{id}` - Update user
- `DELETE /api/admin/users/{id}` - Delete user (soft delete)

### Department Management
- `GET /api/admin/departments` - List departments
- `POST /api/admin/departments` - Create department
- `PUT /api/admin/departments/{id}` - Update department

### Supplier Management
- `GET /api/suppliers` - List suppliers
- `POST /api/suppliers` - Create supplier

### Dashboard
- `GET /api/admin/dashboard/stats` - Summary statistics
- `GET /api/admin/dashboard/activity` - Recent activity

### Dashboard Stats (Supplier Portal)
- **Active Products** - Live on market
- **Registered Suppliers** - Factory partners
- **Registered Materials** - Total products
- **Registered Substances** - CAS substances
- **Missing Seal Sample** - Products without sample (red when ≥1, blue when 0)

### Dashboard Stats (Management Portal)
- **Total Suppliers** - All registered suppliers
- **Active Suppliers** - Active status suppliers
- **Seal Sample** - Missing seal samples (red when ≥1)
- **VCM CAP** - Missing VCM CAP documents (red when ≥1)
- **QC CAP** - Missing QC CAP documents (red when ≥1)

### BOM Pipeline
- `GET /api/bom/template` - Download template (CSV/XLSX)
- `POST /api/bom/upload` - Upload and process BOM
- `GET /api/bom/records` - List BOM records
- `GET /api/bom/materials` - List materials
- `GET /api/bom/manufacturers` - List manufacturers

### Lab Report Extraction
- `POST /api/bom/lab-reports/extract` - Extract from PDF
- `GET /api/bom/lab-reports` - List extracted reports

## Development Workflow

### Adding a Database Migration

1. Edit `backend/migrate.py` - add SQL to migrations list
2. Run in container: `python backend/migrate.py`

### Adding a New API Endpoint

1. Add route to appropriate file (`main.py`, `bom_routes.py`)
2. Use `@app.get()`, `@app.post()`, etc. decorators
3. Add database model in `models.py` or `pipeline/models/database.py`
4. Create migration if adding new table

### Common Tasks (Local)

```bash
# Initialize database
python backend/init_db.py

# Start server
python run.py

# Force admin initialization
python backend/force_init.py

# Run migrations
python backend/migrate.py
```

### Common Tasks (Docker)

```bash
# Rebuild after code changes
docker compose up -d --build
```

## User Interface

### Supplier Portal - Bilingual Support

The Supplier Portal supports **English (default)** and **Mandarin (中文)**.

- Language selection is available in the top navigation bar
- Selection persists in browser `localStorage`
- All UI elements (sidebar, stats, sections) translate automatically

## User Roles

| Role | Permissions |
|------|-------------|
| **Admin** | Full system access, user management, password resets |
| **Manager** | Manage assigned suppliers, view team data |
| **QA** | Materials compliance, formulation approval |
| **Viewer** | Read-only access to assigned data |

## Security Features

- Invitation-only registration via invitation codes
- Password hashing with bcrypt
- JWT authentication with configurable expiry
- Soft delete for users (is_active flag)
- Audit logging for all admin actions

## Pipeline Details

### BOM Processing Workflow

1. Download template → Fill Excel → Upload BOM → Auto-process → Save to database
2. Column names are auto-mapped using fuzzy matching against 50+ variant names
3. Inserts/updates: Manufacturers, Suppliers, MaterialLibrary, BOMRecord
4. Files: `backend/pipeline/ingest/bom_cleaner.py` processes and validates

### Lab Report Extraction (AI-Powered)

1. Upload PDF → Convert to image → Send to Ollama (qwen3.5:4b with vision) → Parse JSON → Save
2. Two modes: Vision (PDF as image) or Text (extracted text fallback)
3. Auto-detects report type (EN 71-3, GHS, or general)
4. Saves: TestHistory (migration results), SubstanceBreakdown (CAS composition), ComplianceCheck
5. Files: `backend/pipeline/ingest/lab_extractor.py` handles extraction and DB persistence

### Compliance Automation

- **EN 71-3 Toy Directive**: Migration limits for 8 heavy metals (Pb, Cd, Hg, etc.)
- **REACh Regulation**: SVHC screening, Annex XVII restrictions
- **GHS Classification**: Section 3 (composition) and Section 14 (transport) extraction
- **Internal Standards**: Custom limits and category-based thresholds

## Database Models

### Application (supplier_hub)
- `InternalUser` - Admin/staff users with roles
- `Department` - Organizational departments
- `Supplier` - Registered suppliers
- `AuditLog` - Activity tracking

### Pipeline (hti_pipeline)
- `Manufacturer` - Raw material makers
- `Supplier` - Material suppliers (different schema)
- `MaterialLibrary` - Internal material database
- `SubstanceBreakdown` - CAS-level composition
- `MaterialDocument` - File attachments
- `ComplianceCheck` - REACh/Toy Directive results
- `BOMRecord` - Standardized BOM entries
- `RiskAlert` - Flagged compliance issues
- `TestHistory` - Lab report test results
