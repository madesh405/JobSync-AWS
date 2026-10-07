import json
import time
import boto3

from source_state import (
    get_all_sources,
    is_source_due,
    record_source_skip
)


REGION="us-east-1"

QUEUE_URL="https://sqs.us-east-1.amazonaws.com/673396344578/JobSync-CrawlQueue"


sqs=boto3.client(
    "sqs",
    region_name=REGION
)


def enqueue_source(source):
    source_id=source.get("source_id")
    source_name=source.get("source_name")

    message={
        "source_id":source_id,
        "reason":"SCHEDULED_SYNC",
        "requested_at":int(time.time())
    }

    response=sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(message)
    )

    print(
        f"QUEUED | "
        f"{source_name} | "
        f"source_id={source_id} | "
        f"message_id={response['MessageId']}"
    )


def run_controller():
    sources=get_all_sources()

    print("="*60)
    print("CRAWL CONTROLLER")
    print("="*60)
    print(f"Sources found: {len(sources)}")
    print()

    queued=0
    skipped=0

    for source in sources:
        source_id=source.get("source_id")
        source_name=source.get("source_name")
        status=source.get("status")

        if status!="ACTIVE":
            print(
                f"SKIPPED | "
                f"{source_name} | "
                f"status={status}"
            )
            skipped+=1
            continue

        if not is_source_due(source):
            print(
                f"SKIPPED | "
                f"{source_name} | "
                f"not due"
            )

            record_source_skip(source_id)

            skipped+=1
            continue

        enqueue_source(source)
        queued+=1

    print()
    print("-"*60)
    print("SUMMARY")
    print("-"*60)
    print(f"QUEUED: {queued}")
    print(f"SKIPPED: {skipped}")

    return {
        "queued":queued,
        "skipped":skipped
    }


if __name__=="__main__":
    result=run_controller()

    print()
    print(
        json.dumps(
            {
                "status":"SUCCESS",
                "summary":result
            },
            indent=2
        )
    )