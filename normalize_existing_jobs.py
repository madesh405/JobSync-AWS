import boto3
import re


REGION="us-east-1"
TABLE_NAME="JobSync-Jobs"


dynamodb=boto3.resource(
    "dynamodb",
    region_name=REGION
)

table=dynamodb.Table(
    TABLE_NAME
)


def normalize_employment_type(value):
    if not value:
        return "OTHER"

    text=str(
        value
    ).strip().lower()

    text=text.replace(
        "-",
        " "
    )

    text=text.replace(
        "_",
        " "
    )

    text=re.sub(
        r"\s+",
        " ",
        text
    )

    if (
        "full time" in text or
        "fulltime" in text
    ):
        return "FULL_TIME"

    if (
        "part time" in text or
        "parttime" in text
    ):
        return "PART_TIME"

    if (
        "contractor" in text or
        "contract" in text or
        "freelance" in text
    ):
        return "CONTRACT"

    if (
        "internship" in text or
        "intern" in text
    ):
        return "INTERNSHIP"

    if (
        "temporary" in text or
        re.search(
            r"\btemp\b",
            text
        )
    ):
        return "TEMPORARY"

    return "OTHER"


def scan_all_jobs():
    items=[]

    response=table.scan()

    items.extend(
        response.get(
            "Items",
            []
        )
    )

    while "LastEvaluatedKey" in response:
        response=table.scan(
            ExclusiveStartKey=
                response[
                    "LastEvaluatedKey"
                ]
        )

        items.extend(
            response.get(
                "Items",
                []
            )
        )

    return items


def migrate():
    jobs=scan_all_jobs()

    print("="*60)
    print("EMPLOYMENT TYPE MIGRATION")
    print("="*60)
    print(
        f"Jobs found: {len(jobs)}"
    )
    print()

    updated=0
    unchanged=0

    for job in jobs:
        job_id=job.get(
            "canonical_job_id"
        )

        old_value=job.get(
            "employment_type"
        )

        new_value=normalize_employment_type(
            old_value
        )

        if old_value==new_value:
            unchanged+=1
            continue

        table.update_item(
            Key={
                "canonical_job_id":
                    job_id
            },
            UpdateExpression=(
                "SET employment_type=:employment_type"
            ),
            ExpressionAttributeValues={
                ":employment_type":
                    new_value
            }
        )

        updated+=1

        print(
            f"UPDATED | "
            f"{job_id} | "
            f"{old_value} -> {new_value}"
        )

    print()
    print("-"*60)
    print("SUMMARY")
    print("-"*60)
    print(
        f"UPDATED: {updated}"
    )
    print(
        f"UNCHANGED: {unchanged}"
    )

    return {
        "updated":updated,
        "unchanged":unchanged
    }


if __name__=="__main__":
    result=migrate()

    print()
    print(
        "Migration completed."
    )