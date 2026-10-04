import requests

TIMEOUT=20

def get_himalayas():
    r=requests.get(
        "https://himalayas.app/jobs/api",
        params={"limit":5},
        timeout=TIMEOUT
    )
    r.raise_for_status()
    data=r.json()
    return data.get("jobs",[])

def get_jobicy():
    r=requests.get(
        "https://jobicy.com/api/v2/remote-jobs",
        params={"count":5},
        timeout=TIMEOUT
    )
    r.raise_for_status()
    data=r.json()
    return data.get("jobs",[])

def get_remoteok():
    r=requests.get(
        "https://remoteok.com/api",
        headers={
            "User-Agent":"JobSyncStudentProject/1.0"
        },
        timeout=TIMEOUT
    )
    r.raise_for_status()
    data=r.json()

    jobs=[]

    for item in data:
        if not isinstance(item,dict):
            continue

        # Remote OK contains metadata as the first item.
        if "position" not in item:
            continue

        jobs.append(item)

    return jobs

def print_sample(source,jobs):
    print("\n"+"="*60)
    print(source)
    print("="*60)
    print("Jobs:",len(jobs))

    if not jobs:
        print("❌ No jobs found")
        return

    job=jobs[0]

    print("\nAvailable fields:")
    for key in job.keys():
        print(" -",key)

    print("\nSample:")
    print(job)


try:
    h=get_himalayas()
    print_sample("HIMALAYAS",h)
except Exception as e:
    print("❌ HIMALAYAS:",e)

try:
    j=get_jobicy()
    print_sample("JOBICY",j)
except Exception as e:
    print("❌ JOBICY:",e)

try:
    r=get_remoteok()
    print_sample("REMOTE OK",r)
except Exception as e:
    print("❌ REMOTE OK:",e)