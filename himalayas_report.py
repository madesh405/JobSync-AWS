import boto3
from collections import Counter


REGION="us-east-1"
TABLE_NAME="JobSync-Jobs"


dynamodb=boto3.resource(
    "dynamodb",
    region_name=REGION
)

table=dynamodb.Table(TABLE_NAME)


items=[]

response=table.scan()

items.extend(
    response.get("Items",[])
)

last_key=response.get("LastEvaluatedKey")

while last_key:
    response=table.scan(
        ExclusiveStartKey=last_key
    )

    items.extend(
        response.get("Items",[])
    )

    last_key=response.get("LastEvaluatedKey")


himalayas=[
    item
    for item in items
    if item.get("source")=="himalayas"
]


status_counts=Counter(
    item.get("status","UNKNOWN")
    for item in himalayas
)


source_id_counts=Counter(
    item.get("source_id")
    for item in himalayas
)


print("="*60)
print("HIMALAYAS JOB REPORT")
print("="*60)

print(
    f"Total Himalayas records: {len(himalayas)}"
)

print()

print("STATUS:")

for status,count in sorted(
    status_counts.items()
):
    print(
        f"{status}: {count}"
    )

print()

print("UNIQUE SOURCE IDs:")
print(
    len(source_id_counts)
)

print()

print("RECORDS:")

for item in sorted(
    himalayas,
    key=lambda x:str(x.get("first_seen",""))
):
    print(
        f"{item.get('first_seen')} | "
        f"{item.get('canonical_job_id')} | "
        f"{item.get('source_id')} | "
        f"{item.get('company')} | "
        f"{item.get('title')} | "
        f"{item.get('status')}"
    )