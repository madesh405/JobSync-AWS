import base64
import json
from decimal import Decimal

import boto3

REGION = "us-east-1"
JOBS_TABLE = "JobSync-Jobs"
SOURCES_TABLE = "JobSync-Sources"


dynamodb = boto3.resource("dynamodb", region_name=REGION)
jobs_table = dynamodb.Table(JOBS_TABLE)
sources_table = dynamodb.Table(SOURCES_TABLE)


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
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
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


def lambda_handler(event, context):
    route = get_route(event)
    method = (
        route.split(" ", 1)[0]
        if " " in route
        else event.get("httpMethod", "GET")
    )

    if method == "OPTIONS":
        return response(200, {"ok": True})

    path = event.get("rawPath") or event.get("path") or ""

    if (
        route == "GET /admin/metrics"
        or path.endswith("/admin/metrics")
    ):
        return get_admin_metrics()

    if (
        get_path_parameter(
            event,
            "canonical_job_id",
        )
    ):
        return get_single_job(event)

    if method == "GET":
        return list_jobs(event)

    return response(
        405,
        {"message": "Method not allowed."},
    )
