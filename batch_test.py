from job_pipeline import get_himalayas
from sync_engine import sync_job


def main():

    print("="*60)
    print("BATCH SYNC TEST")
    print("="*60)

    jobs=get_himalayas()[:2]

    print("\nJobs fetched:",len(jobs))

    for i,job in enumerate(jobs,1):

        print("\n"+"-"*60)
        print("JOB",i)
        print("-"*60)

        print("Title:",job.title)
        print("Company:",job.company)
        print("Canonical ID:",job.canonical_job_id)

        result=sync_job(job)

        print("RESULT:",result["type"])

        if result["changed_fields"]:
            print(
                "CHANGED FIELDS:",
                result["changed_fields"]
            )


if __name__=="__main__":
    main()