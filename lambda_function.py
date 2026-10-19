import json
import logging
import time

from custom_api_connector import fetch_custom_api_jobs
from job_pipeline import get_himalayas, get_jobicy, get_remoteok
from sync_engine import sync_job
from source_state import (
    get_source,
    mark_crawl_start,
    record_crawl_result,
    mark_success,
    mark_failure,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

METRIC_NAMESPACE = "JobSync/Operations"
METRIC_UNITS = {
    "JobsFetched": "Count",
    "JobsNew": "Count",
    "JobsChanged": "Count",
    "CacheHits": "Count",
    "CacheMisses": "Count",
    "RedundantUpdatesPrevented": "Count",
    "CrawlDurationSeconds": "Seconds",
    "CrawlSuccesses": "Count",
    "CrawlFailures": "Count",
}
SOURCE_FUNCTIONS = {
    "himalayas": get_himalayas,
    "jobicy": get_jobicy,
    "remoteok": get_remoteok,
}


def emit_emf_metrics(values):
    """Emit low-cardinality CloudWatch Embedded Metric Format to stdout."""
    try:
        definitions = []
        metric_values = {}
        for name, value in values.items():
            unit = METRIC_UNITS.get(name)
            if unit is None or isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            metric_values[name] = int(value) if unit == "Count" else float(value)
            definitions.append({"Name": name, "Unit": unit})
        if not definitions:
            return
        payload = {
            "_aws": {
                "Timestamp": int(time.time() * 1000),
                "CloudWatchMetrics": [{
                    "Namespace": METRIC_NAMESPACE,
                    "Dimensions": [[]],
                    "Metrics": definitions,
                }],
            },
        }
        payload.update(metric_values)
        print(json.dumps(payload, separators=(",", ":"), allow_nan=False))
    except Exception:
        logger.exception("Unable to emit EMF metrics; crawl processing continues.")


def get_fetch_function(source):
    source_id = source.get("source_id")
    source_type = str(source.get("source_type", "BUILTIN")).upper()
    if source_type == "CUSTOM_API":
        return lambda: fetch_custom_api_jobs(source)
    if source_type not in ("BUILTIN", "", "NONE"):
        raise ValueError(f"Unsupported source_type for source {source_id}: {source_type}")
    if source_id not in SOURCE_FUNCTIONS:
        raise ValueError(f"Unknown built-in source_id: {source_id}")
    return SOURCE_FUNCTIONS[source_id]


def process_source(source_id):
    source = get_source(source_id)
    if source is None:
        raise ValueError(f"Source not found: {source_id}")
    if source.get("status") != "ACTIVE":
        raise ValueError(f"Source is not ACTIVE: {source_id}")

    fetch_function = get_fetch_function(source)
    logger.info("Processing source: %s (%s)", source.get("source_name", source_id), source_id)
    start_time = time.time()
    mark_crawl_start(source_id)

    jobs = fetch_function()
    logger.info("Fetched jobs: %d", len(jobs))

    summary = {"NEW": 0, "UNCHANGED": 0, "CHANGED": 0}
    for job in jobs:
        result = sync_job(job)
        result_type = result.get("type")
        if result_type in summary:
            summary[result_type] += 1

    duration = time.time() - start_time
    record_crawl_result(
        source_id=source_id,
        summary=summary,
        fetched_count=len(jobs),
        duration=duration,
    )
    changed = summary["NEW"] > 0 or summary["CHANGED"] > 0
    mark_success(source_id, int(source.get("crawl_interval", 3600)), changed)

    cache_hits = summary["UNCHANGED"]
    cache_misses = summary["NEW"] + summary["CHANGED"]
    logger.info("Source summary: %s", json.dumps(summary))
    logger.info("Cache hits: %d", cache_hits)
    logger.info("Cache misses: %d", cache_misses)
    logger.info("Redundant updates prevented: %d", cache_hits)
    logger.info("Crawl duration: %.2f seconds", duration)

    emit_emf_metrics({
        "JobsFetched": len(jobs),
        "JobsNew": summary["NEW"],
        "JobsChanged": summary["CHANGED"],
        "CacheHits": cache_hits,
        "CacheMisses": cache_misses,
        "RedundantUpdatesPrevented": cache_hits,
        "CrawlDurationSeconds": round(duration, 3),
        "CrawlSuccesses": 1,
    })
    return summary


def lambda_handler(event, context):
    records = event.get("Records", [])
    logger.info("JOBSYNC CRAWL WORKER: %d SQS record(s)", len(records))
    results = []

    for record in records:
        message_id = record.get("messageId")
        body = record.get("body", "")
        source_id = None
        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError("SQS message body must be a JSON object.")
            source_id = data.get("source_id")
            if not source_id:
                raise ValueError("Message does not contain source_id.")
            summary = process_source(source_id)
            results.append({"message_id": message_id, "source_id": source_id, "summary": summary})
        except Exception:
            if source_id is None:
                try:
                    data = json.loads(body)
                    source_id = data.get("source_id") if isinstance(data, dict) else None
                except Exception:
                    source_id = None
            if source_id:
                try:
                    mark_failure(source_id)
                except Exception as state_error:
                    logger.error("Failed to update source failure state: %s", state_error)
            emit_emf_metrics({"CrawlFailures": 1})
            logger.exception("Message processing failed: %s", message_id)
            raise

    return {"status": "SUCCESS", "processed": len(results), "results": results}
