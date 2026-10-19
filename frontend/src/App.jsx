import { useEffect, useMemo, useState } from "react";



import "./App.css";







import {



  getCurrentSession,



  loginUser,



  logoutUser



} from "./cognito";







const API_URL="https://cviwg4d4h2.execute-api.us-east-1.amazonaws.com/jobs";



const METRICS_URL="https://cviwg4d4h2.execute-api.us-east-1.amazonaws.com/admin/metrics";
const SOURCES_URL="https://cviwg4d4h2.execute-api.us-east-1.amazonaws.com/admin/sources";
const SOURCE_TEST_URL=SOURCES_URL + "/test";







function formatTime(timestamp) {



  if (!timestamp) return "—";



  return new Date(timestamp).toLocaleString();



}







function formatNumber(value) {



  return new Intl.NumberFormat("en-IN").format(



    Number(value || 0)



  );



}







function formatSalary(job) {



  const min=Number(job.salary_min);



  const max=Number(job.salary_max);







  if (!Number.isFinite(min) && !Number.isFinite(max)) {



    return "Salary not specified";



  }







  if (Number.isFinite(min) && Number.isFinite(max)) {



    return `${min.toLocaleString()} - ${max.toLocaleString()}`;



  }







  if (Number.isFinite(min)) {



    return `${min.toLocaleString()}+`;



  }







  return `Up to ${max.toLocaleString()}`;



}







const EMPLOYMENT_TYPES=[

  { value:"FULL_TIME", label:"Full Time" },

  { value:"PART_TIME", label:"Part Time" },

  { value:"CONTRACT", label:"Contract" },

  { value:"INTERNSHIP", label:"Internship" },

  { value:"TEMPORARY", label:"Temporary" },

  { value:"OTHER", label:"Other" }

];



function normalizeEmploymentType(value) {

  const text=String(value || "")

    .trim()

    .toLowerCase()

    .replace(/-/g," ")

    .replace(/_/g," ")

    .replace(/\s+/g," ");



  if (

    text.includes("full time") ||

    text.includes("fulltime")

  ) {

    return "FULL_TIME";

  }



  if (

    text.includes("part time") ||

    text.includes("parttime")

  ) {

    return "PART_TIME";

  }



  if (

    text.includes("contractor") ||

    text.includes("contract") ||

    text.includes("freelance")

  ) {

    return "CONTRACT";

  }



  if (

    text.includes("internship") ||

    text.includes("intern")

  ) {

    return "INTERNSHIP";

  }



  if (

    text.includes("temporary") ||

    /\btemp\b/.test(text)

  ) {

    return "TEMPORARY";

  }



  return "OTHER";

}



function getEmploymentLabel(value) {

  const normalized=normalizeEmploymentType(value);



  const match=EMPLOYMENT_TYPES.find(

    item=>item.value===normalized

  );



  return match ? match.label : "Other";

}





function getWorkMode(job) {



  const text=[



    job.location,



    job.description,



    job.title



  ]



    .filter(Boolean)



    .join(" ")



    .toLowerCase();







  if (



    text.includes("remote") ||



    text.includes("work from home") ||



    text.includes("work-from-home") ||



    text.includes("fully distributed")



  ) {



    return "Remote";



  }







  if (



    text.includes("hybrid") ||



    text.includes("flexible location") ||



    text.includes("partial remote")



  ) {



    return "Hybrid";



  }







  return "On-site";



}







function MetricCard({ label, value, note, muted=false }) {



  return (



    <div className={`metric-card${muted ? " muted" : ""}`}>



      <span className="metric-label">{label}</span>



      <strong className="metric-value">{value}</strong>







      {note && (



        <span className="metric-note">{note}</span>



      )}



    </div>



  );



}







function App() {



  const requestedAdmin=



    new URLSearchParams(



      window.location.search



    ).get("view")==="admin";







  const [view,setView]=useState("jobs");



  const [authChecked,setAuthChecked]=useState(false);







  const [jobs,setJobs]=useState([]);



  const [loading,setLoading]=useState(true);



  const [error,setError]=useState("");







  const [search,setSearch]=useState("");



  const [source,setSource]=useState("all");



  const [locationFilter,setLocationFilter]=useState("");



  const [workMode,setWorkMode]=useState("all");



  const [employmentType,setEmploymentType]=useState("all");







  const [selectedJob,setSelectedJob]=useState(null);







  const [fetchCount,setFetchCount]=useState(0);



  const [successfulFetches,setSuccessfulFetches]=useState(0);



  const [failedFetches,setFailedFetches]=useState(0);



  const [lastRefreshAt,setLastRefreshAt]=useState(null);



  const [lastFetchDuration,setLastFetchDuration]=useState(null);







  const [adminMetrics,setAdminMetrics]=useState(null);



  const [metricsLoading,setMetricsLoading]=useState(false);



  const [metricsError,setMetricsError]=useState("");



  const [metricsRefreshAt,setMetricsRefreshAt]=useState(null);

  const [customSources,setCustomSources]=useState([]);
  const [sourceManagementLoading,setSourceManagementLoading]=useState(false);
  const [sourceManagementBusy,setSourceManagementBusy]=useState(false);
  const [sourceManagementError,setSourceManagementError]=useState("");
  const [sourceManagementMessage,setSourceManagementMessage]=useState("");
  const [newSourceName,setNewSourceName]=useState("");
  const [newSourceEndpoint,setNewSourceEndpoint]=useState("");
  const [newSourceRecordsPath,setNewSourceRecordsPath]=useState("jobs");
  const [newSourceTitlePath,setNewSourceTitlePath]=useState("title");
  const [newSourceCompanyPath,setNewSourceCompanyPath]=useState("company");
  const [newSourceIdPath,setNewSourceIdPath]=useState("id");
  const [newSourceLocationPath,setNewSourceLocationPath]=useState("location");
  const [newSourceEmploymentTypePath,setNewSourceEmploymentTypePath]=useState("employment_type");
  const [newSourceDescriptionPath,setNewSourceDescriptionPath]=useState("description");
  const [newSourceApplyUrlPath,setNewSourceApplyUrlPath]=useState("apply_url");
  const [newSourceSalaryMinPath,setNewSourceSalaryMinPath]=useState("salary_min");
  const [newSourceSalaryMaxPath,setNewSourceSalaryMaxPath]=useState("salary_max");
  const [newSourcePublishedAtPath,setNewSourcePublishedAtPath]=useState("published_at");
  const [newSourcePaginationType,setNewSourcePaginationType]=useState("NONE");
  const [newSourcePageParameter,setNewSourcePageParameter]=useState("page");
  const [newSourceStartPage,setNewSourceStartPage]=useState("1");
  const [newSourceMaxPages,setNewSourceMaxPages]=useState("3");
  const [newSourceInterval,setNewSourceInterval]=useState("3600");
  const [sourceTestResult,setSourceTestResult]=useState(null);







  const [currentUserEmail,setCurrentUserEmail]=useState("");



  const [showLogin,setShowLogin]=useState(false);



  const [loginEmail,setLoginEmail]=useState("");



  const [loginPassword,setLoginPassword]=useState("");



  const [loginLoading,setLoginLoading]=useState(false);



  const [loginError,setLoginError]=useState("");



  const [loginMessage,setLoginMessage]=useState("");







  useEffect(() => {



    fetchJobs();



    loadCurrentUser();



  },[]);







  useEffect(() => {



    if (!authChecked) {



      return;



    }







    if (



      requestedAdmin &&



      currentUserEmail



    ) {



      setView("admin");



      return;



    }







    setView("jobs");







    if (



      requestedAdmin &&



      !currentUserEmail



    ) {



      setShowLogin(true);



    }



  },[



    authChecked,



    currentUserEmail,



    requestedAdmin



  ]);







  useEffect(() => {



    if (



      view==="admin" &&



      currentUserEmail



    ) {



      fetchAdminMetrics();
      fetchAdminSources();
    }
  },[
    view,
    currentUserEmail
  ]);







  function changeView(nextView) {



    if (



      nextView==="admin" &&



      !currentUserEmail



    ) {



      setLoginError(



        "Login is required to access Admin."



      );







      setLoginMessage("");



      setShowLogin(true);



      return;



    }







    setView(nextView);







    const params=



      new URLSearchParams(



        window.location.search



      );







    if (nextView==="admin") {



      params.set(



        "view",



        "admin"



      );



    } else {



      params.delete("view");



    }







    const query=params.toString();







    window.history.replaceState(



      {},



      "",



      `${window.location.pathname}${



        query ? `?${query}` : ""



      }`



    );



  }







  function loadCurrentUser() {



    const session=getCurrentSession();







    if (!session) {



      setCurrentUserEmail("");



      setAuthChecked(true);



      return;



    }







    setCurrentUserEmail(



      session.email || ""



    );







    setAuthChecked(true);



  }







  async function handleLogin(event) {



    event.preventDefault();







    setLoginLoading(true);



    setLoginError("");



    setLoginMessage("");







    try {



      const user=



        await loginUser(



          loginEmail.trim(),



          loginPassword



        );







      setCurrentUserEmail(



        user.email



      );







      setLoginMessage(



        "Login successful."



      );







      setLoginPassword("");







      const wantsAdmin=



        requestedAdmin ||



        view==="admin";







      setTimeout(() => {



        setShowLogin(false);



        setLoginMessage("");







        if (wantsAdmin) {



          setView("admin");







          const params=



            new URLSearchParams(



              window.location.search



            );







          params.set(



            "view",



            "admin"



          );







          window.history.replaceState(



            {},



            "",



            `${window.location.pathname}?${params.toString()}`



          );



        }



      },500);



    } catch (error) {



      console.error(error);







      setLoginError(



        error?.message ||



        "Login failed."



      );



    } finally {



      setLoginLoading(false);



    }



  }







  function handleLogout() {



    logoutUser();







    setCurrentUserEmail("");



    setLoginEmail("");



    setLoginPassword("");



    setLoginError("");



    setLoginMessage("");



    setShowLogin(false);



    setAdminMetrics(null);



    setView("jobs");







    const params=



      new URLSearchParams(



        window.location.search



      );







    params.delete("view");







    const query=params.toString();







    window.history.replaceState(



      {},



      "",



      `${window.location.pathname}${



        query ? `?${query}` : ""



      }`



    );



  }







  function openLogin() {



    setLoginError("");



    setLoginMessage("");



    setShowLogin(true);



  }







  function closeLogin() {



    if (loginLoading) {



      return;



    }







    setShowLogin(false);



    setLoginError("");



    setLoginMessage("");



    setLoginPassword("");



  }







  function openJobDetails(job) {



    setSelectedJob(job);



  }







  function closeJobDetails() {



    setSelectedJob(null);



  }







  async function fetchJobs() {

    const startedAt=
      performance.now();

    let pageCount=0;

    try {

      setLoading(true);
      setError("");

      const allJobs=[];
      let nextToken="";

      do {

        const url=
          nextToken
            ? `${API_URL}?limit=100&next_token=${encodeURIComponent(nextToken)}`
            : `${API_URL}?limit=100`;

        const response=
          await fetch(url);

        pageCount+=1;

        if (!response.ok) {
          throw new Error(
            `API request failed: ${response.status}`
          );
        }

        const data=
          await response.json();

        if (Array.isArray(data.jobs)) {
          allJobs.push(...data.jobs);
        }

        nextToken=
          data.next_token ||
          "";

      } while (nextToken);

      setJobs(allJobs);

      setFetchCount(
        value=>value+pageCount
      );

      setSuccessfulFetches(
        value=>value+1
      );

      setLastRefreshAt(
        Date.now()
      );

      setLastFetchDuration(
        Math.round(
          performance.now()-
          startedAt
        )
      );

    } catch (error) {

      console.error(error);

      setError(
        "Unable to load jobs from AWS API."
      );

      setFetchCount(
        value=>value+pageCount
      );

      setFailedFetches(
        value=>value+1
      );

      setLastRefreshAt(
        Date.now()
      );

      setLastFetchDuration(
        Math.round(
          performance.now()-
          startedAt
        )
      );

    } finally {

      setLoading(false);

    }

  }



async function fetchAdminMetrics() {



    if (!currentUserEmail) {
      return;
    }

    const session=getCurrentSession();

    if (!session || !session.idToken) {
      setMetricsError("Your session has expired. Please sign in again.");
      return;
    }







    try {



      setMetricsLoading(true);



      setMetricsError("");







      const response=await fetch(
        METRICS_URL,
        {
          headers:{
            Authorization:`Bearer ${session.idToken}`
          }
        }
      );







      if (!response.ok) {



        throw new Error(



          `Metrics request failed: ${response.status}`



        );



      }







      const data=



        await response.json();







      setAdminMetrics(



        data



      );







      setMetricsRefreshAt(



        Date.now()



      );



    } catch (error) {



      console.error(error);







      setMetricsError(



        "Unable to load synchronization metrics from AWS."



      );



    } finally {



      setMetricsLoading(false);



    }



  }







  function buildCustomSourcePayload() {
    const fields = {
      title:newSourceTitlePath.trim(),
      company:newSourceCompanyPath.trim(),
      source_id:newSourceIdPath.trim(),
      location:newSourceLocationPath.trim(),
      employment_type:newSourceEmploymentTypePath.trim(),
      description:newSourceDescriptionPath.trim(),
      apply_url:newSourceApplyUrlPath.trim(),
      salary_min:newSourceSalaryMinPath.trim(),
      salary_max:newSourceSalaryMaxPath.trim(),
      published_at:newSourcePublishedAtPath.trim()
    };
    Object.keys(fields).forEach(key=>{
      if (!fields[key]) delete fields[key];
    });
    return {
      source_name:newSourceName.trim(),
      endpoint:newSourceEndpoint.trim(),
      records_path:newSourceRecordsPath.trim(),
      fields,
      pagination:{
        type:newSourcePaginationType,
        page_parameter:newSourcePageParameter.trim() || "page",
        start_page:Number(newSourceStartPage),
        max_pages:Number(newSourceMaxPages)
      },
      crawl_interval:Number(newSourceInterval)
    };
  }

  async function adminApiRequest(url,options={}) {
    const session=getCurrentSession();
    if (!session || !session.idToken) {
      throw new Error("Your session has expired. Sign in again.");
    }
    const response=await fetch(url,{
      ...options,
      headers:{
        Authorization:"Bearer " + session.idToken,
        ...(options.body ? {"Content-Type":"application/json"} : {}),
        ...(options.headers || {})
      }
    });
    let data={};
    try { data=await response.json(); } catch { data={}; }
    if (!response.ok) {
      throw new Error(data.message || ("Admin request failed: " + response.status));
    }
    return data;
  }

  async function fetchAdminSources() {
    if (!currentUserEmail) return;
    try {
      setSourceManagementLoading(true);
      setSourceManagementError("");
      const data=await adminApiRequest(SOURCES_URL);
      setCustomSources(Array.isArray(data.sources) ? data.sources : []);
    } catch (error) {
      console.error(error);
      setSourceManagementError(error.message || "Unable to load source configuration.");
    } finally {
      setSourceManagementLoading(false);
    }
  }

  async function handleTestCustomSource() {
    setSourceTestResult(null);
    setSourceManagementMessage("");
    setSourceManagementError("");
    try {
      setSourceManagementBusy(true);
      const data=await adminApiRequest(SOURCE_TEST_URL,{
        method:"POST",
        body:JSON.stringify(buildCustomSourcePayload())
      });
      setSourceTestResult(data);
      setSourceManagementMessage(
        "Connection test succeeded. " + data.sample_count + " mapped sample job(s) found; nothing was saved."
      );
    } catch (error) {
      console.error(error);
      setSourceManagementError(error.message || "API connection test failed.");
    } finally {
      setSourceManagementBusy(false);
    }
  }

  async function handleCreateCustomSource() {
    setSourceTestResult(null);
    setSourceManagementMessage("");
    setSourceManagementError("");
    try {
      setSourceManagementBusy(true);
      const payload=buildCustomSourcePayload();
      const data=await adminApiRequest(SOURCES_URL,{
        method:"POST",
        body:JSON.stringify(payload)
      });
      setSourceManagementMessage(
        'Source "' + (data.source?.source_name || payload.source_name) + '" was created. It will run through the existing crawl queue.'
      );
      await fetchAdminSources();
    } catch (error) {
      console.error(error);
      setSourceManagementError(error.message || "Unable to create custom source.");
    } finally {
      setSourceManagementBusy(false);
    }
  }

  async function handleToggleCustomSource(item) {
    setSourceManagementError("");
    setSourceManagementMessage("");
    try {
      setSourceManagementBusy(true);
      const nextStatus=item.status==="ACTIVE" ? "DISABLED" : "ACTIVE";
      const data=await adminApiRequest(
        SOURCES_URL + "/" + encodeURIComponent(item.source_id),
        {method:"PATCH",body:JSON.stringify({status:nextStatus})}
      );
      setCustomSources(items=>items.map(source=>
        source.source_id===item.source_id ? data.source : source
      ));
      setSourceManagementMessage(
        'Source "' + item.source_name + '" is now ' + nextStatus.toLowerCase() + "."
      );
    } catch (error) {
      console.error(error);
      setSourceManagementError(error.message || "Unable to update source status.");
    } finally {
      setSourceManagementBusy(false);
    }
  }

  async function handleRefresh() {



    await fetchJobs();







    if (currentUserEmail) {



      await fetchAdminMetrics();



    }



  }







  function clearFilters() {



    setSearch("");



    setSource("all");



    setLocationFilter("");



    setWorkMode("all");



    setEmploymentType("all");



  }







  const filteredJobs=



    useMemo(() => {



      return jobs.filter(job => {



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







        const matchesLocation=



          !locationFilter.trim() ||



          String(



            job.location || ""



          )



            .toLowerCase()



            .includes(



              locationFilter



                .trim()



                .toLowerCase()



            );







        const matchesWorkMode=



          workMode==="all" ||



          getWorkMode(job)===workMode;







        const matchesEmployment=

          employmentType==="all" ||

          normalizeEmploymentType(

            job.employment_type

          )===employmentType;







        return (



          matchesSearch &&



          matchesSource &&



          matchesLocation &&



          matchesWorkMode &&



          matchesEmployment



        );



      });



    },[



      jobs,



      search,



      source,



      locationFilter,



      workMode,



      employmentType



    ]);







  const sources=[



    ...new Set(



      jobs



        .map(



          job=>job.source



        )



        .filter(Boolean)



    )



  ];







  const employmentTypes=EMPLOYMENT_TYPES;







  const workModes=[



    "Remote",



    "Hybrid",



    "On-site"



  ];







  const openJobs=



    jobs.filter(



      job=>job.status==="OPEN"



    ).length;







  const recentlyChangedJobs=



    jobs.filter(job => {



      if (!job.last_changed) {



        return false;



      }







      const changedAt=



        Number(



          job.last_changed



        );







      if (



        !Number.isFinite(



          changedAt



        )



      ) {



        return false;



      }







      const milliseconds=



        changedAt<



        100000000000



          ? changedAt*1000



          : changedAt;







      return (



        Date.now()-



        milliseconds <=



        24*60*60*1000



      );



    }).length;







  const sourceCounts=



    sources



      .map(item=>({



        name:item,



        count:



          jobs.filter(



            job =>



              job.source===item



          ).length



      }))



      .sort(



        (a,b)=>



          b.count-a.count



      );







  const metrics=



    adminMetrics?.metrics ||



    {};







  const metricSources=



    adminMetrics?.sources ||



    [];







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



              {formatNumber(



                jobs.length



              )}



            </strong>







            <span>



              Loaded jobs



            </span>



          </div>







          <div className="stat">



            <strong>



              {formatNumber(



                sources.length



              )}



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







      <section className="job-filters">



        <div className="search-row">



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







          <button



            className="clear-filter-button"



            onClick={



              clearFilters



            }



          >



            Clear



          </button>



        </div>







        <div className="filter-row">



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



            value={workMode}



            onChange={



              event=>



                setWorkMode(



                  event.target.value



                )



            }



          >



            <option value="all">



              All work modes



            </option>







            {workModes.map(item=>(



              <option



                key={item}



                value={item}



              >



                {item}



              </option>



            ))}



          </select>







          <input



            type="text"



            placeholder="Location"



            value={locationFilter}



            onChange={



              event=>



                setLocationFilter(



                  event.target.value



                )



            }



          />







          <select



            value={employmentType}



            onChange={



              event=>



                setEmploymentType(



                  event.target.value



                )



            }



          >



            <option value="all">



              All employment types



            </option>







            {employmentTypes.map(item=>(

              <option

                key={item.value}

                value={item.value}

              >

                {item.label}

              </option>

            ))}



          </select>



        </div>



      </section>







      <div className="filter-summary">



        <span>



          {formatNumber(



            filteredJobs.length



          )} matching jobs



        </span>



      </div>







      {loading&&(



        <div className="message">



          <span className="spinner" />



          Loading jobs from AWS...



        </div>



      )}







      {error&&(



        <div className="message error">



          <strong>



            API error



          </strong>







          <span>



            {error}



          </span>



        </div>



      )}







      {!loading&&



        !error&&



        filteredJobs.length===0&&(



          <div className="message">



            No jobs match your current filters.



          </div>



        )}







      <section className="jobs">



        {filteredJobs.map(job=>(



          <article



            className="job-card"



            key={



              job.canonical_job_id



            }



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



                className={



                  `status ${



                    String(



                      job.status



                    ).toLowerCase()



                  }`



                }



              >



                {job.status||



                  "OPEN"}



              </span>



            </div>







            <div className="details">



              <span>



                {job.location||



                  "Location not specified"}



              </span>







              <span>



                {getWorkMode(job)}



              </span>







              <span>



                {getEmploymentLabel(

                  job.employment_type

                )}



              </span>



            </div>







            {job.description&&(



              <p className="description">



                {job.description.length>



                240



                  ? `${job.description.slice(



                      0,



                      240



                    )}...`



                  : job.description}



              </p>



            )}







            <div className="card-footer">



              <small>



                ID:{" "}



                {job.canonical_job_id}



              </small>







              <button



                className="view-job-button"



                onClick={() =>



                  openJobDetails(job)



                }



              >



                View details



              </button>



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







      <section className="panel custom-sources-panel">
        <div className="panel-heading">
          <div>
            <p className="section-kicker">SOURCE INTEGRATION</p>
            <h3>Custom API sources</h3>
            <p className="custom-source-intro">
              Register a public HTTPS JSON API and map its response fields into the existing cache-aware crawl pipeline.
            </p>
          </div>
          <button className="source-secondary-button" type="button" onClick={fetchAdminSources} disabled={sourceManagementLoading || sourceManagementBusy}>
            {sourceManagementLoading ? "Loading..." : "Refresh sources"}
          </button>
        </div>
        {sourceManagementError && (
          <div className="message error custom-source-feedback">
            <strong>Source management error</strong>
            <span>{sourceManagementError}</span>
          </div>
        )}
        {sourceManagementMessage && (
          <div className="message custom-source-success">{sourceManagementMessage}</div>
        )}
        <div className="custom-source-form">
          <label>
            Source name
            <input value={newSourceName} onChange={event=>setNewSourceName(event.target.value)} placeholder="Example: Company Careers" maxLength={80} />
          </label>
          <label className="custom-source-wide">
            HTTPS JSON API endpoint
            <input value={newSourceEndpoint} onChange={event=>setNewSourceEndpoint(event.target.value)} placeholder="https://api.example.com/jobs" type="url" />
          </label>
          <label>
            Records path
            <input value={newSourceRecordsPath} onChange={event=>setNewSourceRecordsPath(event.target.value)} placeholder="jobs" />
            <small>Path to the jobs array, such as data.jobs</small>
          </label>
          <label>
            Title field path
            <input value={newSourceTitlePath} onChange={event=>setNewSourceTitlePath(event.target.value)} placeholder="title" required />
          </label>
          <label>
            Company field path
            <input value={newSourceCompanyPath} onChange={event=>setNewSourceCompanyPath(event.target.value)} placeholder="company" required />
          </label>
          <label>
            External ID field path
            <input value={newSourceIdPath} onChange={event=>setNewSourceIdPath(event.target.value)} placeholder="id" />
          </label>
          <label>
            Location field path
            <input value={newSourceLocationPath} onChange={event=>setNewSourceLocationPath(event.target.value)} placeholder="location" />
          </label>
          <label>
            Employment type path
            <input value={newSourceEmploymentTypePath} onChange={event=>setNewSourceEmploymentTypePath(event.target.value)} placeholder="employment_type" />
          </label>
          <label>
            Description field path
            <input value={newSourceDescriptionPath} onChange={event=>setNewSourceDescriptionPath(event.target.value)} placeholder="description" />
          </label>
          <label>
            Apply URL field path
            <input value={newSourceApplyUrlPath} onChange={event=>setNewSourceApplyUrlPath(event.target.value)} placeholder="apply_url" />
          </label>
          <label>
            Salary minimum path
            <input value={newSourceSalaryMinPath} onChange={event=>setNewSourceSalaryMinPath(event.target.value)} placeholder="salary_min" />
          </label>
          <label>
            Salary maximum path
            <input value={newSourceSalaryMaxPath} onChange={event=>setNewSourceSalaryMaxPath(event.target.value)} placeholder="salary_max" />
          </label>
          <label>
            Publication date path
            <input value={newSourcePublishedAtPath} onChange={event=>setNewSourcePublishedAtPath(event.target.value)} placeholder="published_at" />
          </label>
          <label>
            Pagination
            <select value={newSourcePaginationType} onChange={event=>setNewSourcePaginationType(event.target.value)}>
              <option value="NONE">Single response</option>
              <option value="PAGE">Page number</option>
            </select>
          </label>
          {newSourcePaginationType==="PAGE" && (
            <>
              <label>
                Page query parameter
                <input value={newSourcePageParameter} onChange={event=>setNewSourcePageParameter(event.target.value)} placeholder="page" />
              </label>
              <label>
                Start page
                <input type="number" min="0" value={newSourceStartPage} onChange={event=>setNewSourceStartPage(event.target.value)} />
              </label>
              <label>
                Maximum pages (1–10)
                <input type="number" min="1" max="10" value={newSourceMaxPages} onChange={event=>setNewSourceMaxPages(event.target.value)} />
              </label>
            </>
          )}
          <label>
            Crawl interval
            <select value={newSourceInterval} onChange={event=>setNewSourceInterval(event.target.value)}>
              <option value="900">Every 15 minutes</option>
              <option value="3600">Every hour</option>
              <option value="21600">Every 6 hours</option>
              <option value="86400">Every 24 hours</option>
            </select>
          </label>
        </div>
        <div className="custom-source-actions">
          <button type="button" className="source-secondary-button" onClick={handleTestCustomSource} disabled={sourceManagementBusy}>
            {sourceManagementBusy ? "Working..." : "Test connection"}
          </button>
          <button type="button" className="source-primary-button" onClick={handleCreateCustomSource} disabled={sourceManagementBusy}>
            {sourceManagementBusy ? "Working..." : "Save API source"}
          </button>
        </div>
        {sourceTestResult && (
          <div className="custom-source-preview">
            <strong>Connection preview — {sourceTestResult.records_seen} record(s) inspected</strong>
            {sourceTestResult.jobs?.length ? (
              sourceTestResult.jobs.map((job,index)=>(
                <div className="custom-source-preview-row" key={job.title + "-" + index}>
                  <span>{job.title}</span>
                  <small>{job.company}{job.location ? " · " + job.location : ""}</small>
                </div>
              ))
            ) : (
              <p>No records matched both configured title and company paths. Check the mappings.</p>
            )}
          </div>
        )}
        <div className="custom-source-list-heading">
          <h4>Registered sources</h4>
          <span>{customSources.length} source(s)</span>
        </div>
        {sourceManagementLoading && customSources.length===0 && <p className="custom-source-muted">Loading source configuration…</p>}
        {!sourceManagementLoading && customSources.length===0 && <p className="custom-source-muted">No source configuration loaded.</p>}
        <div className="custom-source-list">
          {customSources.map(item=>(
            <div className="custom-source-item" key={item.source_id}>
              <div className="custom-source-item-copy">
                <strong>{item.source_name}</strong>
                <span>{item.source_id}</span>
                {item.source_type==="CUSTOM_API" && item.endpoint && <small>{item.endpoint}</small>}
                <small>
                  {item.source_type==="CUSTOM_API" ? "Custom JSON API" : "Built-in connector"}
                  {" · "}{item.status}
                  {" · "}{formatNumber(item.crawl_interval)} sec interval
                  {" · "}{formatNumber(item.successful_crawl_count)} successful
                  {" · "}{formatNumber(item.failed_crawl_count)} failed
                </small>
              </div>
              {item.source_type==="CUSTOM_API" && (
                <button type="button" className="source-secondary-button" onClick={()=>handleToggleCustomSource(item)} disabled={sourceManagementBusy}>
                  {item.status==="ACTIVE" ? "Disable" : "Enable"}
                </button>
              )}
            </div>
          ))}
        </div>
        <p className="custom-source-footnote">
          This first version supports unauthenticated public HTTPS JSON APIs. Do not put API keys in endpoint URLs. Custom sources run through the existing controller, SQS, Lambda, and DynamoDB workflow.
        </p>
      </section>

      {metricsError&&(



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



            metrics.cache_hits!==undefined



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



            metrics.cache_misses!==undefined



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



            metrics.redundant_updates_prevented!==undefined



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



            metrics.controller_skips!==undefined



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



            metrics.successful_crawls!==undefined



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



            metrics.failed_crawls!==undefined



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



            metrics.jobs_processed!==undefined



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



              ? `${cacheHitRate.toFixed(



                  1



                )}%`



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



                metrics.new!==undefined



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



                metrics.unchanged!==undefined



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



                metrics.changed!==undefined



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



                metrics.cache_misses!==undefined



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



            {metricSources.length===0&&(



              <div className="empty-source">



                No source metrics available.



              </div>



            )}







            {metricSources.map(item=>(



              <div



                className="source-row"



                key={



                  item.source_id



                }



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



              key={



                stage.number



              }



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



          {sourceCounts.length===0&&(



            <div className="empty-source">



              No job data available.



            </div>



          )}







          {sourceCounts.map(item=>{



            const width=



              jobs.length>0



                ? `${



                    (



                      item.count/



                      jobs.length



                    )*100



                  }%`



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



            onClick={() =>



              changeView("jobs")



            }



          >



            Jobs



          </button>







          {currentUserEmail&&(



            <button



              className={



                view==="admin"



                  ? "nav-button active"



                  : "nav-button"



              }



              onClick={() =>



                changeView("admin")



              }



            >



              Admin



            </button>



          )}







          {currentUserEmail ? (



            <button



              className="logout-button"



              onClick={



                handleLogout



              }



            >



              Logout



            </button>



          ) : (



            <button



              className="account-button"



              onClick={



                openLogin



              }



            >



              Login



            </button>



          )}







          <button



            className="refresh-button"



            onClick={



              handleRefresh



            }



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



        {view==="admin"&&



        !currentUserEmail



          ? null



          : view==="admin"



            ? renderAdminPage()



            : renderJobsPage()}



      </main>







      {showLogin&&(



        <div



          className="auth-overlay"



          onClick={



            closeLogin



          }



        >



          <div



            className="auth-modal"



            onClick={event =>



              event.stopPropagation()



            }



          >



            <div className="auth-header">



              <div>



                <p className="section-kicker">



                  JOBSYNC ACCOUNT



                </p>







                <h2>



                  Login



                </h2>



              </div>







              <button



                className="auth-close"



                onClick={



                  closeLogin



                }



              >



                ×



              </button>



            </div>







            <form



              className="auth-form"



              onSubmit={



                handleLogin



              }



            >



              <label>



                Email



                <input



                  type="email"



                  value={



                    loginEmail



                  }



                  onChange={



                    event =>



                      setLoginEmail(



                        event.target



                          .value



                      )



                  }



                  placeholder="you@example.com"



                  autoComplete="email"



                  disabled={



                    loginLoading



                  }



                  required



                />



              </label>







              <label>



                Password



                <input



                  type="password"



                  value={



                    loginPassword



                  }



                  onChange={



                    event =>



                      setLoginPassword(



                        event.target



                          .value



                      )



                  }



                  placeholder="Enter your password"



                  autoComplete="current-password"



                  disabled={



                    loginLoading



                  }



                  required



                />



              </label>







              {loginError&&(



                <div className="auth-error">



                  {loginError}



                </div>



              )}







              {loginMessage&&(



                <div className="auth-message">



                  {loginMessage}



                </div>



              )}







              <button



                type="submit"



                className="auth-primary"



                disabled={



                  loginLoading



                }



              >



                {loginLoading



                  ? "Logging in..."



                  : "Login"}



              </button>



            </form>



          </div>



        </div>



      )}







      {selectedJob&&(



        <div



          className="auth-overlay"



          onClick={



            closeJobDetails



          }



        >



          <div



            className="job-detail-modal"



            onClick={event =>



              event.stopPropagation()



            }



          >



            <div className="job-detail-header">



              <div>



                <p className="source">



                  {selectedJob.source}



                </p>







                <h2>



                  {selectedJob.title}



                </h2>







                <p className="job-detail-company">



                  {selectedJob.company}



                </p>



              </div>







              <button



                className="auth-close"



                onClick={



                  closeJobDetails



                }



              >



                ×



              </button>



            </div>







            <div className="job-detail-tags">



              <span>



                {selectedJob.location||



                  "Location not specified"}



              </span>







              <span>



                {getWorkMode(



                  selectedJob



                )}



              </span>







              <span>



                {getEmploymentLabel(

                  selectedJob.employment_type

                )}



              </span>







              <span>



                {formatSalary(



                  selectedJob



                )}



              </span>



            </div>







            <div className="job-detail-meta">



              {selectedJob.published_at&&(



                <div>



                  <strong>



                    Published



                  </strong>







                  <span>



                    {formatTime(



                      selectedJob.published_at



                    )}



                  </span>



                </div>



              )}







              {selectedJob.first_seen&&(



                <div>



                  <strong>



                    First seen



                  </strong>







                  <span>



                    {formatTime(



                      selectedJob.first_seen



                    )}



                  </span>



                </div>



              )}







              {selectedJob.last_changed&&(



                <div>



                  <strong>



                    Last changed



                  </strong>







                  <span>



                    {formatTime(



                      selectedJob.last_changed



                    )}



                  </span>



                </div>



              )}



            </div>







            <div className="job-detail-description">



              <p className="section-kicker">



                JOB DESCRIPTION



              </p>







              <div>



                {selectedJob.description ? (



                  selectedJob.description



                    .split(/\n+/)



                    .map(



                      (paragraph,index)=>(



                        <p



                          key={index}



                        >



                          {paragraph}



                        </p>



                      )



                    )



                ) : (



                  <p>



                    No description available.



                  </p>



                )}



              </div>



            </div>







            <div className="job-detail-footer">



              <small>



                ID:{" "}



                {selectedJob.canonical_job_id}



              </small>







              {selectedJob.apply_url&&(



                <a



                  className="apply-button"



                  href={



                    selectedJob.apply_url



                  }



                  target="_blank"



                  rel="noreferrer"



                >



                  Apply on original website



                </a>



              )}



            </div>



          </div>



        </div>



      )}



    </div>



  );



}







export default App;