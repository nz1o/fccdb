import os
import csv
import logging
from io import BytesIO
from zipfile import ZipFile
from urllib.request import urlopen
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import UpdateLog

logger = logging.getLogger(__name__)

# Column definitions for each file type
FILE_COLUMNS = {
    "AM": [
        "record_type", "unique_system_identifier", "uls_file_num", "ebf_number",
        "callsign", "operator_class", "group_code", "region_code", "trustee_callsign",
        "trustee_indicator", "physician_certification", "ve_signature",
        "systematic_callsign_change", "vanity_callsign_change", "vanity_relationship",
        "previous_callsign", "previous_operator_class", "trustee_name"
    ],
    "EN": [
        "record_type", "unique_system_identifier", "uls_file_number", "ebf_number",
        "call_sign", "entity_type", "licensee_id", "entity_name", "first_name", "mi",
        "last_name", "suffix", "phone", "fax", "email", "street_address", "city",
        "state", "zip_code", "po_box", "attention_line", "sgin", "frn",
        "applicant_type_code", "applicant_type_other", "status_code", "status_date",
        "lic_category_code", "linked_license_id", "linked_callsign"
    ],
    "HS": [
        "record_type", "unique_system_identifier", "uls_file_number", "callsign",
        "log_date", "code"
    ],
    "HD": [
        "record_type", "unique_system_identifier", "uls_file_number", "ebf_number",
        "call_sign", "license_status", "radio_service_code", "grant_date",
        "expired_date", "cancellation_date", "eligibility_rule_num",
        "applicant_type_code_reserved", "alien", "alien_government", "alien_corporation",
        "alien_officer", "alien_control", "revoked", "convicted", "adjudged",
        "involved_reserved", "common_carrier", "non_common_carrier", "private_comm",
        "fixed", "mobile", "radiolocation", "satellite", "developmental_or_sta",
        "interconnected_service", "certifier_first_name", "certifier_mi",
        "certifier_last_name", "certifier_suffix", "certifier_title", "gender",
        "african_american", "native_american", "hawaiian", "asian", "white",
        "ethnicity", "effective_date", "last_action_date", "auction_id",
        "reg_stat_broad_serv", "band_manager", "type_serv_broad_serv", "alien_ruling",
        "licensee_name_change", "whitespace_ind", "additional_cert_choice",
        "additional_cert_answer", "discontinuation_ind", "regulatory_compliance_ind",
        "eligibility_cert_900", "transition_plan_cert_900", "return_spectrum_cert_900",
        "payment_cert_900"
    ]
}

TABLE_MAPPING = {
    "AM": ("_tmp_pubacc_am", "pubacc_am"),
    "EN": ("_tmp_pubacc_en", "pubacc_en"),
    "HS": ("_tmp_pubacc_hs", "pubacc_hs"),
    "HD": ("_tmp_pubacc_hd", "pubacc_hd"),
}


class FCCDataLoader:
    """Handles downloading and loading FCC amateur radio license data."""

    def __init__(self):
        self.temp_dir = settings.temp_dir
        self.chunk_size = settings.db_chunk_size
        self._is_loading = False

    @property
    def is_loading(self) -> bool:
        return self._is_loading

    def download_fcc_data(self) -> bool:
        """Download and extract FCC data files."""
        logger.info("Downloading FCC data from %s", settings.fcc_data_url)

        os.makedirs(self.temp_dir, exist_ok=True)

        try:
            http_response = urlopen(settings.fcc_data_url, timeout=300)
            zipfile = ZipFile(BytesIO(http_response.read()))
            zipfile.extractall(path=self.temp_dir)
            logger.info("Download and extraction complete")
            return True
        except Exception as e:
            logger.error("Error downloading FCC data: %s", e)
            return False

    def get_file_type(self, file_path: str) -> Optional[str]:
        """Determine file type from filename."""
        file_name = os.path.basename(file_path).lower()
        type_map = {
            "en.dat": "EN",
            "am.dat": "AM",
            "hs.dat": "HS",
            "hd.dat": "HD"
        }
        return type_map.get(file_name)

    def remove_quotes(self, file_path: str) -> None:
        """Remove quote characters from file that can cause parsing issues."""
        with open(file_path, 'r', encoding='latin-1') as f:
            data = f.read()
        data = data.replace('"', '')
        with open(file_path, 'w', encoding='latin-1') as f:
            f.write(data)

    def clear_staging_table(self, db: Session, file_type: str) -> bool:
        """Clear the staging table for a file type."""
        tmp_table, _ = TABLE_MAPPING[file_type]
        try:
            db.execute(text(f"TRUNCATE TABLE {tmp_table}"))
            db.commit()
            logger.info("Cleared staging table %s", tmp_table)
            return True
        except Exception as e:
            logger.error("Error clearing staging table %s: %s", tmp_table, e)
            db.rollback()
            return False

    def load_file_to_staging(self, db: Session, file_path: str) -> int:
        """Load a data file into its staging table."""
        file_type = self.get_file_type(file_path)
        if not file_type:
            logger.error("Unknown file type: %s", file_path)
            return 0

        if not self.clear_staging_table(db, file_type):
            return 0

        tmp_table, _ = TABLE_MAPPING[file_type]
        columns = FILE_COLUMNS[file_type]
        total_records = 0
        batch = []

        self.remove_quotes(file_path)

        with open(file_path, 'r', encoding='latin-1') as f:
            reader = csv.reader(f, delimiter='|')
            for row in reader:
                # Pad row if needed, truncate if too long
                if len(row) < len(columns):
                    row.extend([''] * (len(columns) - len(row)))
                elif len(row) > len(columns):
                    row = row[:len(columns)]

                batch.append(tuple(row))

                if len(batch) >= self.chunk_size:
                    inserted = self._insert_batch(db, tmp_table, columns, batch)
                    total_records += inserted
                    batch = []
                    logger.info("Loaded %d records into %s", total_records, tmp_table)

            # Insert remaining records
            if batch:
                inserted = self._insert_batch(db, tmp_table, columns, batch)
                total_records += inserted

        logger.info("Completed loading %d records into %s", total_records, tmp_table)
        return total_records

    def _insert_batch(self, db: Session, table: str, columns: list, batch: list) -> int:
        """Insert a batch of records into the database."""
        if not batch:
            return 0

        cols = ", ".join(columns)
        placeholders = ", ".join([f":{c}" for c in columns])
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"

        try:
            db.execute(
                text(sql),
                [dict(zip(columns, row)) for row in batch]
            )
            db.commit()
            return len(batch)
        except Exception as e:
            logger.error("Error inserting batch: %s", e)
            db.rollback()
            return 0

    def promote_staging_to_live(self, db: Session) -> bool:
        """Copy data from staging tables to live tables."""
        logger.info("Promoting staging data to live tables")

        try:
            for file_type, (tmp_table, live_table) in TABLE_MAPPING.items():
                # Clear live table
                db.execute(text(f"TRUNCATE TABLE {live_table}"))
                db.commit()
                logger.info("Cleared %s", live_table)

                # Copy from staging - exclude the id column
                columns = ", ".join(FILE_COLUMNS[file_type])
                db.execute(text(
                    f"INSERT INTO {live_table} ({columns}) "
                    f"SELECT {columns} FROM {tmp_table}"
                ))
                db.commit()
                logger.info("Copied data to %s", live_table)

            return True
        except Exception as e:
            logger.error("Error promoting staging data: %s", e)
            db.rollback()
            return False

    def run_full_update(self) -> dict:
        """Run a complete data update from FCC."""
        if self._is_loading:
            return {
                "success": False,
                "message": "Update already in progress"
            }

        self._is_loading = True
        start_time = datetime.now(timezone.utc)
        total_records = 0

        db = SessionLocal()
        update_log = UpdateLog(status="in_progress")
        db.add(update_log)
        db.commit()

        try:
            # Download data
            if not self.download_fcc_data():
                raise Exception("Failed to download FCC data")

            # Process each file
            files = ["AM.dat", "EN.dat", "HS.dat", "HD.dat"]
            for filename in files:
                file_path = os.path.join(self.temp_dir, filename)
                if os.path.exists(file_path):
                    records = self.load_file_to_staging(db, file_path)
                    total_records += records
                else:
                    logger.warning("File not found: %s", file_path)

            # Promote to live tables
            if not self.promote_staging_to_live(db):
                raise Exception("Failed to promote staging data")

            # Update log
            update_log.status = "success"
            update_log.records_loaded = total_records
            db.commit()

            elapsed = datetime.now(timezone.utc) - start_time
            logger.info(
                "Update complete: %d records loaded in %s",
                total_records, elapsed
            )

            return {
                "success": True,
                "message": "Update completed successfully",
                "records_loaded": total_records,
                "duration_seconds": elapsed.total_seconds()
            }

        except Exception as e:
            logger.error("Update failed: %s", e)
            update_log.status = "failed"
            update_log.error_message = str(e)[:500]
            db.commit()
            return {
                "success": False,
                "message": str(e)
            }

        finally:
            self._is_loading = False
            db.close()
            # Cleanup temp files
            self._cleanup_temp()

    def _cleanup_temp(self):
        """Remove temporary files."""
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info("Cleaned up temp directory")
        except Exception as e:
            logger.warning("Error cleaning temp directory: %s", e)


# Singleton instance
fcc_loader = FCCDataLoader()
