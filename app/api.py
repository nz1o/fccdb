import logging
from datetime import datetime, timezone
from typing import Optional, Any, List, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import text, func, or_, and_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Amateur, Entity, History, Header, UpdateLog, HistoryCode, OperatorClass, LicenseStatus
from app.fcc_loader import fcc_loader
from app.code_loader import load_code_definitions
from app.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# Response Models for OpenAPI Documentation
# ============================================================================

class NameInfo(BaseModel):
    """Licensee name information."""
    entity_name: Optional[str] = Field(None, description="Organization or club name")
    first_name: Optional[str] = Field(None, description="First name")
    mi: Optional[str] = Field(None, description="Middle initial")
    last_name: Optional[str] = Field(None, description="Last name")
    suffix: Optional[str] = Field(None, description="Name suffix (Jr, Sr, III, etc.)")

    class Config:
        json_schema_extra = {
            "example": {
                "entity_name": None,
                "first_name": "JOHN",
                "mi": "A",
                "last_name": "SMITH",
                "suffix": None
            }
        }


class AddressInfo(BaseModel):
    """Licensee address information."""
    street: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State (2-letter code)")
    zip_code: Optional[str] = Field(None, description="ZIP code")

    class Config:
        json_schema_extra = {
            "example": {
                "street": "225 MAIN ST",
                "city": "NEWINGTON",
                "state": "CT",
                "zip_code": "061111400"
            }
        }


class LicenseInfo(BaseModel):
    """License status and dates."""
    operator_class: Optional[str] = Field(None, description="License class code: E=Extra, G=General, T=Technician, A=Advanced, N=Novice")
    operator_class_desc: Optional[str] = Field(None, description="License class description")
    status: Optional[str] = Field(None, description="License status code: A=Active, E=Expired, C=Cancelled")
    status_desc: Optional[str] = Field(None, description="License status description")
    grant_date: Optional[str] = Field(None, description="Date license was granted (MM/DD/YYYY)")
    expired_date: Optional[str] = Field(None, description="Date license expires (MM/DD/YYYY)")
    cancellation_date: Optional[str] = Field(None, description="Date license was cancelled (MM/DD/YYYY)")

    class Config:
        json_schema_extra = {
            "example": {
                "operator_class": "E",
                "operator_class_desc": "Amateur Extra",
                "status": "A",
                "status_desc": "Active",
                "grant_date": "03/15/2023",
                "expired_date": "03/16/2033",
                "cancellation_date": None
            }
        }


class LicenseResult(BaseModel):
    """A single license record."""
    unique_system_identifier: Optional[str] = Field(None, description="Unique system identifier (USI)")
    call_sign: str = Field(..., description="Amateur radio callsign")
    name: NameInfo = Field(..., description="Licensee name information")
    attention_line: Optional[str] = Field(None, description="Attention line for address")
    address: AddressInfo = Field(..., description="Licensee address")
    frn: Optional[str] = Field(None, description="FCC Registration Number")
    license: LicenseInfo = Field(..., description="License status and dates")
    trustee_callsign: Optional[str] = Field(None, description="Trustee callsign for club stations")
    previous_callsign: Optional[str] = Field(None, description="Previous callsign if changed")

    class Config:
        json_schema_extra = {
            "example": {
                "call_sign": "W1AW",
                "name": {
                    "entity_name": "ARRL INC",
                    "first_name": None,
                    "mi": None,
                    "last_name": None,
                    "suffix": None
                },
                "address": {
                    "street": "225 MAIN ST",
                    "city": "NEWINGTON",
                    "state": "CT",
                    "zip_code": "061111400"
                },
                "frn": "0001430385",
                "license": {
                    "operator_class": "E",
                    "status": "A",
                    "grant_date": "03/15/2023",
                    "expired_date": "03/16/2033"
                },
                "trustee_callsign": "N1ND",
                "previous_callsign": None
            }
        }


class QueryResponse(BaseModel):
    """Response from license query endpoint."""
    total: int = Field(..., description="Total number of matching records")
    offset: int = Field(..., description="Number of records skipped")
    limit: int = Field(..., description="Maximum records returned")
    results: List[LicenseResult] = Field(..., description="License records")


class RefreshResponse(BaseModel):
    """Response from refresh endpoint."""
    message: str = Field(..., description="Status message")
    status: str = Field(..., description="Current status: in_progress, success, failed")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Database refresh started",
                "status": "in_progress"
            }
        }


class RefreshStatusResponse(BaseModel):
    """Response from refresh status endpoint."""
    status: str = Field(..., description="Status: in_progress, success, failed, never_run")
    message: Optional[str] = Field(None, description="Status message")
    update_time: Optional[str] = Field(None, description="ISO 8601 timestamp of last update")
    records_loaded: Optional[int] = Field(None, description="Number of records loaded")
    error_message: Optional[str] = Field(None, description="Error message if failed")


class VersionResponse(BaseModel):
    """Response from version endpoint."""
    last_update: Optional[str] = Field(None, description="ISO 8601 timestamp of last successful update")
    records_loaded: Optional[int] = Field(None, description="Number of records in last update")
    message: Optional[str] = Field(None, description="Message if no updates have been performed")


class TotalRecords(BaseModel):
    """Record counts by table."""
    entities: int = Field(..., description="Entity records (EN table)")
    amateur: int = Field(..., description="Amateur records (AM table)")
    headers: int = Field(..., description="Header records (HD table)")
    history: int = Field(..., description="History records (HS table)")


class StatsResponse(BaseModel):
    """Response from stats endpoint."""
    total_records: TotalRecords = Field(..., description="Record counts by table")
    active_licenses: int = Field(..., description="Number of active licenses")
    operator_classes: Dict[str, int] = Field(..., description="License count by operator class")
    top_states: Dict[str, int] = Field(..., description="Top 10 states by license count")
    last_update: Optional[str] = Field(None, description="ISO 8601 timestamp of last update")
    is_updating: bool = Field(..., description="Whether an update is currently in progress")


class HealthResponse(BaseModel):
    """Response from health check endpoint."""
    status: str = Field(..., description="Overall health status: healthy or unhealthy")
    database: str = Field(..., description="Database connection status")
    updating: bool = Field(..., description="Whether an update is currently in progress")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "database": "healthy",
                "updating": False
            }
        }


class FieldInfo(BaseModel):
    """Information about a queryable field."""
    name: str = Field(..., description="Field name to use in queries")
    description: str = Field(..., description="Description of the field")
    aliases: Optional[List[str]] = Field(None, description="Alternative names for this field")


class WildcardInfo(BaseModel):
    """Wildcard character documentation."""
    asterisk: str = Field(..., alias="*", description="Matches any number of characters")
    question: str = Field(..., alias="?", description="Matches exactly one character")


class FieldsResponse(BaseModel):
    """Response from fields endpoint."""
    fields: List[FieldInfo] = Field(..., description="List of queryable fields")
    wildcard_support: Dict[str, str] = Field(..., description="Wildcard characters and their meanings")
    examples: List[str] = Field(..., description="Example query URLs")


# ============================================================================
# API Router
# ============================================================================

router = APIRouter(prefix="/api", tags=["FCC License Database"])

# Mapping of query parameter names to model columns for the combined license view
QUERYABLE_FIELDS = {
    # Entity fields (EN)
    "call_sign": Entity.call_sign,
    "callsign": Entity.call_sign,  # alias
    "entity_name": Entity.entity_name,
    "first_name": Entity.first_name,
    "last_name": Entity.last_name,
    "city": Entity.city,
    "state": Entity.state,
    "zip_code": Entity.zip_code,
    "street_address": Entity.street_address,
    "frn": Entity.frn,
    # Amateur fields (AM)
    "operator_class": Amateur.operator_class,
    "trustee_callsign": Amateur.trustee_callsign,
    "previous_callsign": Amateur.previous_callsign,
    # Header fields (HD)
    "license_status": Header.license_status,
    "grant_date": Header.grant_date,
    "expired_date": Header.expired_date,
}


def wildcard_to_like(value: str) -> str:
    """Convert wildcard pattern to SQL LIKE pattern."""
    # Replace * with % and ? with _
    return value.replace("*", "%").replace("?", "_")


@router.get(
    "/query",
    response_model=QueryResponse,
    summary="Query license database",
    description="""
Search the FCC amateur radio license database with flexible filtering options.

## Wildcard Support

All string fields support wildcard searches:
- `*` matches any number of characters (including zero)
- `?` matches exactly one character

## Examples

| Query | Description |
|-------|-------------|
| `call_sign=W1AW` | Exact callsign match |
| `call_sign=W1*` | All callsigns starting with W1 |
| `call_sign=*AW` | All callsigns ending with AW |
| `call_sign=W?AW` | Callsigns like W1AW, W2AW, etc. |
| `state=CA&operator_class=E` | Extra class licenses in California |
| `last_name=Smith&city=Boston` | People named Smith in Boston |
| `street_address=*Main St*` | Addresses containing "Main St" |

## Pagination

Use `limit` and `offset` for pagination. Maximum limit is 1000 records per request.
    """,
    responses={
        200: {
            "description": "Successful query",
            "content": {
                "application/json": {
                    "example": {
                        "total": 1,
                        "offset": 0,
                        "limit": 100,
                        "results": [{
                            "call_sign": "W1AW",
                            "name": {"entity_name": "ARRL INC", "first_name": None, "mi": None, "last_name": None, "suffix": None},
                            "address": {"street": "225 MAIN ST", "city": "NEWINGTON", "state": "CT", "zip_code": "061111400"},
                            "frn": "0001430385",
                            "license": {"operator_class": "E", "status": "A", "grant_date": "03/15/2023", "expired_date": "03/16/2033"},
                            "trustee_callsign": "N1ND",
                            "previous_callsign": None
                        }]
                    }
                }
            }
        },
        400: {"description": "No search parameters provided"}
    }
)
async def query_licenses(
    db: Session = Depends(get_db),
    call_sign: Optional[str] = Query(
        None,
        description="Callsign to search for. Supports wildcards: W1AW, W1*, *AW, W?AW",
        examples=["W1AW", "W1*", "K?ABC"]
    ),
    callsign: Optional[str] = Query(None, description="Alias for call_sign", include_in_schema=False),
    entity_name: Optional[str] = Query(
        None,
        description="Organization or club name. Supports wildcards.",
        examples=["ARRL*", "*Radio Club*"]
    ),
    first_name: Optional[str] = Query(
        None,
        description="First name of licensee. Supports wildcards.",
        examples=["John", "J*"]
    ),
    last_name: Optional[str] = Query(
        None,
        description="Last name of licensee. Supports wildcards.",
        examples=["Smith", "*son"]
    ),
    city: Optional[str] = Query(
        None,
        description="City name. Supports wildcards.",
        examples=["Boston", "*port*"]
    ),
    state: Optional[str] = Query(
        None,
        description="Two-letter state code",
        examples=["CA", "TX", "MA"],
        min_length=2,
        max_length=2
    ),
    zip_code: Optional[str] = Query(
        None,
        description="ZIP code (5 or 9 digits). Supports wildcards.",
        examples=["02101", "021*"]
    ),
    street_address: Optional[str] = Query(
        None,
        description="Street address. Supports wildcards.",
        examples=["*Main St*", "123 Oak*"]
    ),
    frn: Optional[str] = Query(
        None,
        description="FCC Registration Number (10 digits)",
        examples=["0001430385"]
    ),
    operator_class: Optional[str] = Query(
        None,
        description="License class: E=Extra, G=General, T=Technician, A=Advanced, N=Novice",
        examples=["E", "G", "T"]
    ),
    license_status: Optional[str] = Query(
        None,
        description="License status: A=Active, E=Expired, C=Cancelled",
        examples=["A"]
    ),
    limit: int = Query(
        100,
        ge=1,
        le=1000,
        description="Maximum number of results to return (1-1000)"
    ),
    offset: int = Query(
        0,
        ge=0,
        description="Number of results to skip for pagination"
    ),
):
    """
    Query the FCC amateur radio license database.

    Supports wildcard searches using * (any characters) and ? (single character).
    """
    # Collect query parameters
    params = {
        "call_sign": call_sign or callsign,
        "entity_name": entity_name,
        "first_name": first_name,
        "last_name": last_name,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "street_address": street_address,
        "frn": frn,
        "operator_class": operator_class,
        "license_status": license_status,
    }

    # Remove None values
    params = {k: v for k, v in params.items() if v is not None}

    if not params:
        raise HTTPException(
            status_code=400,
            detail="At least one search parameter is required"
        )

    # Build the query - join EN, AM, HD, and code lookup tables
    query = (
        db.query(
            Entity.unique_system_identifier,
            Entity.call_sign,
            Entity.entity_name,
            Entity.first_name,
            Entity.mi,
            Entity.last_name,
            Entity.suffix,
            Entity.attention_line,
            Entity.street_address,
            Entity.city,
            Entity.state,
            Entity.zip_code,
            Entity.frn,
            Amateur.operator_class,
            OperatorClass.description.label("operator_class_desc"),
            Amateur.trustee_callsign,
            Amateur.previous_callsign,
            Header.license_status,
            LicenseStatus.description.label("license_status_desc"),
            Header.grant_date,
            Header.expired_date,
            Header.cancellation_date,
        )
        .join(
            Amateur,
            Entity.unique_system_identifier == Amateur.unique_system_identifier,
            isouter=True
        )
        .join(
            Header,
            Entity.unique_system_identifier == Header.unique_system_identifier,
            isouter=True
        )
        .outerjoin(
            OperatorClass,
            Amateur.operator_class == OperatorClass.code
        )
        .outerjoin(
            LicenseStatus,
            Header.license_status == LicenseStatus.code
        )
        .filter(Entity.entity_type == "L")  # Licensee records only
    )

    # Apply filters
    for param_name, value in params.items():
        column = QUERYABLE_FIELDS.get(param_name)
        if column is None:
            continue

        if "*" in value or "?" in value:
            # Wildcard search - use ILIKE for case-insensitive matching
            pattern = wildcard_to_like(value)
            query = query.filter(column.ilike(pattern))
        else:
            # Exact match (case-insensitive)
            query = query.filter(func.upper(column) == value.upper())

    # Get total count before pagination
    total_count = query.count()

    # Apply pagination and execute
    results = query.offset(offset).limit(limit).all()

    # Format results
    licenses = []
    for row in results:
        licenses.append({
            "unique_system_identifier": row.unique_system_identifier,
            "call_sign": row.call_sign,
            "name": {
                "entity_name": row.entity_name,
                "first_name": row.first_name,
                "mi": row.mi,
                "last_name": row.last_name,
                "suffix": row.suffix,
            },
            "attention_line": row.attention_line,
            "address": {
                "street": row.street_address,
                "city": row.city,
                "state": row.state,
                "zip_code": row.zip_code,
            },
            "frn": row.frn,
            "license": {
                "operator_class": row.operator_class,
                "operator_class_desc": row.operator_class_desc,
                "status": row.license_status,
                "status_desc": row.license_status_desc,
                "grant_date": row.grant_date,
                "expired_date": row.expired_date,
                "cancellation_date": row.cancellation_date,
            },
            "trustee_callsign": row.trustee_callsign,
            "previous_callsign": row.previous_callsign,
        })

    return {
        "total": total_count,
        "offset": offset,
        "limit": limit,
        "results": licenses
    }


def _query_by_callsign(db: Session, call_sign: str):
    """Query the database for an exact callsign match and return formatted results."""
    query = (
        db.query(
            Entity.unique_system_identifier,
            Entity.call_sign,
            Entity.entity_name,
            Entity.first_name,
            Entity.mi,
            Entity.last_name,
            Entity.suffix,
            Entity.attention_line,
            Entity.street_address,
            Entity.city,
            Entity.state,
            Entity.zip_code,
            Entity.frn,
            Amateur.operator_class,
            OperatorClass.description.label("operator_class_desc"),
            Amateur.trustee_callsign,
            Amateur.previous_callsign,
            Header.license_status,
            LicenseStatus.description.label("license_status_desc"),
            Header.grant_date,
            Header.expired_date,
            Header.cancellation_date,
        )
        .join(
            Amateur,
            Entity.unique_system_identifier == Amateur.unique_system_identifier,
            isouter=True
        )
        .join(
            Header,
            Entity.unique_system_identifier == Header.unique_system_identifier,
            isouter=True
        )
        .outerjoin(
            OperatorClass,
            Amateur.operator_class == OperatorClass.code
        )
        .outerjoin(
            LicenseStatus,
            Header.license_status == LicenseStatus.code
        )
        .filter(Entity.entity_type == "L")
        .filter(func.upper(Entity.call_sign) == call_sign.upper())
    )
    results = query.all()
    licenses = []
    for row in results:
        licenses.append({
            "unique_system_identifier": row.unique_system_identifier,
            "call_sign": row.call_sign,
            "name": {
                "entity_name": row.entity_name,
                "first_name": row.first_name,
                "mi": row.mi,
                "last_name": row.last_name,
                "suffix": row.suffix,
            },
            "attention_line": row.attention_line,
            "address": {
                "street": row.street_address,
                "city": row.city,
                "state": row.state,
                "zip_code": row.zip_code,
            },
            "frn": row.frn,
            "license": {
                "operator_class": row.operator_class,
                "operator_class_desc": row.operator_class_desc,
                "status": row.license_status,
                "status_desc": row.license_status_desc,
                "grant_date": row.grant_date,
                "expired_date": row.expired_date,
                "cancellation_date": row.cancellation_date,
            },
            "trustee_callsign": row.trustee_callsign,
            "previous_callsign": row.previous_callsign,
        })
    return licenses


@router.get(
    "/query/call",
    response_model=QueryResponse,
    summary="Query by callsign",
    description="Look up a specific callsign and return matching results as JSON.",
)
async def query_call_json(
    call_sign: str = Query(..., description="Full callsign to look up"),
    db: Session = Depends(get_db),
):
    """Query the FCC database by exact callsign and return JSON."""
    licenses = _query_by_callsign(db, call_sign)
    return {
        "total": len(licenses),
        "offset": 0,
        "limit": len(licenses),
        "results": licenses
    }


def _format_license_text(lic: dict) -> str:
    """Format a single license record as text."""
    name = lic["name"]["entity_name"] or ""
    attention = lic.get("attention_line") or ""
    addr = lic["address"]
    street = addr.get("street") or ""
    city = addr.get("city") or ""
    state = addr.get("state") or ""
    zip_code = addr.get("zip_code") or ""
    address_line = f"{street} {city} {state} {zip_code}".strip()
    license_info = lic["license"]
    # Format class with description if available
    op_class = license_info.get('operator_class') or ''
    op_class_desc = license_info.get('operator_class_desc') or ''
    class_str = f"{op_class} ({op_class_desc})" if op_class_desc else op_class
    # Format status with description if available
    status = license_info.get('status') or ''
    status_desc = license_info.get('status_desc') or ''
    status_str = f"{status} ({status_desc})" if status_desc else status
    lines = [
        f"USI:      {lic.get('unique_system_identifier') or ''}",
        f"FRN:      {lic.get('frn') or ''}",
        f"Name:     {name}",
    ]
    if attention:
        lines.append(f"Attn:     {attention}")
    lines.extend([
        f"Address:  {address_line}",
        f"Class:    {class_str}",
        f"Status:   {status_str}",
        f"Granted:  {license_info.get('grant_date') or ''}",
        f"Expires:  {license_info.get('expired_date') or ''}",
    ])
    if license_info.get('cancellation_date'):
        lines.append(f"Cancelled: {license_info.get('cancellation_date')}")
    lines.append(f"Previous: {lic.get('previous_callsign') or ''}")
    return "\n".join(lines)


@router.get(
    "/query/callastext",
    response_class=PlainTextResponse,
    summary="Query by callsign (text)",
    description="Look up a specific callsign and return matching results as plain text.",
)
async def query_call_text(
    call_sign: str = Query(..., description="Full callsign to look up"),
    db: Session = Depends(get_db),
):
    """Query the FCC database by exact callsign and return plain text."""
    licenses = _query_by_callsign(db, call_sign)

    active = [l for l in licenses if l["license"].get("status") == "A"]
    inactive = [l for l in licenses if l["license"].get("status") != "A"]

    sections = []
    sections.append("Active Licenses:\n")
    if active:
        sections.append("\n\n".join(_format_license_text(l) for l in active))
    sections.append("\nInactive Licenses:\n")
    if inactive:
        sections.append("\n\n".join(_format_license_text(l) for l in inactive))

    return "\n".join(sections) + "\n"


class HistoryEntry(BaseModel):
    """A single history entry."""
    callsign: Optional[str] = Field(None, description="Callsign")
    log_date: Optional[str] = Field(None, description="Date of the history event")
    code: Optional[str] = Field(None, description="History event code")
    description: Optional[str] = Field(None, description="Description of the history event")

    class Config:
        from_attributes = True


class HistoryByUsiResponse(BaseModel):
    """Response model for history queries by USI."""
    total: int = Field(..., description="Total number of history entries")
    unique_system_identifier: str = Field(..., description="The unique system identifier queried")
    results: List[HistoryEntry] = Field(..., description="List of history entries")


class HistoryByFrnResponse(BaseModel):
    """Response model for history queries by FRN."""
    total: int = Field(..., description="Total number of history entries")
    frn: str = Field(..., description="The FRN queried")
    unique_system_identifiers: List[str] = Field(..., description="USIs associated with this FRN")
    results: List[HistoryEntry] = Field(..., description="List of history entries")


@router.get(
    "/query/history/usi",
    response_model=HistoryByUsiResponse,
    summary="Query license history by USI",
    description="Look up license history by unique_system_identifier.",
)
async def query_history_by_usi(
    usi: str = Query(..., description="Unique system identifier to look up history for"),
    db: Session = Depends(get_db),
):
    """Query the FCC database for license history by unique_system_identifier."""
    results = (
        db.query(
            History.callsign,
            History.log_date,
            History.code,
            HistoryCode.description,
        )
        .outerjoin(HistoryCode, History.code == HistoryCode.code)
        .filter(History.unique_system_identifier == usi)
        .order_by(History.log_date.desc())
        .all()
    )

    entries = [
        {
            "callsign": row.callsign,
            "log_date": row.log_date,
            "code": row.code,
            "description": row.description,
        }
        for row in results
    ]

    return {
        "total": len(entries),
        "unique_system_identifier": usi,
        "results": entries
    }


@router.get(
    "/query/history/frn",
    response_model=HistoryByFrnResponse,
    summary="Query license history by FRN",
    description="Look up license history for all licenses associated with an FRN.",
)
async def query_history_by_frn(
    frn: str = Query(..., description="FCC Registration Number to look up history for"),
    db: Session = Depends(get_db),
):
    """Query the FCC database for license history by FRN (all associated licenses)."""
    # First, find all unique_system_identifiers associated with this FRN
    usi_results = (
        db.query(Entity.unique_system_identifier)
        .filter(Entity.frn == frn)
        .distinct()
        .all()
    )

    usis = [row.unique_system_identifier for row in usi_results]

    if not usis:
        return {
            "total": 0,
            "frn": frn,
            "unique_system_identifiers": [],
            "results": []
        }

    # Query history for all associated USIs
    results = (
        db.query(
            History.callsign,
            History.log_date,
            History.code,
            HistoryCode.description,
        )
        .outerjoin(HistoryCode, History.code == HistoryCode.code)
        .filter(History.unique_system_identifier.in_(usis))
        .order_by(History.log_date.desc())
        .all()
    )

    entries = [
        {
            "callsign": row.callsign,
            "log_date": row.log_date,
            "code": row.code,
            "description": row.description,
        }
        for row in results
    ]

    return {
        "total": len(entries),
        "frn": frn,
        "unique_system_identifiers": usis,
        "results": entries
    }


@router.get(
    "/codes/history",
    summary="List history codes",
    description="Get all history code definitions.",
)
async def list_history_codes(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
):
    """List all history code definitions."""
    total = db.query(HistoryCode).count()
    codes = db.query(HistoryCode).offset(offset).limit(limit).all()
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "codes": [{"code": c.code, "description": c.description} for c in codes]
    }


@router.get(
    "/codes/operator-class",
    summary="List operator class codes",
    description="Get all operator class code definitions.",
)
async def list_operator_classes(db: Session = Depends(get_db)):
    """List all operator class definitions."""
    codes = db.query(OperatorClass).all()
    return {
        "total": len(codes),
        "codes": [{"code": c.code, "description": c.description} for c in codes]
    }


@router.get(
    "/codes/license-status",
    summary="List license status codes",
    description="Get all license status code definitions.",
)
async def list_license_statuses(db: Session = Depends(get_db)):
    """List all license status definitions."""
    codes = db.query(LicenseStatus).all()
    return {
        "total": len(codes),
        "codes": [{"code": c.code, "description": c.description} for c in codes]
    }


@router.post(
    "/codes/reload",
    summary="Reload code definitions",
    description="Reload all code definitions from the ULS definitions file.",
)
async def reload_codes():
    """Reload code definitions from file."""
    try:
        counts = load_code_definitions()
        return {
            "message": "Code definitions reloaded successfully",
            "counts": counts
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Force database refresh",
    description="""
Trigger an immediate refresh of the FCC database from the online source.

The refresh downloads approximately 100MB of data and processes it in the background.
This typically takes several minutes to complete.

Use `/api/refresh/status` or `/api/version` to check when the update completes.
    """,
    responses={
        200: {"description": "Refresh started successfully"},
        409: {"description": "A refresh is already in progress"}
    }
)
async def refresh_database(background_tasks: BackgroundTasks):
    """
    Force a refresh of the FCC database from the online source.

    The refresh runs in the background. Use /api/version to check
    when the update completes.
    """
    if fcc_loader.is_loading:
        raise HTTPException(
            status_code=409,
            detail="A database refresh is already in progress"
        )

    background_tasks.add_task(fcc_loader.run_full_update)

    return {
        "message": "Database refresh started",
        "status": "in_progress"
    }


@router.get(
    "/refresh/status",
    response_model=RefreshStatusResponse,
    summary="Get refresh status",
    description="Get the status of the current or most recent database refresh operation."
)
async def refresh_status(db: Session = Depends(get_db)):
    """Get the status of the current or most recent database refresh."""
    if fcc_loader.is_loading:
        return {
            "status": "in_progress",
            "message": "Database refresh is currently running"
        }

    # Get most recent update log
    latest = (
        db.query(UpdateLog)
        .order_by(UpdateLog.update_time.desc())
        .first()
    )

    if not latest:
        return {
            "status": "never_run",
            "message": "No database refresh has been performed"
        }

    return {
        "status": latest.status,
        "update_time": latest.update_time.isoformat() if latest.update_time else None,
        "records_loaded": latest.records_loaded,
        "error_message": latest.error_message
    }


@router.get(
    "/version",
    response_model=VersionResponse,
    summary="Get database version",
    description="Get the date and details of the most recent successful data pull from the FCC database."
)
async def get_version(db: Session = Depends(get_db)):
    """
    Get the date of the most recent successful data pull from the FCC database.
    """
    latest = (
        db.query(UpdateLog)
        .filter(UpdateLog.status == "success")
        .order_by(UpdateLog.update_time.desc())
        .first()
    )

    if not latest:
        return {
            "last_update": None,
            "message": "No successful update has been performed"
        }

    return {
        "last_update": latest.update_time.isoformat(),
        "records_loaded": latest.records_loaded
    }


@router.get(
    "/stats",
    response_model=StatsResponse,
    summary="Get database statistics",
    description="""
Get comprehensive statistics about the license database including:
- Total record counts by table
- Number of active licenses
- License distribution by operator class
- Top 10 states by license count
- Last update timestamp
    """
)
async def get_stats(db: Session = Depends(get_db)):
    """
    Get statistics about the license database.
    """
    # Count records in each table
    en_count = db.query(func.count(Entity.id)).scalar() or 0
    am_count = db.query(func.count(Amateur.id)).scalar() or 0
    hd_count = db.query(func.count(Header.id)).scalar() or 0
    hs_count = db.query(func.count(History.id)).scalar() or 0

    # Count unique callsigns with active licenses
    active_licenses = (
        db.query(func.count(func.distinct(Header.call_sign)))
        .filter(Header.license_status == "A")
        .scalar() or 0
    )

    # Count by operator class
    class_counts = (
        db.query(Amateur.operator_class, func.count(Amateur.id))
        .group_by(Amateur.operator_class)
        .all()
    )
    operator_classes = {row[0] or "Unknown": row[1] for row in class_counts}

    # Count by state
    state_counts = (
        db.query(Entity.state, func.count(Entity.id))
        .filter(Entity.entity_type == "L")
        .filter(Entity.state.isnot(None))
        .filter(Entity.state != "")
        .group_by(Entity.state)
        .order_by(func.count(Entity.id).desc())
        .limit(10)
        .all()
    )
    top_states = {row[0]: row[1] for row in state_counts}

    # Get last update info
    latest = (
        db.query(UpdateLog)
        .filter(UpdateLog.status == "success")
        .order_by(UpdateLog.update_time.desc())
        .first()
    )

    return {
        "total_records": {
            "entities": en_count,
            "amateur": am_count,
            "headers": hd_count,
            "history": hs_count,
        },
        "active_licenses": active_licenses,
        "operator_classes": operator_classes,
        "top_states": top_states,
        "last_update": latest.update_time.isoformat() if latest else None,
        "is_updating": fcc_loader.is_loading
    }


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Health check endpoint for container orchestration and monitoring systems.",
    tags=["System"]
)
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint for container orchestration."""
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "database": db_status,
        "updating": fcc_loader.is_loading
    }


@router.get(
    "/fields",
    response_model=FieldsResponse,
    summary="List queryable fields",
    description="List all fields that can be used in the /api/query endpoint with descriptions and examples.",
    tags=["Documentation"]
)
async def list_queryable_fields():
    """List all fields that can be used in queries."""
    return {
        "fields": [
            {"name": "call_sign", "description": "Amateur radio callsign", "aliases": ["callsign"]},
            {"name": "entity_name", "description": "Entity/organization name (for clubs)"},
            {"name": "first_name", "description": "First name of licensee"},
            {"name": "last_name", "description": "Last name of licensee"},
            {"name": "city", "description": "City"},
            {"name": "state", "description": "State (2-letter code, e.g., CA, TX, MA)"},
            {"name": "zip_code", "description": "ZIP code (5 or 9 digits)"},
            {"name": "street_address", "description": "Street address"},
            {"name": "frn", "description": "FCC Registration Number (10 digits)"},
            {"name": "operator_class", "description": "License class: E=Extra, G=General, T=Technician, A=Advanced (grandfathered), N=Novice (grandfathered)"},
            {"name": "license_status", "description": "License status: A=Active, E=Expired, C=Cancelled"},
        ],
        "wildcard_support": {
            "*": "Matches any number of characters (including zero)",
            "?": "Matches exactly one character"
        },
        "examples": [
            "/api/query?call_sign=W1AW",
            "/api/query?call_sign=W1*",
            "/api/query?call_sign=K?ABC",
            "/api/query?state=CA&operator_class=E",
            "/api/query?last_name=Smith&city=Boston",
            "/api/query?street_address=*Main St*",
        ]
    }
