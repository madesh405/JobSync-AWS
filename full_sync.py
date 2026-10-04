from job_pipeline import (
    get_himalayas,
    get_jobicy,
    get_remoteok
)

from sync_engine import sync_job


def sync_source(name,jobs):

    print("\n"+"="*60)
    print(name)
    print("="*60)

    counts={
        "NEW":0,
        "UNCHANGED":0,
        "CHANGED":0
    }

    for i,job in enumerate(jobs,1):

        result=sync_job(job)

        result_type=result["type"]

        counts[result_type]+=1

        print(
            f"[{i}/{len(jobs)}] "
            f"{result_type:10} "
            f"{job.company} - {job.title}"
        )

        if result["changed_fields"]:
            print(
                "    Changed:",
                result["changed_fields"]
            )

    print("\nSOURCE SUMMARY")
    print("NEW:",counts["NEW"])
    print("UNCHANGED:",counts["UNCHANGED"])
    print("CHANGED:",counts["CHANGED"])

    return counts


def main():

    print("="*60)
    print("FULL JOB SYNCHRONIZATION")
    print("="*60)

    total={
        "NEW":0,
        "UNCHANGED":0,
        "CHANGED":0
    }

    # ========================================================
    # HIMALAYAS
    # ========================================================

    print("\nFetching Himalayas...")

    h=get_himalayas()

    print("Fetched:",len(h))

    result=sync_source(
        "HIMALAYAS",
        h
    )

    for key in total:
        total[key]+=result[key]

    # ========================================================
    # JOBICY
    # ========================================================

    print("\nFetching Jobicy...")

    j=get_jobicy()

    print("Fetched:",len(j))

    result=sync_source(
        "JOBICY",
        j
    )

    for key in total:
        total[key]+=result[key]

    # ========================================================
    # REMOTE OK
    # ========================================================

    print("\nFetching Remote OK...")

    r=get_remoteok()

    print("Fetched:",len(r))

    result=sync_source(
        "REMOTE OK",
        r
    )

    for key in total:
        total[key]+=result[key]

    # ========================================================
    # FINAL SUMMARY
    # ========================================================

    print("\n"+"="*60)
    print("TOTAL SYNCHRONIZATION RESULT")
    print("="*60)

    print("NEW:",total["NEW"])
    print("UNCHANGED:",total["UNCHANGED"])
    print("CHANGED:",total["CHANGED"])

    print(
        "TOTAL SOURCE RECORDS:",
        sum(total.values())
    )


if __name__=="__main__":
    main()