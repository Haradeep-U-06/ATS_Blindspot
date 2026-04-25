const BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function fetcher(url, options) {
  const r = await fetch(url, options);
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error(data.detail || `Request failed with status ${r.status}`);
  }
  return r.json();
}

export const api = {
  getDashboard: () => fetcher(`${BASE}/dashboard`),
  
  createJob: (payload) => fetcher(`${BASE}/jobs/create`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }),

  getJob: (jobId) => fetcher(`${BASE}/jobs/${jobId}`),

  uploadResume: (formData) => fetcher(`${BASE}/upload/resume`, {
    method: "POST",
    body: formData,
  }),

  getResumeStatus: (resumeId) => fetcher(`${BASE}/status/${resumeId}`),

  triggerEvaluation: (jobId) => fetcher(`${BASE}/jobs/${jobId}/evaluation/trigger`, {
    method: "POST",
  }),

  getEvaluationStatus: (jobId) => fetcher(`${BASE}/jobs/${jobId}/evaluation/status`),

  getRankedCandidates: (jobId) => fetcher(`${BASE}/jobs/${jobId}/candidates`),

  getCandidateDashboard: (jobId, candidateId) => fetcher(`${BASE}/jobs/${jobId}/candidates/${candidateId}`),

  getResumeContent: (resumeId) => fetcher(`${BASE}/resume/${resumeId}`),
};
