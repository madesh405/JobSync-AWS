# Deploying Custom API Sources

This feature is prepared on the `feature/custom-api-sources` branch. It is not live in AWS until the API Lambda, worker Lambda, API Gateway routes, and IAM permissions described below are deployed.

## 1. Get the generated Lambda packages

Open the successful validation workflow for the latest feature commit:

https://github.com/madesh405/JobSync-AWS/actions

Open the run named **Validate Custom API Source Feature** on branch `feature/custom-api-sources`, download the `jobsync-lambda-packages` artifact, and extract it. The extracted artifact contains:

- `JobSyncJobApi.zip`
- `JobSyncCrawlWorker.zip`

The packages are built from repository source in GitHub Actions; do not manually rebuild or modify them before deploying.

## 2. Update the Lambda code packages

From PowerShell, set paths to the extracted ZIP files first:

```powershell
$apiZip = "C:\path\to\extracted\JobSyncJobApi.zip"
$workerZip = "C:\path\to\extracted\JobSyncCrawlWorker.zip"

aws lambda update-function-code --function-name JobSyncJobApi --zip-file "fileb://$apiZip" --region us-east-1 --no-cli-pager
aws lambda update-function-code --function-name JobSyncCrawlWorker --zip-file "fileb://$workerZip" --region us-east-1 --no-cli-pager

aws lambda wait function-updated-v2 --function-name JobSyncJobApi --region us-east-1
aws lambda wait function-updated-v2 --function-name JobSyncCrawlWorker --region us-east-1

aws lambda get-function-configuration --function-name JobSyncJobApi --region us-east-1 --query "{State:State,Update:LastUpdateStatus}" --output json
aws lambda get-function-configuration --function-name JobSyncCrawlWorker --region us-east-1 --query "{State:State,Update:LastUpdateStatus}" --output json
```

**Important:** once the new API Lambda handler is deployed, all `/admin/*` requests require JWT claims for the `JobSyncAdmins` group. Keep the deployment window short and continue with the API Gateway routes immediately below.

## 3. Update API Gateway CORS

```powershell
@'
{
  "AllowOrigins": [
    "https://madesh405.github.io",
    "http://localhost:5173"
  ],
  "AllowMethods": [
    "GET",
    "POST",
    "PATCH",
    "OPTIONS"
  ],
  "AllowHeaders": [
    "authorization",
    "content-type"
  ],
  "MaxAge": 300
}
'@ | Set-Content -Encoding ascii .\api-cors.json

aws apigatewayv2 update-api --api-id cviwg4d4h2 --cors-configuration file://api-cors.json --region us-east-1 --no-cli-pager
```

## 4. Attach the existing JWT authorizer and add routes

The existing JWT authorizer is named `JobSyncCognitoJwtAuthorizer`, ID `sc2jn7`. It uses the existing Cognito user pool and app client. The Lambda handler independently checks `cognito:groups` for `JobSyncAdmins`.

First get the existing jobs integration target:

```powershell
$target = aws apigatewayv2 get-routes --api-id cviwg4d4h2 --region us-east-1 --query "Items[?RouteKey=='GET /jobs'].Target | [0]" --output text
$metricsRouteId = aws apigatewayv2 get-routes --api-id cviwg4d4h2 --region us-east-1 --query "Items[?RouteKey=='GET /admin/metrics'].RouteId | [0]" --output text
```

Protect the existing metrics route:

```powershell
aws apigatewayv2 update-route --api-id cviwg4d4h2 --route-id $metricsRouteId --authorization-type JWT --authorizer-id sc2jn7 --region us-east-1 --no-cli-pager
```

Create the custom-source routes (run this set only once):

```powershell
aws apigatewayv2 create-route --api-id cviwg4d4h2 --route-key "GET /admin/sources" --target $target --authorization-type JWT --authorizer-id sc2jn7 --region us-east-1 --no-cli-pager
aws apigatewayv2 create-route --api-id cviwg4d4h2 --route-key "POST /admin/sources/test" --target $target --authorization-type JWT --authorizer-id sc2jn7 --region us-east-1 --no-cli-pager
aws apigatewayv2 create-route --api-id cviwg4d4h2 --route-key "POST /admin/sources" --target $target --authorization-type JWT --authorizer-id sc2jn7 --region us-east-1 --no-cli-pager
aws apigatewayv2 create-route --api-id cviwg4d4h2 --route-key "PATCH /admin/sources/{source_id}" --target $target --authorization-type JWT --authorizer-id sc2jn7 --region us-east-1 --no-cli-pager
aws apigatewayv2 create-route --api-id cviwg4d4h2 --route-key "POST /admin/sources/{source_id}/sync" --target $target --authorization-type JWT --authorizer-id sc2jn7 --region us-east-1 --no-cli-pager
```

If any route already exists, do not create a duplicate; retrieve its `RouteId` and use `update-route` with the same JWT authorizer.

## 5. Verify API Gateway can invoke the Lambda

Check the Lambda resource policy:

```powershell
aws lambda get-policy --function-name JobSyncJobApi --region us-east-1 --no-cli-pager
```

The policy must allow API Gateway to invoke `JobSyncJobApi` for this API's routes. If invocation fails with a permission error, add or update a narrowly scoped Lambda permission for the API ID `cviwg4d4h2`; don't grant public Lambda invocation.

## 6. IAM permissions for source management and Sync Now

The `JobSyncJobApi` execution role needs these additional operations:

- `dynamodb:Scan`, `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem` on `arn:aws:dynamodb:us-east-1:673396344578:table/JobSync-Sources`
- `sqs:SendMessage` on `arn:aws:sqs:us-east-1:673396344578:JobSync-CrawlQueue`

Use a least-privilege inline policy on the existing API Lambda role. If your CLI identity is denied IAM policy changes, configure the same actions through the AWS Console using an authorized account. Do not create a new role or widen permissions to all resources.

## 7. Final verification

1. Verify all admin routes use `JobSyncCognitoJwtAuthorizer`; the public `GET /jobs` routes remain unauthenticated.
2. Sign out of JobSync and sign back in so Cognito issues an ID token containing the new `JobSyncAdmins` group claim.
3. Open Admin, confirm the existing metrics and registered sources load.
4. Use **Test connection** with a public HTTPS JSON API and verify the mapped preview.
5. Save a custom source, then check that its record appears in `JobSync-Sources`.
6. Use **Sync now** to enqueue one message; monitor `JobSync-CrawlQueue`, Lambda logs, cache metrics, and the dead-letter queue.
7. Merge the pull request only after the AWS backend tests pass.

The custom connector v1 supports unauthenticated public HTTPS JSON APIs and page-number pagination (maximum 10 pages per run). Credentialed APIs and Secrets Manager integration are a separate next step; never put credentials in the endpoint URL.
