"use client";
import { useState } from "react";

interface Props {
  onSubmit: (payload: any) => Promise<void>;
}

export default function JobSubmitForm({ onSubmit }: Props) {
  const [name, setName] = useState("");
  const [image, setImage] = useState("nvcr.io/nvidia/pytorch:24.01-py3");
  const [command, setCommand] = useState("python -c \"import torch; print(torch.cuda.is_available())\"");
  const [gpuCount, setGpuCount] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await onSubmit({ name, image, command, env: {}, gpu_count: gpuCount });
      setName("");
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-gray-900 rounded-lg p-4 space-y-3">
      <h2 className="text-sm font-bold text-green-400 uppercase tracking-wider">Submit Job</h2>
      {error && <p className="text-red-400 text-xs">{error}</p>}
      <input
        className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
        placeholder="Job name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
      />
      <input
        className="w-full bg-gray-800 rounded px-3 py-2 text-sm"
        placeholder="Docker image"
        value={image}
        onChange={(e) => setImage(e.target.value)}
        required
      />
      <textarea
        className="w-full bg-gray-800 rounded px-3 py-2 text-sm font-mono h-20 resize-none"
        placeholder="Command"
        value={command}
        onChange={(e) => setCommand(e.target.value)}
        required
      />
      <div className="flex items-center gap-2 text-sm">
        <label className="text-gray-400">GPUs:</label>
        <select
          className="bg-gray-800 rounded px-2 py-1"
          value={gpuCount}
          onChange={(e) => setGpuCount(Number(e.target.value))}
        >
          <option value={0}>0 (CPU only)</option>
          <option value={1}>1 (A10)</option>
        </select>
      </div>
      <button
        type="submit"
        disabled={loading}
        className="w-full bg-green-600 hover:bg-green-500 disabled:bg-gray-700 rounded py-2 text-sm font-bold transition-colors"
      >
        {loading ? "Submitting..." : "Submit Job"}
      </button>
    </form>
  );
}
