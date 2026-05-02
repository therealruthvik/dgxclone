const BASE = process.env.NEXT_PUBLIC_API_URL || "";

function authHeaders(): HeadersInit {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function login(username: string, password: string): Promise<string> {
  const body = new URLSearchParams({ username, password });
  const res = await fetch(`${BASE}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Incorrect username or password");
  }
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
  return data.access_token;
}

export async function register(username: string, password: string) {
  const res = await fetch(`${BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Registration failed");
  }
}

export async function fetchJobs() {
  const res = await fetch(`${BASE}/jobs/`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to fetch jobs");
  return res.json();
}

export async function submitJob(payload: {
  name: string;
  image: string;
  command: string;
  env: Record<string, string>;
  gpu_count: number;
}) {
  const res = await fetch(`${BASE}/jobs/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to submit job");
  return res.json();
}

export async function deleteJob(jobId: string) {
  const res = await fetch(`${BASE}/jobs/${jobId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to delete job");
}

export async function fetchGpuMetrics() {
  const res = await fetch(`${BASE}/metrics/gpu`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to fetch GPU metrics");
  return res.json();
}

export async function fetchK8sStats() {
  const res = await fetch(`${BASE}/k8s/stats`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Failed to fetch k8s stats");
  return res.json();
}
