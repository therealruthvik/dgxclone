"use client";
import { useState, useEffect } from "react";
import { login, register, fetchJobs, fetchK8sStats, submitJob, deleteJob } from "@/lib/api";
import JobSubmitForm from "@/components/JobSubmitForm";
import JobList from "@/components/JobList";
import K8sStats from "@/components/K8sStats";

export default function Home() {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [jobs, setJobs] = useState<any[]>([]);
  const [k8s, setK8s] = useState<any>(null);

  useEffect(() => {
    const stored = localStorage.getItem("token");
    if (stored) setToken(stored);
  }, []);

  useEffect(() => {
    if (!token) return;
    const load = async () => {
      const [j, k] = await Promise.all([fetchJobs(), fetchK8sStats()]);
      setJobs(j);
      setK8s(k);
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [token]);

  const handleLogin = async () => {
    try {
      const t = await login(username, password);
      setToken(t);
      setError("");
    } catch {
      setError("Login failed");
    }
  };

  const handleRegister = async () => {
    try {
      await register(username, password);
      await handleLogin();
    } catch {
      setError("Registration failed");
    }
  };

  const handleSubmit = async (payload: any) => {
    await submitJob(payload);
    const j = await fetchJobs();
    setJobs(j);
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteJob(id);
      setJobs((prev: any[]) => prev.filter((j: any) => j.id !== id));
    } catch {}
  };

  if (!token) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="bg-gray-900 p-8 rounded-lg w-80 space-y-4">
          <h1 className="text-2xl font-bold text-green-400">RUN:ai</h1>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <input
            className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            type="password"
            className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <div className="flex gap-2">
            <button onClick={handleLogin} className="flex-1 bg-green-600 hover:bg-green-500 rounded py-2 text-sm">
              Login
            </button>
            <button onClick={handleRegister} className="flex-1 bg-gray-700 hover:bg-gray-600 rounded py-2 text-sm">
              Register
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-green-400">RUN:ai</h1>
        <button
          onClick={() => { localStorage.removeItem("token"); setToken(null); }}
          className="text-sm text-gray-400 hover:text-white"
        >
          Logout
        </button>
      </div>
      <K8sStats data={k8s} />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <JobSubmitForm onSubmit={handleSubmit} />
        </div>
        <div className="lg:col-span-2">
          <JobList jobs={jobs} onDelete={handleDelete} />
        </div>
      </div>
    </div>
  );
}
