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
        "format": "csv",
        "method": "post",
        "url": "https://echa.europa.eu/candidate-list-table",
        "source_url": "https://echa.europa.eu/candidate-list-table",
        "fallback_url": None,
        "table": "svhc",
        "parse_func": "_parse_candidate_list"
    },
    "authorisation_list": {
        "name": "Authorisation List (Annex XIV)",
        "format": "csv",
        "method": "post",
        "url": "https://echa.europa.eu/authorisation-list",
        "source_url": "https://echa.europa.eu/authorisation-list",
        "fallback_url": None,
        "table": "echa",
        "parse_func": "_parse_authorisation_list"
    },
    "restriction_list": {
        "name": "Restriction List (Annex XVII)",
        "format": "xls",
        "method": "post",
        "url": "https://echa.europa.eu/substances-restricted-under-reach",
        "source_url": "https://echa.europa.eu/substances-restricted-under-reach",
        "fallback_url": None,
        "table": "echa",
        "parse_func": "_parse_restriction_list"
    },
    "corap": {
        "name": "CoRAP \u2014 Community Rolling Action Plan",
        "format": "csv",
        "method": "post",
        "url": "https://echa.europa.eu/information-on-chemicals/evaluation/community-rolling-action-plan/corap-table",
        "source_url": "https://echa.europa.eu/information-on-chemicals/evaluation/community-rolling-action-plan/corap-table",
        "fallback_url": None,
        "table": "echa",
        "parse_func": "_parse_corap"
    },
    "pbt": {
        "name": "PBT/vPvB Assessment List",
        "format": "csv",
        "method": "post",
        "url": "https://echa.europa.eu/pbt",
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

def _download_echa_table_export(page_url: str, export_type: str = "csv") -> Optional[bytes]:
    """
    Download ECHA table export via Liferay POST endpoint.
    Steps:
        1. GET the page to obtain session cookies + hidden form fields
        2. POST to the export endpoint with all form fields
    Returns the raw file bytes, or None on failure.
    """
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Referer": page_url
    })

    # 1. Load page to get session + tokens
    page_resp = session.get(page_url, timeout=60)
    if page_resp.status_code != 200:
        logger.warning(f"Could not load ECHA page {page_url}: HTTP {page_resp.status_code}")
        return None

    text = page_resp.text

    # Extract p_auth token
    auth_match = re.search(r'p_auth=(\w+)', text)
    if not auth_match:
        logger.warning("No p_auth token found in ECHA page")
        return None
    p_auth = auth_match.group(1)

    # Extract hidden form inputs from export form
    form_match = re.search(r'<form[^>]*id="_disslists_WAR_disslistsportlet_exportForm".*?</form>', text, re.DOTALL)
    if not form_match:
        logger.warning("No export form found in ECHA page")
        return None

    form_html = form_match.group(0)
    # Parse input name/value pairs
    inputs = re.findall(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"[^>]*/?>', form_html)
    payload = {k: v for k, v in inputs}
    payload["_disslists_WAR_disslistsportlet_exportType"] = export_type

    # Build POST URL
    post_url = (
        f"{page_url}?p_p_id=disslists_WAR_disslistsportlet"
        f"&p_p_lifecycle=2&p_p_state=normal&p_p_mode=view"
        f"&p_p_resource_id=exportResults&p_p_cacheability=cacheLevelPage&p_auth={p_auth}"
    )

    post_resp = session.post(
        post_url,
        data=payload,
        timeout=120,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://echa.europa.eu"
        }
    )

    if post_resp.status_code != 200:
        logger.warning(f"Export POST failed: HTTP {post_resp.status_code}")
        return None
    if len(post_resp.content) < 1000:
        logger.warning(f"Export returned {len(post_resp.content)} bytes — likely empty")
        return None

    return post_resp.content


def download_echa_file(key: str) -> Optional[str]:
    """Download official ECHA file by key. Returns local file path."""
    cfg = ECHA_DOWNLOADS.get(key)
    if not cfg:
        logger.error(f"Unknown ECHA dataset key: {key}")
        return None

    method = cfg.get("method", "get")
    urls_to_try = [u for u in [cfg.get("url"), cfg.get("fallback_url")] if u]
    if not urls_to_try:
        logger.error(f"No download URL configured for {key}")
        return None

    for url in urls_to_try:
        try:
            logger.info(f"Downloading {cfg['name']} from {url} (method={method})")

            if method == "post":
                export_type = cfg.get("format", "csv")
                file_bytes = _download_echa_table_export(url, export_type)
                if file_bytes is None:
                    continue
                resp_content = file_bytes
                logger.info(f"POST export received {len(resp_content)} bytes")
            else:
                resp = requests.get(url, timeout=60, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                })
                if resp.status_code != 200:
                    logger.warning(f"HTTP {resp.status_code} for {url}")
                    continue
                resp_content = resp.content

            ext = cfg.get("format", "csv")
            # ECHA sometimes returns XLSX regardless of requested format
            if isinstance(resp_content, bytes) and resp_content[:2] == b"PK":
                ext = "xlsx"
            local_path = os.path.join(DOWNLOAD_DIR, f"{key}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")
            with open(local_path, "wb") as f:
                f.write(resp_content)
            logger.info(f"Saved {cfg['name']} ({len(resp_content)} bytes) to {local_path}")
            return local_path
        except Exception as e:
            logger.warning(f"Download failed for {url}: {e}")
            continue

    logger.error(f"All download attempts failed for {key}")
    return None


# ======================================================================
# Parsers
# ======================================================================

def _read_csv_with_header(raw_bytes: bytes, encoding: str = "utf-8") -> pd.DataFrame:
    """Read ECHA-style CSV that has title/filter rows before the actual header."""
    text = raw_bytes.decode(encoding, errors="replace")
    lines = text.splitlines()
    header_idx = None
    header_keywords = ["substance name", "chemical name", "name", "ec no", "cas no"]
    for i, line in enumerate(lines):
        lower = line.lower()
        if any(kw in lower for kw in header_keywords):
            # Must look like a real header row (has tabs/commas separating fields)
            if '\t' in line or ',' in line:
                header_idx = i
                break
    if header_idx is None:
        header_idx = 0
    clean_text = "\n".join(lines[header_idx:])
    # Detect delimiter
    delimiter = "\t" if "\t" in lines[header_idx] else ","
    return pd.read_csv(io.StringIO(clean_text), sep=delimiter, engine="python")


def _read_file(filepath: str) -> pd.DataFrame:
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".xlsx":
        engine = "openpyxl"
    elif ext == ".xls":
        engine = "xlrd"
    else:
        engine = None

    if ext in (".xlsx", ".xls"):
        # ECHA bulk files often have multi-row headers; try skiprows dynamically
        df_raw = pd.read_excel(filepath, engine=engine, header=None)
        # Find the first row that contains 'Substance' or 'Chemical' or 'CAS'
        header_row = None
        keywords = ["substance", "chemical", "chemical_name", "cas", "ec number", "ec no", "entry no", "inclusion", "reason", "name"]
        for i in range(min(15, len(df_raw))):
            row_text = " ".join([str(v).lower() for v in df_raw.iloc[i] if pd.notna(v)])
            matches = sum(1 for k in keywords if k in row_text)
            if matches >= 2:
                header_row = i
                break
        if header_row is not None:
            df = pd.read_excel(filepath, engine=engine, header=header_row)
            logger.debug(f"Detected header at row {header_row}, columns: {list(df.columns)}")
        else:
            df = pd.read_excel(filepath, engine=engine)
            logger.warning(f"No header row detected, using default. Columns: {list(df.columns)}")
        return df
    elif ext == ".csv":
        with open(filepath, "rb") as f:
            raw = f.read()
        return _read_csv_with_header(raw)
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
    if cas in ("-", "—", "", "nan", "none"):
        return None
    m = re.match(r"(\d{1,7})\s*[-–]\s*(\d{2})\s*[-–]\s*(\d)", cas)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return cas


def _get_or_create_substance(db, name: str, cas: str, ec: str) -> SubstanceLibrary:
    name = (name or "Unknown")[:200]  # Truncate to VARCHAR(200)
    substance = db.query(SubstanceLibrary).filter(SubstanceLibrary.cas_number == cas).first() if cas else None
    if not substance and ec:
        substance = db.query(SubstanceLibrary).filter(SubstanceLibrary.ec_number == ec).first()
    if not substance and name:
        substance = db.query(SubstanceLibrary).filter(SubstanceLibrary.name == name).first()

    if not substance:
        substance = SubstanceLibrary(
            name=name,
            cas_number=cas,
            ec_number=ec,
            source_url="https://echa.europa.eu",
            notes=f"Auto-imported from ECHA on {datetime.now().isoformat()[:10]}"
        )
        db.add(substance)
        db.flush()
    return substance


def _fuzzy_get(row: pd.Series, *keys: str) -> Any:
    """Fetch value from row with fuzzy column matching."""
    row_keys = {str(k).strip().lower().replace(" ", "_"): v for k, v in row.items()}
    for k in keys:
        k_norm = k.strip().lower().replace(" ", "_")
        if k_norm in row_keys and pd.notna(row_keys[k_norm]):
            return row_keys[k_norm]
        # Also try direct match on original keys
        for orig_k in row.index:
            if k.lower() in str(orig_k).lower():
                v = row[orig_k]
                if pd.notna(v):
                    return v
    return None


def _parse_candidate_list(filepath: str, db) -> Dict[str, Any]:
    df = _read_file(filepath)
    logger.info(f"Candidate List columns: {list(df.columns)}")
    imported = updated = skipped = 0
    for _, row in df.iterrows():
        # ECHA Candidate List has "Chemical Name", "EC Number", "CAS Number", "Inclusion Date"
        name = _fuzzy_get(row, "Chemical Name", "Substance", "Name")
        name = str(name).strip() if pd.notna(name) else None
        ec = _normalise_ec(_fuzzy_get(row, "EC Number", "EC", "EC/List"))
        cas = _normalise_cas(_fuzzy_get(row, "CAS Number", "CAS No", "CAS"))
        reason = _fuzzy_get(row, "Reason for inclusion", "Reason", "Substance of very high concern")
        reason = str(reason).strip() if pd.notna(reason) else None

        if not name or (not ec and not cas):
            skipped += 1
            continue

        name = name[:200]  # Truncate to fit VARCHAR(200)

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
        name = _fuzzy_get(row, "Substance", "Chemical Name", "Name")
        name = str(name).strip() if pd.notna(name) else None
        ec = _normalise_ec(_fuzzy_get(row, "EC Number", "EC", "EC No"))
        cas = _normalise_cas(_fuzzy_get(row, "CAS Number", "CAS", "CAS No"))
        sunset = _fuzzy_get(row, "Sunset Date", "Latest date")
        sunset = str(sunset).strip() if pd.notna(sunset) else None

        if not name or (not ec and not cas):
            skipped += 1
            continue

        name = name[:200]
        sub = _get_or_create_substance(db, name, cas, ec)
        existing = db.query(ECHASubstance).filter(
            ECHASubstance.cas_number == cas,
            ECHASubstance.ec_number == ec
        ).first() if cas and ec else None

        if existing:
            existing.reach_status = "authorisation"
            existing.notes = sunset or existing.notes
            updated += 1
        else:
            db.add(ECHASubstance(
                substance_id=sub.id,
                cas_number=cas,
                ec_number=ec,
                name=name or sub.name,
                reach_status="authorisation",
                notes=sunset,
                source_url="https://echa.europa.eu/authorisation-list",
            ))
            imported += 1

    return {"imported": imported, "updated": updated, "skipped": skipped, "dataset": "Authorisation List"}


def _parse_restriction_list(filepath: str, db) -> Dict[str, Any]:
    df = _read_file(filepath)
    imported = updated = skipped = 0
    for _, row in df.iterrows():
        name = _fuzzy_get(row, "Substance", "Chemical Name", "Name")
        name = str(name).strip() if pd.notna(name) else None
        if not name and len(row) > 0:
            # Some files have unnamed first column containing the substance name
            first = row.iloc[0]
            if pd.notna(first):
                name = str(first).strip()
        ec = _normalise_ec(_fuzzy_get(row, "EC Number", "EC", "EC no"))
        cas = _normalise_cas(_fuzzy_get(row, "CAS Number", "CAS", "CAS no"))
        entry_no = _fuzzy_get(row, "Entry No", "Entry")
        entry_no = str(entry_no).strip() if pd.notna(entry_no) else None

        if not name or (not ec and not cas):
            skipped += 1
            continue

        name = name[:200]
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
        name = _fuzzy_get(row, "Substance name", "Name")
        name = str(name).strip() if pd.notna(name) else None
        ec = _normalise_ec(_fuzzy_get(row, "EC / List no", "EC Number", "EC"))
        cas = _normalise_cas(_fuzzy_get(row, "CAS no", "CAS Number", "CAS"))
        member_state = _fuzzy_get(row, "Evaluating Member State", "Member State")
        member_state = str(member_state).strip() if pd.notna(member_state) else None
        status = _fuzzy_get(row, "Status of evaluation", "Status")
        status = str(status).strip() if pd.notna(status) else None

        if not name or (not ec and not cas):
            skipped += 1
            continue

        name = name[:200]
        sub = _get_or_create_substance(db, name, cas, ec)

        existing = db.query(ECHASubstance).filter(
            ECHASubstance.cas_number == cas,
            ECHASubstance.ec_number == ec
        ).first() if cas and ec else None

        if existing:
            existing.reach_status = status or existing.reach_status
            existing.clp_notes = member_state or existing.clp_notes
            existing.updated_at = utcnow()
            updated += 1
        else:
            db.add(ECHASubstance(
                substance_id=sub.id,
                cas_number=cas,
                ec_number=ec,
                name=name or sub.name,
                reach_status=status or "evaluating",
                clp_notes=member_state,
                source_url="https://echa.europa.eu/corap",
            ))
            imported += 1

    return {"imported": imported, "updated": updated, "skipped": skipped, "dataset": "CoRAP"}


def _parse_pbt(filepath: str, db) -> Dict[str, Any]:
    df = _read_file(filepath)
    imported = updated = skipped = 0
    for _, row in df.iterrows():
        name = _fuzzy_get(row, "Substance", "Chemical Name", "Name")
        name = str(name).strip() if pd.notna(name) else None
        ec = _normalise_ec(_fuzzy_get(row, "EC Number", "EC"))
        cas = _normalise_cas(_fuzzy_get(row, "CAS Number", "CAS"))
        outcome = _fuzzy_get(row, "Outcome", "Conclusion")
        outcome = str(outcome).strip() if pd.notna(outcome) else None

        if not name or (not ec and not cas):
            skipped += 1
            continue

        name = name[:200]
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
