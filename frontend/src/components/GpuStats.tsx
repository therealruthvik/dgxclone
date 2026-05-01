"use client";

interface GpuData {
  gpu_name?: string;
  gpu_utilization_pct?: number;
  memory_used_mb?: number;
  memory_total_mb?: number;
  temperature_c?: number;
  power_draw_w?: number;
  error?: string;
}

function Bar({ value, max }: { value: number; max: number }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
      <div
        className="h-full bg-green-500 transition-all duration-500"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export default function GpuStats({ data }: { data: GpuData | null }) {
  if (!data) return <div className="bg-gray-900 rounded-lg p-4 text-gray-500 text-sm">Loading GPU stats...</div>;
  if (data.error) return <div className="bg-gray-900 rounded-lg p-4 text-red-400 text-sm">GPU error: {data.error}</div>;

  return (
    <div className="bg-gray-900 rounded-lg p-4 space-y-3">
      <h2 className="text-sm font-bold text-green-400 uppercase tracking-wider">GPU</h2>
      <p className="text-xs text-gray-400">{data.gpu_name}</p>
      <div className="space-y-2">
        <div>
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>GPU Util</span>
            <span>{data.gpu_utilization_pct?.toFixed(0)}%</span>
          </div>
          <Bar value={data.gpu_utilization_pct ?? 0} max={100} />
        </div>
        <div>
          <div className="flex justify-between text-xs text-gray-400 mb-1">
            <span>VRAM</span>
            <span>{((data.memory_used_mb ?? 0) / 1024).toFixed(1)} / {((data.memory_total_mb ?? 0) / 1024).toFixed(1)} GB</span>
          </div>
          <Bar value={data.memory_used_mb ?? 0} max={data.memory_total_mb ?? 1} />
        </div>
      </div>
      <div className="flex justify-between text-xs text-gray-400 pt-1 border-t border-gray-800">
        <span>Temp: {data.temperature_c}°C</span>
        <span>Power: {data.power_draw_w?.toFixed(0)}W</span>
      </div>
    </div>
  );
}
