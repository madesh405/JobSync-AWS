import time
from decimal import Decimal

import boto3

REGION="us-east-1"
TABLE_NAME="JobSync-Sources"

dynamodb=boto3.resource(
    "dynamodb",
    region_name=REGION
)

table=dynamodb.Table(TABLE_NAME)


def get_source(source_id):
    response=table.get_item(
        Key={
            "source_id":source_id
        },
        ConsistentRead=True
    )
    return response.get("Item")


def get_all_sources():
    response=table.scan()
    return response.get("Items",[])


def is_source_due(source):
    next_check=source.get("next_check")

    if next_check is None:
        return True

    return int(time.time())>=int(next_check)


def mark_crawl_start(source_id):
    current=int(time.time())

    source=get_source(source_id)

    if source is None:
        raise ValueError(f"Source not found: {source_id}")

    table.update_item(
        Key={
            "source_id":source_id
        },
        UpdateExpression=(
            "SET last_crawl_started=:last_crawl_started "
            "ADD fetch_attempt_count :one"
        ),
        ExpressionAttributeValues={
            ":last_crawl_started":current,
            ":one":1
        }
    )


def record_crawl_result(
    source_id,
    summary,
    fetched_count=None,
    duration=None
):
    current=int(time.time())

    new_count=int(summary.get("NEW",0))
    unchanged_count=int(summary.get("UNCHANGED",0))
    changed_count=int(summary.get("CHANGED",0))

    total_processed=(
        new_count+
        unchanged_count+
        changed_count
    )

    cache_hit_count=unchanged_count
    cache_miss_count=new_count+changed_count

    update_expression=(
        "SET last_crawl_completed=:last_crawl_completed,"
        "last_sync_new=:last_sync_new,"
        "last_sync_unchanged=:last_sync_unchanged,"
        "last_sync_changed=:last_sync_changed,"
        "last_sync_total=:last_sync_total,"
        "last_cache_hits=:last_cache_hits,"
        "last_cache_misses=:last_cache_misses"
    )

    expression_values={
        ":last_crawl_completed":current,
        ":last_sync_new":new_count,
        ":last_sync_unchanged":unchanged_count,
        ":last_sync_changed":changed_count,
        ":last_sync_total":total_processed,
        ":last_cache_hits":cache_hit_count,
        ":last_cache_misses":cache_miss_count
    }

    if fetched_count is not None:
        update_expression+=(
            ",last_fetched_count=:last_fetched_count"
        )

        expression_values[
            ":last_fetched_count"
        ]=int(fetched_count)

    if duration is not None:
        update_expression+=(
            ",last_crawl_duration=:last_crawl_duration"
        )

        expression_values[
            ":last_crawl_duration"
        ]=Decimal(str(round(duration,2)))

    update_expression+=(
        " ADD successful_crawl_count :one,"
        " total_jobs_processed :processed,"
        " new_count :new_count,"
        " unchanged_count :unchanged_count,"
        " changed_count :changed_count,"
        " cache_hit_count :cache_hits,"
        " cache_miss_count :cache_misses,"
        " redundant_updates_prevented :unchanged"
    )

    expression_values.update({
        ":one":1,
        ":processed":total_processed,
        ":new_count":new_count,
        ":unchanged_count":unchanged_count,
        ":changed_count":changed_count,
        ":cache_hits":cache_hit_count,
        ":cache_misses":cache_miss_count,
        ":unchanged":unchanged_count
    })

    table.update_item(
        Key={
            "source_id":source_id
        },
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values
    )


def mark_success(source_id,crawl_interval,changed):
    current=int(time.time())

    source=get_source(source_id)

    if source is None:
        raise ValueError(f"Source not found: {source_id}")

    update_expression=(
        "SET last_checked=:last_checked,"
        "next_check=:next_check,"
        "failure_count=:failure_count,"
        "#status=:status"
    )

    table.update_item(
        Key={
            "source_id":source_id
        },
        UpdateExpression=update_expression,
        ExpressionAttributeNames={
            "#status":"status"
        },
        ExpressionAttributeValues={
            ":last_checked":current,
            ":next_check":current+int(crawl_interval),
            ":failure_count":0,
            ":status":"ACTIVE"
        }
    )

    if changed:
        current_change_count=int(
            source.get("change_count",0)
        )

        table.update_item(
            Key={
                "source_id":source_id
            },
            UpdateExpression=(
                "SET last_changed=:last_changed,"
                "change_count=:change_count"
            ),
            ExpressionAttributeValues={
                ":last_changed":current,
                ":change_count":current_change_count+1
            }
        )


def mark_failure(source_id):
    source=get_source(source_id)

    if source is None:
        raise ValueError(f"Source not found: {source_id}")

    failure_count=int(source.get("failure_count",0))+1

    status="ACTIVE"

    if failure_count>=3:
        status="ERROR"

    table.update_item(
        Key={
            "source_id":source_id
        },
        UpdateExpression=(
            "SET last_checked=:last_checked,"
            "failure_count=:failure_count,"
            "#status=:status "
            "ADD failed_crawl_count :one"
        ),
        ExpressionAttributeNames={
            "#status":"status"
        },
        ExpressionAttributeValues={
            ":last_checked":int(time.time()),
            ":failure_count":failure_count,
            ":status":status,
            ":one":1
        }
    )


def record_source_skip(source_id):
    current=int(time.time())

    source=get_source(source_id)

    if source is None:
        raise ValueError(f"Source not found: {source_id}")

    table.update_item(
        Key={
            "source_id":source_id
        },
        UpdateExpression=(
            "SET last_skipped=:last_skipped "
            "ADD skip_count :one"
        ),
        ExpressionAttributeValues={
            ":last_skipped":current,
            ":one":1
        }
    )


if __name__=="__main__":
    sources=get_all_sources()

    print("="*60)
    print("JOB SOURCE STATE TEST")
    print("="*60)
    print(f"Sources found: {len(sources)}")

    for source in sources:
        print()
        print(f"Source ID: {source.get('source_id')}")
        print(f"Name: {source.get('source_name')}")
        print(f"Status: {source.get('status')}")
        print(
            f"Crawl interval: "
            f"{source.get('crawl_interval')} seconds"
        )
        print(f"Next check: {source.get('next_check')}")
        print(f"Due now: {is_source_due(source)}")
        print(
            f"Fetch attempts: "
            f"{source.get('fetch_attempt_count',0)}"
        )
        print(
            f"Successful crawls: "
            f"{source.get('successful_crawl_count',0)}"
        )
        print(
            f"NEW: "
            f"{source.get('new_count',0)}"
        )
        print(
            f"UNCHANGED: "
            f"{source.get('unchanged_count',0)}"
        )
        print(
            f"CHANGED: "
            f"{source.get('changed_count',0)}"
        )
        print(
            f"Cache hits: "
            f"{source.get('cache_hit_count',0)}"
        )
        print(
            f"Cache misses: "
            f"{source.get('cache_miss_count',0)}"
        )
        print(
            f"Redundant updates prevented: "
            f"{source.get('redundant_updates_prevented',0)}"
        )
        print(
            f"Skipped: "
            f"{source.get('skip_count',0)}"
        )
        print(
            f"Failures: "
            f"{source.get('failed_crawl_count',0)}"
        )