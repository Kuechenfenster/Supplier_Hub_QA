"""
Seed script for Substance Library tables.
Populates symbol_references with all 9 GHS pictograms and a few sample substances.
Usage: python -m backend.seed_substance_library
"""
import logging
from datetime import datetime, timezone

from pipeline.models.database import (
    init_db, get_db,
    SubstanceLibrary, CMRSubstance, ECHASubstance,
    CLPClassification, GHSClassification, SymbolReference
)

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(timezone.utc)


SYMBOLS = [
    {"symbol_code": "GHS01", "name": "Explosive", "description": "Explosive; Self-reactive; Organic peroxide", "emoji": "💥", "regulation_source": "GHS"},
    {"symbol_code": "GHS02", "name": "Flammable", "description": "Flammable (gas, aerosol, liquid, solid); Pyrophoric; Self-heating; Water reactive", "emoji": "🔥", "regulation_source": "GHS"},
    {"symbol_code": "GHS03", "name": "Oxidizing", "description": "Oxidizing (gas, liquid, solid); Organic peroxide", "emoji": "🧨", "regulation_source": "GHS"},
    {"symbol_code": "GHS04", "name": "Gas Under Pressure", "description": "Compressed gas; Liquefied gas; Refrigerated liquefied gas; Dissolved gas", "emoji": "🫙", "regulation_source": "GHS"},
    {"symbol_code": "GHS05", "name": "Corrosive", "description": "Corrosive to metals; Skin corrosion; Serious eye damage", "emoji": "🧪", "regulation_source": "GHS"},
    {"symbol_code": "GHS06", "name": "Acute Toxicity", "description": "Acute toxicity (fatal or toxic)", "emoji": "☠️", "regulation_source": "GHS"},
    {"symbol_code": "GHS07", "name": "Health Hazard", "description": "Harmful; Irritant; Sensitization; Narcotic effects; Respiratory tract irritation; Hazardous to ozone layer", "emoji": "⚠️", "regulation_source": "GHS"},
    {"symbol_code": "GHS08", "name": "Serious Health Hazard", "description": "Carcinogen; Mutagen; Reprotoxic; Respiratory sensitization; Target organ toxicity; Aspiration toxicity", "emoji": "🫁", "regulation_source": "GHS"},
    {"symbol_code": "GHS09", "name": "Environment", "description": "Aquatic toxicity; Hazardous to the aquatic environment", "emoji": "🌊", "regulation_source": "GHS"},
]

SAMPLE_SUBSTANCES = [
    {
        "name": "Formaldehyde",
        "cas_number": "50-00-0",
        "ec_number": "200-001-8",
        "iupac_name": "Formaldehyde",
        "molecular_formula": "CH2O",
        "registration_status": "registered",
        "source_url": "https://echa.europa.eu/substance-information/-/substanceinfo/100.000.002",
    },
    {
        "name": "Lead",
        "cas_number": "7439-92-1",
        "ec_number": "231-100-4",
        "iupac_name": "Lead",
        "molecular_formula": "Pb",
        "registration_status": "restricted",
        "source_url": "https://echa.europa.eu/substance-information/-/substanceinfo/100.026.814",
    },
    {
        "name": "Benzene",
        "cas_number": "71-43-2",
        "ec_number": "200-753-7",
        "iupac_name": "Benzene",
        "molecular_formula": "C6H6",
        "registration_status": "registered",
        "source_url": "https://echa.europa.eu/substance-information/-/substanceinfo/100.000.685",
    },
]

CMR_ENTRIES = [
    {
        "cas_number": "50-00-0",
        "ec_number": "200-001-8",
        "name": "Formaldehyde",
        "cmr_type": "carcinogen",
        "cmr_category": "1B",
        "hazard_class": "Carc. 1B",
        "hazard_statements": "H350",
        "clp_notes": "May cause cancer by inhalation.",
        "atp_reference": "ATP 18",
    },
    {
        "cas_number": "7439-92-1",
        "ec_number": "231-100-4",
        "name": "Lead",
        "cmr_type": "reprotoxic",
        "cmr_category": "1A",
        "hazard_class": "Repr. 1A",
        "hazard_statements": "H360Df",
        "clp_notes": "May damage the unborn child. Suspected of damaging fertility.",
        "atp_reference": "ATP 14",
    },
    {
        "cas_number": "71-43-2",
        "ec_number": "200-753-7",
        "name": "Benzene",
        "cmr_type": "carcinogen",
        "cmr_category": "1A",
        "hazard_class": "Carc. 1A",
        "hazard_statements": "H350",
        "clp_notes": "May cause cancer.",
        "atp_reference": "ATP 12",
    },
]

ECHA_ENTRIES = [
    {
        "cas_number": "50-00-0",
        "ec_number": "200-001-8",
        "name": "Formaldehyde",
        "reach_status": "registered",
        "tonnage_band": "100-1000",
        "registration_type": "full",
        "index_number": "605-001-00-5",
        "clp_notes": "Annex VI harmonised classification",
        "atp_reference": "ATP 18",
    },
    {
        "cas_number": "7439-92-1",
        "ec_number": "231-100-4",
        "name": "Lead",
        "reach_status": "restricted",
        "tonnage_band": ">1000",
        "registration_type": "full",
        "index_number": "082-001-00-6",
        "clp_notes": "Annex XVII restriction entry 63",
        "atp_reference": "ATP 14",
    },
    {
        "cas_number": "71-43-2",
        "ec_number": "200-753-7",
        "name": "Benzene",
        "reach_status": "registered",
        "tonnage_band": ">1000",
        "registration_type": "full",
        "index_number": "601-020-00-8",
        "clp_notes": "Annex VI harmonised classification",
        "atp_reference": "ATP 12",
    },
]

CLP_ENTRIES = [
    {
        "cas_number": "50-00-0",
        "ec_number": "200-001-8",
        "name": "Formaldehyde",
        "hazard_class": "Carcinogenicity",
        "hazard_category": "Category 1B",
        "hazard_statement_code": "H350",
        "hazard_statement": "May cause cancer by inhalation.",
        "p_statements": "P201, P202, P281, P308+P313",
        "signal_word": "Danger",
        "pictograms": "GHS08, GHS06",
        "concentration_limit": "0.1%",
        "m_factor": "1",
    },
    {
        "cas_number": "7439-92-1",
        "ec_number": "231-100-4",
        "name": "Lead",
        "hazard_class": "Reproductive toxicity",
        "hazard_category": "Category 1A",
        "hazard_statement_code": "H360Df",
        "hazard_statement": "May damage the unborn child. Suspected of damaging fertility.",
        "p_statements": "P201, P202, P308+P313",
        "signal_word": "Danger",
        "pictograms": "GHS08, GHS07",
        "concentration_limit": "0.03%",
        "m_factor": "10",
    },
    {
        "cas_number": "71-43-2",
        "ec_number": "200-753-7",
        "name": "Benzene",
        "hazard_class": "Carcinogenicity",
        "hazard_category": "Category 1A",
        "hazard_statement_code": "H350",
        "hazard_statement": "May cause cancer.",
        "p_statements": "P201, P202, P281, P308+P313, P405, P501",
        "signal_word": "Danger",
        "pictograms": "GHS02, GHS08, GHS07",
        "concentration_limit": "0.1%",
        "m_factor": "1",
    },
]

GHS_ENTRIES = [
    {
        "cas_number": "50-00-0",
        "ec_number": "200-001-8",
        "name": "Formaldehyde",
        "ghs_hazard_class": "Carcinogenicity",
        "ghs_category": "Category 1B",
        "pictogram_codes": "GHS08, GHS06",
        "signal_word": "Danger",
        "hazard_statements": "H350, H330, H314, H301, H311, H331",
        "precautionary_statements": "P201, P202, P260, P264, P270, P271, P281, P284, P301+P310, P303+P361+P353, P304+P340, P310, P320, P330, P361, P363, P403+P233, P405, P501",
    },
    {
        "cas_number": "7439-92-1",
        "ec_number": "231-100-4",
        "name": "Lead",
        "ghs_hazard_class": "Reproductive toxicity / Specific target organ toxicity",
        "ghs_category": "Category 1A / Repeated exposure",
        "pictogram_codes": "GHS08, GHS07",
        "signal_word": "Danger",
        "hazard_statements": "H360Df, H372, H302, H332, H319, H335",
        "precautionary_statements": "P201, P202, P260, P261, P264, P270, P271, P281, P304+P340, P312, P314, P330, P403+P233, P405, P501",
    },
    {
        "cas_number": "71-43-2",
        "ec_number": "200-753-7",
        "name": "Benzene",
        "ghs_hazard_class": "Carcinogenicity / Flammable liquid",
        "ghs_category": "Category 1A / Category 2",
        "pictogram_codes": "GHS02, GHS08, GHS07",
        "signal_word": "Danger",
        "hazard_statements": "H350, H340, H304, H225, H315, H319",
        "precautionary_statements": "P201, P202, P210, P233, P240, P241, P242, P243, P260, P264, P280, P281, P303+P361+P353, P304+P340, P308+P313, P310, P331, P363, P370+P378, P403+P235, P405, P501",
    },
]


def seed_symbol_references(db):
    existing = db.query(SymbolReference).count()
    if existing > 0:
        logger.info("Symbol references already seeded (%d records). Skipping.", existing)
        return
    for sym in SYMBOLS:
        db.add(SymbolReference(**sym))
    db.commit()
    logger.info("Seeded %d symbol references.", len(SYMBOLS))


def seed_substances(db):
    existing = db.query(SubstanceLibrary).count()
    if existing > 0:
        logger.info("Substance library already seeded (%d records). Skipping.", existing)
        return

    for sub in SAMPLE_SUBSTANCES:
        substance = SubstanceLibrary(**sub)
        db.add(substance)
        db.flush()  # get ID

        # Link related entries by substance_id
        for cmr in CMR_ENTRIES:
            if cmr["cas_number"] == substance.cas_number:
                db.add(CMRSubstance(substance_id=substance.id, **cmr))
        for echa in ECHA_ENTRIES:
            if echa["cas_number"] == substance.cas_number:
                db.add(ECHASubstance(substance_id=substance.id, **echa))
        for clp in CLP_ENTRIES:
            if clp["cas_number"] == substance.cas_number:
                db.add(CLPClassification(substance_id=substance.id, **clp))
        for ghs in GHS_ENTRIES:
            if ghs["cas_number"] == substance.cas_number:
                db.add(GHSClassification(substance_id=substance.id, **ghs))

    db.commit()
    logger.info("Seeded %d sample substances with linked library entries.", len(SAMPLE_SUBSTANCES))


def run_seed():
    logging.basicConfig(level=logging.INFO)
    init_db()
    db = get_db()
    try:
        seed_symbol_references(db)
        seed_substances(db)
        logger.info("Seeding complete.")
    except Exception as e:
        logger.error("Seed error: %s", e)
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
