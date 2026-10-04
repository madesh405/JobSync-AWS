import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_URL = "https://cviwg4d4h2.execute-api.us-east-1.amazonaws.com/jobs";

function App() {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [source, setSource] = useState("all");
  const [status, setStatus] = useState("all");

  useEffect(() => {
    fetchJobs();
  }, []);

  async function fetchJobs() {
    try {
      setLoading(true);
      setError("");

      const response = await fetch(`${API_URL}?limit=100`);

      if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`);
      }

      const data = await response.json();
      setJobs(data.jobs || []);
    } catch (err) {
      console.error(err);
      setError("Unable to load jobs from AWS API.");
    } finally {
      setLoading(false);
    }
  }

  const filteredJobs = useMemo(() => {
    return jobs.filter((job) => {
      const text = [
        job.title,
        job.company,
        job.location,
        job.description,
        job.employment_type
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      const matchesSearch = text.includes(search.toLowerCase());
      const matchesSource = source === "all" || job.source === source;
      const matchesStatus = status === "all" || job.status === status;

      return matchesSearch && matchesSource && matchesStatus;
    });
  }, [jobs, search, source, status]);

  const sources = [...new Set(jobs.map((job) => job.source).filter(Boolean))];

  return (
    <div className="app">
      <header className="header">
        <div>
          <p className="eyebrow">AWS CLOUD PROJECT</p>
          <h1>JobSync</h1>
          <p className="subtitle">
            Cache-aware event-driven job synchronization and discovery
          </p>
        </div>

        <button className="refresh-button" onClick={fetchJobs}>
          Refresh
        </button>
      </header>

      <main className="container">
        <section className="hero">
          <div>
            <h2>Find your next opportunity</h2>
            <p>
              Jobs synchronized from multiple sources through the AWS
              serverless backend.
            </p>
          </div>

          <div className="stats">
            <div className="stat">
              <strong>{jobs.length}</strong>
              <span>Loaded jobs</span>
            </div>

            <div className="stat">
              <strong>{sources.length}</strong>
              <span>Sources</span>
            </div>

            <div className="stat">
              <strong>{filteredJobs.length}</strong>
              <span>Matching</span>
            </div>
          </div>
        </section>

        <section className="filters">
          <input
            type="text"
            placeholder="Search title, company, location, skills..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="all">All sources</option>
            {sources.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>

          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="all">All status</option>
            <option value="OPEN">Open</option>
            <option value="MISSING_ONCE">Missing once</option>
            <option value="CLOSED">Closed</option>
          </select>
        </section>

        {loading && (
          <div className="message">
            Loading jobs from AWS...
          </div>
        )}

        {error && (
          <div className="message error">
            {error}
          </div>
        )}

        {!loading && !error && filteredJobs.length === 0 && (
          <div className="message">
            No jobs match your filters.
          </div>
        )}

        <section className="jobs">
          {filteredJobs.map((job) => (
            <article className="job-card" key={job.canonical_job_id}>
              <div className="job-top">
                <div>
                  <p className="source">{job.source}</p>
                  <h3>{job.title}</h3>
                  <p className="company">{job.company}</p>
                </div>

                <span className={`status ${String(job.status).toLowerCase()}`}>
                  {job.status || "OPEN"}
                </span>
              </div>

              <div className="details">
                <span>{job.location || "Location not specified"}</span>
                <span>
                  {job.employment_type || "Employment type not specified"}
                </span>
              </div>

              {job.description && (
                <p className="description">
                  {job.description.length > 260
                    ? `${job.description.slice(0, 260)}...`
                    : job.description}
                </p>
              )}

              <div className="card-footer">
                <small>ID: {job.canonical_job_id}</small>

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
      </main>
    </div>
  );
}

export default App;