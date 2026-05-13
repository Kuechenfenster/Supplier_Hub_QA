# HTI Portal — Requirements Specification

> **Project:** HTI Portal — Material Compliance & Supplier Hub  
> **Version:** 1.0  
> **Date:** 2026-04-30  
> **Status:** Active Development

---

## 1. Executive Summary

The **HTI Portal** is a vendor / factory and customer-facing web application designed to manage material compliance data for toy and consumer-goods manufacturing. It centralizes Bill of Materials (BOM) ingestion, material library management, manufacturer/supplier hierarchies, compliance checking (REACh, EU Toy Directive, EN 71-3), risk alerting, and reporting into a single unified platform.

---

## 2. Stakeholders

| Role | Responsibility |
|------|----------------|
| **Quality / Compliance Teams** | Review materials, approve declarations, resolve risk alerts |
| **Suppliers / Vendors** | Upload BOMs, SDS/TDS/CoA documents, declare substance breakdowns |
| **Manufacturers** | Provide material specifications, CAS numbers, GHS classifications |
| **Internal Admins** | Manage users, configure compliance rules, run reports |
| **AI Pipeline** | Auto-extract data from documents, verify compliance, flag anomalies |

---

## 3. Functional Requirements

### 3.1 BOM Management (Bill of Materials)

| ID | Requirement | Priority |
|----|-------------|----------|
| BOM-01 | Support upload of `.xlsx`, `.xls`, and `.csv` BOM files via drag-and-drop UI | Must |
| BOM-02 | Auto-detect and map messy column names to standard schema using fuzzy matching | Must |
| BOM-03 | Validate required fields: `material_id`, `material_name`, `manufacturer_name`, `supplier_id`, `sku` | Must |
| BOM-04 | Support multi-sheet Excel files with configurable header row | Should |
| BOM-05 | Generate a unique `bom_id` per upload (format: `BOM-YYYYMMDD-<name>`) | Must |
| BOM-06 | Display upload progress, validation warnings, and skipped rows with reasons | Must |
| BOM-07 | Provide downloadable BOM templates (`.xlsx` and `.csv`) with correct headers | Must |
| BOM-08 | Allow manual BOM entry / editing for single-line corrections | Should |
| BOM-09 | Maintain BOM version history (`version` field) | Should |
| BOM-10 | Move successfully processed files to a `processed/` archive folder | Must |

**Standard BOM Columns:**
- `material_id` — Internal material code
- `material_name` / `component_name` — Human-readable name
- `manufacturer_name` — Raw material maker
- `manufacturer_code` — Mfg internal code
- `part_spec_name` — Part specification / drawing name
- `supplier_id` — Direct supplier code
- `supplier_material_id` — Supplier's own material code
- `sku` — Finished good / product SKU
- `quantity` + `unit` — Usage amount
- `component_role` — e.g., colorant, base, solvent, mechanical, electronic
- `material_type` — `substance` | `mixture` | `article`
- `is_sub_supplier` — Boolean flag for sub-supplier sourcing
- `sub_supplier_id` — Sub-supplier identifier

### 3.2 Material Library

| ID | Requirement | Priority |
|----|-------------|----------|
| MAT-01 | Store a master material record with CAS number, GHS classification, physical state | Must |
| MAT-02 | Categorize materials: `pigment`, `resin`, `solvent`, `packaging`, `additive`, `mechanical`, `electronic` | Must |
| MAT-03 | Track EN 71-3 toy safety category (`I` / `II` / `III`) and migration limits (mg/kg) | Must |
| MAT-04 | Track REACh status: `registered`, `pre-registered`, `exempt`, `svhc` | Must |
| MAT-05 | Support AI verification status: `unverified` / `verified` / `flagged` / `failed` | Must |
| MAT-06 | Allow manual override of AI-extracted fields by compliance officers | Must |
| MAT-07 | Full-text search across material names, CAS numbers, supplier codes | Should |
| MAT-08 | Link each material to its `supplier` and `manufacturer` | Must |
| MAT-09 | Support sub-supplier linkage (`sub_supplier_id`) | Must |
| MAT-10 | Internal approval workflow: `pending_review` → `approved` / `conditional` / `rejected` | Must |

### 3.3 Manufacturer & Supplier Management

| ID | Requirement | Priority |
|----|-------------|----------|
| MFG-01 | Maintain a Manufacturer directory (name, code, country, website, contact) | Must |
| MFG-02 | Maintain a Supplier directory linked to Manufacturer (3-tier hierarchy) | Must |
| MFG-03 | Track supplier status: `active` / `inactive` / `pending` | Must |
| MFG-04 | Allow multiple suppliers per manufacturer | Should |
| MFG-05 | Auto-create manufacturer/supplier entries on first BOM ingestion if missing | Must |
| MFG-06 | Display manufacturer → supplier → material hierarchy in BOM table | Should |

### 3.4 Substance Breakdown (CAS-Level)

| ID | Requirement | Priority |
|----|-------------|----------|
| SUB-01 | Decompose each material into constituent substances with CAS numbers | Must |
| SUB-02 | Record concentration ranges: `min`, `max`, `typical` (%) | Must |
| SUB-03 | Flag impurities separately (`is_impurity`) | Should |
| SUB-04 | Track source of data: `sds`, `tds`, `supplier_declaration`, `ai_extracted` | Must |
| SUB-05 | Mark SVHC (Substances of Very High Concern) and Annex XVII restrictions | Must |
| SUB-06 | Compare substance concentrations against regulatory limits automatically | Must |

### 3.5 Compliance Checking

| ID | Requirement | Priority |
|----|-------------|----------|
| CMP-01 | Auto-check against REACh regulations (SVHC screening, Annex XVII) | Must |
| CMP-02 | Auto-check against EU Toy Directive and EN 71-3 migration limits | Must |
| CMP-03 | Support internal company standards in addition to legal limits | Must |
| CMP-04 | Record check results: `pass`, `fail`, `review`, `exempt` | Must |
| CMP-05 | Store measured vs. limit values with units | Must |
| CMP-06 | Tag check source: `ai_check`, `manual`, `test_report` | Must |
| CMP-07 | Re-evaluate compliance when regulations update (e.g., new SVHC list) | Should |

**EN 71-3 Migration Limits (mg/kg):**
| Category | Description | Limit |
|----------|-------------|-------|
| I | Dry, brittle, powder-like | 60.0 |
| II | Liquid or sticky | 300.0 |
| III | Scraped-off | 15.0 |

### 3.6 Document Upload & Management

| ID | Requirement | Priority |
|----|-------------|----------|
| DOC-01 | Upload SDS (Safety Data Sheet), TDS (Technical Data Sheet), CoA, declarations, test reports, drawings | Must |
| DOC-02 | Attach documents to specific materials | Must |
| DOC-03 | Extract text/data from PDFs and images using AI (Gemini / OCR) | Must |
| DOC-04 | Track document validity (`valid_until`) and version | Should |
| DOC-05 | Flag expired documents in risk alerts | Must |
| DOC-06 | Support file types: `.pdf`, `.xlsx`, `.csv`, `.png`, `.jpg`, `.dwg` | Should |

### 3.7 Risk Alerts

| ID | Requirement | Priority |
|----|-------------|----------|
| ALR-01 | Auto-generate alerts for: missing SDS, expired test, SVHC found, REACh violation, internal standard fail | Must |
| ALR-02 | Severity levels: `high`, `medium`, `low` | Must |
| ALR-03 | Link alerts to specific `material_id`, `sku`, or `bom_id` | Must |
| ALR-04 | Provide resolution workflow (assign, comment, mark resolved) | Must |
| ALR-05 | Dashboard widget showing open alert count | Must |
| ALR-06 | Email / notification integration for high-severity alerts | Should |

### 3.8 Reporting & Dashboard

| ID | Requirement | Priority |
|----|-------------|----------|
| RPT-01 | Compliance summary per SKU / BOM (pass/fail/pending counts) | Must |
| RPT-02 | Material status overview (approved / conditional / rejected / pending) | Must |
| RPT-03 | Supplier performance scorecard (on-time docs, test validity, alert history) | Should |
| RPT-04 | Risk alert trend report (open vs. resolved over time) | Should |
| RPT-05 | Export reports to PDF and Excel | Should |
| RPT-06 | Real-time dashboard with KPI cards (materials, manufacturers, suppliers, alerts) | Must |

### 3.9 User Management & Access Control

| ID | Requirement | Priority |
|----|-------------|----------|
| USR-01 | Role-based access: Admin, Compliance Officer, Supplier, Viewer | Must |
| USR-02 | Suppliers can only see their own materials and BOMs | Must |
| USR-03 | Audit log for all data changes and approvals | Should |
| USR-04 | SSO / OAuth2 login support | Could |

### 3.10 AI Pipeline Integration

| ID | Requirement | Priority |
|----|-------------|----------|
| AI-01 | Use Google Gemini (or equivalent LLM) for document data extraction | Must |
| AI-02 | Auto-classify materials into `substance` / `mixture` / `article` | Should |
| AI-03 | Auto-suggest CAS numbers and substance names from SDS text | Should |
| AI-04 | Flag anomalies between declared and extracted data | Should |
| AI-05 | Provide confidence score for each AI extraction | Should |

---

## 4. Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NF-01 | **Security** — All file uploads scanned; sensitive data encrypted at rest | TLS 1.3, AES-256 |
| NF-02 | **Performance** — BOM upload of 1,000 rows processes in < 10 seconds | < 10s |
| NF-03 | **Availability** — 99.5% uptime during business hours | 99.5% |
| NF-04 | **Scalability** — Support 10,000 materials and 1,000 suppliers | 10k mats |
| NF-05 | **Data Retention** — Keep processed files and audit logs for 7 years | 7 years |
| NF-06 | **Compliance** — GDPR-ready data handling for EU suppliers | GDPR |
| NF-07 | **Browser Support** — Chrome, Firefox, Edge, Safari (last 2 versions) | Last 2 versions |
| NF-08 | **Responsive** — Sidebar + content layout works on 1440px+ desktops | 1440px+ |

---

## 5. Data & Integration Requirements

| ID | Requirement |
|----|-------------|
| DAT-01 | Primary database: PostgreSQL (production) with SQLite fallback (local dev) |
| DAT-02 | ORM: SQLAlchemy 2.x with Pydantic validation schemas |
| DAT-03 | File storage: local filesystem (dev) → S3-compatible (production) |
| DAT-04 | API: RESTful JSON API for all CRUD operations |
| DAT-05 | Integration: ECHA REACh API for SVHC list updates (future) |
| DAT-06 | Integration: Email service (SendGrid / AWS SES) for alerts (future) |
| DAT-07 | Integration: ERP connector for SKU and supplier master data (future) |

---

## 6. UI/UX Requirements

| ID | Requirement |
|----|-------------|
| UI-01 | Dark navy + cyan accent color theme (`#0d1b2a`, `#4fc3f7`) |
| UI-02 | Left sidebar navigation with sections: Compliance, Pipeline, Reports, System |
| UI-03 | Card-based layout for all content areas |
| UI-04 | Inline status tags: `Approved`, `Review`, `Flagged`, `Pending` |
| UI-05 | Document iconography: SDS (red S), TDS (green T), Drawing (blue D), CoA (orange C) |
| UI-06 | Manufacturer → Sub-supplier hierarchy visualized with arrows in table cells |
| UI-07 | Drag-and-drop upload zone with template download buttons |
| UI-08 | Tabbed interface for BOM Upload / BOM Records / Materials / Documents |

---

## 7. Glossary

| Term | Definition |
|------|------------|
| **BOM** | Bill of Materials — list of components in a finished product |
| **CAS** | Chemical Abstracts Service number — unique chemical identifier |
| **SDS** | Safety Data Sheet — regulatory hazard communication document |
| **TDS** | Technical Data Sheet — product specifications from manufacturer |
| **CoA** | Certificate of Analysis — lab test results for a material batch |
| **SVHC** | Substance of Very High Concern under REACh |
| **EN 71-3** | European toy safety standard for migration of certain elements |
| **REACh** | EU regulation on Registration, Evaluation, Authorisation and Restriction of Chemicals |
| **SKU** | Stock Keeping Unit — finished product identifier |

---

## 8. Open Questions / Future Roadmap

1. **Multi-tenant support** — Should each factory/supplier see a fully isolated tenant?
2. **Electronic signatures** — Do compliance approvals need e-signature (21 CFR Part 11)?
3. **API for suppliers** — Will suppliers integrate via API instead of web UI?
4. **Blockchain anchoring** — Should test reports be anchored to a blockchain for immutability?
5. **Mobile app** — Is a mobile companion app needed for warehouse scanning?
