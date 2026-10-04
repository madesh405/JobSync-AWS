import hashlib
import re
import unicodedata
from dataclasses import dataclass, asdict

import requests
from bs4 import BeautifulSoup

TIMEOUT=20

@dataclass
class Job:
    source:str
    source_id:str
    title:str
    company:str
    location:str
    employment_type:str
    salary_min:float|None
    salary_max:float|None
    description:str
    apply_url:str
    published_at:str

    canonical_job_id:str=""
    content_hash:str=""

def clean_text(value):
    if value is None:
        return ""

    text=BeautifulSoup(str(value),"html.parser").get_text(" ",strip=True)
    text=unicodedata.normalize("NFKC",text)
    text=re.sub(r"\s+"," ",text)

    return text.strip()

def normalize_text(value):
    text=clean_text(value).lower()

    text=text.replace("&"," and ")

    text=re.sub(r"[^\w+#.]+"," ",text)
    text=re.sub(r"\s+"," ",text)

    return text.strip()

def normalize_company(value):
    return normalize_text(value)

def normalize_location(value):
    text=normalize_text(value)

    replacements={
        "bengaluru":"bangalore",
        "bombay":"mumbai",
        "calcutta":"kolkata",
        "madras":"chennai"
    }

    for old,new in replacements.items():
        text=re.sub(rf"\b{old}\b",new,text)

    return text

def normalize_title(value):
    text=normalize_text(value)

    # Make word order irrelevant for the canonical identity.
    words=text.split()

    stop_words={
        "a",
        "an",
        "the",
        "and",
        "for",
        "of",
        "in",
        "on",
        "to"
    }

    words=[x for x in words if x not in stop_words]

    return " ".join(sorted(words))

def make_canonical_id(job):
    company=normalize_company(job.company)
    title=normalize_title(job.title)
    location=normalize_location(job.location)

    raw=f"{company}|{title}|{location}"

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:16]

def make_content_hash(job):
    content={
        "title":normalize_title(job.title),
        "company":normalize_company(job.company),
        "location":normalize_location(job.location),
        "employment_type":normalize_text(job.employment_type),
        "salary_min":job.salary_min,
        "salary_max":job.salary_max,
        "description":normalize_text(job.description)
    }

    raw="|".join(
        f"{k}={content[k]}"
        for k in sorted(content)
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()

def finalize_job(job):
    job.canonical_job_id=make_canonical_id(job)
    job.content_hash=make_content_hash(job)

    return job


# ============================================================
# HIMALAYAS
# ============================================================

def get_himalayas():
    r=requests.get(
        "https://himalayas.app/jobs/api",
        params={"limit":20},
        timeout=TIMEOUT
    )

    r.raise_for_status()

    data=r.json()
    jobs=[]

    for item in data.get("jobs",[]):
        locations=item.get("locationRestrictions",[])

        if isinstance(locations,list):
            location=", ".join(locations)
        else:
            location=str(locations or "")

        job=Job(
            source="himalayas",
            source_id=item.get("guid") or item.get("applicationLink",""),
            title=clean_text(item.get("title")),
            company=clean_text(item.get("companyName")),
            location=clean_text(location),
            employment_type=clean_text(item.get("employmentType")),
            salary_min=item.get("minSalary"),
            salary_max=item.get("maxSalary"),
            description=clean_text(item.get("description")),
            apply_url=item.get("applicationLink",""),
            published_at=str(item.get("pubDate",""))
        )

        jobs.append(finalize_job(job))

    return jobs


# ============================================================
# JOBICY
# ============================================================

def get_jobicy():
    r=requests.get(
        "https://jobicy.com/api/v2/remote-jobs",
        params={"count":20},
        timeout=TIMEOUT
    )

    r.raise_for_status()

    data=r.json()
    jobs=[]

    for item in data.get("jobs",[]):

        job_types=item.get("jobType",[])

        if isinstance(job_types,list):
            employment_type=", ".join(
                clean_text(x) for x in job_types
            )
        else:
            employment_type=clean_text(job_types)

        job=Job(
            source="jobicy",
            source_id=str(item.get("id","")),
            title=clean_text(item.get("jobTitle")),
            company=clean_text(item.get("companyName")),
            location=clean_text(item.get("jobGeo")),
            employment_type=employment_type,
            salary_min=None,
            salary_max=None,
            description=clean_text(item.get("jobDescription")),
            apply_url=item.get("url",""),
            published_at=str(item.get("pubDate",""))
        )

        jobs.append(finalize_job(job))

    return jobs


# ============================================================
# REMOTE OK
# ============================================================

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

        # Remote OK includes a metadata object.
        if "position" not in item:
            continue

        tags=item.get("tags",[])

        if isinstance(tags,list):
            employment=[]
            for tag in tags:
                tag=clean_text(tag).lower()

                if tag in {
                    "full time",
                    "part time",
                    "contract",
                    "freelance",
                    "internship"
                }:
                    employment.append(tag)

            employment_type=", ".join(employment)
        else:
            employment_type=""

        job=Job(
            source="remoteok",
            source_id=str(item.get("id","")),
            title=clean_text(item.get("position")),
            company=clean_text(item.get("company")),
            location=clean_text(item.get("location")),
            employment_type=employment_type,
            salary_min=item.get("salary_min"),
            salary_max=item.get("salary_max"),
            description=clean_text(item.get("description")),
            apply_url=item.get("apply_url") or item.get("url",""),
            published_at=str(item.get("date",""))
        )

        jobs.append(finalize_job(job))

    return jobs


# ============================================================
# MAIN DEBUG TEST
# ============================================================

def print_job(job):

    print("-"*60)
    print("SOURCE:",job.source)
    print("SOURCE ID:",job.source_id)
    print("TITLE:",job.title)
    print("COMPANY:",job.company)
    print("LOCATION:",job.location)
    print("TYPE:",job.employment_type)
    print("SALARY:",job.salary_min,"-",job.salary_max)
    print("CANONICAL ID:",job.canonical_job_id)
    print("CONTENT HASH:",job.content_hash)
    print("URL:",job.apply_url)

def main():

    all_jobs=[]

    print("\nFetching Himalayas...")
    h=get_himalayas()
    print("✅ Himalayas:",len(h))
    all_jobs.extend(h)

    print("\nFetching Jobicy...")
    j=get_jobicy()
    print("✅ Jobicy:",len(j))
    all_jobs.extend(j)

    print("\nFetching Remote OK...")
    r=get_remoteok()
    print("✅ Remote OK:",len(r))
    all_jobs.extend(r)

    print("\nTOTAL RAW JOBS:",len(all_jobs))

    print("\nFIRST 3 NORMALIZED JOBS:")

    for job in all_jobs[:3]:
        print_job(job)

if __name__=="__main__":
    main()