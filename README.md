# JobSync-AWS

## Cache-Aware Event-Driven Job Synchronization and Job Discovery Using AWS

JobSync-AWS is a cloud-native job synchronization system that collects jobs from multiple sources, normalizes and deduplicates them, detects meaningful changes using content hashing, and processes only the data that has changed.

> **Core idea: Don't process what hasn't changed.**

## 🚀 Live

**Frontend:**  
https://madesh405.github.io/JobSync-AWS/

**API:**  
https://cviwg4d4h2.execute-api.us-east-1.amazonaws.com/jobs

**GitHub:**  
https://github.com/madesh405/JobSync-AWS

## 🏗️ Architecture

~~~text
EventBridge Scheduler
        ↓
Crawl Controller Lambda
        ↓
SQS
        ↓
Crawl Worker Lambda
        ↓
Himalayas / Jobicy / Remote OK
        ↓
Normalize + Hash + Deduplicate
        ↓
DynamoDB
        ↓
DynamoDB Streams
        ↓
EventBridge Pipe
        ↓
EventBridge Bus
        ↓
Business Event Processing
~~~

### Frontend

~~~text
GitHub Pages
     ↓
React
     ↓
API Gateway
     ↓
Lambda
     ↓
DynamoDB
~~~

## ☁️ AWS Services

| Service | Purpose |
|---|---|
| AWS Lambda | Serverless processing |
| Amazon DynamoDB | Job and source state |
| Amazon SQS | Decoupled job crawling |
| EventBridge Scheduler | Scheduled synchronization |
| EventBridge Pipes | Stream event routing |
| Amazon EventBridge | Business event processing |
| API Gateway | Backend API |
| Amazon Cognito | Authentication |
| Amazon S3 | Resume and history storage |
| CloudWatch | Monitoring |

## 🔄 Key Features

### Cache-Aware Synchronization

Sources are checked only when they are due.

~~~text
Source State
     ↓
Is source due?
   ┌─┴─┐
  NO  YES
  ↓    ↓
STOP  Fetch
~~~

### Change Detection

Each normalized job receives a content hash.

~~~text
Same hash
   ↓
UNCHANGED
   ↓
No unnecessary database write
~~~

~~~text
Different hash
      ↓
CHANGED
      ↓
Process update
~~~

### Deduplication

Jobs from different sources are converted into a canonical job ID using normalized company, title and location.

~~~text
Himalayas ─┐
Jobicy ────┼──→ One Canonical Job
Remote OK ─┘
~~~

### Event-Driven Processing

Meaningful database changes flow through:

~~~text
DynamoDB
    ↓
DynamoDB Stream
    ↓
EventBridge Pipe
    ↓
EventBridge
    ↓
Business Event Processing
~~~

## 🔌 API

~~~http
GET /jobs
GET /jobs/{canonical_job_id}
GET /jobs?source=jobicy
GET /jobs?status=OPEN
~~~

## 🖥️ Technology

### Frontend

- React
- Vite
- JavaScript
- CSS
- GitHub Pages

### Backend

- Python
- AWS Lambda
- Amazon DynamoDB
- Amazon API Gateway
- Amazon SQS
- Amazon EventBridge
- Amazon Cognito
- Amazon S3

## 📊 Synchronization Logic

~~~text
Fetch Source
     ↓
Normalize Data
     ↓
Generate Canonical ID
     ↓
Calculate Content Hash
     ↓
Compare With Stored Job
     ↓
 ┌───────┼────────┐
 ↓       ↓        ↓
NEW   CHANGED   UNCHANGED
 ↓       ↓        ↓
Store   Update   Stop
 ↓       ↓
DynamoDB
     ↓
DynamoDB Stream
     ↓
EventBridge
~~~

## 🎯 Objective

The project demonstrates how AWS can be used for asynchronous, event-driven and cache-aware synchronization instead of relying on a continuously running server.

The main principle is:

> **Don't process what hasn't changed.**

## 👨‍💻 Repository

https://github.com/madesh405/JobSync-AWS


## 🔌 Custom API Sources

The custom-source extension allows an administrator to register a public HTTPS JSON API without adding another hard-coded fetcher.

Configuration includes:

- Source name and HTTPS endpoint
- JSON path to the jobs array, such as `data.jobs`
- Field mappings for title, company, external ID, location, employment type, description, apply URL, salary, and publication date
- Single-response or page-number pagination (up to 10 pages per run)
- Crawl interval from 15 minutes to 24 hours
- Source enable/disable controls

New custom sources use the existing controller → SQS → crawl worker → DynamoDB pipeline. The worker normalizes the mapped jobs and uses the existing canonical-ID and content-hash logic.

### Security boundaries

- Admin endpoints require a Cognito JWT authorizer and membership in the `JobSyncAdmins` Cognito group.
- The connector requires HTTPS, blocks redirects, limits response size and pagination, and rejects private or reserved endpoint addresses.
- This initial connector supports unauthenticated APIs only. Do not put credentials in endpoint URLs; credentialed APIs will require a follow-up Secrets Manager integration.
- Adding a source saves its configuration; the first actual synchronization occurs through the existing scheduler/controller flow.

### Custom-source API

~~~http
GET   /admin/sources
POST  /admin/sources/test
POST  /admin/sources
PATCH /admin/sources/{source_id}
~~~

All of these routes are administrator-only. The public job routes remain separate.

## 📈 Operations and Recovery

- CloudWatch dashboard: `JobSync-Operations`
- Custom metric namespace: `JobSync/Operations`
- Metrics include fetched/new/changed jobs, cache hits/misses, redundant writes prevented, crawl duration, successes, and failures.
- `JobSync-CrawlDLQ` receives repeatedly failing SQS crawl messages after three unsuccessful receives.
- `JobSync-DLQ-HasMessages` monitors messages waiting in the dead-letter queue.
