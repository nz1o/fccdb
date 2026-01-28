from sqlalchemy import Column, String, DateTime, BigInteger, Text
from sqlalchemy.sql import func
from app.database import Base


class Amateur(Base):
    """Amateur license data (AM.dat)"""
    __tablename__ = "pubacc_am"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    record_type = Column(String(10))
    unique_system_identifier = Column(String(20), index=True)
    uls_file_num = Column(String(20))
    ebf_number = Column(String(50))
    callsign = Column(String(20), index=True)
    operator_class = Column(String(10))
    group_code = Column(String(10))
    region_code = Column(String(10))
    trustee_callsign = Column(String(20))
    trustee_indicator = Column(String(10))
    physician_certification = Column(String(10))
    ve_signature = Column(String(10))
    systematic_callsign_change = Column(String(10))
    vanity_callsign_change = Column(String(10))
    vanity_relationship = Column(String(20))
    previous_callsign = Column(String(20))
    previous_operator_class = Column(String(10))
    trustee_name = Column(String(100))


class Entity(Base):
    """Entity/licensee data (EN.dat)"""
    __tablename__ = "pubacc_en"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    record_type = Column(String(10))
    unique_system_identifier = Column(String(20), index=True)
    uls_file_number = Column(String(20))
    ebf_number = Column(String(50))
    call_sign = Column(String(20), index=True)
    entity_type = Column(String(10))
    licensee_id = Column(String(20))
    entity_name = Column(String(250), index=True)
    first_name = Column(String(50), index=True)
    mi = Column(String(10))
    last_name = Column(String(50), index=True)
    suffix = Column(String(10))
    phone = Column(String(20))
    fax = Column(String(20))
    email = Column(String(100))
    street_address = Column(String(100))
    city = Column(String(50), index=True)
    state = Column(String(10), index=True)
    zip_code = Column(String(20), index=True)
    po_box = Column(String(30))
    attention_line = Column(String(50))
    sgin = Column(String(10))
    frn = Column(String(20), index=True)
    applicant_type_code = Column(String(10))
    applicant_type_other = Column(String(50))
    status_code = Column(String(10))
    status_date = Column(String(20))
    lic_category_code = Column(String(10))
    linked_license_id = Column(String(20))
    linked_callsign = Column(String(20))


class History(Base):
    """History data (HS.dat)"""
    __tablename__ = "pubacc_hs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    record_type = Column(String(10))
    unique_system_identifier = Column(String(20), index=True)
    uls_file_number = Column(String(20))
    callsign = Column(String(20), index=True)
    log_date = Column(String(20))
    code = Column(String(20))


class Header(Base):
    """Header/license status data (HD.dat)"""
    __tablename__ = "pubacc_hd"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    record_type = Column(String(10))
    unique_system_identifier = Column(String(20), index=True)
    uls_file_number = Column(String(20))
    ebf_number = Column(String(50))
    call_sign = Column(String(20), index=True)
    license_status = Column(String(10), index=True)
    radio_service_code = Column(String(10))
    grant_date = Column(String(20))
    expired_date = Column(String(20))
    cancellation_date = Column(String(20))
    eligibility_rule_num = Column(String(20))
    applicant_type_code_reserved = Column(String(10))
    alien = Column(String(10))
    alien_government = Column(String(10))
    alien_corporation = Column(String(10))
    alien_officer = Column(String(10))
    alien_control = Column(String(10))
    revoked = Column(String(10))
    convicted = Column(String(10))
    adjudged = Column(String(10))
    involved_reserved = Column(String(10))
    common_carrier = Column(String(10))
    non_common_carrier = Column(String(10))
    private_comm = Column(String(10))
    fixed = Column(String(10))
    mobile = Column(String(10))
    radiolocation = Column(String(10))
    satellite = Column(String(10))
    developmental_or_sta = Column(String(10))
    interconnected_service = Column(String(10))
    certifier_first_name = Column(String(50))
    certifier_mi = Column(String(10))
    certifier_last_name = Column(String(50))
    certifier_suffix = Column(String(10))
    certifier_title = Column(String(60))
    gender = Column(String(10))
    african_american = Column(String(10))
    native_american = Column(String(10))
    hawaiian = Column(String(10))
    asian = Column(String(10))
    white = Column(String(10))
    ethnicity = Column(String(10))
    effective_date = Column(String(20))
    last_action_date = Column(String(20))
    auction_id = Column(String(20))
    reg_stat_broad_serv = Column(String(10))
    band_manager = Column(String(10))
    type_serv_broad_serv = Column(String(10))
    alien_ruling = Column(String(10))
    licensee_name_change = Column(String(10))
    whitespace_ind = Column(String(10))
    additional_cert_choice = Column(String(10))
    additional_cert_answer = Column(String(10))
    discontinuation_ind = Column(String(10))
    regulatory_compliance_ind = Column(String(10))
    eligibility_cert_900 = Column(String(10))
    transition_plan_cert_900 = Column(String(10))
    return_spectrum_cert_900 = Column(String(10))
    payment_cert_900 = Column(String(10))


class UpdateLog(Base):
    """Track database update history"""
    __tablename__ = "update_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    update_time = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20))  # 'success', 'failed', 'in_progress'
    records_loaded = Column(BigInteger, default=0)
    error_message = Column(String(500))


# Code lookup tables
class HistoryCode(Base):
    """History code definitions from FCC ULS"""
    __tablename__ = "uls_history_code"

    code = Column(String(10), primary_key=True)
    description = Column(String(255))


class OperatorClass(Base):
    """Operator class code definitions"""
    __tablename__ = "uls_operator_class"

    code = Column(String(10), primary_key=True)
    description = Column(String(100))


class LicenseStatus(Base):
    """License status code definitions"""
    __tablename__ = "uls_license_status"

    code = Column(String(10), primary_key=True)
    description = Column(String(100))


# Staging tables - same structure but with _tmp_ prefix
class TmpAmateur(Base):
    """Staging table for Amateur data"""
    __tablename__ = "_tmp_pubacc_am"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    record_type = Column(String(10))
    unique_system_identifier = Column(String(20))
    uls_file_num = Column(String(20))
    ebf_number = Column(String(50))
    callsign = Column(String(20))
    operator_class = Column(String(10))
    group_code = Column(String(10))
    region_code = Column(String(10))
    trustee_callsign = Column(String(20))
    trustee_indicator = Column(String(10))
    physician_certification = Column(String(10))
    ve_signature = Column(String(10))
    systematic_callsign_change = Column(String(10))
    vanity_callsign_change = Column(String(10))
    vanity_relationship = Column(String(20))
    previous_callsign = Column(String(20))
    previous_operator_class = Column(String(10))
    trustee_name = Column(String(100))


class TmpEntity(Base):
    """Staging table for Entity data"""
    __tablename__ = "_tmp_pubacc_en"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    record_type = Column(String(10))
    unique_system_identifier = Column(String(20))
    uls_file_number = Column(String(20))
    ebf_number = Column(String(50))
    call_sign = Column(String(20))
    entity_type = Column(String(10))
    licensee_id = Column(String(20))
    entity_name = Column(String(250))
    first_name = Column(String(50))
    mi = Column(String(10))
    last_name = Column(String(50))
    suffix = Column(String(10))
    phone = Column(String(20))
    fax = Column(String(20))
    email = Column(String(100))
    street_address = Column(String(100))
    city = Column(String(50))
    state = Column(String(10))
    zip_code = Column(String(20))
    po_box = Column(String(30))
    attention_line = Column(String(50))
    sgin = Column(String(10))
    frn = Column(String(20))
    applicant_type_code = Column(String(10))
    applicant_type_other = Column(String(50))
    status_code = Column(String(10))
    status_date = Column(String(20))
    lic_category_code = Column(String(10))
    linked_license_id = Column(String(20))
    linked_callsign = Column(String(20))


class TmpHistory(Base):
    """Staging table for History data"""
    __tablename__ = "_tmp_pubacc_hs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    record_type = Column(String(10))
    unique_system_identifier = Column(String(20))
    uls_file_number = Column(String(20))
    callsign = Column(String(20))
    log_date = Column(String(20))
    code = Column(String(20))


class TmpHeader(Base):
    """Staging table for Header data"""
    __tablename__ = "_tmp_pubacc_hd"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    record_type = Column(String(10))
    unique_system_identifier = Column(String(20))
    uls_file_number = Column(String(20))
    ebf_number = Column(String(50))
    call_sign = Column(String(20))
    license_status = Column(String(10))
    radio_service_code = Column(String(10))
    grant_date = Column(String(20))
    expired_date = Column(String(20))
    cancellation_date = Column(String(20))
    eligibility_rule_num = Column(String(20))
    applicant_type_code_reserved = Column(String(10))
    alien = Column(String(10))
    alien_government = Column(String(10))
    alien_corporation = Column(String(10))
    alien_officer = Column(String(10))
    alien_control = Column(String(10))
    revoked = Column(String(10))
    convicted = Column(String(10))
    adjudged = Column(String(10))
    involved_reserved = Column(String(10))
    common_carrier = Column(String(10))
    non_common_carrier = Column(String(10))
    private_comm = Column(String(10))
    fixed = Column(String(10))
    mobile = Column(String(10))
    radiolocation = Column(String(10))
    satellite = Column(String(10))
    developmental_or_sta = Column(String(10))
    interconnected_service = Column(String(10))
    certifier_first_name = Column(String(50))
    certifier_mi = Column(String(10))
    certifier_last_name = Column(String(50))
    certifier_suffix = Column(String(10))
    certifier_title = Column(String(60))
    gender = Column(String(10))
    african_american = Column(String(10))
    native_american = Column(String(10))
    hawaiian = Column(String(10))
    asian = Column(String(10))
    white = Column(String(10))
    ethnicity = Column(String(10))
    effective_date = Column(String(20))
    last_action_date = Column(String(20))
    auction_id = Column(String(20))
    reg_stat_broad_serv = Column(String(10))
    band_manager = Column(String(10))
    type_serv_broad_serv = Column(String(10))
    alien_ruling = Column(String(10))
    licensee_name_change = Column(String(10))
    whitespace_ind = Column(String(10))
    additional_cert_choice = Column(String(10))
    additional_cert_answer = Column(String(10))
    discontinuation_ind = Column(String(10))
    regulatory_compliance_ind = Column(String(10))
    eligibility_cert_900 = Column(String(10))
    transition_plan_cert_900 = Column(String(10))
    return_spectrum_cert_900 = Column(String(10))
    payment_cert_900 = Column(String(10))
