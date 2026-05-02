"use client";

interface ClusterData {
  nodes?: number | null;
  pods_running?: number | null;
  pods_total?: number | null;
  namespaces?: number | null;
  memory_used_gb?: number | null;
  memory_total_gb?: number | null;
  gpu_utilization_pct?: number | null;
  gpu_memory_used_mb?: number | null;
  gpu_memory_total_mb?: number | null;
  gpu_temperature_c?: number | null;
  gpu_power_w?: number | null;
  k8s_error?: string | null;
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-gray-800 rounded-lg p-3 flex flex-col gap-1 min-w-0">
      <span className="text-xs text-gray-500 uppercase tracking-wider truncate">{label}</span>
      <span className="text-xl font-bold text-white">{value}</span>
      {sub && <span className="text-xs text-gray-500">{sub}</span>}
    </div>
  );
}

function MeterBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = Math.min((value / Math.max(max, 1)) * 100, 100);
  return (
    <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
      <div className={`h-full ${color} transition-all duration-500`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function GpuMeter({
  label,
  value,
  max,
  unit,
  display,
  color,
}: {
  label: string;
  value: number;
  max: number;
  unit: string;
  display: string;
  color: string;
}) {
  return (
    <div className="bg-gray-800 rounded-lg p-3 space-y-2">
      <div className="flex justify-between items-center">
        <span className="text-xs text-gray-500 uppercase tracking-wider">{label}</span>
        <span className="text-sm font-bold text-white">{display}</span>
      </div>
      <MeterBar value={value} max={max} color={color} />
      <span className="text-xs text-gray-600">{unit}</span>
    </div>
  );
}

export default function K8sStats({ data }: { data: ClusterData | null }) {
  if (!data) {
    return (
      <div className="bg-gray-900 rounded-lg p-4 text-gray-500 text-sm animate-pulse">
        Loading cluster stats...
      </div>
    );
  }

  const gpuUtil = data.gpu_utilization_pct ?? 0;
  const gpuUtilColor = gpuUtil > 80 ? "bg-red-500" : gpuUtil > 50 ? "bg-yellow-500" : "bg-green-500";
  const vramUsed = data.gpu_memory_used_mb ?? 0;
  const vramTotal = data.gpu_memory_total_mb ?? 1;
  const vramPct = (vramUsed / vramTotal) * 100;
  const vramColor = vramPct > 85 ? "bg-red-500" : vramPct > 60 ? "bg-yellow-500" : "bg-blue-500";

  return (
    <div className="bg-gray-900 rounded-lg p-4 space-y-4">
      <h2 className="text-sm font-bold text-green-400 uppercase tracking-wider">Cluster</h2>

      {/* GPU metrics row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <GpuMeter
          label="GPU Utilization"
          value={gpuUtil}
          max={100}
          unit="%"
          display={data.gpu_utilization_pct != null ? `${gpuUtil.toFixed(0)}%` : "—"}
          color={gpuUtilColor}
        />
        <GpuMeter
          label="VRAM"
          value={vramUsed}
          max={vramTotal}
          unit={`${(vramUsed / 1024).toFixed(1)} / ${(vramTotal / 1024).toFixed(1)} GB`}
          display={data.gpu_memory_used_mb != null ? `${(vramUsed / 1024).toFixed(1)} GB` : "—"}
          color={vramColor}
        />
        <StatCard
          label="Temperature"
          value={data.gpu_temperature_c != null ? `${data.gpu_temperature_c.toFixed(0)}°C` : "—"}
          sub={data.gpu_temperature_c != null
            ? data.gpu_temperature_c > 80 ? "⚠ High" : "Normal"
            : undefined}
        />
        <StatCard
          label="Power Draw"
          value={data.gpu_power_w != null ? `${data.gpu_power_w.toFixed(0)} W` : "—"}
        />
      </div>

      {/* k8s stats row */}
      <div className="border-t border-gray-800 pt-3">
        {data.k8s_error ? (
          <p className="text-xs text-yellow-600 font-mono">{data.k8s_error}</p>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard label="Nodes" value={data.nodes != null ? String(data.nodes) : "—"} />
            <StatCard
              label="Pods Running"
              value={data.pods_running != null ? String(data.pods_running) : "—"}
              sub={data.pods_total != null ? `${data.pods_total} total` : undefined}
            />
            <StatCard label="Namespaces" value={data.namespaces != null ? String(data.namespaces) : "—"} />
            <StatCard
              label="Memory"
              value={data.memory_used_gb != null ? `${data.memory_used_gb} GB` : data.memory_total_gb != null ? `${data.memory_total_gb} GB` : "—"}
              sub={data.memory_used_gb != null && data.memory_total_gb != null
                ? `of ${data.memory_total_gb} GB`
                : data.memory_total_gb != null ? "total allocatable" : undefined}
            />
          </div>
        )}
      </div>
    </div>
  );
}
