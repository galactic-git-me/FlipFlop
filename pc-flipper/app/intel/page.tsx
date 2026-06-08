"use client";

import { useEffect, useState } from "react";
import { Brain, TrendingUp, RefreshCw, Gem, Clock, Award, Lightbulb, BarChart3, Zap } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/empty-state";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/utils";

interface IntelSummary {
  total_flips: number;
  total_profit: number;
  avg_profit: number;
  avg_roi_pct: number;
  avg_days_to_sell: number;
  best_source: string | null;
  best_cpu_tier: string | null;
}

interface BreakdownRow {
  source?: string;
  cpu_tier?: string;
  platform?: string;
  count: number;
  avg_profit: number;
  total_profit?: number;
}

interface Recommendation {
  insight: string;
  action: string;
  confidence: number;
}

interface HistoryEntry {
  id: number;
  flip_id: number;
  buy_price: number;
  sell_price: number;
  profit: number;
  roi_pct: number;
  days_to_sell: number;
  source_site: string;
  cpu_tier: string;
  sell_platform: string;
  case_theme: string | null;
  created_at: string;
}

interface RetrainStatus {
  checkpoint: string;
  sold_flips_since: number;
  retrain_ready: boolean;
  last_flip_id: number;
  updated_at: string | null;
}
interface ModelVersionRow { version: string; status: string; score_profit_mae?: number; score_roi_mae?: number; trained_on_samples?: number; created_at?: string }
interface TrainingRunRow { status: string; started_at?: string; finished_at?: string; message?: string; version_produced?: string }

const CHART_COLORS = ["#00dc82", "#22d3ee", "#a78bfa", "#f59e0b", "#f43f5e", "#10b981"];

function StatCard({ label, value, sub, icon, color }: { label: string; value: string; sub: string; icon: React.ReactNode; color: string }) {
  return (
    <Card>
      <CardContent className="pt-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">{label}</span>
          <div className={`${color} opacity-60`}>{icon}</div>
        </div>
        <div className={`text-2xl font-bold ${color}`}>{value}</div>
        <div className="text-xs text-slate-600 mt-1">{sub}</div>
      </CardContent>
    </Card>
  );
}

function ConfidenceDot({ confidence }: { confidence: number }) {
  const color = confidence >= 0.8 ? "bg-[#00dc82]" : confidence >= 0.6 ? "bg-yellow-400" : "bg-slate-500";
  const label = confidence >= 0.8 ? "High" : confidence >= 0.6 ? "Medium" : "Low";
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold ${color} text-[#080c14]`}>
      {label}
    </span>
  );
}

export default function IntelPage() {
  const [summary, setSummary] = useState<IntelSummary | null>(null);
  const [bySource, setBySource] = useState<BreakdownRow[]>([]);
  const [byCpu, setByCpu] = useState<BreakdownRow[]>([]);
  const [byPlatform, setByPlatform] = useState<BreakdownRow[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [retrain, setRetrain] = useState<RetrainStatus | null>(null);
  const [externalDemand, setExternalDemand] = useState<Record<string, { count: number; avg_score: number; avg_confidence: number }>>({});
  const [multipliers, setMultipliers] = useState<Record<string, number>>({});
  const [modelVersions, setModelVersions] = useState<ModelVersionRow[]>([]);
  const [trainingRuns, setTrainingRuns] = useState<TrainingRunRow[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [sum, src, cpu, plat, recs, hist, retrainStatus, ext, mult, versions, runs] = await Promise.all([
        api.intel.summary(),
        api.intel.bySource(),
        api.intel.byCpuTier(),
        api.intel.byPlatform(),
        api.intel.recommendations(),
        api.intel.history({ limit: "20" }),
        api.intel.retrainStatus(),
        api.demand.externalSignals(12),
        api.demand.pricingMultipliers(),
        api.intel.modelVersions(6),
        api.intel.modelRuns(6),
      ]);
      setSummary(sum);
      setBySource(src as BreakdownRow[]);
      setByCpu(cpu as BreakdownRow[]);
      setByPlatform(plat as BreakdownRow[]);
      setRecommendations(recs as Recommendation[]);
      setHistory(hist as HistoryEntry[]);
      setRetrain(retrainStatus as RetrainStatus);
      setExternalDemand((ext as { summary: Record<string, { count: number; avg_score: number; avg_confidence: number }> }).summary || {});
      setMultipliers((mult as { multipliers: Record<string, number> }).multipliers || {});
      setModelVersions(((versions as { items: ModelVersionRow[] }).items || []));
      setTrainingRuns(((runs as { items: TrainingRunRow[] }).items || []));
    } catch {
      setSummary(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const id = setTimeout(() => { void load(); }, 0);
    return () => clearTimeout(id);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-slate-500 text-sm gap-2">
        <RefreshCw className="w-4 h-4 animate-spin" /> Loading intelligence data…
      </div>
    );
  }

  const noData = !summary || summary.total_flips === 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[var(--nf-primary)] font-mono tracking-wider uppercase flex items-center gap-2">
            <Brain className="w-5 h-5 text-[var(--nf-primary)]" /> Analytics
          </h1>
          <p className="text-sm text-[var(--nf-text-muted)] mt-0.5 font-mono">
            Learn from every flip — profit patterns, best sources, timing, and AI-driven recommendations
          </p>
        </div>
        <Button variant="secondary" size="sm" onClick={load}>
          <RefreshCw className="w-3.5 h-3.5" /> Refresh
        </Button>
      </div>

      {noData ? (
        <EmptyState
          icon={Brain}
          title="No flip history yet"
          description='Complete your first flip and mark it as sold — the intelligence engine learns from every transaction. The more flips you complete, the better its recommendations become.'
        />
      ) : (
        <>
          {/* Stats */}
          <div className="grid grid-cols-2 lg:grid-cols-4 xl:grid-cols-8 gap-4">
            <StatCard label="Total Flips" value={(summary?.total_flips ?? 0).toString()} sub="completed" icon={<Gem className="w-4 h-4" />} color="text-slate-300" />
            <StatCard label="Total Profit" value={formatCurrency(summary?.total_profit ?? 0)} sub="all time" icon={<TrendingUp className="w-4 h-4" />} color="text-[#00dc82]" />
            <StatCard label="Avg Profit" value={formatCurrency(summary?.avg_profit ?? 0)} sub="per flip" icon={<Award className="w-4 h-4" />} color="text-[#00dc82]" />
            <StatCard label="Avg ROI" value={`${(summary?.avg_roi_pct ?? 0).toFixed(1)}%`} sub="return on cost" icon={<BarChart3 className="w-4 h-4" />} color="text-cyan-400" />
            <StatCard label="Avg Days to Sell" value={(summary?.avg_days_to_sell ?? 0).toFixed(1)} sub="listing → sold" icon={<Clock className="w-4 h-4" />} color="text-yellow-400" />
            <StatCard
              label="Best Source"
              value={summary?.best_source ?? "—"}
              sub="highest avg profit"
              icon={<Zap className="w-4 h-4" />}
              color="text-purple-400"
            />
            <StatCard
              label="Retrain Status"
              value={retrain?.retrain_ready ? "READY" : "Collecting"}
              sub={`${retrain?.sold_flips_since ?? 0} sold since checkpoint`}
              icon={<Brain className="w-4 h-4" />}
              color={retrain?.retrain_ready ? "text-emerald-400" : "text-slate-300"}
            />
            <StatCard
              label="AM5 Multiplier"
              value={`${((multipliers.motherboard_am5 ?? 1) * 100).toFixed(0)}%`}
              sub="demand-adjusted pricing"
              icon={<TrendingUp className="w-4 h-4" />}
              color="text-cyan-400"
            />
          </div>

          {/* External signal pulse */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="w-3.5 h-3.5 text-cyan-400" /> External Demand Signals
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {Object.entries(externalDemand).length === 0 ? (
                  <div className="text-xs text-slate-600">No external signals yet.</div>
                ) : (
                  Object.entries(externalDemand).map(([source, s]) => (
                    <div key={source} className="rounded-lg border border-[#1e2d45] bg-[#0a1119] p-3">
                      <div className="text-xs uppercase tracking-wider text-slate-500">{source.replace("_", " ")}</div>
                      <div className="text-lg font-semibold text-slate-200 mt-1">{s.count} signals</div>
                      <div className="text-xs text-slate-500 mt-1">score {s.avg_score.toFixed(1)} · conf {(s.avg_confidence * 100).toFixed(0)}%</div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="w-3.5 h-3.5 text-emerald-400" /> Model Registry
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <div className="rounded-lg border border-[#1e2d45] bg-[#0a1119] p-3">
                  <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">Recent Versions</div>
                  {modelVersions.length === 0 ? <div className="text-xs text-slate-600">No versions yet</div> : modelVersions.map((v) => (
                    <div key={v.version} className="text-xs text-slate-300 flex items-center justify-between py-1 border-b border-[#142033] last:border-0">
                      <span>{v.version} · {v.status}</span>
                      <span className="text-slate-500">MAE £{(v.score_profit_mae ?? 0).toFixed(1)}</span>
                    </div>
                  ))}
                </div>
                <div className="rounded-lg border border-[#1e2d45] bg-[#0a1119] p-3">
                  <div className="text-xs uppercase tracking-wider text-slate-500 mb-2">Recent Training Runs</div>
                  {trainingRuns.length === 0 ? <div className="text-xs text-slate-600">No runs yet</div> : trainingRuns.map((r, idx) => (
                    <div key={`${r.started_at ?? "run"}-${idx}`} className="text-xs text-slate-300 py-1 border-b border-[#142033] last:border-0">
                      <div>{r.status} {r.version_produced ? `· ${r.version_produced}` : ""}</div>
                      <div className="text-slate-500">{r.message || "—"}</div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Charts row */}
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2"><BarChart3 className="w-3.5 h-3.5 text-[#00dc82]" /> Profit by Source</CardTitle></CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={bySource} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" />
                    <XAxis dataKey="source" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={{ stroke: "#1e2d45" }} tickLine={false} />
                    <YAxis tickFormatter={v => `£${v}`} tick={{ fill: "#64748b", fontSize: 10 }} axisLine={{ stroke: "#1e2d45" }} tickLine={false} />
                    <Tooltip
                      contentStyle={{ background: "#0d1320", border: "1px solid #1e2d45", borderRadius: 8 }}
                      labelStyle={{ color: "#94a3b8" }}
                      formatter={(v) => [formatCurrency(Number(v ?? 0)), "Avg Profit"]}
                    />
                    <Bar dataKey="avg_profit" radius={[4, 4, 0, 0]}>
                      {bySource.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2"><BarChart3 className="w-3.5 h-3.5 text-cyan-400" /> Profit by CPU Tier</CardTitle></CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={byCpu} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" />
                    <XAxis dataKey="cpu_tier" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={{ stroke: "#1e2d45" }} tickLine={false} />
                    <YAxis tickFormatter={v => `£${v}`} tick={{ fill: "#64748b", fontSize: 10 }} axisLine={{ stroke: "#1e2d45" }} tickLine={false} />
                    <Tooltip
                      contentStyle={{ background: "#0d1320", border: "1px solid #1e2d45", borderRadius: 8 }}
                      labelStyle={{ color: "#94a3b8" }}
                      formatter={(v) => [formatCurrency(Number(v ?? 0)), "Avg Profit"]}
                    />
                    <Bar dataKey="avg_profit" radius={[4, 4, 0, 0]}>
                      {byCpu.map((_, i) => <Cell key={i} fill={CHART_COLORS[(i + 2) % CHART_COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2"><BarChart3 className="w-3.5 h-3.5 text-purple-400" /> Profit by Sell Platform</CardTitle></CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={byPlatform} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" />
                    <XAxis dataKey="platform" tick={{ fill: "#64748b", fontSize: 10 }} axisLine={{ stroke: "#1e2d45" }} tickLine={false} />
                    <YAxis tickFormatter={v => `£${v}`} tick={{ fill: "#64748b", fontSize: 10 }} axisLine={{ stroke: "#1e2d45" }} tickLine={false} />
                    <Tooltip
                      contentStyle={{ background: "#0d1320", border: "1px solid #1e2d45", borderRadius: 8 }}
                      labelStyle={{ color: "#94a3b8" }}
                      formatter={(v) => [formatCurrency(Number(v ?? 0)), "Avg Profit"]}
                    />
                    <Bar dataKey="avg_profit" radius={[4, 4, 0, 0]}>
                      {byPlatform.map((_, i) => <Cell key={i} fill={CHART_COLORS[(i + 4) % CHART_COLORS.length]} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>

          {/* Recommendations + History */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            {/* AI Recommendations */}
            <Card className="border-cyan-400/15">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Lightbulb className="w-3.5 h-3.5 text-yellow-400" /> Hermes Recommendations
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 pt-0">
                {recommendations.length === 0 ? (
                  <p className="text-sm text-slate-600 text-center py-4">More data needed — complete more flips to unlock recommendations.</p>
                ) : (
                  recommendations.map((rec, i) => (
                    <div key={i} className="p-3 rounded-xl bg-[#0a1119] border border-[#1e2d45] space-y-1.5">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium text-slate-200 leading-snug">{rec.insight}</p>
                        <ConfidenceDot confidence={rec.confidence} />
                      </div>
                      <p className="text-xs text-[#00dc82]">→ {rec.action}</p>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            {/* Recent History */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Clock className="w-3.5 h-3.5 text-slate-400" /> Recent Flip History
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-96 overflow-y-auto">
                  {history.length === 0 ? (
                    <div className="text-xs text-slate-600 col-span-full text-center py-4">No flip history yet</div>
                  ) : (
                    history.map(row => (
                      <div key={row.id} className="p-2.5 rounded-lg bg-[#0a1119] border border-[#1e2d45] hover:border-[#2a4d5d] transition-colors">
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex flex-col gap-0.5">
                            <span className="text-[10px] text-slate-500 uppercase tracking-wider">{row.source_site}</span>
                            <span className="text-xs font-mono text-slate-400">{row.cpu_tier}</span>
                          </div>
                          <span className="text-[10px] text-slate-600 capitalize">{row.sell_platform}</span>
                        </div>
                        <div className="flex items-end justify-between pt-1 border-t border-white/5">
                          <div className="space-y-0.5">
                            <div className="text-[9px] text-slate-600">ROI</div>
                            <div className="text-sm font-semibold text-cyan-400">{row.roi_pct.toFixed(1)}%</div>
                          </div>
                          <div className="space-y-0.5">
                            <div className="text-[9px] text-slate-600">Days</div>
                            <div className="text-sm font-semibold text-slate-400">{row.days_to_sell}d</div>
                          </div>
                          <div className="space-y-0.5 text-right">
                            <div className="text-[9px] text-slate-600">Profit</div>
                            <div className={`text-sm font-black ${row.profit > 0 ? "text-[#00dc82]" : "text-red-400"}`}>
                              {row.profit > 0 ? "+" : ""}{formatCurrency(row.profit)}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
