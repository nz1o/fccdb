import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.models import Base
from app.api import router as api_router
from app.scheduler import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown."""
    # Startup
    logger.info("Starting FCC Database API")

    # Create database tables
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    # Start the scheduler for automatic updates
    start_scheduler()

    yield

    # Shutdown
    logger.info("Shutting down FCC Database API")
    stop_scheduler()


app = FastAPI(
    title="FCC Amateur Radio License Database API",
    description="""
# FCC Amateur Radio License Database API

A REST API for querying an offline copy of the FCC Amateur Radio License Database.

## Features

- **Full Database**: Contains all US amateur radio licenses (~800,000+ records)
- **Wildcard Search**: Query using `*` (any characters) and `?` (single character)
- **Multiple Query Fields**: Search by callsign, name, location, license class, and more
- **Automatic Updates**: Configurable automatic refresh from FCC data (default: every 7 days)
- **Manual Refresh**: Trigger updates on demand via API

## Quick Start

### Lookup a callsign
```
GET /api/query?call_sign=W1AW
```

### Search with wildcards
```
GET /api/query?call_sign=W1*
GET /api/query?last_name=Smith&state=CA
GET /api/query?street_address=*Main St*
```

## License Classes

| Code | Class | Description |
|------|-------|-------------|
| E | Extra | Highest class, all privileges |
| G | General | HF privileges with some restrictions |
| T | Technician | Entry level, primarily VHF/UHF |
| A | Advanced | Grandfathered, no longer issued |
| N | Novice | Grandfathered, no longer issued |

## License Status Codes

| Code | Status |
|------|--------|
| A | Active |
| E | Expired |
| C | Cancelled |

## Data Source

Data is sourced from the FCC Universal Licensing System (ULS):
- URL: https://data.fcc.gov/download/pub/uls/complete/l_amat.zip
- Format: Pipe-delimited text files
- Update frequency: Weekly (configurable)
    """,
    version="1.0.0",
    lifespan=lifespan,
    contact={
        "name": "FCC Database API",
        "url": "https://github.com/your-repo/fccdb",
    },
    license_info={
        "name": "Public Domain",
        "identifier": "Unlicense",
    },
    openapi_tags=[
        {
            "name": "FCC License Database",
            "description": "Query and manage the FCC amateur radio license database",
        },
        {
            "name": "System",
            "description": "System health and status endpoints",
        },
        {
            "name": "Documentation",
            "description": "API documentation and field information",
        },
    ],
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "FCC Amateur Radio License Database API",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "query": "/api/query",
            "refresh": "/api/refresh",
            "version": "/api/version",
            "stats": "/api/stats",
            "health": "/api/health",
            "fields": "/api/fields",
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_interface,
        port=settings.api_port,
        reload=False
    )
