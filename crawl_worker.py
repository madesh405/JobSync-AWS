import json
import sys

from job_pipeline import (
    get_himalayas,
    get_jobicy,
    get_remoteok
)

from sync_engine import sync_job


SOURCE_FUNCTIONS={
    "himalayas":get_himalayas,
    "jobicy":get_jobicy,
    "remoteok":get_remoteok
}


def crawl_source(source_id):
    if source_id not in SOURCE_FUNCTIONS:
        raise ValueError(f"Unknown source_id: {source_id}")

    fetch_function=SOURCE_FUNCTIONS[source_id]

    print("="*60)
    print("CRAWL WORKER")
    print("="*60)
    print(f"Source: {source_id}")
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

    print()
    print("-"*60)
    print("SUMMARY")
    print("-"*60)
    print(f"NEW: {summary['NEW']}")
    print(f"UNCHANGED: {summary['UNCHANGED']}")
    print(f"CHANGED: {summary['CHANGED']}")

    return summary


def lambda_style_event(event):
    body=event.get("body")

    if isinstance(body,str):
        body=json.loads(body)

    if not isinstance(body,dict):
        raise ValueError("Invalid event body")

    source_id=body.get("source_id")

    if not source_id:
        raise ValueError("source_id is required")

    return crawl_source(source_id)


if __name__=="__main__":
    if len(sys.argv)!=2:
        print("Usage:")
        print("python crawl_worker.py <source_id>")
        print()
        print("Example:")
        print("python crawl_worker.py himalayas")
        sys.exit(1)

    source_id=sys.argv[1]

    try:
        summary=crawl_source(source_id)

        print()
        print(
            json.dumps(
                {
                    "status":"SUCCESS",
                    "source_id":source_id,
                    "summary":summary
                },
                indent=2
            )
        )

    except Exception as e:
        print()
        print("CRAWL FAILED")
        print(f"Error: {e}")
        sys.exit(1)