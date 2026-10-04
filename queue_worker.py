import json
import time
import boto3

from job_pipeline import (
    get_himalayas,
    get_jobicy,
    get_remoteok
)

from sync_engine import sync_job
from source_state import get_source,mark_success,mark_failure


REGION="us-east-1"

QUEUE_URL="https://sqs.us-east-1.amazonaws.com/673396344578/JobSync-CrawlQueue"

POLL_WAIT_SECONDS=20
MAX_POLL_ATTEMPTS=20
MAX_MESSAGES_PER_RECEIVE=2


SOURCE_FUNCTIONS={
    "himalayas":get_himalayas,
    "jobicy":get_jobicy,
    "remoteok":get_remoteok
}


sqs=boto3.client(
    "sqs",
    region_name=REGION
)


def process_source(source_id):
    if source_id not in SOURCE_FUNCTIONS:
        raise ValueError(f"Unknown source_id: {source_id}")

    source=get_source(source_id)

    if source is None:
        raise ValueError(f"Source not found in JobSync-Sources: {source_id}")

    if source.get("status")!="ACTIVE":
        raise ValueError(
            f"Source {source_id} is not ACTIVE: {source.get('status')}"
        )

    fetch_function=SOURCE_FUNCTIONS[source_id]

    print()
    print("="*60)
    print("PROCESSING SOURCE")
    print("="*60)
    print(f"Source: {source.get('source_name')}")
    print(f"Source ID: {source_id}")
    print()

    jobs=fetch_function()

    print(f"Fetched jobs: {len(jobs)}")
    print()

    summary={
        "NEW":0,
        "UNCHANGED":0,
        "CHANGED":0
    }

    for index,job in enumerate(jobs,1):
        result=sync_job(job)

        result_type=result.get("type")

        if result_type in summary:
            summary[result_type]+=1

        print(
            f"{index:03d}. "
            f"{job.company} | "
            f"{job.title} | "
            f"{result_type}"
        )

    changed=(
        summary["NEW"]>0 or
        summary["CHANGED"]>0
    )

    mark_success(
        source_id,
        int(source.get("crawl_interval",3600)),
        changed
    )

    print()
    print("-"*60)
    print(f"Source summary: {source_id}")
    print("-"*60)
    print(f"NEW: {summary['NEW']}")
    print(f"UNCHANGED: {summary['UNCHANGED']}")
    print(f"CHANGED: {summary['CHANGED']}")
    print(f"Source state updated: YES")

    return summary


def receive_messages():
    response=sqs.receive_message(
        QueueUrl=QUEUE_URL,
        MaxNumberOfMessages=MAX_MESSAGES_PER_RECEIVE,
        WaitTimeSeconds=POLL_WAIT_SECONDS,
        VisibilityTimeout=300
    )

    return response.get("Messages",[])


def process_message(message):
    message_id=message.get("MessageId")
    receipt_handle=message.get("ReceiptHandle")
    body=message.get("Body","")

    print()
    print("#"*60)
    print("SQS MESSAGE")
    print("#"*60)
    print(f"Message ID: {message_id}")
    print(f"Body: {body}")

    data=json.loads(body)

    source_id=data.get("source_id")

    if not source_id:
        raise ValueError("SQS message does not contain source_id")

    print(f"Source ID from message: {source_id}")

    try:
        summary=process_source(source_id)

        sqs.delete_message(
            QueueUrl=QUEUE_URL,
            ReceiptHandle=receipt_handle
        )

        print()
        print(f"MESSAGE DELETED: {message_id}")

        return {
            "success":True,
            "message_id":message_id,
            "source_id":source_id,
            "summary":summary
        }

    except Exception:
        mark_failure(source_id)
        print()
        print(
            f"MESSAGE NOT DELETED: {message_id}"
        )
        print(
            "SQS will make the message visible again for retry."
        )
        raise


def run_worker():
    processed=0

    print("="*60)
    print("SQS CRAWL WORKER")
    print("="*60)
    print(f"Queue: {QUEUE_URL}")
    print()

    for attempt in range(1,MAX_POLL_ATTEMPTS+1):
        print(
            f"Polling attempt {attempt}/{MAX_POLL_ATTEMPTS}..."
        )

        messages=receive_messages()

        if not messages:
            print("No visible messages.")
            continue

        print(
            f"Received {len(messages)} message(s)."
        )

        for message in messages:
            try:
                process_message(message)
                processed+=1

            except Exception as e:
                print()
                print(f"PROCESSING FAILED: {e}")

    print()
    print("="*60)
    print("WORKER SUMMARY")
    print("="*60)
    print(f"Messages processed successfully: {processed}")


if __name__=="__main__":
    try:
        run_worker()

    except KeyboardInterrupt:
        print()
        print("Worker stopped by user.")