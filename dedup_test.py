from job_pipeline import Job,finalize_job,normalize_title,normalize_location


def check(condition,message):
    if condition:
        print("✅",message)
    else:
        print("❌",message)
        raise AssertionError(message)


print("\n" + "="*60)
print("TEST 1 — SAME JOB FROM DIFFERENT SOURCES")
print("="*60)

job1=Job(
    source="himalayas",
    source_id="h-001",
    title="Software Engineer - Backend",
    company="Acme",
    location="Bengaluru",
    employment_type="Full Time",
    salary_min=800000,
    salary_max=1200000,
    description="Build backend services using Python and AWS.",
    apply_url="https://himalayas.example/job1",
    published_at="2026-10-01"
)

job2=Job(
    source="jobicy",
    source_id="j-999",
    title="Backend Software Engineer",
    company="ACME",
    location="Bangalore",
    employment_type="Full-Time",
    salary_min=800000,
    salary_max=1200000,
    description="Build backend services using Python and AWS.",
    apply_url="https://jobicy.example/job999",
    published_at="2026-10-01"
)

job1=finalize_job(job1)
job2=finalize_job(job2)

print("Job 1 canonical ID:",job1.canonical_job_id)
print("Job 2 canonical ID:",job2.canonical_job_id)

check(
    job1.canonical_job_id==job2.canonical_job_id,
    "Different source records identified as the SAME job"
)


print("\n" + "="*60)
print("TEST 2 — SAME JOB SHOULD HAVE SAME CONTENT HASH")
print("="*60)

check(
    job1.content_hash==job2.content_hash,
    "Equivalent content produces the same content hash"
)


print("\n" + "="*60)
print("TEST 3 — SALARY CHANGE")
print("="*60)

job3=Job(
    source="jobicy",
    source_id="j-999",
    title="Backend Software Engineer",
    company="ACME",
    location="Bangalore",
    employment_type="Full-Time",
    salary_min=1000000,
    salary_max=1400000,
    description="Build backend services using Python and AWS.",
    apply_url="https://jobicy.example/job999",
    published_at="2026-10-02"
)

job3=finalize_job(job3)

print("Old hash:",job2.content_hash)
print("New hash:",job3.content_hash)

check(
    job2.canonical_job_id==job3.canonical_job_id,
    "Salary change did NOT create a new job"
)

check(
    job2.content_hash!=job3.content_hash,
    "Salary change detected by content hash"
)


print("\n" + "="*60)
print("TEST 4 — DESCRIPTION CHANGE")
print("="*60)

job4=Job(
    source="jobicy",
    source_id="j-999",
    title="Backend Software Engineer",
    company="ACME",
    location="Bangalore",
    employment_type="Full-Time",
    salary_min=800000,
    salary_max=1200000,
    description="Build backend services using Python, AWS and Docker.",
    apply_url="https://jobicy.example/job999",
    published_at="2026-10-02"
)

job4=finalize_job(job4)

check(
    job2.canonical_job_id==job4.canonical_job_id,
    "Description change did NOT create a new job"
)

check(
    job2.content_hash!=job4.content_hash,
    "Description change detected by content hash"
)


print("\n" + "="*60)
print("TEST 5 — COMPLETELY DIFFERENT JOB")
print("="*60)

job5=Job(
    source="remoteok",
    source_id="r-555",
    title="Data Scientist",
    company="Acme",
    location="Bangalore",
    employment_type="Full Time",
    salary_min=900000,
    salary_max=1500000,
    description="Build machine learning models.",
    apply_url="https://remoteok.example/job555",
    published_at="2026-10-02"
)

job5=finalize_job(job5)

print("Backend job ID:",job1.canonical_job_id)
print("Data Scientist ID:",job5.canonical_job_id)

check(
    job1.canonical_job_id!=job5.canonical_job_id,
    "Different jobs receive different canonical IDs"
)


print("\n" + "="*60)
print("TEST 6 — NORMALIZATION")
print("="*60)

print(
    "Title A:",
    normalize_title("Software Engineer - Backend")
)

print(
    "Title B:",
    normalize_title("Backend Software Engineer")
)

print(
    "Location A:",
    normalize_location("Bengaluru")
)

print(
    "Location B:",
    normalize_location("Bangalore")
)

check(
    normalize_title("Software Engineer - Backend")
    ==
    normalize_title("Backend Software Engineer"),
    "Title normalization works"
)

check(
    normalize_location("Bengaluru")
    ==
    normalize_location("Bangalore"),
    "Location normalization works"
)


print("\n" + "="*60)
print("ALL DEDUPLICATION TESTS PASSED")
print("="*60)