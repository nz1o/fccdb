"""
Loader for ULS code definitions (history codes, operator classes, license status).
Parses the FCC ULS code definitions file and populates lookup tables.
"""

import logging
import os
import re
from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import HistoryCode, OperatorClass, LicenseStatus

logger = logging.getLogger(__name__)

# Static definitions for operator class and license status
# These are small and stable, so we define them here rather than parsing
OPERATOR_CLASSES = [
    ("A", "Advanced"),
    ("E", "Amateur Extra"),
    ("G", "General"),
    ("N", "Novice"),
    ("P", "Technician Plus"),
    ("T", "Technician"),
]

LICENSE_STATUSES = [
    ("A", "Active"),
    ("C", "Cancelled"),
    ("E", "Expired"),
    ("T", "Terminated"),
]


def parse_history_codes(filepath: str) -> List[Tuple[str, str]]:
    """
    Parse history codes from ULS code definitions file.

    Returns list of (code, description) tuples.
    """
    codes = []
    in_history_section = False

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            # Check for start of history section
            if line.startswith("HS\tHistory Code"):
                in_history_section = True
                continue

            # Check for end of history section (next section header)
            if in_history_section and re.match(r'^[A-Z][A-Z0-9]\t[A-Za-z]', line):
                break

            if in_history_section:
                # History code lines start with a tab
                if line.startswith('\t'):
                    # Parse: \t<code>\t<description>
                    # The line format is: \tCODE\t\t\tDescription
                    parts = line.strip().split('\t')
                    if len(parts) >= 2:
                        code = parts[0].strip()
                        # Find the description (first non-empty part after code)
                        description = ""
                        for part in parts[1:]:
                            if part.strip():
                                description = part.strip()
                                break
                        if code and description:
                            codes.append((code, description))

    logger.info(f"Parsed {len(codes)} history codes from {filepath}")
    return codes


def load_code_definitions(definitions_file: str = None) -> Dict[str, int]:
    """
    Load all code definitions into the database.

    Args:
        definitions_file: Path to ULS code definitions file.
                         If None, uses the path from settings.

    Returns:
        Dict with counts of loaded records by type.
    """
    # Find the definitions file
    if definitions_file is None:
        definitions_file = settings.uls_code_definitions_file
        # If config path doesn't exist, check fallback locations
        if not os.path.exists(definitions_file):
            possible_paths = [
                "uls_definitions/uls_code_definitions_20240718.txt",
                "/app/uls_definitions/uls_code_definitions_20240718.txt",
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    definitions_file = path
                    break

    db = SessionLocal()
    counts = {"history_codes": 0, "operator_classes": 0, "license_statuses": 0}

    try:
        # Load operator classes (static)
        db.query(OperatorClass).delete()
        for code, description in OPERATOR_CLASSES:
            db.add(OperatorClass(code=code, description=description))
        counts["operator_classes"] = len(OPERATOR_CLASSES)
        logger.info(f"Loaded {counts['operator_classes']} operator classes")

        # Load license statuses (static)
        db.query(LicenseStatus).delete()
        for code, description in LICENSE_STATUSES:
            db.add(LicenseStatus(code=code, description=description))
        counts["license_statuses"] = len(LICENSE_STATUSES)
        logger.info(f"Loaded {counts['license_statuses']} license statuses")

        # Load history codes from file
        if definitions_file and os.path.exists(definitions_file):
            history_codes = parse_history_codes(definitions_file)
            db.query(HistoryCode).delete()
            for code, description in history_codes:
                db.add(HistoryCode(code=code, description=description))
            counts["history_codes"] = len(history_codes)
            logger.info(f"Loaded {counts['history_codes']} history codes")
        else:
            logger.warning(
                "ULS code definitions file not found. "
                "History code descriptions will not be available."
            )

        db.commit()
        logger.info("Code definitions loaded successfully")

    except Exception as e:
        logger.error(f"Error loading code definitions: {e}")
        db.rollback()
        raise
    finally:
        db.close()

    return counts


def get_history_code_description(db: Session, code: str) -> str:
    """Get the description for a history code."""
    result = db.query(HistoryCode).filter(HistoryCode.code == code).first()
    return result.description if result else None


def get_operator_class_description(db: Session, code: str) -> str:
    """Get the description for an operator class code."""
    result = db.query(OperatorClass).filter(OperatorClass.code == code).first()
    return result.description if result else None


def get_license_status_description(db: Session, code: str) -> str:
    """Get the description for a license status code."""
    result = db.query(LicenseStatus).filter(LicenseStatus.code == code).first()
    return result.description if result else None
