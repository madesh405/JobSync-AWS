import json
import logging

from job_pipeline import (
    get_himalayas,
    get_jobicy,
    get_remoteok
)

from sync_engine import sync_job
from source_state import get_source,mark_success,mark_failure


logger=logging.getLogger()
logger.setLevel(logging.INFO)


SOURCE_FUNCTIONS={
    "himalayas":get_himalayas,
    "jobicy":get_jobicy,
    "remoteok":get_remoteok
}


def process_source(source_id):
    if source_id not in SOURCE_FUNCTIONS:
        raise ValueError(f"Unknown source_id: {source_id}")

    source=get_source(source_id)

    if source is None:
        raise ValueError(
            f"Source not found: {source_id}"
        )

    if source.get("status")!="ACTIVE":
        raise ValueError(
            f"Source is not ACTIVE: {source_id}"
        )

    logger.info("="*60)
    logger.info("PROCESSING SOURCE")
    logger.info("="*60)
    logger.info("Source: %s",source.get("source_name"))
    logger.info("Source ID: %s",source_id)

    jobs=SOURCE_FUNCTIONS[source_id]()

    logger.info(
        "Fetched jobs: %d",
        len(jobs)
    )

    summary={
        "NEW":0,
        "UNCHANGED":0,
        "CHANGED":0
    }

    for job in jobs:
        result=sync_job(job)

        result_type=result.get("type")

        if result_type in summary:
            summary[result_type]+=1

    changed=(
        summary["NEW"]>0 or
        summary["CHANGED"]>0
    )

    mark_success(
        source_id,
        int(source.get("crawl_interval",3600)),
        changed
    )

    logger.info(
        "Source summary: %s",
        json.dumps(summary)
    )

    logger.info(
        "Source state updated successfully"
    )

    return summary


def lambda_handler(event,context):
    records=event.get("Records",[])

    logger.info("="*60)
    logger.info("JOBSYNC CRAWL WORKER")
    logger.info("="*60)
    logger.info(
        "SQS records received: %d",
        len(records)
    )

    results=[]

    for record in records:
        message_id=record.get("messageId")
        body=record.get("body","")

        logger.info(
            "Processing message: %s",
            message_id
        )

        try:
            data=json.loads(body)

            source_id=data.get("source_id")

            if not source_id:
                raise ValueError(
                    "Message does not contain source_id"
                )

            logger.info(
                "Source ID: %s",
                source_id
            )

            summary=process_source(source_id)

            results.append(
                {
                    "message_id":message_id,
                    "source_id":source_id,
                    "summary":summary
                }
            )

        except Exception:
            source_id=None

            try:
                data=json.loads(body)
                source_id=data.get("source_id")
            except Exception:
                pass

            if source_id:
                try:
                    mark_failure(source_id)
                except Exception as state_error:
                    logger.error(
                        "Failed to update source failure state: %s",
                        state_error
                    )

            logger.exception(
                "Message processing failed: %s",
                message_id
            )

            raise

    logger.info(
        "All SQS records processed successfully"
    )

    return {
        "status":"SUCCESS",
        "processed":len(results),
        "results":results
    }