import time
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
            "#status=:status"
        ),
        ExpressionAttributeNames={
            "#status":"status"
        },
        ExpressionAttributeValues={
            ":last_checked":int(time.time()),
            ":failure_count":failure_count,
            ":status":status
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
        print(f"Crawl interval: {source.get('crawl_interval')} seconds")
        print(f"Next check: {source.get('next_check')}")
        print(f"Due now: {is_source_due(source)}")