"use client";
import { useState, useEffect, useRef } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const STATUS_COLORS: Record<string, string> = {
  queued: "text-yellow-400",
  running: "text-blue-400",
  completed: "text-green-400",
  failed: "text-red-400",
};

function LogStream({ jobId, status }: { jobId: string; status: string }) {
  const [lines, setLines] = useState<string[]>([]);
  const [streaming, setStreaming] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const startStream = () => {
    if (esRef.current) return;
    const token = localStorage.getItem("token");
    setStreaming(true);
    setLines([]);
    const es = new EventSource(
      `${BASE}/jobs/${jobId}/logs/stream?token=${token}`
    );
    esRef.current = es;

    es.onmessage = (e) => {
      if (e.data === "[DONE]") {
        es.close();
        esRef.current = null;
        setStreaming(false);
        return;
      }
      setLines((prev) => [...prev, e.data]);
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    es.onerror = () => {
      es.close();
      esRef.current = null;
      setStreaming(false);
    };
  };

  useEffect(() => {
    return () => {
      esRef.current?.close();
    };
  }, []);

  return (
    <div className="mt-2">
      <button
        onClick={startStream}
        disabled={streaming}
        className="text-xs bg-gray-700 hover:bg-gray-600 disabled:opacity-50 rounded px-2 py-1 mb-2"
      >
        {streaming ? "Streaming..." : "Stream Logs"}
      </button>
      {lines.length > 0 && (
        <pre className="text-xs bg-gray-950 rounded p-2 max-h-48 overflow-y-auto text-gray-300 whitespace-pre-wrap">
          {lines.join("\n")}
          <div ref={bottomRef} />
        </pre>
      )}
    </div>
  );
}

export default function JobList({ jobs, onDelete }: { jobs: any[]; onDelete: (id: string) => void }) {
  if (!jobs.length) {
    return (
      <div className="bg-gray-900 rounded-lg p-4 text-gray-500 text-sm">
        No jobs yet. Submit your first job.
      </div>
    );
  }

  return (
    <div className="bg-gray-900 rounded-lg p-4 space-y-3">
      <h2 className="text-sm font-bold text-green-400 uppercase tracking-wider">Jobs</h2>
      <div className="space-y-2">
        {[...jobs].reverse().map((job) => (
          <div key={job.id} className="bg-gray-800 rounded p-3 space-y-1">
            <div className="flex items-center justify-between">
              <span className="font-bold text-sm">{job.name}</span>
              <div className="flex items-center gap-2">
                <span className={`text-xs font-mono uppercase ${STATUS_COLORS[job.status] ?? "text-gray-400"}`}>
                  {job.status}
                </span>
                {job.status !== "running" && (
                  <button
                    onClick={() => onDelete(job.id)}
                    className="text-xs text-gray-600 hover:text-red-400 transition-colors leading-none"
                    title="Delete job"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>
            <div className="text-xs text-gray-400 font-mono truncate">{job.command}</div>
            <div className="text-xs text-gray-500">
              {job.image} &middot; {job.gpu_count} GPU &middot; {new Date(job.created_at).toLocaleString()}
            </div>
            <LogStream jobId={job.id} status={job.status} />
          </div>
        ))}
      </div>
    </div>
  );
}
