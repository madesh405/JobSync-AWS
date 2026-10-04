import time

import boto3

from job_pipeline import Job,finalize_job
from sync_engine import sync_job


TABLE_NAME="JobSync-Jobs"
REGION="us-east-1"

TEST_JOB_ID="4ef95ef00b5510ae"

dynamodb=boto3.resource(
    "dynamodb",
    region_name=REGION
)

table=dynamodb.Table(TABLE_NAME)

client=boto3.client(
    "dynamodbstreams",
    region_name=REGION
)


def get_stream_arn():

    response=table.meta.client.describe_table(
        TableName=TABLE_NAME
    )

    arn=response["Table"].get(
        "LatestStreamArn"
    )

    if not arn:
        raise RuntimeError(
            "DynamoDB Stream is not enabled."
        )

    return arn


def get_all_shards(stream_arn):

    shards=[]
    last_shard_id=None

    while True:

        params={
            "StreamArn":stream_arn,
            "Limit":100
        }

        if last_shard_id:
            params["ExclusiveStartShardId"]=last_shard_id

        response=client.describe_stream(
            **params
        )

        description=response["StreamDescription"]

        shards.extend(
            description.get(
                "Shards",
                []
            )
        )

        last_shard_id=description.get(
            "LastEvaluatedShardId"
        )

        if not last_shard_id:
            break

    return shards


def create_latest_iterators(
    stream_arn,
    shards
):

    iterators={}

    print("\nCreating LATEST iterators...")

    for shard in shards:

        shard_id=shard["ShardId"]

        try:

            response=client.get_shard_iterator(
                StreamArn=stream_arn,
                ShardId=shard_id,
                ShardIteratorType="LATEST"
            )

            iterator=response.get(
                "ShardIterator"
            )

            if iterator:

                iterators[shard_id]=iterator

                print(
                    "✅ Iterator:",
                    shard_id
                )

        except Exception as e:

            print(
                "⚠️ Could not create iterator:",
                shard_id
            )

            print(
                type(e).__name__,
                e
            )

    return iterators


def get_existing_job():

    response=table.get_item(
        Key={
            "canonical_job_id":TEST_JOB_ID
        },
        ConsistentRead=True
    )

    item=response.get("Item")

    if not item:
        return None

    job=Job(
        source=item.get("source",""),
        source_id=item.get("source_id",""),
        title=item.get("title",""),
        company=item.get("company",""),
        location=item.get("location",""),
        employment_type=item.get(
            "employment_type",
            ""
        ),
        salary_min=item.get(
            "salary_min"
        ),
        salary_max=item.get(
            "salary_max"
        ),
        description=item.get(
            "description",
            ""
        ),
        apply_url=item.get(
            "apply_url",
            ""
        ),
        published_at=item.get(
            "published_at",
            ""
        )
    )

    job=finalize_job(job)

    return job


def poll_for_job(
    iterators,
    target_job_id,
    timeout_seconds=30
):

    print(
        "\nPolling all shards..."
    )

    deadline=time.time()+timeout_seconds

    current_iterators=dict(
        iterators
    )

    while time.time()<deadline:

        for shard_id in list(
            current_iterators.keys()
        ):

            if time.time()>=deadline:
                break

            iterator=current_iterators.get(
                shard_id
            )

            if not iterator:
                continue

            try:

                response=client.get_records(
                    ShardIterator=iterator,
                    Limit=1000
                )

                records=response.get(
                    "Records",
                    []
                )

                current_iterators[
                    shard_id
                ]=response.get(
                    "NextShardIterator"
                )

                if records:

                    print(
                        f"{shard_id}: "
                        f"{len(records)} record(s)"
                    )

                for record in records:

                    dynamodb_data=record.get(
                        "dynamodb",
                        {}
                    )

                    keys=dynamodb_data.get(
                        "Keys",
                        {}
                    )

                    key=keys.get(
                        "canonical_job_id",
                        {}
                    ).get(
                        "S"
                    )

                    if key==target_job_id:

                        return record

            except Exception as e:

                print(
                    "⚠️ Error reading:",
                    shard_id
                )

                print(
                    type(e).__name__,
                    e
                )

        time.sleep(1)

    return None


def print_record(record):

    if not record:

        print(
            "\n❌ No matching Stream event found"
        )

        return

    dynamodb_data=record.get(
        "dynamodb",
        {}
    )

    keys=dynamodb_data.get(
        "Keys",
        {}
    )

    print(
        "\n"+"-"*60
    )

    print(
        "MATCHING STREAM EVENT"
    )

    print(
        "-"*60
    )

    print(
        "Event:",
        record.get("eventName")
    )

    print(
        "Event ID:",
        record.get("eventID")
    )

    print(
        "Canonical ID:",
        keys.get(
            "canonical_job_id",
            {}
        ).get("S")
    )

    print(
        "Has Old Image:",
        "OldImage" in dynamodb_data
    )

    print(
        "Has New Image:",
        "NewImage" in dynamodb_data
    )


def main():

    print("="*60)
    print("DETERMINISTIC END-TO-END TEST")
    print("="*60)

    # --------------------------------------------------------
    # STREAM
    # --------------------------------------------------------

    stream_arn=get_stream_arn()

    print(
        "\nStream ARN:"
    )

    print(stream_arn)

    shards=get_all_shards(
        stream_arn
    )

    print(
        "\nTotal shards:",
        len(shards)
    )

    if not shards:

        print(
            "❌ No Stream shards found"
        )

        return

    # --------------------------------------------------------
    # ITERATORS BEFORE CHANGE
    # --------------------------------------------------------

    iterators=create_latest_iterators(
        stream_arn,
        shards
    )

    if not iterators:

        print(
            "❌ Could not create iterators"
        )

        return

    # --------------------------------------------------------
    # GET EXISTING JOB FROM DYNAMODB
    # --------------------------------------------------------

    job=get_existing_job()

    if job is None:

        print(
            "\n❌ Test job not found in DynamoDB"
        )

        return

    print(
        "\nEXISTING JOB FOUND"
    )

    print(
        "Title:",
        job.title
    )

    print(
        "Company:",
        job.company
    )

    print(
        "Canonical ID:",
        job.canonical_job_id
    )

    print(
        "Original hash:",
        job.content_hash
    )

    # --------------------------------------------------------
    # VERIFY CANONICAL ID
    # --------------------------------------------------------

    if job.canonical_job_id!=TEST_JOB_ID:

        print(
            "\n❌ Canonical ID mismatch"
        )

        print(
            "Expected:",
            TEST_JOB_ID
        )

        print(
            "Actual:",
            job.canonical_job_id
        )

        return

    # --------------------------------------------------------
    # SAVE ORIGINAL
    # --------------------------------------------------------

    original_description=job.description

    # --------------------------------------------------------
    # TEMPORARY CHANGE
    # --------------------------------------------------------

    print(
        "\nCreating temporary change..."
    )

    job.description=(
        original_description+
        " [END TO END TEST]"
    )

    job=finalize_job(job)

    print(
        "New hash:",
        job.content_hash
    )

    result=sync_job(job)

    print(
        "\nSYNC RESULT:",
        result["type"]
    )

    print(
        "Changed fields:",
        result["changed_fields"]
    )

    if result["type"]!="CHANGED":

        print(
            "\n❌ Expected CHANGED"
        )

        # Restore immediately if something
        # unexpected happened.
        job.description=original_description
        job=finalize_job(job)

        restore_result=sync_job(job)

        print(
            "RESTORE RESULT:",
            restore_result["type"]
        )

        return

    # --------------------------------------------------------
    # STREAM
    # --------------------------------------------------------

    record=poll_for_job(
        iterators,
        TEST_JOB_ID,
        timeout_seconds=30
    )

    print_record(
        record
    )

    # --------------------------------------------------------
    # RESTORE
    # --------------------------------------------------------

    print(
        "\nRestoring original job..."
    )

    job.description=original_description

    job=finalize_job(job)

    restore_result=sync_job(job)

    print(
        "RESTORE RESULT:",
        restore_result["type"]
    )

    print(
        "Restored hash:",
        job.content_hash
    )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    print(
        "\n"+"="*60
    )

    if record:

        print(
            "✅ DYNAMODB STREAM TEST PASSED"
        )

    else:

        print(
            "❌ DYNAMODB STREAM TEST FAILED"
        )

    print(
        "="*60
    )


if __name__=="__main__":
    main()