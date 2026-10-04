import requests

TIMEOUT=20

def test_api(name,url,params=None,headers=None):
    print("\n"+"="*60)
    print(name)
    print("="*60)
    print("URL:",url)

    try:
        r=requests.get(
            url,
            params=params or {},
            headers=headers or {},
            timeout=TIMEOUT
        )

        print("HTTP:",r.status_code)
        print("TYPE:",r.headers.get("content-type"))
        print("SIZE:",len(r.content),"bytes")

        if r.status_code!=200:
            print("❌ REQUEST FAILED")
            print(r.text[:500])
            return

        print("✅ REQUEST OK")

        try:
            data=r.json()
        except ValueError:
            print("❌ NOT JSON")
            print(r.text[:500])
            return

        print("✅ VALID JSON")
        print("DATA TYPE:",type(data).__name__)

        if isinstance(data,dict):
            print("KEYS:",list(data.keys()))

            if "jobs" in data:
                jobs=data["jobs"]
                print("JOB COUNT:",len(jobs))

                if jobs:
                    print("\nFIRST JOB:")
                    print(jobs[0])

        elif isinstance(data,list):
            print("ITEM COUNT:",len(data))

            if data:
                print("\nFIRST ITEM:")
                print(data[0])

    except requests.exceptions.Timeout:
        print("❌ TIMEOUT")

    except requests.exceptions.ConnectionError as e:
        print("❌ CONNECTION ERROR")
        print(e)

    except Exception as e:
        print("❌ ERROR:",type(e).__name__)
        print(e)


test_api(
    "HIMALAYAS",
    "https://himalayas.app/jobs/api",
    params={"limit":5}
)

test_api(
    "JOBICY",
    "https://jobicy.com/api/v2/remote-jobs",
    params={"count":5}
)

test_api(
    "REMOTE OK",
    "https://remoteok.com/api",
    headers={
        "User-Agent":"JobSyncStudentProject/1.0"
    }
)