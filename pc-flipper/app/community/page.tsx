"use client";

import { useEffect, useRef, useState } from "react";
import { ExternalLink, RefreshCw, Rss } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

interface FeedPost {
  subreddit: string;
  id: string;
  title: string;
  url: string;
  flair: string;
  created_utc: number;
  selftext: string;
}

const SUBREDDIT_COLORS: Record<string, string> = {
  PCBuildsUK:  "#00dc82",
  HotUKDeals:  "#f59e0b",
};

function timeAgo(ts: number): string {
  if (!ts) return "—";
  const diff = Math.floor(Date.now() / 1000) - ts;
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function stripHtml(s: string): string {
  return s.replace(/<[^>]*>/g, "").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&#39;/g, "'").replace(/&quot;/g, '"').trim();
}

function PostCard({ post }: { post: FeedPost }) {
  const color = SUBREDDIT_COLORS[post.subreddit] ?? "#94a3b8";
  const snippet = stripHtml(post.selftext).slice(0, 160);

  return (
    <a
      href={post.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-xl border border-white/8 bg-white/3 hover:bg-white/6 hover:border-white/15 transition-all p-4 group"
    >
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span
              className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded"
              style={{ color, background: `${color}20` }}
            >
              r/{post.subreddit}
            </span>
            {post.flair && (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/60 text-slate-400 font-medium">
                {post.flair}
              </span>
            )}
            <span className="text-[10px] text-slate-500 ml-auto">{timeAgo(post.created_utc)}</span>
          </div>
          <p className="text-sm font-medium text-slate-100 leading-snug group-hover:text-white transition-colors line-clamp-2">
            {post.title}
          </p>
          {snippet && (
            <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">{snippet}</p>
          )}
        </div>
        <ExternalLink className="h-3.5 w-3.5 text-slate-600 group-hover:text-slate-400 shrink-0 mt-0.5 transition-colors" />
      </div>
    </a>
  );
}

export default function CommunityPage() {
  const [posts, setPosts] = useState<FeedPost[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = async () => {
    try {
      const resp = await fetch(`${API_BASE_URL}/ram-watch/community-feed`);
      if (resp.ok) {
        const data: FeedPost[] = await resp.json();
        setPosts(data);
        setLastRefresh(new Date());
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    intervalRef.current = setInterval(() => { void load(); }, 5 * 60 * 1000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, []);

  const subreddits = ["all", ...Array.from(new Set(posts.map(p => p.subreddit)))];
  const visible = filter === "all" ? posts : posts.filter(p => p.subreddit === filter);

  return (
    <div className="p-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Rss className="h-5 w-5 text-[#00dc82]" />
          <div>
            <h1 className="text-xl font-bold text-white">Community Feed</h1>
            <p className="text-xs text-slate-500 mt-0.5">
              r/PCBuildsUK · r/HotUKDeals — refreshes every 15 min
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-[11px] text-slate-500">
              Updated {timeAgo(Math.floor(lastRefresh.getTime() / 1000))}
            </span>
          )}
          <button
            onClick={() => { setLoading(true); void load(); }}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-slate-400 hover:text-white hover:border-white/20 transition-all disabled:opacity-40"
          >
            <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Subreddit filter pills */}
      <div className="flex gap-2 mb-5 flex-wrap">
        {subreddits.map(sub => {
          const color = sub === "all" ? "#94a3b8" : (SUBREDDIT_COLORS[sub] ?? "#94a3b8");
          const active = filter === sub;
          return (
            <button
              key={sub}
              onClick={() => setFilter(sub)}
              className="px-3 py-1 rounded-full text-xs font-medium transition-all border"
              style={
                active
                  ? { background: `${color}25`, borderColor: `${color}60`, color }
                  : { background: "transparent", borderColor: "rgba(255,255,255,0.1)", color: "#64748b" }
              }
            >
              {sub === "all" ? "All" : `r/${sub}`}
              {sub !== "all" && (
                <span className="ml-1.5 opacity-60">
                  {posts.filter(p => p.subreddit === sub).length}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Feed */}
      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-20 rounded-xl bg-white/4 animate-pulse" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <div className="text-center py-16 text-slate-500 text-sm">
          No posts loaded yet — Reddit RSS may be rate-limited. Try refreshing in a moment.
        </div>
      ) : (
        <div className="space-y-2.5">
          {visible.map(post => (
            <PostCard key={`${post.subreddit}-${post.id}`} post={post} />
          ))}
        </div>
      )}
    </div>
  );
}
