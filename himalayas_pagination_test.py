import requests


URL="https://himalayas.app/jobs/api"

LIMIT=20


def get_page(cursor=None):
    params={
        "limit":LIMIT
    }

    if cursor:
        params["cursor"]=cursor

    response=requests.get(
        URL,
        params=params,
        timeout=20
    )

    response.raise_for_status()

    return response.json()


first=get_page()

first_jobs=first.get("jobs",[])
next_cursor=first.get("nextCursor")

print("="*60)
print("HIMALAYAS CURSOR PAGINATION TEST")
print("="*60)

print(f"First page jobs: {len(first_jobs)}")
print(f"Next cursor present: {bool(next_cursor)}")
print(f"Total count reported: {first.get('totalCount')}")
print()

if not next_cursor:
    raise RuntimeError(
        "Himalayas did not return nextCursor"
    )


second=get_page(next_cursor)

second_jobs=second.get("jobs",[])

print(f"Second page jobs: {len(second_jobs)}")
print(f"Second page next cursor present: {bool(second.get('nextCursor'))}")
print()

first_ids={
    str(job.get("guid"))
    for job in first_jobs
    if job.get("guid") is not None
}

second_ids={
    str(job.get("guid"))
    for job in second_jobs
    if job.get("guid") is not None
}

overlap=first_ids & second_ids

print(f"First page unique IDs: {len(first_ids)}")
print(f"Second page unique IDs: {len(second_ids)}")
print(f"Overlapping IDs: {len(overlap)}")

print()

print("FIRST PAGE SAMPLE:")

for job in first_jobs[:3]:
    print(
        f"{job.get('title')} | "
        f"{job.get('companyName')} | "
        f"{job.get('guid')}"
    )

print()

print("SECOND PAGE SAMPLE:")

for job in second_jobs[:3]:
    print(
        f"{job.get('title')} | "
        f"{job.get('companyName')} | "
        f"{job.get('guid')}"
    )

print()

if overlap:
    raise RuntimeError(
        "Pagination test failed: pages overlap"
    )

print("CURSOR PAGINATION TEST PASSED")