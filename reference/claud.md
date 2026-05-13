# HTI Portal — Current Functions & System State

> **Generated:** 2026-04-30  
> **Based on:** Live codebase audit of `/a0/usr/projects/hti_portal`  
> **Purpose:** Snapshot of what is implemented, how it works, and what remains to be built.

---

## 1. Project Overview

The HTI Portal ("Material Compliance & Supplier Hub") is a compliance data pipeline and web portal for managing toy-manufacturing material data. The current implementation is a **backend-heavy Python pipeline** with a **static HTML mockup** for the frontend. It is in active development and not yet a fully deployed web application.

---

## 2. Technology Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Language** | Python | 3.x |
| **Data Processing** | pandas | >= 2.0 |
| **Excel I/O** | openpyxl | >= 3.1 |
| **ORM / Database** | SQLAlchemy 2.x + SQLite / PostgreSQL | >= 2.0 |
| **Validation** | Pydantic v2 | >= 2.0 |
| **AI / LLM** | Google Gemini API (via `google-generativeai`) | >= 0.7 |
| **Image Processing** | Pillow (PIL) | >= 10.0 |
| **PDF Parsing** | pypdf, pdf2image | >= 4.0 / >= 1.16 |
| **Templating** | Jinja2 | >= 3.1 |
| **File Watching** | watchdog | >= 3.0 |
| **Frontend** | Static HTML + CSS (mockup only) | — |
| **Icons** | Unicode emoji | — |

---

## 3. Repository Structure

```
/a0/usr/projects/hti_portal/
├── data/
│   ├── incoming/
│   │   ├── boms/                 # Drop-zone for BOM uploads
│   │   │   ├── bom_template.csv  # Canonical CSV template
│   │   │   ├── bom_template.xlsx # Canonical Excel template
│   │   │   └── sample_bom_messy.xlsx  # Test data with messy headers
│   │   └── lab_reports/          # Placeholder for lab test uploads
│   ├── processed/                # Archive for successfully ingested files
│   ├── reports/                  # Placeholder for generated reports
│   ├── bom_mockup.html           # UI concept / static mockup
│   ├── bom_mockup.png            # Screenshot of mockup
│   └── bom_template.csv          # Root-level copy of template
├── pipeline/                     # Core Python application
│   ├── config.py                 # Paths, column maps, compliance constants
│   ├── models/
│   │   ├── database.py           # SQLAlchemy ORM models + DB engine
│   │   └── schemas.py            # Pydantic validation schemas (DTOs)
│   ├── ingest/
│   │   └── bom_cleaner.py        # BOM ingestion, cleaning, DB persistence
│   ├── logic/                    # (empty placeholder)
│   └── reporting/                # (empty placeholder)
├── db/
│   └── material_library.db       # SQLite development database
├── tests/
│   └── __init__.py               # (empty)
├── logs/                         # Runtime logs
└── requirements.txt              # Python dependencies
```

---

## 4. Implemented Modules

### 4.1 Configuration (`pipeline/config.py`)

**What it does:**
- Defines all filesystem paths (`data/incoming`, `data/processed`, `db/`, `logs/`)
- Sets database URL (PostgreSQL default, SQLite fallback possible)
- Stores Google AI API key + Gemini model name
- Maintains `BOM_COLUMN_MAP`: a 30+ entry dictionary mapping messy column names to canonical fields
- Defines `BOM_REQUIRED_COLUMNS`: `material_id`, `material_name`, `manufacturer_name`, `supplier_id`, `sku`
- Hard-codes EN 71-3 migration limits:
  - Category I (dry/brittle): 60.0 mg/kg
  - Category II (liquid/sticky): 300.0 mg/kg
  - Category III (scraped-off): 15.0 mg/kg
- Defines alert severity mapping
- Sets test validity period: 12 months

**Key constants:**
```python
TEST_VALIDITY_MONTHS = 12
EN71_3_MIGRATION_LIMITS = {"I": 60.0, "II": 300.0, "III": 15.0}
```

### 4.2 Database Schema (`pipeline/models/database.py`)

**Engine:** SQLAlchemy 2.x with `declarative_base()`. Supports both PostgreSQL (`postgresql://supplier:supplier123@localhost:5432/hti_pipeline`) and SQLite (local dev).

**8 tables are fully modeled:**

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `manufacturers` | Raw material makers | `manufacturer_id`, `name`, `code`, `country`, `website` |
| `suppliers` | Direct vendors (linked to manufacturer) | `supplier_id`, `name`, `status`, `manufacturer_id` FK |
| `material_library` | Master material DNA | `material_id`, `name`, `CAS`, `GHS`, `EN71-3 cat`, `REACh`, `status` |
| `substance_breakdown` | CAS-level decomposition | `material_id` FK, `cas_number`, `concentration_min/max/typical`, `svhc` |
| `material_documents` | Uploaded file metadata | `material_id` FK, `document_type` (sds/tds/coa/etc), `file_path`, `valid_until` |
| `compliance_checks` | Per-material regulation checks | `material_id` FK, `regulation`, `check_type`, `result` (pass/fail/review/exempt) |
| `bom_records` | Standardized BOM line items | `bom_id`, `sku`, `material_id` FK, `quantity`, `unit`, `is_sub_supplier` |
| `risk_alerts` | Flagged compliance issues | `material_id` FK, `alert_type`, `severity` (high/medium/low), `resolved` |

**Relationships:**
- `Manufacturer` 1 → N `Supplier`
- `Supplier` 1 → N `MaterialLibrary`
- `MaterialLibrary` 1 → N `SubstanceBreakdown`, `MaterialDocument`, `ComplianceCheck`, `BOMRecord`, `RiskAlert`

### 4.3 Pydantic Schemas (`pipeline/models/schemas.py`)

**Pydantic v2 models for every table:**
- `ManufacturerBase / Create / Read`
- `SupplierBase / Create / Read`
- `MaterialLibraryBase / Create / Read`
- `BOMRecordBase / Create / Read` (incl. extended fields for manufacturer/supplier/part-spec)
- `SubstanceBreakdownBase / Create / Read`
- `ComplianceCheckBase / Create / Read`
- `RiskAlertBase / Create / Read`
- `BOMCleanResult` — aggregate DTO returned by the cleaner

**Validation rules include:**
- Regex patterns for `status`, `material_type`, `result`, `alert_type`, `severity`
- Length limits on all string fields
- Positive-or-zero floats for concentrations and quantities

### 4.4 BOM Cleaner (`pipeline/ingest/bom_cleaner.py`)

**Current capabilities:**

| Feature | Status |
|---------|--------|
| Read `.xlsx`, `.xls`, `.csv` files | ✅ Implemented |
| Auto-map messy column names via fuzzy/partial matching | ✅ Implemented |
| Validate required columns | ✅ Implemented |
| Detect duplicate mappings | ✅ Implemented |
| Clean material IDs (uppercase, normalize whitespace) | ✅ Implemented |
| Clean SKUs and supplier IDs | ✅ Implemented |
| Handle `is_sub_supplier` boolean parsing | ✅ Implemented |
| Skip rows with missing required fields | ✅ Implemented |
| Generate `bom_id` (`BOM-YYYYMMDD-<stem>`) | ✅ Implemented |
| Build `BOMCleanResult` with full metadata | ✅ Implemented |
| **Persist to database** (`save_to_database`) | ✅ Implemented |
| Auto-create missing manufacturers | ✅ Implemented |
| Auto-create missing suppliers | ✅ Implemented |
| Upsert materials into `material_library` | ✅ Implemented |
| Insert BOM records | ✅ Implemented |
| Process entire folder of BOM files | ✅ Implemented |
| Move processed files to `data/processed/` | ✅ Implemented |
| CLI entry point (`__main__`) | ✅ Implemented |

**Functions:**
- `clean_bom(file_path, ...)` — main single-file processor
- `process_bom_folder(folder_path)` — batch processor
- `save_to_database(result)` — persistence layer
- `normalize_column_name()` / `map_columns()` / `validate_bom()` — helper utilities

**CLI arguments supported:**
```bash
python -m pipeline.ingest.bom_cleaner <file> [--bom-id] [--sku] [--product] [--version] [--sheet] [--dry-run]
python -m pipeline.ingest.bom_cleaner --folder <path>
```

### 4.5 UI Mockup (`data/bom_mockup.html`)

**What exists:** A single-page, static HTML/CSS prototype demonstrating the desired UI. **Not a functional app.**

**Visual elements:**
- Header bar with logo "HTI Portal — Material Compliance" and user avatar
- Left sidebar navigation (6 sections, 12 menu items)
- KPI stat cards (Materials, Manufacturers, Suppliers, Sub-Supplier, Pending, Approved)
- Drag-and-drop upload zone with template download buttons
- BOM data table with:
  - Material ID, Name, Part Spec, Manufacturer, Mfg Code, Supplier
  - Supplier Material ID, Sub-Supplier checkbox, Type, Qty, Role
  - Document icons (SDS/TDS/Drawing/CoA) with missing-state styling
  - Status tags (Approved, Review, Flag)
- Manufacturer → Sub-supplier hierarchy visualization inline
- Legend / key card explaining all symbols

**Color theme:**
- Primary dark navy: `#0d1b2a`
- Accent cyan: `#4fc3f7`
- Status colors: green (approved), amber (review), red (flag)

---

## 5. Current Data Flow (Implemented)

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Supplier drops  │────▶│ BOM Cleaner      │────▶│ SQLite /        │
│ .xlsx / .csv   │     │ (bom_cleaner.py) │     │ PostgreSQL      │
│ into data/       │     │                  │     │                 │
│ incoming/boms/   │     │ • Map columns    │     │ • manufacturers │
└─────────────────┘     │ • Validate       │     │ • suppliers     │
                        │ • Clean values   │     │ • material_library
                        │ • Upsert DB      │     │ • bom_records   │
                        └──────────────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │ Move file to     │
                        │ data/processed/  │
                        └──────────────────┘
```

---

## 6. What Is Currently Working

| Capability | State |
|------------|-------|
| BOM ingestion from Excel/CSV with fuzzy column mapping | ✅ Functional |
| SQLite local database creation and queries | ✅ Functional |
| Manufacturer / Supplier auto-creation on BOM import | ✅ Functional |
| Material library upsert (insert or update) | ✅ Functional |
| BOM record storage with version tracking | ✅ Functional |
| CLI for single-file and batch processing | ✅ Functional |
| Configuration-driven compliance constants (EN 71-3) | ✅ Defined |
| Static HTML UI mockup for stakeholder review | ✅ Exists |
| Pydantic input validation schemas | ✅ Complete for all tables |

---

## 7. What Is Partially Built / Placeholder

| Module | State | Notes |
|--------|-------|-------|
| `pipeline/logic/__init__.py` | 🟡 Empty | Business logic layer not yet populated |
| `pipeline/reporting/__init__.py` | 🟡 Empty | Report generators not yet built |
| `tests/` | 🟡 Empty | No unit or integration tests written |
| Web API / backend server | 🔴 Missing | No FastAPI/Flask/Django app exists yet |
| Authentication / users | 🔴 Missing | No user model or login system |
| Document upload handler | 🔴 Missing | File upload endpoint not built |
| AI extraction (Gemini) | 🔴 Missing | API key is configured but no extraction code exists |
| Risk alert generator | 🔴 Missing | Schema exists, no generation logic yet |
| Compliance check engine | 🔴 Missing | Rules defined, no automated checking implemented |
| Dashboard / reporting UI | 🔴 Missing | Only static mockup exists |
| Email / notification service | 🔴 Missing | Not implemented |
| Watchdog background worker | 🔴 Missing | `watchdog` in requirements but unused |

---

## 8. Current Database Content

The SQLite file `db/material_library.db` exists but its population status depends on whether `bom_cleaner.py` has been executed against test data. The `sample_bom_messy.xlsx` file is provided for testing the ingestion pipeline.

---

## 9. Configuration Reference

### 9.1 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `PIPELINE_DATABASE_URL` | `postgresql://supplier:supplier123@localhost:5432/hti_pipeline` | Production DB connection |
| `GOOGLE_AI_API_KEY` | `