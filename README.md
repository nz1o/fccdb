**Warning! This application is in no way hardened or secure. The entire first draft of the OWASP Top 10 probably could have been written with this single example. DO NOT run this application exposed to anyone that you do not trust.**

---

# FCC Amateur Radio License Database API

A containerized service that maintains an offline copy of the FCC Amateur Radio License database with a REST API for querying license data.

## Overview

This service automatically downloads and maintains a local PostgreSQL copy of the FCC Universal Licensing System (ULS) amateur radio database. It provides a fast, queryable API for license lookups without depending on external services.

## Features

- **Automatic Updates**: Configurable automatic refresh from FCC data (default: every 7 days)
- **Full Database**: Contains all US amateur radio licenses with associated data
- **Wildcard Search**: Query using `*` (any characters) and `?` (single character) wildcards
- **Multiple Query Fields**: Search by callsign, name, location, license class, and more
- **Code Lookups**: Human-readable descriptions for operator classes, license statuses, and 463+ history event codes
- **License History**: Query license history by USI or FRN with event descriptions
- **Multiple Output Formats**: JSON and plain text output options
- **RESTful API**: Clean JSON API with interactive Swagger documentation
- **Containerized**: Easy deployment with Docker Compose
- **Staging Pattern**: Uses staging tables to ensure zero-downtime updates

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed on your system:

| Requirement | Minimum Version | Check Command |
|-------------|-----------------|---------------|
| Docker | 20.10+ | `docker --version` |
| Docker Compose | 2.0+ | `docker compose version` |
| Git | 2.0+ | `git --version` |
| curl (optional) | any | `curl --version` |

**System Requirements:**
- **Disk Space**: ~3 GB for the full FCC database
- **Memory**: 2 GB RAM minimum (4 GB recommended during initial data load)
- **Network**: Internet access required for downloading FCC data (~500 MB download)

### Step 1: Download the Repository

```bash
# Clone the repository
git clone https://github.com/yourusername/fccdb.git

# Navigate to the project directory
cd fccdb
```

### Step 2: Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit the configuration file
nano .env   # or use your preferred text editor
```

**Required Changes:**

1. **Set a secure database password** - Replace `your_secure_password_here` with a strong password:
   ```
   POSTGRES_PASSWORD=MySecureP@ssw0rd!
   ```

2. **Update the DATABASE_URL** to match your password:
   ```
   DATABASE_URL=postgresql://fcc:MySecureP@ssw0rd!@db:5432/fccdb
   ```

**Optional Changes:**

| Variable | Default | When to Change |
|----------|---------|----------------|
| `API_PORT` | `8010` | If port 8010 is already in use |
| `AUTO_UPDATE_DAYS` | `7` | To change how often data refreshes |

### Step 3: Start the Service

```bash
# Start the containers in detached mode
docker compose up -d

# Verify both containers are running
docker compose ps
```

You should see two containers running:
- `fccdb-postgres` - The PostgreSQL database
- `fccdb-api` - The FastAPI application

### Step 4: Wait for Initial Data Load

The service automatically downloads FCC data (~500 MB) approximately 30 seconds after startup. This initial load takes 5-15 minutes depending on your internet speed and system performance.

**Monitor the progress:**

```bash
# Watch the API logs
docker compose logs -f api
```

You'll see messages like:
```
INFO - Starting FCC data download...
INFO - Downloading from https://data.fcc.gov/download/pub/uls/complete/l_amat.zip
INFO - Extracting data files...
INFO - Loading EN.dat (entities)...
INFO - Loaded 1,572,538 entity records
INFO - Update complete: 786,269 amateur records loaded
```

### Step 5: Verify the Installation

Once the data load completes, verify everything is working:

```bash
# Check the health endpoint
curl http://localhost:8010/api/health

# Check database statistics
curl http://localhost:8010/api/stats

# Try a sample query
curl "http://localhost:8010/api/query?call_sign=W1AW"
```

### Step 6: Access the API Documentation

Open your web browser and navigate to:

- **Swagger UI**: http://localhost:8010/docs - Interactive API documentation
- **ReDoc**: http://localhost:8010/redoc - Alternative documentation format
- **API Root**: http://localhost:8010 - API information

## Configuration

Environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `fcc` | PostgreSQL username |
| `POSTGRES_PASSWORD` | - | PostgreSQL password (required) |
| `POSTGRES_DB` | `fccdb` | Database name |
| `DATABASE_URL` | - | Full PostgreSQL connection URL |
| `API_INTERFACE` | `0.0.0.0` | API binding interface |
| `API_PORT` | `8010` | API port |
| `AUTO_UPDATE_DAYS` | `7` | Days between automatic FCC data refreshes |
| `ULS_CODE_DEFINITIONS_FILE` | `/app/uls_definitions/uls_code_definitions_20240718.txt` | Path to ULS code definitions file |

## API Endpoints

### Query Licenses

```
GET /api/query
```

Search the license database with various filters. All string fields support wildcard searches.

**Query Parameters:**

| Parameter | Description | Example |
|-----------|-------------|---------|
| `call_sign` | Callsign (alias: `callsign`) | `W1AW`, `W1*`, `*ABC` |
| `first_name` | First name | `John`, `J*` |
| `last_name` | Last name | `Smith`, `*son` |
| `entity_name` | Organization/club name | `*Radio Club*` |
| `city` | City | `Boston`, `*port*` |
| `state` | State (2-letter code) | `MA`, `CA` |
| `zip_code` | ZIP code | `02101`, `021*` |
| `street_address` | Street address | `*Main St*` |
| `frn` | FCC Registration Number | `0012345678` |
| `operator_class` | License class (E/G/T/A/N) | `E` |
| `license_status` | Status (A=Active, E=Expired, C=Cancelled) | `A` |
| `limit` | Max results (1-1000, default 100) | `50` |
| `offset` | Skip results (default 0) | `100` |

**Example Requests:**

```bash
# Exact callsign lookup
curl "http://localhost:8010/api/query?call_sign=W1AW"

# Wildcard search - all callsigns starting with W1
curl "http://localhost:8010/api/query?call_sign=W1*"

# Search by state and license class
curl "http://localhost:8010/api/query?state=CA&operator_class=E&limit=50"

# Search by address
curl "http://localhost:8010/api/query?street_address=*Main%20St*&city=Boston"

# Search by name
curl "http://localhost:8010/api/query?last_name=Smith&state=MA"
```

**Example Response:**

```json
{
  "total": 1,
  "offset": 0,
  "limit": 100,
  "results": [
    {
      "unique_system_identifier": "1234567",
      "call_sign": "W1AW",
      "name": {
        "entity_name": "ARRL INC",
        "first_name": null,
        "mi": null,
        "last_name": null,
        "suffix": null
      },
      "attention_line": null,
      "address": {
        "street": "225 MAIN ST",
        "city": "NEWINGTON",
        "state": "CT",
        "zip_code": "061111400"
      },
      "frn": "0001430385",
      "license": {
        "operator_class": "E",
        "operator_class_desc": "Amateur Extra",
        "status": "A",
        "status_desc": "Active",
        "grant_date": "03/15/2023",
        "expired_date": "03/16/2033",
        "cancellation_date": null
      },
      "trustee_callsign": null,
      "previous_callsign": null
    }
  ]
}
```

### Force Database Refresh

```
POST /api/refresh
```

Triggers an immediate refresh of the FCC database. The refresh runs in the background.

**Example:**

```bash
curl -X POST "http://localhost:8010/api/refresh"
```

**Response:**

```json
{
  "message": "Database refresh started",
  "status": "in_progress"
}
```

### Check Refresh Status

```
GET /api/refresh/status
```

Get the status of the current or most recent database refresh.

**Example Response:**

```json
{
  "status": "success",
  "update_time": "2026-01-28T01:30:00+00:00",
  "records_loaded": 6543210,
  "error_message": null
}
```

### Get Version Info

```
GET /api/version
```

Get the date of the most recent successful data pull.

**Example Response:**

```json
{
  "last_update": "2026-01-28T01:30:00+00:00",
  "records_loaded": 6543210
}
```

### Get Database Statistics

```
GET /api/stats
```

Get statistics about the license database.

**Example Response:**

```json
{
  "total_records": {
    "entities": 1572538,
    "amateur": 786269,
    "headers": 786269,
    "history": 4500000
  },
  "active_licenses": 785000,
  "operator_classes": {
    "E": 180000,
    "G": 210000,
    "T": 395000
  },
  "top_states": {
    "CA": 95000,
    "TX": 65000,
    "FL": 55000
  },
  "last_update": "2026-01-28T01:30:00+00:00",
  "is_updating": false
}
```

### Health Check

```
GET /api/health
```

Health check endpoint for container orchestration.

**Example Response:**

```json
{
  "status": "healthy",
  "database": "healthy",
  "updating": false
}
```

### List Queryable Fields

```
GET /api/fields
```

List all fields that can be used in queries with descriptions and examples.

### Query by Callsign (JSON)

```
GET /api/query/call?call_sign=<callsign>
```

Lookup a specific callsign and return results as JSON. This is a simplified endpoint for exact callsign lookups.

**Example:**

```bash
curl "http://localhost:8010/api/query/call?call_sign=W1AW"
```

### Query by Callsign (Text)

```
GET /api/query/callastext?call_sign=<callsign>
```

Lookup a specific callsign and return results as plain text, organized by active/inactive status.

**Example:**

```bash
curl "http://localhost:8010/api/query/callastext?call_sign=W1AW"
```

**Example Response:**

```
Active Licenses:

USI:      1234567
FRN:      0001430385
Name:     ARRL INC
Address:  225 MAIN ST NEWINGTON CT 061111400
Class:    E (Amateur Extra)
Status:   A (Active)
Granted:  03/15/2023
Expires:  03/16/2033
Previous:

Inactive Licenses:

```

### Query License History by USI

```
GET /api/query/history/usi?usi=<unique_system_identifier>
```

Get license history for a specific unique system identifier.

**Example:**

```bash
curl "http://localhost:8010/api/query/history/usi?usi=1234567"
```

**Example Response:**

```json
{
  "total": 3,
  "unique_system_identifier": "1234567",
  "results": [
    {
      "callsign": "W1AW",
      "log_date": "01/15/2023",
      "code": "LIISS",
      "description": "License Issued"
    },
    {
      "callsign": "W1AW",
      "log_date": "01/10/2023",
      "code": "APGRT",
      "description": "Application Granted"
    }
  ]
}
```

### Query License History by FRN

```
GET /api/query/history/frn?frn=<frn>
```

Get license history for all licenses associated with an FCC Registration Number (FRN).

**Example:**

```bash
curl "http://localhost:8010/api/query/history/frn?frn=0001430385"
```

**Example Response:**

```json
{
  "total": 5,
  "frn": "0001430385",
  "unique_system_identifiers": ["1234567", "2345678"],
  "results": [
    {
      "callsign": "W1AW",
      "log_date": "01/15/2023",
      "code": "LIISS",
      "description": "License Issued"
    }
  ]
}
```

### List History Codes

```
GET /api/codes/history
```

List all history code definitions. Supports pagination with `limit` and `offset` parameters.

**Example:**

```bash
curl "http://localhost:8010/api/codes/history?limit=10"
```

**Example Response:**

```json
{
  "total": 463,
  "offset": 0,
  "limit": 10,
  "codes": [
    {"code": "APGRT", "description": "Application Granted"},
    {"code": "LIISS", "description": "License Issued"},
    {"code": "LIREN", "description": "License Renewed"}
  ]
}
```

### List Operator Class Codes

```
GET /api/codes/operator-class
```

List all operator class code definitions.

**Example Response:**

```json
{
  "total": 6,
  "codes": [
    {"code": "E", "description": "Amateur Extra"},
    {"code": "G", "description": "General"},
    {"code": "T", "description": "Technician"},
    {"code": "P", "description": "Technician Plus"},
    {"code": "A", "description": "Advanced"},
    {"code": "N", "description": "Novice"}
  ]
}
```

### List License Status Codes

```
GET /api/codes/license-status
```

List all license status code definitions.

**Example Response:**

```json
{
  "total": 4,
  "codes": [
    {"code": "A", "description": "Active"},
    {"code": "C", "description": "Cancelled"},
    {"code": "E", "description": "Expired"},
    {"code": "T", "description": "Terminated"}
  ]
}
```

### Reload Code Definitions

```
POST /api/codes/reload
```

Reload all code definitions from the ULS definitions file.

**Example:**

```bash
curl -X POST "http://localhost:8010/api/codes/reload"
```

**Example Response:**

```json
{
  "message": "Code definitions reloaded successfully",
  "counts": {
    "history_codes": 463,
    "operator_classes": 6,
    "license_statuses": 4
  }
}
```

## Data Source

Data is sourced from the FCC Universal Licensing System (ULS):
- **URL**: https://data.fcc.gov/download/pub/uls/complete/l_amat.zip
- **Format**: Pipe-delimited text files
- **Files**: AM.dat (Amateur), EN.dat (Entity), HD.dat (Header), HS.dat (History)

## Database Schema

### Main Tables

| Table | Description |
|-------|-------------|
| `pubacc_am` | Amateur license data (callsign, operator class, trustee info) |
| `pubacc_en` | Entity data (name, address, contact info) |
| `pubacc_hd` | Header data (license status, dates, service codes) |
| `pubacc_hs` | History data (license history events) |
| `update_log` | Tracks database update history |

### Code Lookup Tables

| Table | Description |
|-------|-------------|
| `uls_history_code` | History event code definitions (463+ codes) |
| `uls_operator_class` | Operator class code definitions (6 codes) |
| `uls_license_status` | License status code definitions (4 codes) |

### License Classes

| Code | Class | Description |
|------|-------|-------------|
| `E` | Extra | Highest class, all privileges |
| `G` | General | HF privileges with some restrictions |
| `T` | Technician | Entry level, primarily VHF/UHF |
| `P` | Technician Plus | Technician with Element 1 credit |
| `A` | Advanced | Grandfathered, no longer issued |
| `N` | Novice | Grandfathered, no longer issued |

### License Status

| Code | Status | Description |
|------|--------|-------------|
| `A` | Active | License is currently valid |
| `E` | Expired | License has expired |
| `C` | Cancelled | License was cancelled |
| `T` | Terminated | License was terminated |

## Docker Commands

```bash
# Start services
docker compose up -d

# View logs
docker compose logs -f api

# Stop services
docker compose down

# Rebuild after code changes
docker compose build --no-cache api && docker compose up -d

# Reset database (removes all data)
docker compose down -v
docker compose up -d
```

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │
│   FCC ULS       │────▶│   fccdb-api     │
│   (data.fcc.gov)│     │   (FastAPI)     │
│                 │     │                 │
└─────────────────┘     └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │                 │
                        │  fccdb-postgres │
                        │  (PostgreSQL)   │
                        │                 │
                        └─────────────────┘
```

## Troubleshooting

### Container Issues

#### Containers won't start

**Symptom:** `docker compose up -d` fails or containers immediately exit.

**Solutions:**

1. **Check if ports are in use:**
   ```bash
   # Check if port 8010 is already in use
   lsof -i :8010
   # If so, either stop the other service or change API_PORT in .env
   ```

2. **Check Docker is running:**
   ```bash
   docker info
   # If Docker isn't running, start the Docker service
   ```

3. **View container logs for errors:**
   ```bash
   docker compose logs
   ```

#### Database container keeps restarting

**Symptom:** `fccdb-postgres` container shows "Restarting" status.

**Solutions:**

1. **Check for disk space:**
   ```bash
   df -h
   # Ensure you have at least 3 GB free
   ```

2. **Check database logs:**
   ```bash
   docker compose logs db
   ```

3. **Reset the database volume:**
   ```bash
   docker compose down -v
   docker compose up -d
   ```

---

### Data Loading Issues

#### Initial data load never completes

**Symptom:** The API returns empty results and logs show no progress.

**Solutions:**

1. **Check if download is in progress:**
   ```bash
   docker compose logs -f api | grep -i download
   ```

2. **Verify internet connectivity from container:**
   ```bash
   docker compose exec api curl -I https://data.fcc.gov
   ```

3. **Manually trigger a refresh:**
   ```bash
   curl -X POST http://localhost:8010/api/refresh
   ```

#### "Connection refused" when downloading FCC data

**Symptom:** Logs show connection errors to data.fcc.gov.

**Solutions:**

1. **Check your firewall settings** - Ensure outbound HTTPS (port 443) is allowed

2. **Try again later** - The FCC server may be temporarily unavailable

3. **Check if the URL is accessible from your host:**
   ```bash
   curl -I https://data.fcc.gov/download/pub/uls/complete/l_amat.zip
   ```

---

### API Issues

#### API returns "Internal Server Error" (500)

**Symptom:** API calls return 500 errors.

**Solutions:**

1. **Check API logs for the specific error:**
   ```bash
   docker compose logs api | tail -50
   ```

2. **Verify database connection:**
   ```bash
   docker compose exec api python -c "from app.database import engine; print(engine.connect())"
   ```

3. **Restart the API container:**
   ```bash
   docker compose restart api
   ```

#### API returns empty results

**Symptom:** Queries return `{"total": 0, "results": []}`.

**Solutions:**

1. **Check if data has been loaded:**
   ```bash
   curl http://localhost:8010/api/stats
   # If total_records shows 0, data hasn't loaded yet
   ```

2. **Verify your query parameters are correct:**
   ```bash
   # State codes must be 2 letters (MA, not Massachusetts)
   curl "http://localhost:8010/api/query?state=MA"
   ```

3. **Check refresh status:**
   ```bash
   curl http://localhost:8010/api/refresh/status
   ```

#### "At least one search parameter is required" error

**Symptom:** Query returns 400 error.

**Solution:** You must provide at least one search parameter:
```bash
# Wrong - no parameters
curl http://localhost:8010/api/query

# Correct - include at least one parameter
curl "http://localhost:8010/api/query?state=CA"
```

---

### Database Issues

#### Cannot connect to database

**Symptom:** API logs show database connection errors.

**Solutions:**

1. **Check if database container is running:**
   ```bash
   docker compose ps db
   ```

2. **Verify database credentials match:**
   ```bash
   # Check that POSTGRES_PASSWORD in .env matches the password in DATABASE_URL
   grep POSTGRES_PASSWORD .env
   grep DATABASE_URL .env
   ```

3. **Test database connection directly:**
   ```bash
   docker compose exec db psql -U fcc -d fccdb -c "SELECT 1;"
   ```

#### Database is corrupted

**Symptom:** Strange errors, missing data, or inconsistent results.

**Solution:** Reset the database completely:
```bash
# Stop containers and remove volumes
docker compose down -v

# Start fresh
docker compose up -d

# Wait for data to reload (5-15 minutes)
docker compose logs -f api
```

---

### Performance Issues

#### Queries are slow

**Symptom:** API queries take more than a few seconds.

**Solutions:**

1. **Use more specific queries** - Add more filters to reduce result set size

2. **Reduce the limit:**
   ```bash
   curl "http://localhost:8010/api/query?state=CA&limit=50"
   ```

3. **Check if an update is running:**
   ```bash
   curl http://localhost:8010/api/stats | grep is_updating
   ```

#### High memory usage during data load

**Symptom:** System becomes slow during initial data load.

**Solution:** This is normal. The initial load requires more memory. Once complete, memory usage will decrease.

---

### Common Commands Reference

```bash
# Check service status
docker compose ps

# View real-time logs
docker compose logs -f api

# Restart services
docker compose restart

# Stop services
docker compose down

# Stop and remove all data
docker compose down -v

# Rebuild after code changes
docker compose build --no-cache api && docker compose up -d

# Check database record counts
docker compose exec db psql -U fcc -d fccdb -c "SELECT COUNT(*) FROM pubacc_en;"

# Force data refresh
curl -X POST http://localhost:8010/api/refresh
```

## License

This project uses publicly available FCC data. The FCC data is in the public domain.

## Related Links

- [FCC ULS Database](https://www.fcc.gov/wireless/data/public-access-files-database-downloads)
- [FCC License Search](https://wireless2.fcc.gov/UlsApp/UlsSearch/searchLicense.jsp)
- [Amateur Radio Service](https://www.fcc.gov/wireless/bureau-divisions/mobility-division/amateur-radio-service)
