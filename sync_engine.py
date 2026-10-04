import hashlib
import re
import time
from decimal import Decimal

import boto3

from job_pipeline import normalize_text


REGION="us-east-1"
TABLE_NAME="JobSync-Jobs"


dynamodb=boto3.resource(
    "dynamodb",
    region_name=REGION
)

table=dynamodb.Table(TABLE_NAME)


TRACKED_FIELDS=[
    "title",
    "company",
    "location",
    "employment_type",
    "salary_min",
    "salary_max",
    "description",
    "apply_url"
]


REMOTEOK_VOLATILE_PATTERN=re.compile(
    r"\s*Please mention the word\b.*?"
    r"when applying to show you read the job post completely.*$",
    re.IGNORECASE|re.DOTALL
)


def now():
    return int(time.time())


def dynamo_value(value):
    if isinstance(value,float):
        return Decimal(str(value))

    return value


def normalize_description(source,description):
    if description is None:
        return ""

    description=str(description)

    if source=="remoteok":
        description=REMOTEOK_VOLATILE_PATTERN.sub(
            "",
            description
        )

    return description.strip()


def comparison_hash_from_values(
    source,
    title,
    company,
    location,
    employment_type,
    salary_min,
    salary_max,
    description,
    apply_url
):
    description=normalize_description(
        source,
        description
    )

    values=[
        title or "",
        company or "",
        location or "",
        employment_type or "",
        salary_min if salary_min is not None else "",
        salary_max if salary_max is not None else "",
        description,
        apply_url or ""
    ]

    normalized=[]

    for value in values:
        normalized.append(
            normalize_text(str(value))
        )

    payload="|".join(normalized)

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def comparison_hash_from_job(job):
    return comparison_hash_from_values(
        source=job.source,
        title=job.title,
        company=job.company,
        location=job.location,
        employment_type=job.employment_type,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        description=job.description,
        apply_url=job.apply_url
    )


def comparison_hash_from_item(item):
    return comparison_hash_from_values(
        source=item.get("source"),
        title=item.get("title"),
        company=item.get("company"),
        location=item.get("location"),
        employment_type=item.get("employment_type"),
        salary_min=item.get("salary_min"),
        salary_max=item.get("salary_max"),
        description=item.get("description"),
        apply_url=item.get("apply_url")
    )


def make_content_hash(job):
    return comparison_hash_from_job(job)


def job_to_item(job):
    item={
        "canonical_job_id":job.canonical_job_id,
        "source":job.source,
        "source_id":job.source_id,
        "title":job.title,
        "company":job.company,
        "location":job.location,
        "employment_type":job.employment_type,
        "description":job.description,
        "apply_url":job.apply_url,
        "published_at":job.published_at,
        "content_hash":comparison_hash_from_job(job),
        "status":"OPEN"
    }

    if job.salary_min is not None:
        item["salary_min"]=dynamo_value(
            job.salary_min
        )

    if job.salary_max is not None:
        item["salary_max"]=dynamo_value(
            job.salary_max
        )

    return item


def find_existing(job_id):
    response=table.get_item(
        Key={
            "canonical_job_id":job_id
        },
        ConsistentRead=True
    )

    return response.get("Item")


def find_changes(existing,new_item):
    changed_fields=[]

    for field in TRACKED_FIELDS:
        old=existing.get(field)
        new=new_item.get(field)

        if old!=new:
            changed_fields.append(field)

    return changed_fields


def sync_job(job):
    job_id=job.canonical_job_id

    existing=find_existing(job_id)

    new_item=job_to_item(job)

    if existing is None:
        current=now()

        new_item["first_seen"]=current
        new_item["last_changed"]=current
        new_item["change_count"]=0

        table.put_item(
            Item=new_item
        )

        return {
            "type":"NEW",
            "job_id":job_id,
            "changed_fields":[]
        }

    new_comparison_hash=comparison_hash_from_job(job)
    old_comparison_hash=comparison_hash_from_item(existing)

    if old_comparison_hash==new_comparison_hash:
        return {
            "type":"UNCHANGED",
            "job_id":job_id,
            "changed_fields":[]
        }

    changed_fields=find_changes(
        existing,
        new_item
    )

    current=now()

    new_item["first_seen"]=existing.get(
        "first_seen",
        current
    )

    new_item["last_changed"]=current

    new_item["change_count"]=int(
        existing.get("change_count",0)
    )+1

    table.put_item(
        Item=new_item
    )

    return {
        "type":"CHANGED",
        "job_id":job_id,
        "changed_fields":changed_fields
    }


if __name__=="__main__":
    print("="*60)
    print("SYNC ENGINE TEST")
    print("="*60)
    print("Table:",TABLE_NAME)
    print("Tracked fields:",TRACKED_FIELDS)