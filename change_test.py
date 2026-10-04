from job_pipeline import get_himalayas,finalize_job
from sync_engine import sync_job


def main():

    jobs=get_himalayas()[:2]

    job=jobs[0]

    print("="*60)
    print("CHANGE DETECTION TEST")
    print("="*60)

    print("\nOriginal:")
    print("Title:",job.title)
    print("Company:",job.company)
    print("Original hash:",job.content_hash)

    # Simulate a change coming from the source.
    job.description=job.description+" [TEST CHANGE]"

    job=finalize_job(job)

    print("\nAfter simulated change:")
    print("New hash:",job.content_hash)

    result=sync_job(job)

    print("\nRESULT:",result["type"])
    print("JOB ID:",result["job_id"])
    print("CHANGED FIELDS:",result["changed_fields"])


if __name__=="__main__":
    main()