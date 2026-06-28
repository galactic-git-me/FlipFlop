"use client";

import { useEffect, useState } from "react";
import { Cpu, Zap, RefreshCw, BarChart3, Clock, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

interface BenchmarkStatus {
  total_benchmarks: number;
  cpu_count: number;
  gpu_count: number;
  storage_count: number;
  last_run: {
    run_type: string | null;
    status: string | null;
    started_at: string | null;
    components_checked: number;
    components_updated: number;
    components_failed: number;
  } | null;
}

interface TopBenchmark {
  model: string;
  normalized_model: string;
  overall_score: number;
  gaming_score: number | null;
  last_refreshed_at: string | null;
  confidence_score: number;
}

interface RefreshRun {
  id: number;
  run_type: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  components_checked: number;
  components_updated: number;
  components_failed: number;
  error_log: string | null;
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  completed: <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />,
  failed: <XCircle className="w-3.5 h-3.5 text-red-400" />,
  running: <RefreshCw className="w-3.5 h-3.5 text-yellow-400 animate-spin" />,
};

export default function BenchmarksPage() {
  const [status, setStatus] = useState<BenchmarkStatus | null>(null);
  const [topCpus, setTopCpus] = useState<TopBenchmark[]>([]);
  const [topGpus, setTopGpus] = useState<TopBenchmark[]>([]);
  const [runs, setRuns] = useState<RefreshRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState<"cpu" | "gpu">("cpu");

  const load = async () => {
    setLoading(true);
    try {
      const [s, cpus, gpus, r] = await Promise.all([
        api.benchmarks.status(),
        api.benchmarks.top("cpu", 20),
        api.benchmarks.top("gpu", 20),
        api.benchmarks.refreshRuns(10),
      ]);
      setStatus(s);
      setTopCpus(cpus as TopBenchmark[]);
      setTopGpus(gpus as TopBenchmark[]);
      setRuns(r as RefreshRun[]);
    } catch {
      setStatus(null);
    } finally {
      setLoading(false);
    }
  };

  const triggerRefresh = async (type: "daily" | "weekly" | "manual") => {
    setRefreshing(true);
    try {
      await api.benchmarks.triggerRefresh(type);
      setTimeout(() => { void load(); }, 2000);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => { void load(); }, []);

  const topList = activeTab === "cpu" ? topCpus : topGpus;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
            <Cpu className="w-5 h-5" /> Benchmark Intelligence
          </h1>
          <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
            Performance data — powers gem detection and performance/£ scoring
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
          <Button variant="secondary" size="sm" onClick={() => void triggerRefresh("daily")} disabled={refreshing}>
            <Zap className="w-3.5 h-3.5" /> Daily Refresh
          </Button>
          <Button variant="secondary" size="sm" onClick={() => void triggerRefresh("weekly")} disabled={refreshing}>
            <BarChart3 className="w-3.5 h-3.5" /> Full Refresh
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Total Benchmarks", value: status?.total_benchmarks ?? 0, color: "text-slate-300" },
          { label: "CPUs", value: status?.cpu_count ?? 0, color: "text-[#00dc82]" },
          { label: "GPUs", value: status?.gpu_count ?? 0, color: "text-cyan-400" },
          { label: "Storage", value: status?.storage_count ?? 0, color: "text-purple-400" },
        ].map(({ label, value, color }) => (
          <Card key={label}>
            <CardContent className="pt-5">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-2">{label}</div>
              <div className={`text-2xl font-bold ${color}`}>{value.toLocaleString()}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {status?.last_run && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="w-3.5 h-3.5 text-slate-400" /> Last Refresh Run
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="flex flex-wrap gap-6 text-sm">
              <div><span className="text-slate-500">Type: </span><span className="text-slate-200 font-mono">{status.last_run.run_type ?? "—"}</span></div>
              <div className="flex items-center gap-1">
                <span className="text-slate-500">Status: </span>
                {STATUS_ICON[status.last_run.status ?? ""] ?? <AlertTriangle className="w-3.5 h-3.5 text-slate-500" />}
                <span className="text-slate-200 font-mono">{status.last_run.status ?? "—"}</span>
              </div>
              <div><span className="text-slate-500">Checked: </span><span className="text-slate-200">{status.last_run.components_checked}</span></div>
              <div><span className="text-slate-500">Updated: </span><span className="text-emerald-400">{status.last_run.components_updated}</span></div>
              {status.last_run.components_failed > 0 && (
                <div><span className="text-slate-500">Failed: </span><span className="text-red-400">{status.last_run.components_failed}</span></div>
              )}
              <div><span className="text-slate-500">Started: </span><span className="text-slate-400 font-mono text-xs">{status.last_run.started_at ? new Date(status.last_run.started_at).toLocaleString() : "—"}</span></div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <BarChart3 className="w-3.5 h-3.5 text-[#00dc82]" /> Top Benchmarks
            </CardTitle>
            <div className="flex gap-1">
              {(["cpu", "gpu"] as const).map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)}
                  className={`px-3 py-1 rounded text-xs font-mono uppercase tracking-wider transition-colors ${activeTab === tab ? "bg-[#00dc82] text-[#080c14]" : "text-slate-500 hover:text-slate-300"}`}>
                  {tab}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          {loading ? (
            <div className="text-center text-sm text-slate-600 py-8">Loading...</div>
          ) : topList.length === 0 ? (
            <div className="text-center text-sm text-slate-600 py-8">No data yet. Click Full Refresh to fetch PassMark data.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-slate-500 border-b border-[#1e2d45]">
                    <th className="text-left pb-2 pr-4">#</th>
                    <th className="text-left pb-2 pr-4">Model</th>
                    <th className="text-right pb-2 pr-4">Overall Score</th>
                    <th className="text-right pb-2 pr-4">Gaming Score</th>
                    <th className="text-right pb-2">Last Refreshed</th>
                  </tr>
                </thead>
                <tbody>
                  {topList.map((b, i) => (
                    <tr key={b.normalized_model} className="border-b border-[#0f1c2e] hover:bg-[#0a1119] transition-colors">
                      <td className="py-2 pr-4 text-slate-600">{i + 1}</td>
                      <td className="py-2 pr-4">
                        <div className="text-slate-200 font-medium">{b.model}</div>
                        <div className="text-slate-600 font-mono text-[10px]">{b.normalized_model}</div>
                      </td>
                      <td className="py-2 pr-4 text-right text-[#00dc82] font-mono font-semibold">{b.overall_score?.toLocaleString() ?? "—"}</td>
                      <td className="py-2 pr-4 text-right text-cyan-400 font-mono">{b.gaming_score?.toLocaleString() ?? "—"}</td>
                      <td className="py-2 text-right text-slate-600 font-mono text-[10px]">{b.last_refreshed_at ? new Date(b.last_refreshed_at).toLocaleDateString() : "never"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2"><Clock className="w-3.5 h-3.5 text-slate-400" /> Refresh History</CardTitle>
        </CardHeader>
        <CardContent className="pt-0 space-y-2">
          {runs.length === 0 ? (
            <div className="text-xs text-slate-600 text-center py-4">No refresh runs yet.</div>
          ) : runs.map(run => (
            <div key={run.id} className="flex items-center justify-between p-3 rounded-lg bg-[#0a1119] border border-[#1e2d45]">
              <div className="flex items-center gap-3">
                {STATUS_ICON[run.status] ?? <AlertTriangle className="w-3.5 h-3.5 text-slate-500" />}
                <div>
                  <div className="text-xs text-slate-300 font-mono">{run.run_type} · {run.status}</div>
                  <div className="text-[10px] text-slate-600">{new Date(run.started_at).toLocaleString()}</div>
                </div>
              </div>
              <div className="text-right text-xs">
                <div className="text-slate-400">{run.components_checked} checked</div>
                <div className="text-emerald-400">{run.components_updated} updated</div>
                {run.components_failed > 0 && <div className="text-red-400">{run.components_failed} failed</div>}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
