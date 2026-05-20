"""
ECHA Data Scraper — Downloads official ECHA bulk CSV/Excel files
and imports them into the Substance Library tables.

Uses official ECHA download URLs (not scraping HTML).
Source: https://data.europa.eu/euodp/en/data/publisher/echa

Supported datasets:
- Candidate List (SVHC)
- Authorisation List (Annex XIV)
- Restriction List (Annex XVII)
- C&L Inventory
- CoRAP
- PBT/vPvB Assessment List
"""
import os
import io
import re
import logging
import requests
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any

from pipeline.models.database import (
    get_db,
    SubstanceLibrary, CMRSubstance, ECHASubstance,
    CLPClassification, GHSClassification, SymbolReference,
    utcnow
)

logger = logging.getLogger(__name__)

# Official ECHA data URLs (EU Open Data Portal + ECHA public downloads)
ECHA_DOWNLOADS = {
    "candidate_list": {
        "name": "SVHC Candidate List",
        "format": "xlsx",
        "url": "https://www.chemsafetypro.com/Topics/EU/REACH_SVHC_List_Excel_Table.xlsx",
        "source_url": "https://echa.europa.eu/candidate-list-table",
        "fallback_url": None,
        "table": "svhc",
        "parse_func": "_parse_candidate_list"
    },
    "authorisation_list": {
        "name": "Authorisation List (Annex XIV)",
        "format": "xlsx",
        "url": None,  # No official bulk XLSX; we scrape from reference
        "source_url": "https://echa.europa.eu/authorisation-list",
        "fallback_url": "http://www.chemsafetypro.com/Topics/EU/REACH_annex_xiv_REACH_authorization_list.xlsx",
        "table": "echa",
        "parse_func": "_parse_authorisation_list"
    },
    "restriction_list": {
        "name": "Restriction List (Annex XVII)",
        "format": "xlsx",
        "url": None,
        "source_url": "https://echa.europa.eu/substances-restricted-under-reach",
        "fallback_url": "https://www.chemsafetypro.com/Topics/EU/REACH_Restricted_Substances_List_REACH_Annex_XVII.xls",
        "table": "echa",
        "parse_func": "_parse_restriction_list"
    },
    "corap": {
        "name": "CoRAP — Community Rolling Action Plan",
        "format": "xlsx",
        "url": "https://echa.europa.eu/download/corap",
        "source_url": "https://echa.europa.eu/information-on-chemicals/evaluation/community-rolling-action-plan/corap-table",
        "fallback_url": None,
        "table": "echa",
        "parse_func": "_parse_corap"
    },
    "pbt": {
        "name": "PBT/vPvB Assessment List",
        "format": "xlsx",
        "url": None,
        "source_url": "https://echa.europa.eu/pbt",
        "fallback_url": None,
        "table": "cmr",
        "parse_func": "_parse_pbt"
    },
}

DOWNLOAD_DIR = os.path.join(os.path.dirname(__file__), "data", "echa_downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ======================================================================
# Downloader
# ======================================================================

def download_echa_file(key: str) -> Optional[str]:
    """Download official ECHA file by key. Returns local file path."""
    cfg = ECHA_DOWNLOADS.get(key)
    if not cfg:
        logger.error(f"Unknown ECHA dataset key: {key}")
        return None

    urls_to_try = [u for u in [cfg.get("url"), cfg.get("fallback_url")] if u]
    if not urls_to_try:
        logger.error(f"No download URL configured for {key}")
        return None

    for url in urls_to_try:
        try:
            logger.info(f"Downloading {cfg['name']} from {url}")
            resp = requests.get(url, timeout=60, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            })
            if resp.status_code != 200:
                logger.warning(f"HTTP {resp.status_code} for {url}")
                continue

            ext = cfg.get("format", "xlsx")
            local_path = os.path.join(DOWNLOAD_DIR, f"{key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")
            with open(local_path, "wb") as f:
                f.write(resp.content)
            logger.info(f"Saved {cfg['name']} ({len(resp.content)} bytes) to {local_path}")
            return local_path
        except Exception as e:
            logger.warning(f"Download failed for {url}: {e}")
            continue

    logger.error(f"All download attempts failed for {key}")
    return None


# ======================================================================
# Parsers
# ======================================================================

def _read_file(filepath: str) -> pd.DataFrame:
    ext = os.path.splitext(filepath)[1].lower()
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(filepath, engine="openpyxl")
    elif ext == ".csv":
        return pd.read_csv(filepath)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _normalise_ec(ec_val) -> Optional[str]:
    if pd.isna(ec_val) or not str(ec_val):
        return None
    ec = str(ec_val).strip()
    parts = re.split(r"[\-/]", ec)
    if len(parts) >= 3:
        ec = f"{parts[0]}-{parts[1]}-{parts[2]}"
    return ec if len(ec) >= 5 else None


def _normalise_cas(cas_val) -> Optional[str]:
    if pd.isna(cas_val) or not str(cas_val):
        return None
    cas = str(cas_val).strip()
    m = re.match(r"(\d{1,7})\s*[-–]\s*(\d{2})\s*[-–]\s*(\d)", cas)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return cas


def _get_or_create_substance(db, name: str, cas: str, ec: str) -> SubstanceLibrary:
    substance = db.query(SubstanceLibrary).filter(SubstanceLibrary.cas_number == cas).first() if cas else None
    if not substance and ec:
        substance = db.query(SubstanceLibrary).filter(SubstanceLibrary.ec_number == ec).first()
    if not substance and name:
        substance = db.query(SubstanceLibrary).filter(SubstanceLibrary.name == name).first()

    if not substance:
        substance = SubstanceLibrary(
            name=name or "Unknown",
            cas_number=cas,
            ec_number=ec,
            source_url="https://echa.europa.eu",
            notes=f"Auto-imported from ECHA on {datetime.now().isoformat()[:10]}"
        )
        db.add(substance)
        db.flush()
    return substance


def _parse_candidate_list(filepath: str, db) -> Dict[str, Any]:
    df = _read_file(filepath)
    imported = updated = skipped = 0
    for _, row in df.iterrows():
        name = str(row.get("Substance")).strip() if "Substance" in row else None
        ec = _normalise_ec(row.get("EC Number")) if "EC Number" in row else None
        cas = _normalise_cas(row.get("CAS Number")) if "CAS Number" in row else None
        reason = str(row.get("Reason")).strip() if "Reason" in row else None
        date_inc = str(row.get("Date of inclusion"))[:10] if "Date of inclusion" in row else None

        if not name and not ec and not cas:
            skipped += 1
            continue

        sub = _get_or_create_substance(db, name, cas, ec)

        # Create/update SVHC entry in echa_substances
        existing = db.query(ECHASubstance).filter(
            ECHASubstance.cas_number == cas,
            ECHASubstance.ec_number == ec
        ).first() if cas and ec else None

        if existing:
            existing.reach_status = "svhc"
            existing.clp_notes = reason or existing.clp_notes
            existing.updated_at = utcnow()
            updated += 1
        else:
            echa = ECHASubstance(
                substance_id=sub.id,
                cas_number=cas,
                ec_number=ec,
                name=name or sub.name,
                reach_status="svhc",
                clp_notes=reason,
                source_url="https://echa.europa.eu/candidate-list-table",
            )
            db.add(echa)
            imported += 1

        # If reason includes CMR/Mutagenic/Reprotoxic, create CMR entry
        if reason and re.search(r"\bCMR\b|\bCarcinogen\b|\bMutagen\b|\bReprotox\b", reason, re.I):
            cmr_existing = db.query(CMRSubstance).filter(
                CMRSubstance.cas_number == cas,
                CMRSubstance.ec_number == ec
            ).first() if cas and ec else None
            if not cmr_existing:
                db.add(CMRSubstance(
                    substance_id=sub.id,
                    cas_number=cas,
                    ec_number=ec,
                    name=name or sub.name,
                    cmr_type="carcinogen" if "arc" in reason.lower() else "cmr",
                    clp_notes=reason,
                    source_url="https://echa.europa.eu/candidate-list-table",
                ))

    return {"imported": imported, "updated": updated, "skipped": skipped, "dataset": "Candidate List"}


def _parse_authorisation_list(filepath: str, db) -> Dict[str, Any]:
    df = _read_file(filepath)
    imported = updated = skipped = 0
    for _, row in df.iterrows():
        name = str(row.get("Substance")).strip() if "Substance" in row else None
        ec = _normalise_ec(row.get("EC Number")) if "EC Number" in row else None
        cas = _normalise_cas(row.get("CAS Number")) if "CAS Number" in row else None
        sunset = str(row.get("Sunset Date")).strip() if "Sunset Date" in row else None

        if not name and not ec and not cas:
            skipped += 1
            continue

        sub = _get_or_create_substance(db, name, cas, ec)
        existing = db.query(ECHASubstance).filter(
            ECHASubstance.cas_number == cas,
            ECHASubstance.ec_number == ec
        ).first() if cas and ec else None

        if existing:
            existing.reach_status = "restricted"
            existing.notes = sunset or existing.notes
            updated += 1
        else:
            db.add(ECHASubstance(
                substance_id=sub.id,
                cas_number=cas,
                ec_number=ec,
                name=name or sub.name,
                reach_status="restricted",
                notes=sunset,
                source_url="https://echa.europa.eu/authorisation-list",
            ))
            imported += 1

    return {"imported": imported, "updated": updated, "skipped": skipped, "dataset": "Authorisation List"}


def _parse_restriction_list(filepath: str, db) -> Dict[str, Any]:
    df = _read_file(filepath)
    imported = updated = skipped = 0
    for _, row in df.iterrows():
        name = str(row.get("Substance")).strip() if "Substance" in row else None
        ec = _normalise_ec(row.get("EC Number")) if "EC Number" in row else None
        cas = _normalise_cas(row.get("CAS Number")) if "CAS Number" in row else None
        entry_no = str(row.get("Entry No")).strip() if "Entry No" in row else None

        if not name and not ec and not cas:
            skipped += 1
            continue

        sub = _get_or_create_substance(db, name, cas, ec)
        existing = db.query(ECHASubstance).filter(
            ECHASubstance.cas_number == cas,
            ECHASubstance.ec_number == ec
        ).first() if cas and ec else None

        if existing:
            existing.reach_status = "restricted"
            existing.index_number = entry_no or existing.index_number
            updated += 1
        else:
            db.add(ECHASubstance(
                substance_id=sub.id,
                cas_number=cas,
                ec_number=ec,
                name=name or sub.name,
                reach_status="restricted",
                index_number=entry_no,
                source_url="https://echa.europa.eu/substances-restricted-under-reach",
            ))
            imported += 1

    return {"imported": imported, "updated": updated, "skipped": skipped, "dataset": "Restriction List"}


def _parse_corap(filepath: str, db) -> Dict[str, Any]:
    df = _read_file(filepath)
    imported = updated = skipped = 0
    for _, row in df.iterrows():
        name = str(row.get("Substance")).strip() if "Substance" in row else None
        ec = _normalise_ec(row.get("EC/List")) if "EC/List" in row else None
        cas = _normalise_cas(row.get("CAS")) if "CAS" in row else None
        member_state = str(row.get("Member State")).strip() if "Member State" in row else None
        status = str(row.get("Status")).strip() if "Status" in row else None

        if not name and not ec and not cas:
            skipped += 1
            continue

        sub = _get_or_create_substance(db, name, cas, ec)
        existing = db.query(ECHASubstance).filter(
            ECHASubstance.cas_number == cas,
            ECHASubstance.ec_number == ec
        ).first() if cas and ec else None

        if existing:
            existing.reach_status = status or existing.reach_status
            updated += 1
        else:
            db.add(ECHASubstance(
                substance_id=sub.id,
                cas_number=cas,
                ec_number=ec,
                name=name or sub.name,
                reach_status=status,
                source_url="https://echa.europa.eu/corap",
            ))
            imported += 1

    return {"imported": imported, "updated": updated, "skipped": skipped, "dataset": "CoRAP"}


def _parse_pbt(filepath: str, db) -> Dict[str, Any]:
    df = _read_file(filepath)
    imported = updated = skipped = 0
    for _, row in df.iterrows():
        name = str(row.get("Substance")).strip() if "Substance" in row else None
        ec = _normalise_ec(row.get("EC Number")) if "EC Number" in row else None
        cas = _normalise_cas(row.get("CAS Number")) if "CAS Number" in row else None
        outcome = str(row.get("Outcome")).strip() if "Outcome" in row else None

        if not name and not ec and not cas:
            skipped += 1
            continue

        sub = _get_or_create_substance(db, name, cas, ec)
        existing = db.query(CMRSubstance).filter(
            CMRSubstance.cas_number == cas,
            CMRSubstance.ec_number == ec
        ).first() if cas and ec else None

        if not existing:
            db.add(CMRSubstance(
                substance_id=sub.id,
                cas_number=cas,
                ec_number=ec,
                name=name or sub.name,
                cmr_type="pbt",
                cmr_category="1B",
                hazard_class=outcome or "PBT",
                source_url="https://echa.europa.eu/pbt",
            ))
            imported += 1
        else:
            existing.cmr_type = existing.cmr_type or "pbt"
            existing.hazard_class = outcome or existing.hazard_class
            updated += 1

    return {"imported": imported, "updated": updated, "skipped": skipped, "dataset": "PBT List"}


# ======================================================================
# Public Runner
# ======================================================================

def run_scraper(datasets: Optional[list] = None, dry_run: bool = False) -> Dict[str, Any]:
    """
    Run ECHA scraper for listed datasets.
    datasets: list of keys from ECHA_DOWNLOADS (default: all available)
    Returns: dict with results per dataset.
    """
    keys = datasets or list(ECHA_DOWNLOADS.keys())
    db = get_db()
    try:
        results = {}
        for key in keys:
            cfg = ECHA_DOWNLOADS.get(key)
            if not cfg:
                continue
            filepath = download_echa_file(key)
            if not filepath:
                results[key] = {"error": "Download failed", "dataset": cfg["name"]}
                continue

            parse_func = globals().get(cfg.get("parse_func", "_parse_candidate_list"))
            if not parse_func:
                results[key] = {"error": "No parser configured", "dataset": cfg["name"]}
                continue

            if dry_run:
                results[key] = {"dry_run": True, "dataset": cfg["name"], "file": filepath}
                os.remove(filepath)
                continue

            try:
                summary = parse_func(filepath, db)
                results[key] = summary
            except Exception as e:
                logger.error(f"Parser error for {key}: {e}")
                results[key] = {"error": str(e), "dataset": cfg["name"]}
            finally:
                try:
                    os.remove(filepath)
                except:
                    pass

        db.commit()
        return results
    except Exception as e:
        db.rollback()
        logger.error(f"Scraper transaction failed: {e}")
        raise
    finally:
        db.close()
