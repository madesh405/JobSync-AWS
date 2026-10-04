import boto3
from job_pipeline import get_himalayas

TABLE_NAME="JobSync-Jobs"
REGION="us-east-1"

dynamodb=boto3.resource(
    "dynamodb",
    region_name=REGION
)

table=dynamodb.Table(TABLE_NAME)


def save_job(job):

    item={
        "canonical_job_id":job.canonical_job_id,
        "source":job.source,
        "source_id":job.source_id,
        "title":job.title,
        "company":job.company,
        "location":job.location,
        "employment_type":job.employment_type,
        "salary_min":job.salary_min,
        "salary_max":job.salary_max,
        "description":job.description,
        "apply_url":job.apply_url,
        "published_at":job.published_at,
        "content_hash":job.content_hash,
        "status":"OPEN"
    }

    table.put_item(Item=item)

    print("✅ JOB WRITTEN")
    print("Canonical ID:",job.canonical_job_id)


def read_job(canonical_job_id):

    response=table.get_item(
        Key={
            "canonical_job_id":canonical_job_id
        }
    )

    item=response.get("Item")

    if item:
        print("\n✅ JOB READ FROM DYNAMODB")
        print("Title:",item.get("title"))
        print("Company:",item.get("company"))
        print("Location:",item.get("location"))
        print("Hash:",item.get("content_hash"))
        print("Status:",item.get("status"))
    else:
        print("\n❌ JOB NOT FOUND")


def main():

    print("Fetching one real job from Himalayas...")

    jobs=get_himalayas()

    if not jobs:
        print("❌ Himalayas returned no jobs")
        return

    job=jobs[0]

    print("\nLOCAL JOB")
    print("Title:",job.title)
    print("Company:",job.company)
    print("Location:",job.location)
    print("Canonical ID:",job.canonical_job_id)
    print("Content Hash:",job.content_hash)

    print("\nWriting to DynamoDB...")

    save_job(job)

    print("\nReading it back...")

    read_job(job.canonical_job_id)


if __name__=="__main__":
    main()