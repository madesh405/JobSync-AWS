import json
import time
import boto3

from source_state import get_all_sources,is_source_due


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

    return {
        "source_id":source_id,
        "source_name":source_name,
        "message_id":response["MessageId"]
    }


def lambda_handler(event,context):
    sources=get_all_sources()

    queued=[]
    skipped=[]

    for source in sources:
        source_id=source.get("source_id")
        source_name=source.get("source_name")
        status=source.get("status")

        if status!="ACTIVE":
            skipped.append({
                "source_id":source_id,
                "reason":f"status={status}"
            })
            continue

        if not is_source_due(source):
            skipped.append({
                "source_id":source_id,
                "reason":"not_due"
            })
            continue

        result=enqueue_source(source)
        queued.append(result)

    result={
        "status":"SUCCESS",
        "timestamp":int(time.time()),
        "sources_found":len(sources),
        "queued":queued,
        "skipped":skipped,
        "queued_count":len(queued),
        "skipped_count":len(skipped)
    }

    print(
        json.dumps(
            result,
            indent=2
        )
    )

    return result


if __name__=="__main__":
    result=lambda_handler({},None)

    print()
    print(
        json.dumps(
            result,
            indent=2
        )
    )