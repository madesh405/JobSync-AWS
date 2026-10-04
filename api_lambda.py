import json
import boto3
from decimal import Decimal


REGION="us-east-1"
TABLE_NAME="JobSync-Jobs"


dynamodb=boto3.resource(
    "dynamodb",
    region_name=REGION
)

table=dynamodb.Table(TABLE_NAME)


def decimal_default(value):
    if isinstance(value,Decimal):
        if value % 1 == 0:
            return int(value)

        return float(value)

    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )


def response(status_code,body):
    return {
        "statusCode":status_code,
        "headers":{
            "Content-Type":"application/json",
            "Access-Control-Allow-Origin":"*",
            "Access-Control-Allow-Headers":"Content-Type",
            "Access-Control-Allow-Methods":"GET,OPTIONS"
        },
        "body":json.dumps(
            body,
            default=decimal_default
        )
    }


def get_job(job_id):
    result=table.get_item(
        Key={
            "canonical_job_id":job_id
        },
        ConsistentRead=True
    )

    item=result.get("Item")

    if item is None:
        return response(
            404,
            {
                "error":"Job not found",
                "canonical_job_id":job_id
            }
        )

    return response(
        200,
        {
            "job":item
        }
    )


def get_jobs(event):
    query=event.get("queryStringParameters") or {}

    try:
        limit=int(
            query.get("limit","20")
        )
    except ValueError:
        limit=20

    limit=max(
        1,
        min(limit,100)
    )

    source=query.get("source")
    status=query.get("status")

    response_data=table.scan(
        Limit=limit
    )

    items=response_data.get("Items",[])

    if source:
        items=[
            item
            for item in items
            if item.get("source")==source
        ]

    if status:
        items=[
            item
            for item in items
            if item.get("status")==status
        ]

    jobs=[]

    for item in items:
        jobs.append(
            {
                "canonical_job_id":item.get("canonical_job_id"),
                "source":item.get("source"),
                "source_id":item.get("source_id"),
                "title":item.get("title"),
                "company":item.get("company"),
                "location":item.get("location"),
                "employment_type":item.get("employment_type"),
                "salary_min":item.get("salary_min"),
                "salary_max":item.get("salary_max"),
                "description":item.get("description"),
                "apply_url":item.get("apply_url"),
                "published_at":item.get("published_at"),
                "first_seen":item.get("first_seen"),
                "last_changed":item.get("last_changed"),
                "status":item.get("status")
            }
        )

    return response(
        200,
        {
            "count":len(jobs),
            "jobs":jobs
        }
    )


def lambda_handler(event,context):
    method=event.get("requestContext",{}).get(
        "http",
        {}
    ).get(
        "method"
    )

    if method=="OPTIONS":
        return response(
            200,
            {
                "message":"CORS preflight"
            }
        )

    path_parameters=event.get(
        "pathParameters"
    ) or {}

    job_id=path_parameters.get(
        "canonical_job_id"
    )

    if job_id:
        return get_job(job_id)

    return get_jobs(event)