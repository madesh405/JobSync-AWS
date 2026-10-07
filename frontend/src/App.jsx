import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_URL =
  "https://cviwg4d4h2.execute-api.us-east-1.amazonaws.com/jobs";

const METRICS_URL =
  "https://cviwg4d4h2.execute-api.us-east-1.amazonaws.com/admin/metrics";

function formatTime(timestamp) {
  if (!timestamp) return "—";
  return new Date(timestamp).toLocaleString();
}

function formatUnixTime(timestamp) {
  if (!timestamp) return "—";

  const value=Number(timestamp);

  if (!Number.isFinite(value)) {
    return "—";
  }

  return formatTime(
    value < 100000000000
      ? value*1000
      : value
  );
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-IN").format(
    Number(value||0)
  );
}

function MetricCard({
  label,
  value,
  note,
  muted=false
}) {
  return (
    <div
      className={`metric-card${muted ? " muted" : ""}`}
    >
      <span className="metric-label">
        {label}
      </span>

      <strong className="metric-value">
        {value}
      </strong>

      {note && (
        <span className="metric-note">
          {note}
        </span>
      )}
    </div>
  );
}

function App() {
  const initialView =
    new URLSearchParams(window.location.search).get(
      "view"
    ) === "admin"
      ? "admin"
      : "jobs";

  const [view,setView]=useState(initialView);

  const [jobs,setJobs]=useState([]);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");

  const [search,setSearch]=useState("");
  const [source,setSource]=useState("all");
  const [status,setStatus]=useState("all");

  const [fetchCount,setFetchCount]=useState(0);
  const [successfulFetches,setSuccessfulFetches]=useState(0);
  const [failedFetches,setFailedFetches]=useState(0);
  const [lastRefreshAt,setLastRefreshAt]=useState(null);
  const [lastFetchDuration,setLastFetchDuration]=useState(null);

  const [adminMetrics,setAdminMetrics]=useState(null);
  const [metricsLoading,setMetricsLoading]=useState(false);
  const [metricsError,setMetricsError]=useState("");
  const [metricsRefreshAt,setMetricsRefreshAt]=useState(null);

  useEffect(() => {
    fetchJobs();
  }, []);

  useEffect(() => {
    if (view==="admin") {
      fetchAdminMetrics();
    }
  }, [view]);

  function changeView(nextView) {
    setView(nextView);

    const params=
      new URLSearchParams(
        window.location.search
      );

    if (nextView==="admin") {
      params.set("view","admin");
    } else {
      params.delete("view");
    }

    const query=params.toString();

    window.history.replaceState(
      {},
      "",
      `${window.location.pathname}${
        query
          ? `?${query}`
          : ""
      }`
    );
  }

  async function fetchJobs() {
    const startedAt=performance.now();

    try {
      setLoading(true);
      setError("");

      setFetchCount(
        value=>value+1
      );

      const response=await fetch(
        `${API_URL}?limit=100`
      );

      if (!response.ok) {
        throw new Error(
          `API request failed: ${response.status}`
        );
      }

      const data=await response.json();

      setJobs(
        data.jobs||[]
      );

      setSuccessfulFetches(
        value=>value+1
      );

      setLastRefreshAt(
        Date.now()
      );

      setLastFetchDuration(
        Math.round(
          performance.now()-startedAt
        )
      );
    } catch (err) {
      console.error(err);

      setError(
        "Unable to load jobs from AWS API."
      );

      setFailedFetches(
        value=>value+1
      );

      setLastRefreshAt(
        Date.now()
      );

      setLastFetchDuration(
        Math.round(
          performance.now()-startedAt
        )
      );
    } finally {
      setLoading(false);
    }
  }

  async function fetchAdminMetrics() {
    try {
      setMetricsLoading(true);
      setMetricsError("");

      const response=await fetch(
        METRICS_URL
      );

      if (!response.ok) {
        throw new Error(
          `Metrics request failed: ${response.status}`
        );
      }

      const data=await response.json();

      setAdminMetrics(
        data
      );

      setMetricsRefreshAt(
        Date.now()
      );
    } catch (err) {
      console.error(err);

      setMetricsError(
        "Unable to load synchronization metrics from AWS."
      );
    } finally {
      setMetricsLoading(false);
    }
  }

  async function handleRefresh() {
    await Promise.all([
      fetchJobs(),
      fetchAdminMetrics()
    ]);
  }

  const filteredJobs=useMemo(() => {
    return jobs.filter((job) => {
      const text=[
        job.title,
        job.company,
        job.location,
        job.description,
        job.employment_type
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      const matchesSearch=
        text.includes(
          search.toLowerCase()
        );

      const matchesSource=
        source==="all" ||
        job.source===source;

      const matchesStatus=
        status==="all" ||
        job.status===status;

      return (
        matchesSearch &&
        matchesSource &&
        matchesStatus
      );
    });
  },[
    jobs,
    search,
    source,
    status
  ]);

  const sources=[
    ...new Set(
      jobs
        .map(job=>job.source)
        .filter(Boolean)
    )
  ];

  const openJobs=
    jobs.filter(
      job=>job.status==="OPEN"
    ).length;

  const recentlyChangedJobs=
    jobs.filter((job) => {
      if (!job.last_changed) {
        return false;
      }

      const changedAt=
        Number(
          job.last_changed
        );

      if (
        !Number.isFinite(changedAt)
      ) {
        return false;
      }

      const milliseconds=
        changedAt<100000000000
          ? changedAt*1000
          : changedAt;

      return (
        Date.now()-milliseconds <=
        24*60*60*1000
      );
    }).length;

  const sourceCounts=
    sources
      .map(item=>({
        name:item,
        count:
          jobs.filter(
            job=>job.source===item
          ).length
      }))
      .sort(
        (a,b)=>b.count-a.count
      );

  const metrics=
    adminMetrics?.metrics || {};

  const metricSources=
    adminMetrics?.sources || [];

  const totalProcessed=
    Number(
      metrics.cache_hits||0
    )+
    Number(
      metrics.cache_misses||0
    );

  const cacheHitRate=
    totalProcessed>0
      ? (
          Number(
            metrics.cache_hits||0
          )/
          totalProcessed
        )*100
      : 0;

  const syncStages=[
    {
      number:"01",
      name:"Scheduled check",
      description:
        "EventBridge Scheduler triggers the controller."
    },
    {
      number:"02",
      name:"Source gating",
      description:
        "The controller checks whether each source is due."
    },
    {
      number:"03",
      name:"Queued crawl",
      description:
        "Due sources are placed onto SQS."
    },
    {
      number:"04",
      name:"Change detection",
      description:
        "Jobs are normalized, hashed and compared with DynamoDB."
    },
    {
      number:"05",
      name:"Event processing",
      description:
        "Meaningful changes continue through Streams and EventBridge."
    }
  ];

  const renderJobsPage=() => (
    <>
      <section className="hero">
        <div>
          <p className="section-kicker">
            JOB DISCOVERY
          </p>

          <h2>
            Find your next opportunity
          </h2>

          <p>
            Jobs synchronized from multiple
            sources through the AWS serverless
            backend.
          </p>
        </div>

        <div className="stats">
          <div className="stat">
            <strong>
              {formatNumber(jobs.length)}
            </strong>

            <span>
              Loaded jobs
            </span>
          </div>

          <div className="stat">
            <strong>
              {formatNumber(sources.length)}
            </strong>

            <span>
              Sources
            </span>
          </div>

          <div className="stat">
            <strong>
              {formatNumber(
                filteredJobs.length
              )}
            </strong>

            <span>
              Matching
            </span>
          </div>
        </div>
      </section>

      <section className="filters">
        <input
          type="text"
          placeholder="Search title, company, location, skills..."
          value={search}
          onChange={
            event=>
              setSearch(
                event.target.value
              )
          }
        />

        <select
          value={source}
          onChange={
            event=>
              setSource(
                event.target.value
              )
          }
        >
          <option value="all">
            All sources
          </option>

          {sources.map(item=>(
            <option
              key={item}
              value={item}
            >
              {item}
            </option>
          ))}
        </select>

        <select
          value={status}
          onChange={
            event=>
              setStatus(
                event.target.value
              )
          }
        >
          <option value="all">
            All status
          </option>

          <option value="OPEN">
            Open
          </option>

          <option value="MISSING_ONCE">
            Missing once
          </option>

          <option value="CLOSED">
            Closed
          </option>
        </select>
      </section>

      {loading && (
        <div className="message">
          <span className="spinner" />
          Loading jobs from AWS...
        </div>
      )}

      {error && (
        <div className="message error">
          <strong>
            API error
          </strong>

          <span>
            {error}
          </span>
        </div>
      )}

      {!loading &&
        !error &&
        filteredJobs.length===0 && (
          <div className="message">
            No jobs match your current filters.
          </div>
        )}

      <section className="jobs">
        {filteredJobs.map(job=>(
          <article
            className="job-card"
            key={job.canonical_job_id}
          >
            <div className="job-top">
              <div>
                <p className="source">
                  {job.source}
                </p>

                <h3>
                  {job.title}
                </h3>

                <p className="company">
                  {job.company}
                </p>
              </div>

              <span
                className={`status ${
                  String(
                    job.status
                  ).toLowerCase()
                }`}
              >
                {job.status||"OPEN"}
              </span>
            </div>

            <div className="details">
              <span>
                {job.location||
                  "Location not specified"}
              </span>

              <span>
                {job.employment_type||
                  "Employment type not specified"}
              </span>
            </div>

            {job.description && (
              <p className="description">
                {job.description.length>260
                  ? `${job.description.slice(
                      0,
                      260
                    )}...`
                  : job.description}
              </p>
            )}

            <div className="card-footer">
              <small>
                ID: {job.canonical_job_id}
              </small>

              {job.apply_url && (
                <a
                  href={job.apply_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  View Job
                </a>
              )}
            </div>
          </article>
        ))}
      </section>
    </>
  );

  const renderAdminPage=() => (
    <>
      <section className="admin-heading">
        <div>
          <p className="section-kicker">
            SYSTEM ADMINISTRATION
          </p>

          <h2>
            JobSync Operations
          </h2>

          <p>
            Live operational metrics from the
            cache-aware, event-driven AWS
            synchronization pipeline.
          </p>
        </div>

        <div className="admin-status">
          <span className="status-dot" />

          {metricsLoading
            ? "Refreshing metrics..."
            : "LIVE AWS METRICS"}
        </div>
      </section>

      {metricsError && (
        <div className="message error">
          <strong>
            Metrics error
          </strong>

          <span>
            {metricsError}
          </span>
        </div>
      )}

      <section className="metric-grid">
        <MetricCard
          label="Cache hits / UNCHANGED"
          value={
            metrics.cache_hits !== undefined
              ? formatNumber(
                  metrics.cache_hits
                )
              : "—"
          }
          note="Jobs detected as unchanged"
        />

        <MetricCard
          label="Cache misses"
          value={
            metrics.cache_misses !== undefined
              ? formatNumber(
                  metrics.cache_misses
                )
              : "—"
          }
          note="NEW + CHANGED jobs"
        />

        <MetricCard
          label="Redundant processing prevented"
          value={
            metrics.redundant_updates_prevented !==
            undefined
              ? formatNumber(
                  metrics.redundant_updates_prevented
                )
              : "—"
          }
          note="Unchanged jobs avoided unnecessary updates"
        />

        <MetricCard
          label="Controller skips"
          value={
            metrics.controller_skips !== undefined
              ? formatNumber(
                  metrics.controller_skips
                )
              : "—"
          }
          note="Sources not due for crawling"
        />

        <MetricCard
          label="Successful crawls"
          value={
            metrics.successful_crawls !== undefined
              ? formatNumber(
                  metrics.successful_crawls
                )
              : "—"
          }
          note="Completed source crawls"
        />

        <MetricCard
          label="Crawl failures"
          value={
            metrics.failed_crawls !== undefined
              ? formatNumber(
                  metrics.failed_crawls
                )
              : "—"
          }
          note="Recorded failed crawl attempts"
        />

        <MetricCard
          label="Jobs processed"
          value={
            metrics.jobs_processed !== undefined
              ? formatNumber(
                  metrics.jobs_processed
                )
              : "—"
          }
          note="Total synchronization comparisons"
        />

        <MetricCard
          label="Cache hit rate"
          value={
            totalProcessed>0
              ? `${cacheHitRate.toFixed(1)}%`
              : "—"
          }
          note="UNCHANGED / processed jobs"
        />

        <MetricCard
          label="Last metrics refresh"
          value={
            metricsRefreshAt
              ? formatTime(
                  metricsRefreshAt
                )
              : "—"
          }
          note="Live data from JobSync-Sources"
        />
      </section>

      <section className="admin-grid">
        <div className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">
                SYNCHRONIZATION OUTCOMES
              </p>

              <h3>
                Change detection
              </h3>
            </div>

            <span className="telemetry-badge">
              REAL DATA
            </span>
          </div>

          <div className="telemetry-grid">
            <MetricCard
              label="NEW"
              value={
                metrics.new !== undefined
                  ? formatNumber(
                      metrics.new
                    )
                  : "—"
              }
              note="New jobs discovered"
            />

            <MetricCard
              label="UNCHANGED"
              value={
                metrics.unchanged !== undefined
                  ? formatNumber(
                      metrics.unchanged
                    )
                  : "—"
              }
              note="No processing change needed"
            />

            <MetricCard
              label="CHANGED"
              value={
                metrics.changed !== undefined
                  ? formatNumber(
                      metrics.changed
                    )
                  : "—"
              }
              note="Existing jobs with changes"
            />

            <MetricCard
              label="Cache misses"
              value={
                metrics.cache_misses !== undefined
                  ? formatNumber(
                      metrics.cache_misses
                    )
                  : "—"
              }
              note="NEW + CHANGED"
            />
          </div>

          <div className="notice">
            <strong>
              Current cache behavior
            </strong>

            <p>
              The system compares fetched jobs
              against the existing DynamoDB state.
              An UNCHANGED result is treated as a
              cache hit and avoids unnecessary
              downstream processing.
            </p>
          </div>
        </div>

        <div className="panel">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">
                SOURCE HEALTH
              </p>

              <h3>
                Current source state
              </h3>
            </div>
          </div>

          <div className="source-list">
            {metricSources.length===0 && (
              <div className="empty-source">
                No source metrics available.
              </div>
            )}

            {metricSources.map(item=>(
              <div
                className="source-row"
                key={item.source_id}
              >
                <div className="source-row-top">
                  <span>
                    {item.source_name}
                  </span>

                  <strong>
                    {item.status}
                  </strong>
                </div>

                <div
                  className="source-row-top"
                  style={{
                    marginTop:"8px",
                    fontSize:"12px"
                  }}
                >
                  <span>
                    Hits:{" "}
                    {formatNumber(
                      item.cache_hits
                    )}
                  </span>

                  <span>
                    Misses:{" "}
                    {formatNumber(
                      item.cache_misses
                    )}
                  </span>

                  <span>
                    Skips:{" "}
                    {formatNumber(
                      item.controller_skips
                    )}
                  </span>
                </div>

                <div
                  className="source-row-top"
                  style={{
                    marginTop:"5px",
                    fontSize:"12px"
                  }}
                >
                  <span>
                    Crawls:{" "}
                    {formatNumber(
                      item.successful_crawls
                    )}
                  </span>

                  <span>
                    Failures:{" "}
                    {formatNumber(
                      item.failed_crawls
                    )}
                  </span>

                  <span>
                    Jobs:{" "}
                    {formatNumber(
                      item.jobs_processed
                    )}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="panel pipeline-panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">
              AWS PIPELINE
            </p>

            <h3>
              Synchronization flow
            </h3>
          </div>

          <span className="pipeline-label">
            SERVERLESS
          </span>
        </div>

        <div className="pipeline">
          {syncStages.map(stage=>(
            <div
              className="pipeline-step"
              key={stage.number}
            >
              <span className="step-number">
                {stage.number}
              </span>

              <div>
                <strong>
                  {stage.name}
                </strong>

                <p>
                  {stage.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">
              JOB DATASET
            </p>

            <h3>
              Current jobs by source
            </h3>
          </div>
        </div>

        <div className="source-list">
          {sourceCounts.length===0 && (
            <div className="empty-source">
              No job data available.
            </div>
          )}

          {sourceCounts.map(item=>{
            const width=
              jobs.length>0
                ? `${(
                    item.count/
                    jobs.length
                  )*100}%`
                : "0%";

            return (
              <div
                className="source-row"
                key={item.name}
              >
                <div className="source-row-top">
                  <span>
                    {item.name}
                  </span>

                  <strong>
                    {formatNumber(
                      item.count
                    )}
                  </strong>
                </div>

                <div className="bar">
                  <span
                    style={{
                      width
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">
              API SESSION
            </p>

            <h3>
              Frontend activity
            </h3>
          </div>
        </div>

        <div className="metric-grid">
          <MetricCard
            label="API fetches this session"
            value={formatNumber(
              fetchCount
            )}
            note={`${formatNumber(
              successfulFetches
            )} successful · ${formatNumber(
              failedFetches
            )} failed`}
          />

          <MetricCard
            label="Jobs currently loaded"
            value={formatNumber(
              jobs.length
            )}
            note="Current frontend dataset"
          />

          <MetricCard
            label="Open jobs"
            value={formatNumber(
              openJobs
            )}
            note="Current returned dataset"
          />

          <MetricCard
            label="Updated in last 24h"
            value={formatNumber(
              recentlyChangedJobs
            )}
            note="Based on last_changed"
          />

          <MetricCard
            label="Last job API refresh"
            value={
              lastRefreshAt
                ? formatTime(
                    lastRefreshAt
                  )
                : "—"
            }
            note={
              lastFetchDuration!==null
                ? `${lastFetchDuration} ms response time`
                : "Waiting for refresh"
            }
          />

          <MetricCard
            label="Last metrics refresh"
            value={
              metricsRefreshAt
                ? formatTime(
                    metricsRefreshAt
                  )
                : "—"
            }
            note="Admin metrics endpoint"
          />
        </div>
      </section>
    </>
  );

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <p className="eyebrow">
            AWS CLOUD PROJECT
          </p>

          <h1>
            JobSync
          </h1>

          <p className="subtitle">
            Cache-aware event-driven job synchronization and discovery
          </p>
        </div>

        <nav
          className="nav"
          aria-label="Primary"
        >
          <button
            className={
              view==="jobs"
                ? "nav-button active"
                : "nav-button"
            }
            onClick={
              ()=>changeView("jobs")
            }
          >
            Jobs
          </button>

          <button
            className={
              view==="admin"
                ? "nav-button active"
                : "nav-button"
            }
            onClick={
              ()=>changeView("admin")
            }
          >
            Admin
          </button>

          <button
            className="refresh-button"
            onClick={handleRefresh}
            disabled={
              loading||
              metricsLoading
            }
          >
            {loading||
            metricsLoading
              ? "Refreshing..."
              : "Refresh"}
          </button>
        </nav>
      </header>

      <main className="container">
        {view==="admin"
          ? renderAdminPage()
          : renderJobsPage()}
      </main>
    </div>
  );
}

export default App;