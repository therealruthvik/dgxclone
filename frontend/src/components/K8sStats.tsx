"use client";

interface K8sData {
  nodes?: number;
  pods_running?: number;
  pods_total?: number;
  namespaces?: number;
  memory_used_gb?: number;
  memory_total_gb?: number;
  gpu_utilization_pct?: number | null;
  error?: string;
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-gray-800 rounded-lg p-4 flex flex-col gap-1">
      <span className="text-xs text-gray-500 uppercase tracking-wider">{label}</span>
      <span className="text-2xl font-bold text-white">{value}</span>
      {sub && <span className="text-xs text-gray-500">{sub}</span>}
    </div>
  );
}

function GpuBar({ value }: { value: number }) {
  const color = value > 80 ? "bg-red-500" : value > 50 ? "bg-yellow-500" : "bg-green-500";
  return (
    <div className="bg-gray-800 rounded-lg p-4 flex flex-col gap-2">
      <span className="text-xs text-gray-500 uppercase tracking-wider">GPU Utilization</span>
      <span className="text-2xl font-bold text-white">{value.toFixed(0)}%</span>
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} transition-all duration-500`}
          style={{ width: `${Math.min(value, 100)}%` }}
        />
      </div>
    </div>
  );
}

export default function K8sStats({ data }: { data: K8sData | null }) {
  if (!data) {
    return (
      <div className="bg-gray-900 rounded-lg p-4 text-gray-500 text-sm">
        Loading cluster stats...
      </div>
    );
  }

  if (data.error) {
    return (
      <div className="bg-gray-900 rounded-lg p-4">
        <h2 className="text-sm font-bold text-green-400 uppercase tracking-wider mb-2">Cluster</h2>
        <p className="text-red-400 text-xs font-mono">{data.error}</p>
      </div>
    );
  }

  const memLabel =
    data.memory_total_gb && data.memory_total_gb > 0
      ? `${data.memory_used_gb ?? 0} / ${data.memory_total_gb} GB`
      : data.memory_total_gb
      ? `${data.memory_total_gb} GB total`
      : "—";

  const memValue =
    data.memory_used_gb != null && data.memory_used_gb > 0
      ? `${data.memory_used_gb} GB`
      : data.memory_total_gb
      ? `${data.memory_total_gb} GB`
      : "—";

  return (
    <div className="bg-gray-900 rounded-lg p-4 space-y-3">
      <h2 className="text-sm font-bold text-green-400 uppercase tracking-wider">Cluster</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatCard label="Nodes" value={String(data.nodes ?? "—")} />
        <StatCard
          label="Pods Running"
          value={String(data.pods_running ?? "—")}
          sub={data.pods_total != null ? `${data.pods_total} total` : undefined}
        />
        <StatCard label="Namespaces" value={String(data.namespaces ?? "—")} />
        <StatCard
          label="Memory"
          value={memValue}
          sub={data.memory_used_gb != null && data.memory_total_gb ? memLabel : undefined}
        />
        {data.gpu_utilization_pct != null ? (
          <GpuBar value={data.gpu_utilization_pct} />
        ) : (
          <StatCard label="GPU Utilization" value="—" />
        )}
      </div>
    </div>
  );
}
