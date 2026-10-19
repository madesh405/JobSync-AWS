import base64
import json
import ipaddress
import re
import socket
import time
import uuid
from decimal import Decimal
from urllib.parse import urlparse, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

import boto3

REGION = "us-east-1"
JOBS_TABLE = "JobSync-Jobs"
SOURCES_TABLE = "JobSync-Sources"


dynamodb = boto3.resource("dynamodb", region_name=REGION)
jobs_table = dynamodb.Table(JOBS_TABLE)
sources_table = dynamodb.Table(SOURCES_TABLE)
sqs_client = boto3.client("sqs", region_name=REGION)
CRAWL_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/673396344578/JobSync-CrawlQueue"


def decimal_to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Authorization,Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS",
        },
        "body": json.dumps(body, default=str),
    }


def encode_token(last_evaluated_key):
    if not last_evaluated_key:
        return ""

    raw = json.dumps(
        last_evaluated_key,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")

    return base64.urlsafe_b64encode(raw).decode("utf-8")


def decode_token(token):
    if not token:
        return None

    try:
        padding = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(
            (token + padding).encode("utf-8")
        )
        return json.loads(raw.decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError):
        raise ValueError("Invalid next_token.")


def get_query_parameters(event):
    parameters = event.get("queryStringParameters") or {}
    return {
        str(key): value
        for key, value in parameters.items()
    }


def get_path_parameter(event, name):
    path_parameters = event.get("pathParameters") or {}
    return path_parameters.get(name)


def get_route(event):
    route_key = event.get("routeKey")
    if route_key:
        return route_key

    request_context = event.get("requestContext") or {}
    http = request_context.get("http") or {}
    method = http.get("method") or event.get("httpMethod") or ""
    path = event.get("rawPath") or event.get("path") or ""

    return f"{method} {path}".strip()


def list_jobs(event):
    parameters = get_query_parameters(event)

    try:
        limit = int(parameters.get("limit", "100"))
    except ValueError:
        return response(400, {"message": "limit must be an integer."})

    limit = max(1, min(limit, 100))

    try:
        exclusive_start_key = decode_token(
            parameters.get("next_token", "")
        )
    except ValueError as error:
        return response(400, {"message": str(error)})

    scan_arguments = {
        "Limit": limit,
    }

    if exclusive_start_key:
        scan_arguments["ExclusiveStartKey"] = exclusive_start_key

    try:
        result = jobs_table.scan(**scan_arguments)
    except Exception as error:
        print(f"Job scan failed: {error}")
        return response(
            500,
            {"message": "Failed to load jobs."},
        )

    jobs = result.get("Items", [])

    source_filter = parameters.get("source")
    status_filter = parameters.get("status")

    if source_filter:
        jobs = [
            job
            for job in jobs
            if str(job.get("source", "")).lower()
            == str(source_filter).lower()
        ]

    if status_filter:
        jobs = [
            job
            for job in jobs
            if str(job.get("status", "")).lower()
            == str(status_filter).lower()
        ]

    next_token = encode_token(
        result.get("LastEvaluatedKey")
    )

    return response(
        200,
        {
            "count": len(jobs),
            "jobs": jobs,
            "next_token": next_token or None,
            "has_more": bool(next_token),
        },
    )


def get_single_job(event):
    job_id = get_path_parameter(
        event,
        "canonical_job_id",
    )

    if not job_id:
        return response(
            400,
            {"message": "canonical_job_id is required."},
        )

    try:
        result = jobs_table.get_item(
            Key={
                "canonical_job_id": job_id,
            }
        )
    except Exception as error:
        print(f"Job lookup failed: {error}")
        return response(
            500,
            {"message": "Failed to load job."},
        )

    job = result.get("Item")

    if not job:
        return response(
            404,
            {"message": "Job not found."},
        )

    return response(
        200,
        job,
    )


def get_source_value(item, *names):
    for name in names:
        if name in item:
            return decimal_to_int(item.get(name))
    return 0


def build_source_metrics(item):
    return {
        "source_id": item.get("source_id"),
        "source_name": item.get("name")
        or item.get("source_name")
        or item.get("source_id")
        or "Unknown",
        "status": item.get("status") or "UNKNOWN",
        "fetch_attempts": get_source_value(
            item,
            "fetch_attempt_count",
            "fetch_attempts",
        ),
        "successful_crawls": get_source_value(
            item,
            "successful_crawl_count",
            "successful_crawls",
        ),
        "failed_crawls": get_source_value(
            item,
            "failed_crawl_count",
            "failed_crawls",
        ),
        "new": get_source_value(
            item,
            "new_count",
            "new",
        ),
        "unchanged": get_source_value(
            item,
            "unchanged_count",
            "unchanged",
        ),
        "changed": get_source_value(
            item,
            "changed_count",
            "changed",
        ),
        "cache_hits": get_source_value(
            item,
            "cache_hit_count",
            "cache_hits",
        ),
        "cache_misses": get_source_value(
            item,
            "cache_miss_count",
            "cache_misses",
        ),
        "redundant_updates_prevented": get_source_value(
            item,
            "redundant_updates_prevented",
        ),
        "controller_skips": get_source_value(
            item,
            "skip_count",
            "controller_skips",
        ),
        "jobs_processed": get_source_value(
            item,
            "total_jobs_processed",
            "jobs_processed",
        ),
    }


def get_admin_metrics():
    items = []
    response_data = sources_table.scan()
    items.extend(response_data.get("Items", []))

    while response_data.get("LastEvaluatedKey"):
        response_data = sources_table.scan(
            ExclusiveStartKey=response_data["LastEvaluatedKey"]
        )
        items.extend(response_data.get("Items", []))

    source_metrics = [
        build_source_metrics(item)
        for item in items
    ]

    totals = {
        "sources": len(source_metrics),
        "fetch_attempts": 0,
        "successful_crawls": 0,
        "failed_crawls": 0,
        "new": 0,
        "unchanged": 0,
        "changed": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "redundant_updates_prevented": 0,
        "controller_skips": 0,
        "jobs_processed": 0,
    }

    for source in source_metrics:
        for key in totals:
            if key == "sources":
                continue
            totals[key] += decimal_to_int(source.get(key))

    return response(
        200,
        {
            "metrics": totals,
            "sources": source_metrics,
        },
    )




ADMIN_GROUP = "JobSyncAdmins"
CUSTOM_FIELDS = {
    "source_id", "title", "company", "location", "employment_type",
    "salary_min", "salary_max", "description", "apply_url", "published_at",
}


def get_jwt_claims(event):
    """Read JWT claims from HTTP API v2 and v1 authorizer event shapes."""
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}

    # HTTP API payload format 2.0 stores JWT claims under authorizer.jwt.
    jwt = authorizer.get("jwt") or {}
    claims = jwt.get("claims") or {}

    # Payload format 1.0 exposes authorizer claims directly.
    # Keep this fallback limited to API Gateway's trusted request context.
    if not isinstance(claims, dict) or not claims:
        claims = authorizer.get("claims") or {}

    return claims if isinstance(claims, dict) else {}


def is_admin(event):
    claims = get_jwt_claims(event)
    groups = claims.get("cognito:groups", [])

    if isinstance(groups, str):
        raw_groups = groups.strip()
        try:
            parsed = json.loads(raw_groups)
        except (ValueError, TypeError):
            parsed = None

        if isinstance(parsed, list):
            groups = parsed
        else:
            # HTTP API JWT claim values may stringify array claims as
            # bracketed, whitespace-separated text (for example,
            # "[JobSyncAdmins OtherGroup]"), which is not valid JSON.
            normalized = raw_groups.strip().strip("[]").strip()
            groups = [
                item.strip().strip('"').strip("'")
                for item in re.split(r"[\\s,]+", normalized)
                if item.strip().strip('"').strip("'")
            ]

    return isinstance(groups, list) and ADMIN_GROUP in [str(item) for item in groups]


def is_admin_route(route, path):
    route_path = path or ""
    if " " in route:
        route_path = route.split(" ", 1)[1]
    route_path = route_path.rstrip("/") or "/"
    return route_path == "/admin" or route_path.startswith("/admin/")


def parse_body(event):
    body = event.get("body")
    if not body:
        return {}
    if isinstance(body, dict):
        return body
    if event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode("utf-8")
    try:
        decoded = json.loads(body)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("Request body must be valid JSON.") from error
    if not isinstance(decoded, dict):
        raise ValueError("Request body must be a JSON object.")
    return decoded


def _is_public_address(value):
    address = ipaddress.ip_address(value)
    return address.is_global and not (
        address.is_private or address.is_loopback or address.is_link_local
        or address.is_multicast or address.is_reserved or address.is_unspecified
    )


def validate_public_https_endpoint(endpoint):
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("API endpoint is required.")
    parsed = urlparse(endpoint.strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("API endpoints must use HTTPS and include a hostname.")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Endpoint URLs must not contain embedded credentials or fragments.")
    if parsed.port not in (None, 443):
        raise ValueError("Only HTTPS port 443 is allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "metadata.google.internal", "instance-data.ec2.internal"} or host.endswith(
        (".localhost", ".local", ".internal", ".lan")
    ):
        raise ValueError("The endpoint hostname is not allowed.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        if not _is_public_address(str(address)):
            raise ValueError("The endpoint must not use a private or reserved IP.")
        return endpoint.strip()
    try:
        addresses = {result[4][0] for result in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as error:
        raise ValueError("The API hostname could not be resolved.") from error
    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise ValueError("The API hostname must resolve only to public IP addresses.")
    return endpoint.strip()


def validate_api_config(payload):
    endpoint = validate_public_https_endpoint(payload.get("endpoint"))
    records_path = payload.get("records_path", "jobs")
    if not isinstance(records_path, str) or len(records_path) > 250:
        raise ValueError("Records path must be a string of at most 250 characters.")
    fields = payload.get("fields")
    if not isinstance(fields, dict):
        raise ValueError("Field mappings must be a JSON object.")
    for required in ("title", "company"):
        path = fields.get(required)
        if not isinstance(path, str) or not path.strip():
            raise ValueError(f"A field path is required for '{required}'.")
    normalized_fields = {}
    for name, path in fields.items():
        if name not in CUSTOM_FIELDS:
            raise ValueError(f"Unsupported field mapping: {name}")
        if path is not None and (not isinstance(path, str) or len(path) > 250):
            raise ValueError(f"Field mapping '{name}' must be a string up to 250 characters.")
        if path:
            normalized_fields[name] = path.strip()
    pagination = payload.get("pagination") or {"type": "NONE"}
    if not isinstance(pagination, dict):
        raise ValueError("Pagination must be a JSON object.")
    pagination_type = str(pagination.get("type", "NONE")).upper()
    if pagination_type not in ("NONE", "PAGE"):
        raise ValueError("Pagination type must be NONE or PAGE.")
    page_parameter = pagination.get("page_parameter", "page")
    try:
        start_page = int(pagination.get("start_page", 1))
        max_pages = int(pagination.get("max_pages", 3 if pagination_type == "PAGE" else 1))
    except (TypeError, ValueError) as error:
        raise ValueError("Pagination start page and maximum pages must be integers.") from error
    if pagination_type == "PAGE":
        if not isinstance(page_parameter, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", page_parameter):
            raise ValueError("Page parameter must be a simple query parameter name.")
        if start_page < 0 or not 1 <= max_pages <= 10:
            raise ValueError("Page pagination allows 1–10 pages and a non-negative start page.")
    else:
        start_page = 1
        max_pages = 1
        page_parameter = "page"
    try:
        crawl_interval = int(payload.get("crawl_interval", 3600))
    except (TypeError, ValueError) as error:
        raise ValueError("Crawl interval must be an integer number of seconds.") from error
    if not 900 <= crawl_interval <= 86400:
        raise ValueError("Crawl interval must be between 900 and 86400 seconds.")
    return {
        "endpoint": endpoint,
        "records_path": records_path.strip(),
        "fields": normalized_fields,
        "pagination": {
            "type": pagination_type,
            "page_parameter": page_parameter,
            "start_page": start_page,
            "max_pages": max_pages,
        },
    }, crawl_interval


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def test_api_config(api_config):
    """Make a bounded unauthenticated request and return a tiny field-mapped preview."""
    endpoint = validate_public_https_endpoint(api_config["endpoint"])
    pagination = api_config["pagination"]
    params = {}
    if pagination["type"] == "PAGE":
        params[pagination["page_parameter"]] = pagination["start_page"]
    url = endpoint
    if params:
        url += ("&" if "?" in endpoint else "?") + urlencode(params)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "JobSyncAdminTest/1.0"})
    opener = build_opener(_NoRedirectHandler)
    try:
        with opener.open(request, timeout=10) as result:
            raw = result.read(1024 * 1024 + 1)
    except Exception as error:
        raise ValueError(f"API test request failed: {type(error).__name__}. Check that the endpoint is public, returns JSON, and does not redirect.") from error
    if len(raw) > 1024 * 1024:
        raise ValueError("API test response exceeded the 1 MB preview limit.")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("The API test response was not valid UTF-8 JSON.") from error
    records = payload
    for part in api_config["records_path"].strip(".").split(".") if api_config["records_path"] not in ("", "$", ".") else []:
        if isinstance(records, dict):
            records = records.get(part)
        elif isinstance(records, list) and part.isdigit() and int(part) < len(records):
            records = records[int(part)]
        else:
            records = None
            break
    if not isinstance(records, list):
        raise ValueError("Records path did not resolve to an array in the response.")
    samples = []
    fields = api_config["fields"]
    for record in records:
        if not isinstance(record, dict):
            continue
        mapped = {}
        for field in ("title", "company", "location", "employment_type", "apply_url"):
            path = fields.get(field)
            value = record
            if path:
                for part in path.strip(".").split("."):
                    if isinstance(value, dict):
                        value = value.get(part)
                    elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
                        value = value[int(part)]
                    else:
                        value = None
                        break
            mapped[field] = str(value).strip() if value is not None else ""
        if mapped["title"] and mapped["company"]:
            samples.append(mapped)
        if len(samples) >= 3:
            break
    return {"http_status": 200, "sample_count": len(samples), "jobs": samples, "records_seen": len(records)}


def public_source_view(item):
    """Return source management fields but never arbitrary stored config internals."""
    result = {
        "source_id": item.get("source_id"),
        "source_name": item.get("source_name") or item.get("source_id"),
        "source_type": item.get("source_type", "BUILTIN"),
        "status": item.get("status", "UNKNOWN"),
        "crawl_interval": decimal_to_int(item.get("crawl_interval", 3600)),
        "successful_crawl_count": decimal_to_int(item.get("successful_crawl_count", 0)),
        "failed_crawl_count": decimal_to_int(item.get("failed_crawl_count", 0)),
        "last_checked": item.get("last_checked"),
        "next_check": item.get("next_check"),
    }
    api_config = item.get("api_config")
    if isinstance(api_config, dict):
        result["endpoint"] = api_config.get("endpoint", "")
        result["records_path"] = api_config.get("records_path", "jobs")
        result["pagination_type"] = (api_config.get("pagination") or {}).get("type", "NONE")
    return result


def list_admin_sources():
    items = []
    result = sources_table.scan()
    items.extend(result.get("Items", []))
    while result.get("LastEvaluatedKey"):
        result = sources_table.scan(ExclusiveStartKey=result["LastEvaluatedKey"])
        items.extend(result.get("Items", []))
    items.sort(key=lambda item: str(item.get("source_id", "")))
    return response(200, {"sources": [public_source_view(item) for item in items]})


def create_admin_source(event):
    try:
        payload = parse_body(event)
        source_name = payload.get("source_name")
        if not isinstance(source_name, str) or not source_name.strip() or len(source_name.strip()) > 80:
            return response(400, {"message": "Source name is required and must be at most 80 characters."})
        api_config, crawl_interval = validate_api_config(payload)
        name_slug = re.sub(r"[^a-z0-9]+", "-", source_name.lower()).strip("-")[:32] or "source"
        source_id = f"custom-{name_slug}-{uuid.uuid4().hex[:8]}"
        current = int(time.time())
        item = {
            "source_id": source_id,
            "source_name": source_name.strip(),
            "source_type": "CUSTOM_API",
            "api_config": api_config,
            "status": "ACTIVE",
            "crawl_interval": crawl_interval,
            "created_at": current,
            "last_checked": 0,
            "next_check": current,
            "failure_count": 0,
            "config_version": 1,
        }
        sources_table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(source_id)",
        )
        return response(201, {"source": public_source_view(item), "message": "Custom API source created."})
    except ValueError as error:
        return response(400, {"message": str(error)})
    except Exception as error:
        print(f"Custom source creation failed: {error}")
        return response(500, {"message": "Could not create the source."})


def test_admin_source(event):
    try:
        payload = parse_body(event)
        api_config, crawl_interval = validate_api_config(payload)
        result = test_api_config(api_config)
        result["crawl_interval"] = crawl_interval
        result["message"] = "API test succeeded. No jobs were saved."
        return response(200, result)
    except ValueError as error:
        return response(400, {"message": str(error)})
    except Exception as error:
        print(f"Custom source API test failed: {error}")
        return response(502, {"message": "The API test failed."})


def sync_admin_source(event):
    source_id = get_path_parameter(event, "source_id")
    if not source_id:
        return response(400, {"message": "source_id is required."})
    try:
        source = sources_table.get_item(
            Key={"source_id": source_id},
            ConsistentRead=True,
        ).get("Item")
        if not source:
            return response(404, {"message": "Source not found."})
        if source.get("status") != "ACTIVE":
            return response(409, {"message": "Only ACTIVE sources can be synced."})
        now = int(time.time())
        message = {
            "source_id": source_id,
            "reason": "MANUAL_SYNC",
            "requested_at": now,
            "requested_by": get_jwt_claims(event).get("sub", "admin"),
        }
        sent = sqs_client.send_message(
            QueueUrl=CRAWL_QUEUE_URL,
            MessageBody=json.dumps(message, separators=(",", ":")),
        )
        return response(202, {
            "message": "Sync request queued.",
            "source_id": source_id,
            "message_id": sent.get("MessageId"),
            "reason": "MANUAL_SYNC",
        })
    except Exception as error:
        print(f"Manual source sync enqueue failed for {source_id}: {error}")
        return response(500, {"message": "Could not queue this source for sync."})


def update_admin_source(event):
    source_id = get_path_parameter(event, "source_id")
    if not source_id:
        return response(400, {"message": "source_id is required."})
    try:
        payload = parse_body(event)
    except ValueError as error:
        return response(400, {"message": str(error)})
    status = str(payload.get("status", "")).upper()
    if status not in ("ACTIVE", "DISABLED"):
        return response(400, {"message": "Status must be ACTIVE or DISABLED."})
    try:
        existing = sources_table.get_item(Key={"source_id": source_id}, ConsistentRead=True).get("Item")
        if not existing:
            return response(404, {"message": "Source not found."})
        if str(existing.get("source_type", "")).upper() != "CUSTOM_API":
            return response(403, {"message": "Only custom API sources can be changed here."})
        sources_table.update_item(
            Key={"source_id": source_id},
            UpdateExpression="SET #status=:status, next_check=:next_check",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": status,
                ":next_check": int(time.time()) if status == "ACTIVE" else 0,
            },
        )
        existing["status"] = status
        existing["next_check"] = int(time.time()) if status == "ACTIVE" else 0
        return response(200, {"source": public_source_view(existing), "message": "Source status updated."})
    except Exception as error:
        print(f"Custom source status update failed: {error}")
        return response(500, {"message": "Could not update source status."})


def lambda_handler(event, context):
    route = get_route(event)
    method = (
        route.split(" ", 1)[0]
        if " " in route
        else event.get("httpMethod", "GET")
    )
    path = event.get("rawPath") or event.get("path") or ""

    if method == "OPTIONS":
        return response(200, {"ok": True})

    if is_admin_route(route, path):
        claims = get_jwt_claims(event)
        if not claims:
            return response(401, {"message": "Authentication required."})
        if not is_admin(event):
            return response(403, {"message": "Administrator access required."})

    if route == "GET /admin/metrics" or path.endswith("/admin/metrics"):
        return get_admin_metrics()

    if route == "GET /admin/sources" or (method == "GET" and path.rstrip("/") == "/admin/sources"):
        return list_admin_sources()

    if route == "POST /admin/sources/test" or (method == "POST" and path.rstrip("/") == "/admin/sources/test"):
        return test_admin_source(event)

    if route == "POST /admin/sources" or (method == "POST" and path.rstrip("/") == "/admin/sources"):
        return create_admin_source(event)

    if method == "POST" and path.startswith("/admin/sources/") and path.endswith("/sync"):
        return sync_admin_source(event)

    if method == "PATCH" and path.startswith("/admin/sources/"):
        return update_admin_source(event)

    if get_path_parameter(event, "canonical_job_id"):
        return get_single_job(event)

    if method == "GET":
        return list_jobs(event)

    return response(405, {"message": "Method not allowed."})
