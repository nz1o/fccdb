import logging
from datetime import datetime, timezone
from typing import Optional, Any, List, Dict

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text, func, or_, and_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Amateur, Entity, History, Header, UpdateLog
from app.fcc_loader import fcc_loader
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
    operator_class: Optional[str] = Field(None, description="License class: E=Extra, G=General, T=Technician, A=Advanced, N=Novice")
    status: Optional[str] = Field(None, description="License status: A=Active, E=Expired, C=Cancelled")
    grant_date: Optional[str] = Field(None, description="Date license was granted (MM/DD/YYYY)")
    expired_date: Optional[str] = Field(None, description="Date license expires (MM/DD/YYYY)")

    class Config:
        json_schema_extra = {
            "example": {
                "operator_class": "E",
                "status": "A",
                "grant_date": "03/15/2023",
                "expired_date": "03/16/2033"
            }
        }


class LicenseResult(BaseModel):
    """A single license record."""
    call_sign: str = Field(..., description="Amateur radio callsign")
    name: NameInfo = Field(..., description="Licensee name information")
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

    # Build the query - join EN, AM, and HD tables
    query = (
        db.query(
            Entity.call_sign,
            Entity.entity_name,
            Entity.first_name,
            Entity.mi,
            Entity.last_name,
            Entity.suffix,
            Entity.street_address,
            Entity.city,
            Entity.state,
            Entity.zip_code,
            Entity.frn,
            Amateur.operator_class,
            Amateur.trustee_callsign,
            Amateur.previous_callsign,
            Header.license_status,
            Header.grant_date,
            Header.expired_date,
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
            "call_sign": row.call_sign,
            "name": {
                "entity_name": row.entity_name,
                "first_name": row.first_name,
                "mi": row.mi,
                "last_name": row.last_name,
                "suffix": row.suffix,
            },
            "address": {
                "street": row.street_address,
                "city": row.city,
                "state": row.state,
                "zip_code": row.zip_code,
            },
            "frn": row.frn,
            "license": {
                "operator_class": row.operator_class,
                "status": row.license_status,
                "grant_date": row.grant_date,
                "expired_date": row.expired_date,
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
