# Contextual Side Panel System — UI/UX Design Specification

> **Design Language:** Matches existing Supplier Hub palette (`#1a1a2e`, `#667eea`, `#28a745`, `#dc3545`, `#ffc107`, `#6c757d`) with card-based layouts, badge system, and 10px border-radius.

---

## 1. Global Panel Mechanics

### 1.1 Layout Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  NAVBAR (60px)                                               │
├──────────┬───────────────────────────────────────┬───────────┤
│          │                                       │           │
│ SIDEBAR  │        MAIN CONTENT AREA              │  SLIDE-   │
│ (250px)  │   (card-grid / table / data-view)     │   OVER    │
│          │                                       │  PANEL    │
│          │                                       │ (480px)   │
│          │                                       │           │
│          │                                       │           │
├──────────┴───────────────────────────────────────┼───────────┤
│                                                  │  STICKY   │
│                                                  │  FOOTER   │
│                                                  │  (64px)   │
└──────────────────────────────────────────────────┴───────────┘
```

### 1.2 Panel States

| State | CSS Class | Behavior |
|---|---|---|
| Hidden | `.slide-panel` (default) | `transform: translateX(100%)` off-screen right |
| Opening | `.slide-panel.open` | `transform: translateX(0)` with 300ms ease-out |
| Closing | `.slide-panel` (removing `.open`) | 250ms ease-in back to `translateX(100%)` |
| Locked | `.slide-panel.locked` | All inputs `disabled`, overlay `pointer-events: none` |

### 1.3 Global Header Bar (shared across both variations)

```
┌─ SLIDE PANEL HEADER ────────────────────────────────── [✕] ─┐
│                                                              │
│  Material Name / Product Name              [Lifecycle Badge] │
│  Subtitle: Code / Part Number              [v1.2]            │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│  (scrollable body — variation-specific content below)        │
```

**Lifecycle Badge States:**

```css
.badge-draft            { background: #e0e0e0; color: #666; }     /* Grey */
.badge-pending-review   { background: #fff3cd; color: #856404; }  /* Amber */
.badge-approved         { background: #d4edda; color: #155724; }  /* Green */
.badge-rejected         { background: #f8d7da; color: #721c24; }  /* Red */
.badge-change-requested { background: #d1ecf1; color: #0c5460; }  /* Blue */
.badge-locked           { background: #f5f6fa; color: #333; }     /* Lock icon prepended */
```

---

## 2. Variation A — Material & Substance / Mixture View

### 2.1 Wireframe

```
┌─ SLIDE PANEL ──────────────────────────────────────── [✕] ──┐
│                                                              │
│  Titanium Dioxide (TiO₂)                    [🟢 Compliant]   │
│  INT-0042  ·  EXT-SUP-8831                         [v1.0]    │
│                                                              │
├─ COMPLIANCE INDICATOR ──────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  🟢  COMPLIANT — No restrictions detected              │ │
│  │  CAS: 13463-67-7    EC: 236-675-5                      │ │
│  │  EN 71-3 Category: II  ·  Migration Limit: 300 mg/kg   │ │
│  │  REACh SVHC: Not listed  ·  Annex XVII: No restrictions │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
├─ DOCUMENT VAULT ────────────────────────────────────────────┤
│                                                              │
│  ┌─ SDS ───────────────────────────────────────────── [🔗] ┐│
│  │  📄 TiO2_Safety_Sheet_v3.pdf                            ││
│  │  Issue Date: 2024-03-15   ⚠️  >2 years old              ││
│  │  Expiry Warning: Document exceeds 3-year validity        ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─ CoA ─────────────────────────────────────────── [🔗] ──┐│
│  │  ✅ Certificate of Analysis — TiO2_CoA_2024.pdf         ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─ DoC ───────────────────────────────────────────────────┐│
│  │  ✅ REACh Compliant    ✅ RoHS Compliant                ││
│  │  ✅ EN 71-3 Compliant  ✅ Packaging Compliant           ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
├─ SUBSTANCE COMPOSITION ─────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Substance                Min%   Max%   Typical    Status│ │
│  │  ─────────────────────────────────────────────────────── │ │
│  │  Titanium dioxide        95.0   98.0   96.5     🟢 Clear│ │
│  │  Aluminium oxide          1.0    3.0    2.0      🟢 Clear│ │
│  │  Silicon dioxide          0.5    1.5    1.0      🟢 Clear│ │
│  │  [🔒 Masked CBI]          0.1    0.3    0.2      🟡 Restr│ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
├─ QUICK ACTIONS ─────────────────────────────────────────────┤
│                                                              │
│  [✏️ Edit Formulation]  [📤 Upload SDS Revision]  [📋 View Changelog] │
│                                                              │
├─ FOOTER ─────────────────────────────────────────────────────┤
│                                                              │
│  [💾 Save Changes]                              [✕  Close]   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Compliance Card Color Variants

| Status | Background | Border | Icon |
|---|---|---|---|
| Compliant | `#d4edda` (light green) | `#28a745` 3px left | `🟢` |
| Restricted | `#fff3cd` (light amber) | `#ffc107` 3px left | `🟡` |
| Banned/High Risk | `#f8d7da` (light red) | `#dc3545` 3px left | `🔴` |
| Pending Review | `#e2e3e5` (light grey) | `#6c757d` 3px left | `⚪` |

**Restricted variant expansion** (when status = `restricted`):

```
┌─ COMPLIANCE INDICATOR ──────────────────────────────────────┐
│                                                              │
│  🟡  RESTRICTED — REACH Annex XVII applies                 │
│  CAS: 50-00-0    EC: 200-001-8                             │
│                                                              │
│  Applicable Restrictions:                                    │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Entry 28 — Carcinogen Category 1B                     │ │
│  │  Restriction: Shall not be placed on the market or used │ │
│  │  as a substance or in mixtures in concentration ≥0.1%  │ │
│  │  Link: echa.europa.eu/substance/...                     │ │
│  └─────────────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Entry 30 — Reproductive toxicity                      │ │
│  │  ...                                                    │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**Banned/High Risk variant expansion:**

```
┌─ COMPLIANCE INDICATOR ──────────────────────────────────────┐
│                                                              │
│  🔴  HIGH RISK / BANNED                                     │
│  CAS: 7439-92-1    Substance: Lead                          │
│                                                              │
│  ┌─ SVHC Candidate List ───────────────────────────────────┐│
│  │  ⚠️  SVHC > 0.1% w/w detected in this material          ││
│  │  Measured concentration: 0.42% w/w                      ││
│  │  Notification threshold exceeded                        ││
│  │  SCIP submission required for articles containing this   ││
│  └──────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─ RoHS Exceedance ───────────────────────────────────────┐│
│  │  ❌  Lead exceeds RoHS limit of 0.1% by weight          ││
│  │  Limit: 1000 ppm  ·  Measured: 4200 ppm                 ││
│  └──────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Variation B — Bought Component / Product View

### 3.1 Wireframe

```
┌─ SLIDE PANEL ──────────────────────────────────────── [✕] ──┐
│                                                              │
│  ABS Housing Assembly (Black)               [🟡 Pending]     │
│  PN: ABS-2000-BLK  ·  Variant: V3           [v2.1]           │
│                                                              │
├─ PHYSICAL SNAPSHOT ─────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┬──────────────┬───────────────────────────┐ │
│  │   Total Mass │  Package Wt. │  Pkg-to-Product Ratio     │ │
│  │──────────────│──────────────│───────────────────────────│ │
│  │   247.3 g    │    18.5 g    │  7.5%                     │ │
│  │              │              │  ⚠️ >5% threshold for     │ │
│  │              │              │  German Packaging Act     │ │
│  └──────────────┴──────────────┴───────────────────────────┘ │
│                                                              │
├─ STRUCTURE TREE (Mini-BOM) ─────────────────────────────────┤
│                                                              │
│  ┌─ ABS Housing Assembly ── 247.3g ───────────────────────┐ │
│  │  ├─ 📦 ABS Resin Pellet (40.0g)                        │ │
│  │  │   └─ 🧪 ABS Compound → [BOS: ABS-Form-01]           │ │
│  │  │       ├─ Acrylonitrile (10.0g)     🟢 Clear          │ │
│  │  │       ├─ Butadiene (14.0g)         🟡 Restricted     │ │
│  │  │       └─ Styrene (16.0g)           🟢 Clear          │ │
│  │  │                                                      │ │
│  │  ├─ 🔩 M3 Steel Screw ×4 (12.0g)                       │ │
│  │  │   └─ 🧪 Steel Alloy S304                             │ │
│  │  │       ├─ Iron (8.4g)              🟢 Clear           │ │
│  │  │       ├─ Chromium (2.2g)          🟡 Restricted      │ │
│  │  │       └─ Nickel (1.4g)            🔴 Banned/SVHC     │ │
│  │  │           ⚠️ Nickel >0.1% w/w (SCIP Trigger)        │ │
│  │  │                                                      │ │
│  │  ├─ 🏷️ Paper Label (0.5g)                              │ │
│  │  │   └─ 🛡️ BOP → [Packaging: PKG-LBL-001]              │ │
│  │  │       ├─ Kraft Paper (0.4g)       🟢 Clear           │ │
│  │  │       └─ Adhesive (0.1g)          🟢 Clear           │ │
│  │  │                                                      │ │
│  │  └─ 📐 ABS Injection-Molded Shell (194.8g)              │ │
│  │      └─ 🧪 (Same ABS Compound — contribution merged)    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
├─ FLAGGED SUBSTANCES ────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  🔴  Nickel (CAS: 7440-02-0) — 0.57% w/w of product    │ │
│  │      SVHC Candidate List · SCIP submission required     │ │
│  │      Located in: 🔩 M3 Steel Screw ×4                   │ │
│  │      [📋 Generate SCIP Data Sheet]                      │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  🟡  Butadiene (CAS: 106-99-0) — 5.66% w/w of product  │ │
│  │      REACH Annex XVII Entry 28 · Carcinogen Cat.1A      │ │
│  │      Located in: 📦 ABS Resin Pellet                    │ │
│  ├─────────────────────────────────────────────────────────┤ │
│  │  🟡  Chromium (CAS: 7440-47-3) — 0.89% w/w of product  │ │
│  │      REACH Annex XVII · Skin sensitizer Category 1      │ │
│  │      Located in: 🔩 M3 Steel Screw ×4                   │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
├─ WORKFLOW HUB — Pending Review ─────────────────────────────┤
│                                                              │
│  Assigned to: QA Manager (Sarah Chen)                       │
│  Submitted: 2026-05-14 09:32 UTC                            │
│                                                              │
│  ┌─ Review Actions ────────────────────────────────────────┐ │
│  │                                                          │ │
│  │  [✅ Approve & Lock]  [❌ Reject]  [💬 Request Changes]  │ │
│  │                                                          │ │
│  │  ┌─ Change Request Comments ──────────────────────┐      │ │
│  │  │                                                │      │ │
│  │  │  Line Item: 🔩 M3 Steel Screw ×4               │      │ │
│  │  │  Comment:   [ Replace with nickel-free alloy  ]│      │ │
│  │  │  Severity:  [🔴 Must Fix ▼]                    │      │ │
│  │  │                                                │      │ │
│  │  │  [+ Add Line-Item Comment]                     │      │ │
│  │  └────────────────────────────────────────────────┘      │ │
│  │                                                          │ │
│  │  Summary Comment:                                        │ │
│  │  ┌──────────────────────────────────────────────────┐    │ │
│  │  │ Nickel content must be addressed before approval  │    │ │
│  │  │ to ensure SCIP compliance. Consider alternative   │    │ │
│  │  │ fastener supplier.                                │    │ │
│  │  └──────────────────────────────────────────────────┘    │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                              │
├─ FOOTER (Pending Review State) ─────────────────────────────┤
│                                                              │
│  [✅ Approve & Structural Lock]  [💬 Request Changes]        │
│  [❌ Reject & Archive]                          [✕  Close]   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Workflow Hub Button States by Lifecycle

| Lifecycle | Footer Buttons | Behavior |
|---|---|---|
| **Draft** | `[💾 Save Draft]` `[📤 Submit for Review]` `[✕ Close]` | Supplier can edit; submit triggers validation + status → `pending_review` |
| **Pending Review** | `[✅ Approve & Lock]` `[💬 Request Changes]` `[❌ Reject & Archive]` `[✕ Close]` | Only admin/qa/manager roles see these |
| **Approved** | `[🔒 View Only — Locked]` `[📋 Export SCIP]` `[✕ Close]` | All inputs disabled; export actions enabled |
| **Change Requested** | `[💾 Save Changes]` `[📤 Resubmit]` `[✕ Close]` | Supplier edits; version increments on resubmit |
| **Rejected** | `[📋 View Rejection]` `[📝 Start New Version]` `[✕ Close]` | Read-only view of rejection reason |

---

## 4. Edge Cases

### 4.1 CBI Masked View

When `material.cbi_enabled = true`, the side panel renders:

```
┌─ COMPLIANCE INDICATOR ──────────────────────────────────────┐
│  🔒  CBI Protected — Proprietary Substance                  │
│  CAS: [🔒 Masked for Proprietary Privacy]                   │
│  EC:  [🔒 Masked for Proprietary Privacy]                  │
│                                                              │
│  Overall Compliance: 🟡  Restricted                          │
│  (The substance has REACH Annex XVII restrictions.          │
│   Compliance team can view unmasked details.)               │
└──────────────────────────────────────────────────────────────┘

┌─ SUBSTANCE COMPOSITION ─────────────────────────────────────┐
│  [🔒 Masked CBI]    0.1   0.3   0.2    🟡 Restricted        │
│  (Chemical identity masked — backend evaluation active)      │
└──────────────────────────────────────────────────────────────┘
```

**CBI Logic:**
- Supplier sees: masked names, masked CAS/EC, but still sees the compliance badge
- Internal admin/qa sees: full chemical names with a `[CBI]` suffix indicator
- Backend: always evaluates against the real CAS number regardless of UI masking

### 4.2 Immutable / Locked State

When `bill.is_locked = true` (status = `approved`):

```
┌─ SLIDE PANEL ────────────────────────────────── 🔒 LOCKED ──┐
│  (semi-transparent overlay with lock icon in center)         │
│                                                              │
│  This document has been approved and structurally locked.    │
│  Historical traceability is preserved.                       │
│                                                              │
│  To modify, request a new version (v1.0 → v1.1).            │
│                                                              │
│  [📝 Create New Version]                                     │
└──────────────────────────────────────────────────────────────┘
```

Visual changes when locked:
- All `<input>`, `<textarea>`, `<select>`, `<button>`: `disabled`
- File upload drop zones: `pointer-events: none; opacity: 0.5`
- Edit buttons: replaced with `[🔒 Locked]` label
- Cursor: `not-allowed` on interactive elements
- Semi-transparent overlay: `rgba(255,255,255,0.4)` with centered lock icon

---

## 5. State Management Logic

### 5.1 Panel State Object

```javascript
/**
 * Single source of truth for the side panel.
 * Created fresh when a row is clicked, destroyed on close.
 */
const PanelState = {
    // ── Identity ──
    entityType: null,        // 'material' | 'substance' | 'component' | 'product'
    entityId: null,          // primary key from the clicked row

    // ── Data ──
    data: null,              // full entity payload from API
    composition: [],         // substances / child items
    complianceResult: null,  // { status, restrictions[], svhc[], rohs[] }
    documents: [],           // { type, filename, issueDate, status }
    versionHistory: [],      // { tag, approvedBy, approvedAt, ... }

    // ── UI State ──
    isOpen: false,
    isLocked: false,         // derived: data.status === 'approved'
    isCBI: false,            // derived: data.cbi_enabled === true
    viewMode: null,          // 'read' | 'edit' | 'review' — derived from role + status
    activeTab: 'overview',   // 'overview' | 'documents' | 'changelog'

    // ── Workflow ──
    changeRequestComments: [], // [{ lineItemId, comment, severity }]
    selectedLineItem: null,
};

// ── Derived Computations ──────────────────────────────────────

/** Determine which panel variation to render. */
function resolveVariation(entityType) {
    switch (entityType) {
        case 'material':
        case 'substance':
            return 'A';  // Chemical focus: compliance card, document vault
        case 'component':
        case 'product':
            return 'B';  // Structural focus: mini-BOM, workflow hub
        default:
            return 'A';
    }
}

/** Determine view mode based on user role and document state. */
function resolveViewMode(status, userRole) {
    if (status === 'approved' || status === 'rejected') {
        return 'read';
    }
    if (status === 'pending_review' && ['admin', 'qa', 'manager'].includes(userRole)) {
        return 'review';
    }
    if (status === 'draft' || status === 'change_requested') {
        return 'edit';
    }
    return 'read';
}

/** Determine which footer buttons to render. */
function resolveFooterActions(status, userRole) {
    const actions = {
        draft: [
            { id: 'save',      label: '💾 Save Draft',         visible: true },
            { id: 'submit',    label: '📤 Submit for Review',  visible: true, primary: true },
            { id: 'close',     label: '✕ Close',              visible: true },
        ],
        pending_review: (['admin','qa','manager'].includes(userRole))
            ? [
                { id: 'approve',   label: '✅ Approve & Lock',    visible: true, primary: true },
                { id: 'changes',   label: '💬 Request Changes',   visible: true },
                { id: 'reject',    label: '❌ Reject & Archive',  visible: true, danger: true },
                { id: 'close',     label: '✕ Close',              visible: true },
              ]
            : [
                { id: 'close',     label: '✕ Close',              visible: true },
              ],
        approved: [
            { id: 'newVersion', label: '📝 Create New Version',  visible: true, primary: true },
            { id: 'close',      label: '✕ Close',               visible: true },
        ],
        change_requested: [
            { id: 'save',       label: '💾 Save Changes',       visible: true },
            { id: 'resubmit',   label: '📤 Resubmit',           visible: true, primary: true },
            { id: 'close',      label: '✕ Close',               visible: true },
        ],
        rejected: [
            { id: 'viewReason', label: '📋 View Rejection',     visible: true },
            { id: 'newVersion', label: '📝 Start New Version',  visible: true, primary: true },
            { id: 'close',      label: '✕ Close',               visible: true },
        ],
    };
    return actions[status] || [{ id: 'close', label: '✕ Close', visible: true }];
}
```

### 5.2 Panel Lifecycle Flow

```
  ┌─────────────────┐
  │  Row Clicked    │
  │  in data table  │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────────────────┐
  │  openPanel(entityType, id)  │
  │  - set isOpen = true        │
  │  - dispatch loading state   │
  └────────┬────────────────────┘
           │
           ▼
  ┌──────────────────────────────────────┐
  │  fetchPanelData(entityType, id)       │
  │  ┌──────────────────────────────────┐ │
  │  │ GET /api/panels/{type}/{id}     │ │
  │  │ Returns: { data, composition,   │ │
  │  │   compliance, documents,        │ │
  │  │   versionHistory, childBills }  │ │
  │  └──────────────────────────────────┘ │
  └────────┬─────────────────────────────┘
           │
           ▼
  ┌──────────────────────────────────────┐
  │  resolvePanelConfig(payload)          │
  │  - variation = resolveVariation(type) │
  │  - viewMode  = resolveViewMode(...)   │
  │  - isLocked  = status === 'approved'  │
  │  - isCBI     = cbi_enabled            │
  │  - footer    = resolveFooterActions() │
  └────────┬─────────────────────────────┘
           │
           ▼
  ┌──────────────────────────────────────┐
  │  renderPanel(config)                  │
  │  - IF variation A: render chemicals   │
  │  - IF variation B: render structure   │
  │  - Apply CBI masking if enabled       │
  │  - Apply locked overlay if locked     │
  │  - Render footer buttons              │
  └────────┬─────────────────────────────┘
           │
           ▼
  ┌──────────────┐     ┌─────────────────┐
  │  User clicks  │────▶│  updatePanel()  │──▶ re-render
  │  action btn   │     └─────────────────┘
  └──────────────┘
           │
           ▼
  ┌──────────────┐     ┌─────────────────┐
  │  User clicks  │────▶│  closePanel()   │──▶ remove from DOM
  │  [✕] / Close │     └─────────────────┘
  └──────────────┘
```

### 5.3 API Contract

```python
# GET /api/panels/{entity_type}/{entity_id}

# Response shape (unified for all entity types):
{
    "entity": {
        "id": "MAT-0042",
        "name": "Titanium Dioxide (TiO₂)",
        "entity_type": "material",
        "status": "compliant",           # or lifecycle status for bills
        "version": "v1.0",
        "is_locked": false,
        "cbi_enabled": false,
        "cas_number": "13463-67-7",
        "ec_number": "236-675-5",
        "internal_code": "INT-0042",
        "external_code": "EXT-SUP-8831",
        "part_number": null,             # null for materials
        "variant_id": null,
    },
    "compliance": {
        "status": "compliant",           # compliant | restricted | banned | pending
        "svhc_listed": false,
        "svhc_concentration_pct": null,
        "rohs_exceedance": false,
        "reach_annex_xvii_entries": [],
        "en71_category": "II",
        "en71_migration_limit_mg_kg": 300.0,
    },
    "documents": [
        {
            "type": "sds",
            "filename": "TiO2_Safety_Sheet_v3.pdf",
            "issue_date": "2024-03-15",
            "is_expired": false,         # true if >3 years
            "file_url": "/api/documents/MAT-0042/sds",
        },
        {
            "type": "coa",
            "filename": "TiO2_CoA_2024.pdf",
            "status": "verified",
        },
        {
            "type": "doc",
            "declarations": {
                "reach": true,
                "rohs": true,
                "en71": true,
                "packaging": true,
            },
        }
    ],
    "composition": [                     # for materials: substance list
        {                                # for products: child bill_items tree
            "substance_name": "Titanium dioxide",
            "cas_number": "13463-67-7",
            "concentration_min": 95.0,
            "concentration_max": 98.0,
            "concentration_typical": 96.5,
            "compliance_status": "compliant",
            "is_cbi_masked": false,
            "cbi_label": null,
        },
    ],
    "structure": {                       # only for Variation B (products)
        "total_weight_g": 247.3,
        "package_weight_g": 18.5,
        "package_ratio_pct": 7.5,
        "child_items": [
            {
                "item_id": 42,
                "material_name": "ABS Resin Pellet",
                "quantity": 40.0,
                "unit": "g",
                "component_weight_g": 40.0,
                "has_nested_bill": true,
                "nested_bill_type": "BOS",
                "nested_bill_id": "BOS-001",
                "substances": [ /* rolled-up per item */ ],
                "children": [ /* recursive */ ],
            },
        ],
        "flagged_substances": [          # pre-computed by roll-up engine
            {
                "cas_number": "7440-02-0",
                "substance_name": "Nickel",
                "concentration_w_pct": 0.57,
                "status": "banned",
                "located_in_item": "🔩 M3 Steel Screw ×4",
                "scip_triggered": true,
                "restriction": "SVHC Candidate List (>0.1% w/w)",
            },
        ],
    },
    "version_history": [
        { "tag": "v1.0", "approved_by": "Sarah Chen", "approved_at": "2026-04-10", "change_reason": "Initial version" },
    ],
}
```

---

## 6. CSS Implementation (matching existing design system)

```css
/* ── Slide Panel Container ─────────────────────────────────── */
.slide-panel-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.3);
  z-index: 100;
  opacity: 0;
  pointer-events: none;
  transition: opacity 200ms ease;
}
.slide-panel-overlay.open {
  opacity: 1;
  pointer-events: auto;
}

.slide-panel {
  position: fixed;
  top: 0; right: 0;
  width: 480px;
  height: 100vh;
  background: #f5f6fa;
  box-shadow: -4px 0 20px rgba(0,0,0,0.1);
  z-index: 101;
  display: flex;
  flex-direction: column;
  transform: translateX(100%);
  transition: transform 300ms cubic-bezier(0.4, 0, 0.2, 1);
}
.slide-panel.open {
  transform: translateX(0);
}

/* Locked overlay */
.slide-panel.locked::after {
  content: '';
  position: absolute;
  inset: 0;
  background: rgba(255,255,255,0.4);
  z-index: 10;
  pointer-events: none;
}
.slide-panel.locked .slide-panel-body,
.slide-panel.locked .slide-panel-footer {
  opacity: 0.6;
  pointer-events: none;
}

/* ── Panel Header ──────────────────────────────────────────── */
.slide-panel-header {
  padding: 20px 24px;
  background: white;
  border-bottom: 1px solid #e0e0e0;
  flex-shrink: 0;
}
.slide-panel-header .title {
  font-size: 18px;
  font-weight: 700;
  color: #1a1a2e;
  margin-bottom: 4px;
}
.slide-panel-header .subtitle {
  font-size: 13px;
  color: #666;
}
.slide-panel-header .badges {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.slide-panel-close {
  position: absolute;
  top: 16px; right: 16px;
  background: none; border: none;
  font-size: 20px; cursor: pointer;
  color: #666;
}

/* ── Panel Body (scrollable) ───────────────────────────────── */
.slide-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}

/* ── Compliance Card ───────────────────────────────────────── */
.compliance-card {
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 20px;
  border-left: 4px solid transparent;
}
.compliance-card.compliant  { background: #d4edda; border-left-color: #28a745; }
.compliance-card.restricted { background: #fff3cd; border-left-color: #ffc107; }
.compliance-card.banned     { background: #f8d7da; border-left-color: #dc3545; }
.compliance-card.pending    { background: #e2e3e5; border-left-color: #6c757d; }
.compliance-card.cbi        { background: #e8daef; border-left-color: #6f42c1; }

.compliance-card .badge-icon { font-size: 24px; margin-bottom: 8px; }
.compliance-card .cas-ec    { font-size: 12px; color: #666; margin-top: 8px; }

/* ── Document Vault ────────────────────────────────────────── */
.doc-vault-item {
  background: white;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 8px;
  border: 1px solid #e0e0e0;
}
.doc-vault-item .doc-name { font-weight: 600; color: #1a1a2e; }
.doc-vault-item .doc-meta { font-size: 12px; color: #666; margin-top: 4px; }
.doc-vault-item .doc-warning {
  background: #fff3cd;
  color: #856404;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  display: inline-block;
  margin-top: 6px;
}

/* ── Mini-BOM Tree ─────────────────────────────────────────── */
.mini-bom-tree {
  background: white;
  border-radius: 10px;
  border: 1px solid #e0e0e0;
  padding: 12px;
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.8;
}
.mini-bom-tree .tree-node         { padding-left: 0; }
.mini-bom-tree .tree-node.level-1 { padding-left: 16px; }
.mini-bom-tree .tree-node.level-2 { padding-left: 32px; }
.mini-bom-tree .tree-node.level-3 { padding-left: 48px; }
.mini-bom-tree .tree-node.level-4 { padding-left: 64px; }
.mini-bom-tree .connector          { color: #adb5bd; }
.mini-bom-tree .weight             { color: #666; font-size: 12px; }
.mini-bom-tree .scip-flag          {
  background: #f8d7da;
  color: #721c24;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  margin-left: 6px;
}

/* ── Physical Snapshot Grid ────────────────────────────────── */
.snapshot-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  margin-bottom: 20px;
}
.snapshot-cell {
  background: white;
  border-radius: 10px;
  padding: 16px;
  text-align: center;
  border: 1px solid #e0e0e0;
}
.snapshot-cell .value   { font-size: 24px; font-weight: 700; color: #1a1a2e; }
.snapshot-cell .label   { font-size: 11px; color: #666; margin-top: 4px; }
.snapshot-cell .warning { color: #856404; font-size: 11px; margin-top: 6px; }

/* ── Flagged Substance Card ────────────────────────────────── */
.flagged-substance {
  background: white;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 8px;
  border-left: 4px solid #dc3545;
}
.flagged-substance.restricted { border-left-color: #ffc107; }
.flagged-substance .sub-name  { font-weight: 600; }
.flagged-substance .sub-meta  { font-size: 12px; color: #666; }
.flagged-substance .sub-action { margin-top: 8px; }

/* ── Workflow Hub ──────────────────────────────────────────── */
.workflow-hub {
  background: white;
  border-radius: 10px;
  padding: 16px;
  border: 1px solid #e0e0e0;
  margin-bottom: 20px;
}
.workflow-hub .reviewer-info { font-size: 13px; color: #666; margin-bottom: 12px; }
.workflow-hub .action-row { display: flex; gap: 8px; margin-bottom: 12px; }

.change-request-item {
  background: #f8f9fa;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 8px;
}
.change-request-item .line-item { font-weight: 600; font-size: 13px; }
.change-request-item .comment   { font-size: 12px; color: #666; margin-top: 4px; }

/* ── Sticky Footer ─────────────────────────────────────────── */
.slide-panel-footer {
  background: white;
  border-top: 1px solid #e0e0e0;
  padding: 12px 24px;
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.slide-panel-footer .btn-group { display: flex; gap: 8px; }
```

---

## 7. JavaScript Initialization

```javascript
// ── Panel Entry Point ────────────────────────────────────────

function openPanel(entityType, entityId) {
    // Prevent double-open
    if (PanelState.isOpen) closePanel();

    PanelState.entityType = entityType;
    PanelState.entityId   = entityId;
    PanelState.isOpen     = true;

    document.getElementById('slidePanelOverlay').classList.add('open');
    document.getElementById('slidePanel').classList.add('open');

    // Loading skeleton
    document.getElementById('slidePanelBody').innerHTML = `
        <div class="skeleton-loading">
            <div class="skeleton-line" style="width:80%"></div>
            <div class="skeleton-line" style="width:60%"></div>
            <div class="skeleton-line" style="width:90%"></div>
        </div>`;

    fetch(`/api/panels/${entityType}/${entityId}`)
        .then(r => r.json())
        .then(payload => {
            const config = resolvePanelConfig(payload);
            renderPanel(config);
        })
        .catch(err => {
            document.getElementById('slidePanelBody').innerHTML =
                `<div class="empty-state">⚠️ Failed to load. <a href="#" onclick="openPanel('${entityType}','${entityId}')">Retry</a></div>`;
        });
}

function closePanel() {
    PanelState.isOpen = false;
    document.getElementById('slidePanel').classList.remove('open');
    document.getElementById('slidePanelOverlay').classList.remove('open');
    // Reset state after transition completes
    setTimeout(() => { PanelState.data = null; }, 300);
}

function resolvePanelConfig(payload) {
    return {
        variation: resolveVariation(payload.entity.entity_type),
        entity: payload.entity,
        compliance: payload.compliance,
        documents: payload.documents,
        composition: payload.composition,
        structure: payload.structure,
        versionHistory: payload.version_history,
        isLocked: payload.entity.is_locked,
        isCBI: payload.entity.cbi_enabled,
        viewMode: resolveViewMode(
            payload.entity.status,
            JSON.parse(localStorage.getItem('user') || '{}').role
        ),
        footer: resolveFooterActions(
            payload.entity.status,
            JSON.parse(localStorage.getItem('user') || '{}').role
        ),
    };
}

// Wire row clicks in data tables
document.querySelectorAll('[data-panel-trigger]').forEach(row => {
    row.addEventListener('click', () => {
        openPanel(row.dataset.panelType, row.dataset.panelId);
    });
});
```
