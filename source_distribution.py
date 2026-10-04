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


source_counts=Counter(
    item.get("source","UNKNOWN")
    for item in items
)


print("="*60)
print("JOB SOURCE DISTRIBUTION")
print("="*60)

print(f"TOTAL JOBS: {len(items)}")
print()

for source,count in sorted(source_counts.items()):
    print(f"{source}: {count}")