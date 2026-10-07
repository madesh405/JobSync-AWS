import json
import boto3
from decimal import Decimal


REGION="us-east-1"

JOBS_TABLE_NAME="JobSync-Jobs"
SOURCES_TABLE_NAME="JobSync-Sources"


dynamodb=boto3.resource(
    "dynamodb",
    region_name=REGION
)

jobs_table=dynamodb.Table(JOBS_TABLE_NAME)
sources_table=dynamodb.Table(SOURCES_TABLE_NAME)


def decimal_default(value):
    if isinstance(value,Decimal):
        if value % 1 == 0:
            return int(value)

        return float(value)

    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )


def response(status_code,body):
    return {
        "statusCode":status_code,
        "headers":{
            "Content-Type":"application/json",
            "Access-Control-Allow-Origin":"*",
            "Access-Control-Allow-Headers":"Content-Type",
            "Access-Control-Allow-Methods":"GET,OPTIONS"
        },
        "body":json.dumps(
            body,
            default=decimal_default
        )
    }


def get_job(job_id):
    result=jobs_table.get_item(
        Key={
            "canonical_job_id":job_id
        },
        ConsistentRead=True
    )

    item=result.get("Item")

    if item is None:
        return response(
            404,
            {
                "error":"Job not found",
                "canonical_job_id":job_id
            }
        )

    return response(
        200,
        {
            "job":item
        }
    )


def get_jobs(event):
    query=event.get("queryStringParameters") or {}

    try:
        limit=int(
            query.get("limit","20")
        )
    except ValueError:
        limit=20

    limit=max(
        1,
        min(limit,100)
    )

    source=query.get("source")
    status=query.get("status")

    response_data=jobs_table.scan(
        Limit=limit
    )

    items=response_data.get("Items",[])

    if source:
        items=[
            item
            for item in items
            if item.get("source")==source
        ]

    if status:
        items=[
            item
            for item in items
            if item.get("status")==status
        ]

    jobs=[]

    for item in items:
        jobs.append(
            {
                "canonical_job_id":item.get("canonical_job_id"),
                "source":item.get("source"),
                "source_id":item.get("source_id"),
                "title":item.get("title"),
                "company":item.get("company"),
                "location":item.get("location"),
                "employment_type":item.get("employment_type"),
                "salary_min":item.get("salary_min"),
                "salary_max":item.get("salary_max"),
                "description":item.get("description"),
                "apply_url":item.get("apply_url"),
                "published_at":item.get("published_at"),
                "first_seen":item.get("first_seen"),
                "last_changed":item.get("last_changed"),
                "status":item.get("status")
            }
        )

    return response(
        200,
        {
            "count":len(jobs),
            "jobs":jobs
        }
    )


def get_admin_metrics():
    response_data=sources_table.scan()

    sources=response_data.get("Items",[])

    totals={
        "sources":len(sources),
        "fetch_attempts":0,
        "successful_crawls":0,
        "failed_crawls":0,
        "new":0,
        "unchanged":0,
        "changed":0,
        "cache_hits":0,
        "cache_misses":0,
        "controller_skips":0,
        "redundant_updates_prevented":0,
        "jobs_processed":0
    }

    source_metrics=[]

    for source in sources:
        fetch_attempts=int(
            source.get("fetch_attempt_count",0)
        )

        successful_crawls=int(
            source.get("successful_crawl_count",0)
        )

        failed_crawls=int(
            source.get("failed_crawl_count",0)
        )

        new_count=int(
            source.get("new_count",0)
        )

        unchanged_count=int(
            source.get("unchanged_count",0)
        )

        changed_count=int(
            source.get("changed_count",0)
        )

        cache_hits=int(
            source.get("cache_hit_count",0)
        )

        cache_misses=int(
            source.get("cache_miss_count",0)
        )

        skip_count=int(
            source.get("skip_count",0)
        )

        redundant_updates=int(
            source.get("redundant_updates_prevented",0)
        )

        jobs_processed=int(
            source.get("total_jobs_processed",0)
        )

        totals["fetch_attempts"]+=fetch_attempts
        totals["successful_crawls"]+=successful_crawls
        totals["failed_crawls"]+=failed_crawls
        totals["new"]+=new_count
        totals["unchanged"]+=unchanged_count
        totals["changed"]+=changed_count
        totals["cache_hits"]+=cache_hits
        totals["cache_misses"]+=cache_misses
        totals["controller_skips"]+=skip_count
        totals["redundant_updates_prevented"]+=redundant_updates
        totals["jobs_processed"]+=jobs_processed

        source_metrics.append(
            {
                "source_id":source.get("source_id"),
                "source_name":source.get("source_name"),
                "status":source.get("status"),
                "crawl_interval":source.get("crawl_interval"),
                "next_check":source.get("next_check"),
                "last_checked":source.get("last_checked"),
                "last_crawl_started":source.get(
                    "last_crawl_started"
                ),
                "last_crawl_completed":source.get(
                    "last_crawl_completed"
                ),
                "last_fetched_count":source.get(
                    "last_fetched_count",
                    0
                ),
                "last_crawl_duration":source.get(
                    "last_crawl_duration"
                ),
                "fetch_attempts":fetch_attempts,
                "successful_crawls":successful_crawls,
                "failed_crawls":failed_crawls,
                "new":new_count,
                "unchanged":unchanged_count,
                "changed":changed_count,
                "cache_hits":cache_hits,
                "cache_misses":cache_misses,
                "controller_skips":skip_count,
                "redundant_updates_prevented":redundant_updates,
                "jobs_processed":jobs_processed
            }
        )

    return response(
        200,
        {
            "metrics":totals,
            "sources":source_metrics
        }
    )


def lambda_handler(event,context):
    method=event.get("requestContext",{}).get(
        "http",
        {}
    ).get(
        "method"
    )

    if method=="OPTIONS":
        return response(
            200,
            {
                "message":"CORS preflight"
            }
        )

    raw_path=event.get("rawPath","")

    if raw_path=="/admin/metrics":
        return get_admin_metrics()

    path_parameters=event.get(
        "pathParameters"
    ) or {}

    job_id=path_parameters.get(
        "canonical_job_id"
    )

    if job_id:
        return get_job(job_id)

    return get_jobs(event)