# Supplier Hub — Compliance Platform Architecture v3.0

## 1. Data Model / Entity-Relationship Diagram (ERD)

### 1.1 Core Entity Relationships

```
 ┌──────────────────────┐       ┌──────────────────────┐
 │    material_supplier  │       │       supplier        │
 │──────────────────────│       │──────────────────────│
 │ id (PK)              │──┐    │ id (PK)              │
 │ name                 │  │    │ name                 │
 │ external_material_code│  │    │ email                │
 │ factory_material_code │  │    │ status               │
 │ is_sub_contractor     │  │    └──────────┬───────────┘
 │ ───────────────────── │  │               │
 │ supplier_id (FK) ─────┼──┘               │ registers
 └──────────┬────────────┘                  │
            │                               │
            │ provides                      │
            ▼                               ▼
 ┌──────────────────────┐       ┌──────────────────────┐
 │    material_library   │       │   internal_user       │
 │──────────────────────│       │──────────────────────│
 │ material_id (PK)     │       │ id (PK)              │
 │ material_name        │       │ role (admin/qa/mgr)  │
 │ material_type        │       └──────────┬───────────┘
 │ component_name       │                  │
 │ cas_number           │                  │ reviews/approves
 │ ec_number            │                  │
 │ cbi_enabled          │◄── CBI toggle ───┘
 │ cbi_masked_name      │
 │ supplier_id (FK) ────┘
 │ sds_issue_date       │
 │ sds_expiry_flagged   │
 │ doc_declaration      │──► JSON { conformity_checks[] }
 │ ai_verification_status│
 └──────────┬───────────┘
            │
            │ referenced by
            ▼
 ┌──────────────────────────────────────────────────────┐
 │                  bill (master entity)                 │
 │──────────────────────────────────────────────────────│
 │ bill_id (PK)                  │ bill_type             │
 │ bill_number (SKU)             │   ENUM: BOM | BOS | BOP│
 │ product_name                  │ status                │
 │ created_by (FK→supplier)      │   ENUM: draft |       │
 │ assigned_to (FK→internal_user)│   submitted |         │
 │ current_version               │   approved |          │
 │ is_locked (approved→true)     │   rejected |          │
 │ total_weight_g                │   change_requested    │
 │ mass_balance_valid            │                       │
 │ created_at / updated_at       │                       │
 └────────────────┬─────────────────────────────────────┘
                  │
                  │  bill_items (tree structure)
                  ▼
 ┌──────────────────────────────────────────────────────┐
 │               bill_item (recursive tree)              │
 │──────────────────────────────────────────────────────│
 │ item_id (PK)                  │ parent_item_id (FK→self)│
 │ bill_id (FK→bill)             │ material_id (FK→library)│
 │ child_bill_id (FK→bill, null) │ ◄ BOS/BOP nesting    │
 │ ───────────────────────────── │                      │
 │ quantity                      │ quantity_unit         │
 │ unit_weight_g (if unit=pcs)   │  ENUM: g | pcs       │
 │ component_role                │ sort_order            │
 │ ───────────────────────────── │ computed fields:     │
 │ total_weight_g                │ weight_percentage     │
 │ svhc_above_threshold          │ scip_article_id       │
 └──────────────────────────────────────────────────────┘

 ┌──────────────────────┐       ┌──────────────────────┐
 │    bill_substance     │       │   substance_breakdown │
 │──────────────────────│       │──────────────────────│
 │ id (PK)              │       │ id (PK)              │
 │ bill_item_id (FK)    │       │ material_id (FK)     │
 │ substance_id (FK)────┼──────►│ cas_number           │
 │ concentration_pct    │       │ ec_number            │
 │ is_impurity          │       │ substance_name       │
 │                      │       │ svhc_status          │
 └──────────────────────┘       │ reach_annex_xvii     │
                                │ restriction_category  │
                                │ rohs_exceedance      │
 ┌──────────────────────────────┐ │ en71_category       │
 │     bill_version_history      │ │ migration_limit     │
 │──────────────────────────────│ └─────────────────────┘
 │ version_id (PK)              │
 │ bill_id (FK→bill)            │
 │ version_tag (v1.0, v1.1)     │
 │ snapshot_json (JSONB)         │◄ Immutable full snapshot
 │ approved_by (FK→internal_user)│
 │ approved_at                  │
 │ change_reason                │
 └──────────────────────────────┘

 ┌────────────────────────────────────────────────┐
 │            regulatory_event_log                 │
 │────────────────────────────────────────────────│
 │ event_id (PK)              │ triggered_by       │
 │ substance_id (FK)          │  ENUM: db_update | │
 │ bill_id (FK)               │   new_version     │
 │ previous_status            │                   │
 │ new_status                 │                   │
 │ affected_concentration_pct │                   │
 │ alert_severity             │                   │
 │ notification_sent          │                   │
 │ resolved                   │                   │
 │ created_at                 │                   │
 └────────────────────────────┘```

### 1.2 Key Relationships Summary

| Relationship | Cardinality | Description |
|---|---|---|
| supplier → material_supplier | 1:N | A supplier manages multiple material suppliers |
| material_supplier → material_library | 1:N | Each material supplier provides materials |
| supplier → bill | 1:N | Supplier creates multiple bills |
| bill → bill_item | 1:N | A bill contains items (recursive tree via parent_item_id) |
| bill_item → bill_item | self-referential | Hierarchical nesting of sub-components |
| bill_item → material_library | N:1 | Item references a registered material |
| bill_item → bill | N:1 (via child_bill_id) | A BOS/BOP can be nested inside a BOM |
| bill → bill_version_history | 1:N | Immutable version snapshots |
| material_library → substance_breakdown | 1:N | Material's chemical composition |
| bill_item → bill_substance | 1:N | Rolled-up substance concentrations per item |
| substance_breakdown → regulatory_event_log | 1:N | Regulatory change impact tracking |

### 1.3 Database Migration Script (PostgreSQL DDL)

```sql
-- ======================================================================
-- BILL TABLE (unified for BOM, BOS, BOP)
-- ======================================================================
CREATE TABLE bills (
    bill_id             VARCHAR(50) PRIMARY KEY,
    bill_type           VARCHAR(3)  NOT NULL CHECK (bill_type IN ('BOM','BOS','BOP')),
    bill_number         VARCHAR(50) NOT NULL,
    product_name        VARCHAR(200),
    supplier_id         INTEGER     NOT NULL REFERENCES suppliers(id),
    assigned_to         INTEGER     REFERENCES internal_users(id),
    status              VARCHAR(20) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft','submitted','approved','rejected','change_requested')),
    current_version     VARCHAR(10) NOT NULL DEFAULT 'v1.0',
    is_locked           BOOLEAN     NOT NULL DEFAULT FALSE,
    total_weight_g      NUMERIC(12,3),
    mass_balance_valid  BOOLEAN,
    created_at          TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP   NOT NULL DEFAULT NOW(),
    
    -- A bill is structurally locked once approved
    CONSTRAINT chk_locked_approved CHECK (
        is_locked = FALSE OR status = 'approved'
    )
);

CREATE INDEX idx_bills_supplier ON bills(supplier_id);
CREATE INDEX idx_bills_status   ON bills(status);
CREATE INDEX idx_bills_type     ON bills(bill_type);

-- ======================================================================
-- BILL ITEMS (recursive tree — supports nesting BOS/BOP into BOM)
-- ======================================================================
CREATE TABLE bill_items (
    item_id             SERIAL PRIMARY KEY,
    bill_id             VARCHAR(50) NOT NULL REFERENCES bills(bill_id),
    parent_item_id      INTEGER     REFERENCES bill_items(item_id), -- NULL = root
    material_id         VARCHAR(50) REFERENCES material_library(material_id),
    child_bill_id       VARCHAR(50) REFERENCES bills(bill_id), -- BOS/BOP nested into BOM
    
    quantity            NUMERIC(12,4) NOT NULL,
    quantity_unit       VARCHAR(3)  NOT NULL CHECK (quantity_unit IN ('g','pcs')),
    unit_weight_g       NUMERIC(12,4), -- required when quantity_unit = 'pcs'
    component_role      VARCHAR(50),
    sort_order          INTEGER     NOT NULL DEFAULT 0,
    
    -- Computed / cached fields (populated by roll-up engine)
    total_weight_g      NUMERIC(12,4),
    weight_percentage   NUMERIC(7,4),
    svhc_above_threshold BOOLEAN   NOT NULL DEFAULT FALSE,
    scip_article_id     VARCHAR(100),
    
    CONSTRAINT chk_unit_weight CHECK (
        quantity_unit != 'pcs' OR unit_weight_g IS NOT NULL
    ),
    CONSTRAINT chk_not_self_ref CHECK (item_id != parent_item_id)
);

CREATE INDEX idx_bill_items_bill   ON bill_items(bill_id);
CREATE INDEX idx_bill_items_parent ON bill_items(parent_item_id);
CREATE INDEX idx_bill_items_child  ON bill_items(child_bill_id);

-- ======================================================================
-- BILL SUBSTANCES (rolled-up substance concentrations per item)
-- ======================================================================
CREATE TABLE bill_substances (
    id                  SERIAL PRIMARY KEY,
    bill_item_id        INTEGER     NOT NULL REFERENCES bill_items(item_id),
    substance_id        INTEGER     NOT NULL REFERENCES substance_breakdown(id),
    concentration_pct   NUMERIC(7,4) NOT NULL, -- w/w percentage after roll-up
    is_impurity         BOOLEAN     NOT NULL DEFAULT FALSE,
    
    -- SCIP readiness fields
    scip_article_category VARCHAR(100),
    scip_material_category VARCHAR(100),
    scip_safe_use_instructions TEXT,
    
    created_at          TIMESTAMP   NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_bill_substances_item ON bill_substances(bill_item_id);
CREATE INDEX idx_bill_substances_sub  ON bill_substances(substance_id);

-- ======================================================================
-- VERSION HISTORY (immutable snapshot)
-- ======================================================================
CREATE TABLE bill_version_history (
    version_id          SERIAL PRIMARY KEY,
    bill_id             VARCHAR(50) NOT NULL REFERENCES bills(bill_id),
    version_tag         VARCHAR(10) NOT NULL,
    snapshot_json       JSONB       NOT NULL, -- full structural snapshot
    approved_by         INTEGER     REFERENCES internal_users(id),
    approved_at         TIMESTAMP,
    change_reason       TEXT,
    created_at          TIMESTAMP   NOT NULL DEFAULT NOW(),
    
    CONSTRAINT uq_bill_version UNIQUE (bill_id, version_tag)
);

CREATE INDEX idx_version_history_bill ON bill_version_history(bill_id);

-- ======================================================================
-- REGULATORY EVENT LOG (continuous compliance triggers)
-- ======================================================================
CREATE TABLE regulatory_event_log (
    event_id            SERIAL PRIMARY KEY,
    substance_id        INTEGER     NOT NULL REFERENCES substance_breakdown(id),
    bill_id             VARCHAR(50) REFERENCES bills(bill_id),
    previous_status     VARCHAR(30),
    new_status          VARCHAR(30) NOT NULL,
    affected_concentration_pct NUMERIC(7,4),
    alert_severity      VARCHAR(20) NOT NULL CHECK (alert_severity IN ('low','medium','high','critical')),
    notification_sent   BOOLEAN     NOT NULL DEFAULT FALSE,
    resolved            BOOLEAN     NOT NULL DEFAULT FALSE,
    resolved_by         INTEGER     REFERENCES internal_users(id),
    resolved_at         TIMESTAMP,
    created_at          TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reg_event_bill    ON regulatory_event_log(bill_id);
CREATE INDEX idx_reg_event_sub     ON regulatory_event_log(substance_id);
CREATE INDEX idx_reg_event_pending ON regulatory_event_log(resolved, alert_severity);

-- ======================================================================
-- MATERIAL LIBRARY ENHANCEMENTS (add to existing table)
-- ======================================================================
ALTER TABLE material_library 
    ADD COLUMN IF NOT EXISTS ec_number          VARCHAR(50),
    ADD COLUMN IF NOT EXISTS cbi_enabled         BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS cbi_masked_name     VARCHAR(200),
    ADD COLUMN IF NOT EXISTS sds_issue_date      DATE,
    ADD COLUMN IF NOT EXISTS sds_expiry_flagged  BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS doc_declaration     JSONB,
    ADD COLUMN IF NOT EXISTS material_type       VARCHAR(20) DEFAULT 'raw';

-- Material supplier registration table
ALTER TABLE material_library
    ADD COLUMN IF NOT EXISTS external_material_code VARCHAR(100),
    ADD COLUMN IF NOT EXISTS factory_material_code  VARCHAR(100),
    ADD COLUMN IF NOT EXISTS is_sub_contractor       BOOLEAN NOT NULL DEFAULT FALSE;

-- Substance breakdown enhancements
ALTER TABLE substance_breakdown
    ADD COLUMN IF NOT EXISTS ec_number              VARCHAR(50),
    ADD COLUMN IF NOT EXISTS restriction_category    VARCHAR(30)
        CHECK (restriction_category IN ('cleared','restricted','banned')),
    ADD COLUMN IF NOT EXISTS rohs_exceedance        BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS scip_relevant          BOOLEAN NOT NULL DEFAULT FALSE;
```

---

## 2. Backend Pseudo-Code: Nested w/w Concentration Roll-Up

This engine walks the recursive bill_item tree, computes weight contributions at each level, and rolls up substance concentrations to the top-level product.

```python
# file: backend/compliance/rollup_engine.py

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from decimal import Decimal

# ---------------------------------------------------------------------------
# Data Transfer Objects
# ---------------------------------------------------------------------------

@dataclass
class SubstanceResult:
    """Aggregated substance data for one bill_item node."""
    cas_number: str
    substance_name: str
    concentration_w_percent: Decimal = Decimal('0')
    is_svhc: bool = False
    restriction_category: str = 'cleared'
    rohs_exceedance: bool = False

@dataclass
class NodeResult:
    """Result of processing one bill_item (leaf or branch)."""
    item_id: int
    material_id: Optional[str]
    component_weight_g: Decimal      # absolute weight in grams
    component_percent: Decimal       # relative to parent (0-100)
    substances: Dict[str, SubstanceResult] = field(default_factory=dict)
    children: List[NodeResult] = field(default_factory=list)

# ---------------------------------------------------------------------------
# Step 1: Convert quantity → absolute weight
# ---------------------------------------------------------------------------

def resolve_weight(item: dict) -> Decimal:
    """Convert any quantity unit to absolute grams."""
    qty = Decimal(str(item['quantity']))
    if item['quantity_unit'] == 'g':
        return qty
    if item['quantity_unit'] == 'pcs':
        unit_w = Decimal(str(item['unit_weight_g']))
        return qty * unit_w
    raise ValueError(f"Unknown unit: {item['quantity_unit']}")

# ---------------------------------------------------------------------------
# Step 2: Recursive tree traversal — bottom-up weight accumulation
# ---------------------------------------------------------------------------

def compute_node_weight(node: dict, parent_weight: Decimal) -> NodeResult:
    """
    Recursively compute the absolute weight and substance concentrations
    for a bill_item node.  Leaf nodes resolve from material_library; branch
    nodes recurse into their children.
    """
    own_weight = resolve_weight(node)
    result = NodeResult(
        item_id=node['item_id'],
        material_id=node.get('material_id'),
        component_weight_g=Decimal('0'),
        component_percent=Decimal('0'),
    )

    # ── CASE A: Leaf node (references a material directly) ──────────
    if node.get('material_id') and not node.get('children'):
        result.component_weight_g = own_weight
        result.component_percent = Decimal('100')
        substances = fetch_substances_for_material(node['material_id'])
        for sub in substances:
            # Substance concentration in grams = w/w% of material × material weight
            conc_g = (Decimal(str(sub['concentration_min'])) / Decimal('100')) * own_weight
            result.substances[sub['cas_number']] = SubstanceResult(
                cas_number=sub['cas_number'],
                substance_name=sub['substance_name'],
                concentration_w_percent=sub['concentration_typical'],  # as declared
                is_svhc=sub['svhc'],
                restriction_category=sub.get('restriction_category', 'cleared'),
                rohs_exceedance=sub.get('rohs_exceedance', False),
            )

    # ── CASE B: Branch node (has children, or references a child_bill_id) ──
    else:
        children_weight = Decimal('0')
        for child in node.get('children', []):
            child_result = compute_node_weight(child, own_weight)
            result.children.append(child_result)
            children_weight += child_result.component_weight_g
            # Merge child substances into parent
            merge_substances(result.substances, child_result.substances)

        # If this node references a child BOS/BOP bill, fetch its items
        if node.get('child_bill_id'):
            child_bill_items = fetch_bill_items(node['child_bill_id'])
            for child_item in child_bill_items:
                child_result = compute_node_weight(child_item, own_weight)
                result.children.append(child_result)
                children_weight += child_result.component_weight_g
                merge_substances(result.substances, child_result.substances)

        result.component_weight_g = own_weight + children_weight
        # Recalculate w/w % after merging children
        if result.component_weight_g > 0:
            for sub in result.substances.values():
                sub.concentration_w_percent = (
                    # Substance grams ÷ total weight × 100
                    # (Each SubstanceResult tracks absolute grams internally;
                    #  here we convert to final w/w %)
                    Decimal(str(sub._absolute_g)) / result.component_weight_g * Decimal('100')
                )

    return result

# ---------------------------------------------------------------------------
# Step 2b: Merge substance contributions from children into parent
# ---------------------------------------------------------------------------

def merge_substances(
    parent: Dict[str, SubstanceResult],
    child: Dict[str, SubstanceResult]
) -> None:
    """Accumulate child substance grams into parent."""
    for cas, child_sub in child.items():
        if cas in parent:
            parent[cas].concentration_w_percent += child_sub.concentration_w_percent
        else:
            parent[cas] = SubstanceResult(
                cas_number=cas,
                substance_name=child_sub.substance_name,
                concentration_w_percent=child_sub.concentration_w_percent,
                is_svhc=child_sub.is_svhc,
                restriction_category=child_sub.restriction_category,
                rohs_exceedance=child_sub.rohs_exceedance,
            )

# ---------------------------------------------------------------------------
# Step 3: Top-level roll-up for an entire BOM
# ---------------------------------------------------------------------------

def compute_bom_rollup(bill_id: str) -> dict:
    """
    Entry point: compute full nested roll-up for a BOM.
    Returns the top-level result with cascaded substance concentrations
    and SCIP-relevant flags.
    """
    bill = fetch_bill(bill_id)
    # Fetch root-level items (parent_item_id IS NULL) ...
    root_items = fetch_bill_items(bill_id)  # filtered to roots

    total_product_weight = Decimal('0')
    aggregated_substances: Dict[str, SubstanceResult] = {}

    for root_item in root_items:
        node_result = compute_node_weight(root_item, Decimal('0'))
        total_product_weight += node_result.component_weight_g
        merge_substances(aggregated_substances, node_result.substances)

    # Normalize all substances to w/w % of total product
    final_substances = []
    for cas, sub in aggregated_substances.items():
        ww_pct = Decimal('0')
        if total_product_weight > 0:
            ww_pct = (sub.concentration_w_percent * node_result.component_weight_g
                      / total_product_weight * Decimal('100'))
        # Re-fetch regulatory status from master DB
        reg_status = fetch_regulatory_status(cas)

        final_substances.append({
            'cas_number': cas,
            'substance_name': sub.substance_name,
            'concentration_w_percent': float(ww_pct),
            'regulatory_status': reg_status['status'],  # cleared|restricted|banned
            'svhc_above_threshold': ww_pct > Decimal('0.1'),
            'scip_relevant': ww_pct > Decimal('0.1') and sub.is_svhc,
            'restriction_reference': reg_status.get('reference'),
        })

    # Persist rolled-up substances to bill_substances table
    persist_bill_substances(bill_id, final_substances)

    # Update bill-level cached fields
    update_bill(bill_id, {
        'total_weight_g': float(total_product_weight),
        'mass_balance_valid': True,
    })

    return {
        'bill_id': bill_id,
        'total_weight_g': float(total_product_weight),
        'substances': final_substances,
        'high_risk_count': sum(
            1 for s in final_substances
            if s['regulatory_status'] == 'banned'
            or s['svhc_above_threshold']
        ),
    }

# ---------------------------------------------------------------------------
# Step 4: Continuous compliance trigger (background job)
# ---------------------------------------------------------------------------

def scan_regulatory_changes(substance_id: int):
    """
    Triggered when a substance's regulatory status changes in the master DB.
    Scans all historically APPROVED bills that contain this substance and
    creates regulatory_event_log entries.
    """
    affected_bills = query("""
        SELECT DISTINCT bs.bill_id, bs.bill_item_id, bs.concentration_pct
        FROM bill_substances bs
        JOIN bill_items bi ON bs.bill_item_id = bi.item_id
        JOIN bills b ON bi.bill_id = b.bill_id
        WHERE bs.substance_id = %s
          AND b.status = 'approved'
          AND b.is_locked = TRUE
    """, (substance_id,))

    new_status = fetch_regulatory_status(substance_id)

    for row in affected_bills:
        insert_regulatory_event({
            'substance_id': substance_id,
            'bill_id': row['bill_id'],
            'previous_status': new_status.get('previous'),
            'new_status': new_status['status'],
            'affected_concentration_pct': row['concentration_pct'],
            'alert_severity': 'high' if new_status['status'] == 'banned' else 'medium',
        })

    # Send notification to compliance team members
    if affected_bills:
        notify_compliance_team(substance_id, len(affected_bills))
```

### 2.1 Mass Balance Validation (BOS)

```python
def validate_mass_balance(bill_id: str) -> dict:
    """
    For BOS (formulation) bills: the sum of all ingredient percentages
    must equal exactly 100%.  Returns validation result.
    """
    bill = fetch_bill(bill_id)
    if bill['bill_type'] != 'BOS':
        return {'valid': True, 'message': 'Not a formulation'}

    items = fetch_bill_items(bill_id)  # direct items, not recursive
    total = sum(Decimal(str(item['weight_percentage'] or 0)) for item in items)

    if total != Decimal('100'):
        gap = Decimal('100') - total
        return {
            'valid': False,
            'total_percentage': float(total),
            'gap': float(gap),
            'message': f'Formulation totals {total}%, gap of {gap}%. Must equal exactly 100%.',
        }

    return {'valid': True, 'total_percentage': 100.0}
```

### 2.2 SCIP Article Identifier

```python
def identify_scip_articles(bill_id: str) -> List[dict]:
    """
    After roll-up, find every bill_item where an SVHC exceeds 0.1% w/w.
    Returns the exact sub-component (article) that triggers SCIP reporting.
    """
    rolled_up = compute_bom_rollup(bill_id)

    scip_articles = []
    for substance in rolled_up['substances']:
        if substance['scip_relevant']:
            # Walk the tree to find the exact node where concentration > 0.1%
            offending_node = find_node_exceeding_threshold(
                bill_id, substance['cas_number'], Decimal('0.1')
            )
            if offending_node:
                scip_articles.append({
                    'scip_article_id': offending_node.get('scip_article_id'),
                    'material_name': offending_node.get('material_name'),
                    'cas_number': substance['cas_number'],
                    'concentration': substance['concentration_w_percent'],
                    'scip_article_category': offending_node.get('scip_article_category'),
                    'safe_use_instructions': offending_node.get('scip_safe_use_instructions'),
                })

    return scip_articles
```

---

## 3. UI Validation Rules — Supplier Portal

### 3.1 Material & Supplier Registration

| # | Rule | Severity | Implemented In |
|---|---|---|---|
| R1 | **CAS Number format**: Must match `^\d{1,7}-\d{2}-\d$` regex; reject free text | **BLOCKER** | Frontend + Backend |
| R2 | **EC Number format**: Must match `^\d{3}-\d{3}-\d$` or `^\d{7}$` | **BLOCKER** | Frontend + Backend |
| R3 | **Duplicate CAS check**: Reject if CAS already registered by this supplier | ERROR | Backend |
| R4 | **SDS Issue Date**: Required if SDS document uploaded; warn if >3 years old | WARNING | Frontend |
| R5 | **DoS Declaration**: Must have ≥1 conformity checkbox checked before saving | **BLOCKER** | Frontend |
| R6 | **Internal vs External Code**: At least one code field must be populated | **BLOCKER** | Frontend |
| R7 | **Sub-contractor toggle**: If TRUE, require parent material reference | WARNING | Frontend |
| R8 | **CBI toggle**: If TRUE, backend still validates; frontend shows masked name | INFO | Both |

### 3.2 Bill Creation (BOM / BOS / BOP)

| # | Rule | Severity | Implemented In |
|---|---|---|---|
| B1 | **Empty Bill**: Bill must contain ≥1 item before submission | **BLOCKER** | Frontend |
| B2 | **Unit Weight for Pieces**: If unit = "pcs", unit_weight_g field required | **BLOCKER** | Frontend + Backend (`chk_unit_weight`) |
| B3 | **Material Must Be Registered**: Cannot add unregistered materials | **BLOCKER** | Backend |
| B4 | **Mass Balance (BOS only)**: Sum of ingredient % must = 100.00% ± 0.01% | **BLOCKER** | Backend (block submission) |
| B5 | **Circular Reference**: A BOM cannot reference itself or create a cycle | **BLOCKER** | Backend (graph traversal) |
| B6 | **Nested Bill Type**: Only BOS/BOP can be nested inside BOM | ERROR | Frontend |
| B7 | **Weight Mismatch Warning**: If declared weight differs from computed by >5% | WARNING | Backend |
| B8 | **SDS Expiry Warning**: If any referenced material has SDS >3 years old | WARNING | Backend (on submit) |
| B9 | **CBI Material Used**: Flag to compliance team that CBI material is in this bill | INFO | Backend |
| B10 | **Duplicate Item**: Same material + same role cannot appear twice at same level | WARNING | Frontend |

### 3.3 Real-Time Compliance Indicators

| # | Rule | Severity | UI Action |
|---|---|---|---|
| C1 | **SVHC > 0.1% w/w**: Flag as HIGH RISK, isolate article, prompt SCIP fields | **BLOCKER** | Red badge + SCIP form panel |
| C2 | **REACH Annex XVII Restricted**: Flag as RESTRICTED, show condition text | ERROR | Amber badge + condition info |
| C3 | **RoHS Exceedance**: Flag as BANNED — cannot submit without justification | **BLOCKER** | Red badge + justification required |
| C4 | **EN 71-3 Migration Limit**: Show measured vs. limit comparison | WARNING | Orange badge + test results |
| C5 | **Unknown Substance**: CAS not in master DB — flag for manual review | WARNING | Grey badge + "Pending Review" |
| C6 | **Cleared Substance**: No restrictions found | INFO | Green badge |

### 3.4 Workflow & Submission

| # | Rule | Severity | Description |
|---|---|---|---|
| W1 | **Pre-Submit Scan**: Run full compliance check; block if any BLOCKER rules triggered | **BLOCKER** | Backend |
| W2 | **Submission Checklist**: Show summary of warnings/errors before final submit | INFO | Frontend modal |
| W3 | **Version Increment**: Auto-increment version (v1.0→v1.1) on modification of approved bill | **BLOCKER** | Backend |
| W4 | **Approved Immutability**: UI hides all edit controls when `is_locked = true` | **BLOCKER** | Frontend |
| W5 | **Rejection Reason**: Reject action requires comment | **BLOCKER** | Backend |
| W6 | **Change Request**: Must include line-item comments referencing specific items | **BLOCKER** | Frontend |
| W7 | **Dual Approval**: Banned/High-Risk submissions require QA Manager + Admin approval | INFO | Backend workflow |
| W8 | **Inactivity Timeout**: Auto-save draft every 2 minutes; warn after 30 min inactivity | WARNING | Frontend |

### 3.5 Frontend Validation Snippet (Zod — TypeScript)

```typescript
// Supplier Portal: material registration validation
import { z } from 'zod';

const casRegex = /^\d{1,7}-\d{2}-\d$/;
const ecRegex  = /^(\d{3}-\d{3}-\d|\d{7})$/;

export const materialRegistrationSchema = z.object({
  material_name: z.string().min(2).max(200),
  cas_number: z.string().regex(casRegex, 'Invalid CAS format (e.g. 7732-18-5)'),
  ec_number:  z.string().regex(ecRegex, 'Invalid EC format (e.g. 231-791-2)').optional(),
  external_material_code: z.string().min(1).max(100).optional(),
  factory_material_code:  z.string().min(1).max(100).optional(),
  is_sub_contractor: z.boolean(),
  parent_material_id: z.string().optional(),
  cbi_enabled: z.boolean(),
  cbi_masked_name: z.string().max(200).optional(),

  // Document metadata
  sds_issue_date: z.string().datetime().optional(),
  doc_declaration: z.object({
    reach_compliant: z.boolean(),
    rohs_compliant: z.boolean(),
    en71_compliant: z.boolean(),
    packaging_compliant: z.boolean(),
  }),

  // Composition
  substances: z.array(z.object({
    cas_number: z.string().regex(casRegex),
    substance_name: z.string().min(1).max(200),
    concentration_min: z.number().min(0).max(100),
    concentration_max: z.number().min(0).max(100),
    is_impurity: z.boolean(),
  })).min(1, 'At least one substance is required'),
})
// Custom refinement: at least one material code must be provided
.refine(
  data => data.external_material_code || data.factory_material_code,
  { message: 'At least one material code is required' }
)
// Custom refinement: CBI toggle requires masked name
.refine(
  data => !data.cbi_enabled || data.cbi_masked_name,
  { message: 'CBI masked name is required when CBI is enabled' }
);

// BOS Formulation Validation
export const formulationSchema = z.array(z.object({
  material_id: z.string(),
  percentage: z.number().min(0).max(100),
  component_role: z.string().optional(),
})).refine(
  items => {
    const sum = items.reduce((acc, i) => acc + i.percentage, 0);
    return Math.abs(sum - 100) < 0.01;
  },
  { message: 'Formulation percentages must sum to exactly 100%' }
);
```

### 3.6 Risk Status Hierarchy (Badge System)

```
┌─────────────────────────────────────────────────────────┐
│  COMPLIANT / CLEARED    ████████  Green   #28a745       │
│  RESTRICTED / CONDITIONAL ████████  Amber  #ffc107      │
│  BANNED / HIGH RISK     ████████  Red     #dc3545       │
│  PENDING REVIEW         ████████  Grey    #6c757d       │
│  UNKNOWN SUBSTANCE      ████████  Purple  #6f42c1       │
│  SDS EXPIRED            ████████  Orange  #fd7e14       │
│  SCIP TRIGGERED         ████████  Pink    #e83e8c       │
└─────────────────────────────────────────────────────────┘
```
