"""Configuration-driven connector for administrator-registered HTTPS JSON APIs."""

import ipaddress
import json
import re
import socket
from urllib.parse import urlparse

import requests

from job_pipeline import Job, clean_text, finalize_job

HTTP_TIMEOUT = (3, 20)
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_PAGES_HARD_LIMIT = 10
MAX_JOBS = 500
USER_AGENT = "JobSyncCustomApiConnector/1.0"
REQUIRED_FIELDS = ("title", "company")


def _is_public_address(value):
    address = ipaddress.ip_address(value)
    return address.is_global and not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def validate_endpoint(endpoint):
    """Require a public HTTPS endpoint to reduce server-side request forgery risk."""
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("api_config.endpoint is required.")

    parsed = urlparse(endpoint.strip())
    if parsed.scheme.lower() != "https":
        raise ValueError("Custom API endpoints must use HTTPS.")
    if not parsed.hostname:
        raise ValueError("The API endpoint must contain a hostname.")
    if parsed.username or parsed.password:
        raise ValueError("Credentials must not be embedded in the endpoint URL.")
    if parsed.fragment:
        raise ValueError("The API endpoint must not contain a URL fragment.")
    if parsed.port not in (None, 443):
        raise ValueError("Custom API endpoints must use HTTPS port 443.")

    host = parsed.hostname.rstrip(".").lower()
    if host in {
        "localhost",
        "metadata.google.internal",
        "instance-data.ec2.internal",
    } or host.endswith((".localhost", ".local", ".internal", ".lan")):
        raise ValueError("The API endpoint hostname is not allowed.")

    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None

    if literal_ip is not None:
        if not _is_public_address(str(literal_ip)):
            raise ValueError("The API endpoint must not use a private or reserved IP address.")
        return endpoint.strip()

    try:
        addresses = {
            result[4][0]
            for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as error:
        raise ValueError("The API hostname could not be resolved.") from error

    if not addresses:
        raise ValueError("The API hostname did not resolve to an address.")
    if any(not _is_public_address(address) for address in addresses):
        raise ValueError("The API hostname resolves to a private or reserved address.")

    return endpoint.strip()


def get_path_value(value, path):
    """Resolve a dot-separated JSON path, including numeric list indexes."""
    if path is None or path == "":
        return None
    if path in ("$", "."):
        return value
    if not isinstance(path, str):
        return None

    current = value
    for part in path.strip(".").split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            current = current[index] if index < len(current) else None
        else:
            return None
        if current is None:
            return None
    return current


def _clean_value(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return clean_text(json.dumps(value, ensure_ascii=False))
    return clean_text(value)


def _number_or_none(value):
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            number = float(value)
        else:
            cleaned = re.sub(r"[^0-9.+-]", "", str(value).replace(",", ""))
            if not cleaned:
                return None
            number = float(cleaned)
        return number if number >= 0 else None
    except (TypeError, ValueError, OverflowError):
        return None


def normalize_config(source):
    config = source.get("api_config")
    if not isinstance(config, dict):
        raise ValueError("Custom source is missing its api_config configuration.")

    endpoint = validate_endpoint(config.get("endpoint"))
    fields = config.get("fields")
    if not isinstance(fields, dict):
        raise ValueError("api_config.fields must be a JSON object of field paths.")

    for name in REQUIRED_FIELDS:
        path = fields.get(name)
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"A JSON field path is required for '{name}'.")

    for name, path in fields.items():
        if name not in {
            "source_id", "title", "company", "location", "employment_type",
            "salary_min", "salary_max", "description", "apply_url", "published_at",
        }:
            raise ValueError(f"Unsupported job field mapping: {name}")
        if path is not None and (not isinstance(path, str) or len(path) > 250):
            raise ValueError(f"Field path '{name}' must be a string of at most 250 characters.")

    records_path = config.get("records_path", "jobs")
    if not isinstance(records_path, str) or len(records_path) > 250:
        raise ValueError("api_config.records_path must be a string of at most 250 characters.")

    pagination = config.get("pagination") or {"type": "NONE"}
    if not isinstance(pagination, dict):
        raise ValueError("api_config.pagination must be an object.")

    pagination_type = str(pagination.get("type", "NONE")).upper()
    if pagination_type not in ("NONE", "PAGE"):
        raise ValueError("Pagination type must be NONE or PAGE in this version.")

    page_parameter = pagination.get("page_parameter", "page")
    start_page = pagination.get("start_page", 1)
    max_pages = pagination.get("max_pages", 1 if pagination_type == "NONE" else 3)

    if pagination_type == "PAGE":
        if not isinstance(page_parameter, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", page_parameter):
            raise ValueError("pagination.page_parameter must be a simple query parameter name.")
        try:
            start_page = int(start_page)
            max_pages = int(max_pages)
        except (TypeError, ValueError) as error:
            raise ValueError("pagination.start_page and max_pages must be integers.") from error
        if start_page < 0 or not 1 <= max_pages <= MAX_PAGES_HARD_LIMIT:
            raise ValueError("Pagination must use a non-negative start page and between 1 and 10 pages.")

    return {
        "endpoint": endpoint,
        "records_path": records_path,
        "fields": fields,
        "pagination": {
            "type": pagination_type,
            "page_parameter": page_parameter,
            "start_page": start_page,
            "max_pages": max_pages,
        },
    }


def request_json(endpoint, params=None):
    response = requests.get(
        endpoint,
        params=params or None,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT,
        stream=True,
        allow_redirects=False,
    )
    try:
        response.raise_for_status()
        chunks = []
        total = 0
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise ValueError("The API response exceeded the 5 MB size limit.")
            chunks.append(chunk)
        try:
            return json.loads(b"".join(chunks).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("The API response was not valid UTF-8 JSON.") from error
    finally:
        response.close()


def extract_records(payload, records_path):
    if records_path in ("", "$", "."):
        records = payload
    else:
        records = get_path_value(payload, records_path)
    if not isinstance(records, list):
        raise ValueError("The configured records_path did not resolve to a JSON array.")
    return records


def record_to_job(record, source_id, fields):
    if not isinstance(record, dict):
        return None

    title = _clean_value(get_path_value(record, fields.get("title")))
    company = _clean_value(get_path_value(record, fields.get("company")))
    if not title or not company:
        return None

    location = _clean_value(get_path_value(record, fields.get("location")))
    employment_type = _clean_value(get_path_value(record, fields.get("employment_type")))
    description = _clean_value(get_path_value(record, fields.get("description")))
    apply_url = _clean_value(get_path_value(record, fields.get("apply_url")))
    external_id = _clean_value(get_path_value(record, fields.get("source_id")))
    published_at = _clean_value(get_path_value(record, fields.get("published_at")))
    salary_min = _number_or_none(get_path_value(record, fields.get("salary_min")))
    salary_max = _number_or_none(get_path_value(record, fields.get("salary_max")))

    if not external_id:
        external_id = apply_url or f"{company}|{title}|{location}"

    return finalize_job(Job(
        source=source_id,
        source_id=str(external_id),
        title=title,
        company=company,
        location=location,
        employment_type=employment_type,
        salary_min=salary_min,
        salary_max=salary_max,
        description=description,
        apply_url=apply_url,
        published_at=published_at,
    ))


def fetch_custom_api_jobs(source):
    """Fetch and normalize jobs from a CUSTOM_API source record."""
    source_id = source.get("source_id")
    if not source_id:
        raise ValueError("Custom source is missing source_id.")
    if str(source.get("source_type", "")).upper() != "CUSTOM_API":
        raise ValueError("This connector only accepts source_type=CUSTOM_API.")

    config = normalize_config(source)
    pagination = config["pagination"]
    if pagination["type"] == "PAGE":
        pages = range(
            pagination["start_page"],
            pagination["start_page"] + pagination["max_pages"],
        )
    else:
        pages = (None,)

    jobs = []
    for page in pages:
        params = {}
        if page is not None:
            params[pagination["page_parameter"]] = page

        payload = request_json(config["endpoint"], params)
        records = extract_records(payload, config["records_path"])
        if not records:
            break

        for record in records:
            job = record_to_job(record, source_id, config["fields"])
            if job is not None:
                jobs.append(job)
            if len(jobs) >= MAX_JOBS:
                return jobs
    return jobs


def preview_custom_api(source, sample_limit=3):
    """Fetch one page and return a small, normalized sample without syncing it."""
    config = normalize_config(source)
    params = {}
    pagination = config["pagination"]
    if pagination["type"] == "PAGE":
        params[pagination["page_parameter"]] = pagination["start_page"]
    payload = request_json(config["endpoint"], params)
    records = extract_records(payload, config["records_path"])
    sample = []
    for record in records:
        job = record_to_job(record, source.get("source_id", "custom_preview"), config["fields"])
        if job is not None:
            sample.append({
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "employment_type": job.employment_type,
                "apply_url": job.apply_url,
            })
        if len(sample) >= sample_limit:
            break
    return {"sample_count": len(sample), "jobs": sample}
