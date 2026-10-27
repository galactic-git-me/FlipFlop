'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { CalendarDays, ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import styles from './orders.module.css';

interface Order {
  id: number;
  order_id: string;
  customer_name: string;
  status: string;
  customer_price: number;
  days_elapsed: number;
  created_at: string;
  priority_kind: 'prebuilt_fast_track' | 'prebuilt_standard' | 'build_fast_track' | 'build_normal' | 'build_flexible';
  components_ready_at: string | null;
  promised_delivery_date: string | null;
  delivery_option: 'fast_track' | 'standard' | 'flexible' | string;
  channel: string;
}

interface CalendarEntry {
  key: string;
  kind: 'customer_build' | 'channel_dispatch';
  id: number;
  reference: string;
  customer: string;
  channel: string;
  status: string;
  delivery_option: string;
  priority_kind: string;
  priority_rank: number;
  due_date: string | null;
  due_label: string;
  components_ready_date: string | null;
  date_evidence: string | null;
  href: string;
}

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [view, setView] = useState<'calendar' | 'queue'>('calendar');
  const [calendarEntries, setCalendarEntries] = useState<CalendarEntry[]>([]);
  const [calendarLoading, setCalendarLoading] = useState(true);
  const [calendarError, setCalendarError] = useState<string | null>(null);
  const [weekStart, setWeekStart] = useState(() => mondayOf(new Date()));
  const [calendarAsOf, setCalendarAsOf] = useState<string | null>(null);

  const pageSize = 50;

  useEffect(() => {
    fetchOrders();
  }, [statusFilter, page]);

  useEffect(() => {
    void fetchCalendar();
    const interval = window.setInterval(() => void fetchCalendar(), 60_000);
    return () => window.clearInterval(interval);
  }, [weekStart]);

  const fetchCalendar = async () => {
    setCalendarLoading(true);
    setCalendarError(null);
    try {
      const params = new URLSearchParams({ start_date: weekStart, days: '7' });
      const response = await fetch(`/proxy-api/admin/workshop-calendar?${params}`);
      if (!response.ok) throw new Error(`Could not load the workshop calendar (${response.status})`);
      const data = await response.json() as { entries: CalendarEntry[]; as_of: string };
      setCalendarEntries(data.entries ?? []);
      setCalendarAsOf(data.as_of);
    } catch (error) {
      setCalendarError(error instanceof Error ? error.message : 'Could not load the workshop calendar');
    } finally {
      setCalendarLoading(false);
    }
  };

  const fetchOrders = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      params.append('skip', String(page * pageSize));
      params.append('limit', String(pageSize));

      const res = await fetch(`/proxy-api/admin/order-priority?${params}`);
      if (!res.ok) throw new Error(`Could not load the order queue (${res.status})`);
      const data = await res.json();
      setOrders(data.orders);
      setTotal(data.total);
    } catch (error) {
      console.error('Failed to fetch orders:', error);
      setError(error instanceof Error ? error.message : 'Could not load the order queue');
    } finally {
      setLoading(false);
    }
  };

  const previewPortal = async (orderId: number) => {
    const response = await fetch(`/api/admin/orders/${orderId}/portal-preview`, { method: 'POST' });
    if (!response.ok) { window.alert('Could not create a portal preview.'); return; }
    const payload = await response.json() as { token: string };
    window.open(`https://theflipflop.shop/my-builds/${orderId}?preview=${encodeURIComponent(payload.token)}`, '_blank', 'noopener,noreferrer');
  };

  const statusColors: Record<string, string> = {
    awaiting_sourcing: '#fbbf24',
    parts_ordered: '#3b82f6',
    building: '#8b5cf6',
    qa: '#ec4899',
    ready_to_ship: '#10b981',
    shipped: '#06b6d4',
    completed: '#6b7280',
  };

  const formatStatus = (status: string) => {
    return status
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  const priorityLabels = {
    prebuilt_fast_track: '1 · Pre-built Fast Track',
    prebuilt_standard: '2 · Pre-built Standard',
    build_fast_track: '3 · Curated / Custom Fast Track',
    build_normal: '4 · Curated / Custom Normal',
    build_flexible: '5 · Curated / Custom Flexible',
  };

  const weekDays = Array.from({ length: 7 }, (_, index) => addDays(weekStart, index));
  const weekEnd = weekDays[6];
  const overdueEntries = calendarEntries.filter(entry => entry.due_date && entry.due_date < weekStart);
  const unscheduledEntries = calendarEntries.filter(entry => !entry.due_date);
  const deliveryLabels: Record<string, string> = {
    fast_track: 'Fast Track', standard: 'Standard', flexible: 'Flexible', marketplace_dispatch: 'Channel dispatch',
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1>{view === 'calendar' ? 'Workshop Calendar' : 'Order Priority Queue'}</h1>
        <p>{view === 'calendar' ? 'Daily work focus from paid delivery promises and confirmed channel ship-by dates. Orders remain sellable; this calendar helps you choose what to work on.' : 'Active orders by delivery commitment. Pre-built ties use customer spend; curated and custom ties use component arrival, then spend.'}</p>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setView('calendar')} className={`rounded-lg border px-3 py-2 text-sm font-semibold ${view === 'calendar' ? 'border-cyan-300 bg-cyan-300 text-slate-950' : 'border-slate-300 bg-white text-slate-700'}`}><CalendarDays className="mr-2 inline h-4 w-4" />Calendar</button>
          <button type="button" onClick={() => setView('queue')} className={`rounded-lg border px-3 py-2 text-sm font-semibold ${view === 'queue' ? 'border-cyan-300 bg-cyan-300 text-slate-950' : 'border-slate-300 bg-white text-slate-700'}`}>Priority queue</button>
        </div>
      </div>

      {view === 'calendar' && (
        <section className="mb-6 rounded-xl border border-slate-700 bg-slate-950/70 p-4 text-slate-100" aria-label="Workshop calendar">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">{formatDate(weekStart)} – {formatDate(weekEnd)}</h2>
              <p className="mt-1 text-xs text-slate-400">Sorted by deadline, then paid delivery priority and parts readiness. Refreshes every minute{calendarAsOf ? ` · updated ${new Date(calendarAsOf).toLocaleTimeString('en-GB')}` : ''}.</p>
            </div>
            <div className="flex items-center gap-2">
              <button type="button" aria-label="Previous week" onClick={() => setWeekStart(addDays(weekStart, -7))} className="rounded border border-slate-600 p-2 hover:bg-white/10"><ChevronLeft className="h-4 w-4" /></button>
              <button type="button" onClick={() => setWeekStart(mondayOf(new Date()))} className="rounded border border-slate-600 px-3 py-2 text-xs font-semibold hover:bg-white/10">This week</button>
              <button type="button" aria-label="Next week" onClick={() => setWeekStart(addDays(weekStart, 7))} className="rounded border border-slate-600 p-2 hover:bg-white/10"><ChevronRight className="h-4 w-4" /></button>
              <button type="button" aria-label="Refresh calendar" onClick={() => void fetchCalendar()} disabled={calendarLoading} className="rounded border border-slate-600 p-2 hover:bg-white/10 disabled:opacity-50"><RefreshCw className={`h-4 w-4 ${calendarLoading ? 'animate-spin' : ''}`} /></button>
            </div>
          </div>
          {calendarError && <p role="alert" className="mb-3 rounded border border-rose-400/30 bg-rose-400/10 p-3 text-sm text-rose-200">{calendarError}</p>}
          {calendarLoading && calendarEntries.length === 0 ? <p className="py-8 text-center text-sm text-slate-400">Loading live workshop commitments…</p> : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-7">
              {weekDays.map(day => {
                const dayEntries = calendarEntries.filter(entry => entry.due_date === day);
                const today = day === localDate(new Date());
                return <div key={day} className={`min-h-48 rounded-lg border p-3 ${today ? 'border-cyan-300/70 bg-cyan-300/[.06]' : 'border-slate-800 bg-black/20'}`}>
                  <h3 className={`text-sm font-bold ${today ? 'text-cyan-200' : 'text-slate-200'}`}>{formatDate(day)}{today && <span className="ml-2 text-[10px] uppercase tracking-wider text-cyan-300">Today</span>}</h3>
                  <div className="mt-3 space-y-2">
                    {dayEntries.length === 0 ? <p className="py-3 text-xs text-slate-600">No due commitments</p> : dayEntries.map(entry => (
                      <Link key={entry.key} href={entry.href} className="block rounded-md border border-slate-700 bg-slate-900 p-2.5 transition hover:border-cyan-300/50 hover:bg-slate-800">
                        <div className="flex items-start justify-between gap-2"><span className="text-xs font-bold text-white">{entry.reference}</span><span className="rounded bg-cyan-300/10 px-1.5 py-0.5 text-[9px] font-bold uppercase text-cyan-200">{deliveryLabels[entry.delivery_option] ?? entry.delivery_option}</span></div>
                        <p className="mt-1 truncate text-[11px] text-slate-300">{entry.customer}</p>
                        <p className="mt-1 text-[10px] text-amber-200">{entry.due_label} · {entry.channel}</p>
                        <p className="mt-1 text-[10px] capitalize text-slate-500">{entry.status.replaceAll('_', ' ')}</p>
                        {entry.components_ready_date && <p className="mt-1 text-[10px] text-slate-400">Parts ready {formatDate(entry.components_ready_date)}</p>}
                      </Link>
                    ))}
                  </div>
                </div>;
              })}
            </div>
          )}
          {(overdueEntries.length > 0 || unscheduledEntries.length > 0) && <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {overdueEntries.length > 0 && <div className="rounded-lg border border-rose-400/30 bg-rose-400/[.06] p-3"><h3 className="text-sm font-bold text-rose-200">Past due · {overdueEntries.length}</h3><div className="mt-2 space-y-2">{overdueEntries.map(entry => <CalendarException key={entry.key} entry={entry} label={`Due ${formatDate(entry.due_date!)}`} />)}</div></div>}
            {unscheduledEntries.length > 0 && <div className="rounded-lg border border-amber-400/30 bg-amber-400/[.05] p-3"><h3 className="text-sm font-bold text-amber-100">Deadline needs syncing · {unscheduledEntries.length}</h3><p className="mt-1 text-[11px] text-slate-400">These orders have no confirmed delivery or channel ship-by date in FlipFlop.</p><div className="mt-2 space-y-2">{unscheduledEntries.map(entry => <CalendarException key={entry.key} entry={entry} label={entry.due_label} />)}</div></div>}
          </div>}
        </section>
      )}

      {view === 'queue' && <div className={styles.controls}>
        <div className={styles.filterGroup}>
          <label htmlFor="status-filter">Status:</label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(0);
            }}
          >
            <option value="">All Status</option>
            <option value="awaiting_sourcing">Awaiting Sourcing</option>
            <option value="parts_ordered">Parts Ordered</option>
            <option value="building">Building</option>
            <option value="qa">QA</option>
            <option value="ready_to_ship">Ready to Ship</option>
            <option value="shipped">Shipped</option>
            <option value="completed">Completed</option>
          </select>
        </div>

      </div>}

      {view === 'queue' && (
      loading ? (
        <div className={styles.loading}>Loading orders...</div>
      ) : error ? (
        <div className={styles.loading} role="alert">{error}</div>
      ) : (
        <>
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Order #</th>
                  <th>Customer</th>
                  <th>Priority</th>
                  <th>Components ready</th>
                  <th>Status</th>
                  <th>Price</th>
                  <th>Days Elapsed</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => (
                  <tr key={order.id}>
                    <td className={styles.orderId}>#{order.order_id}</td>
                    <td>{order.customer_name}</td>
                    <td>
                      <span className={`${styles.priorityBadge} ${styles[order.priority_kind]}`}>
                        {priorityLabels[order.priority_kind]}
                      </span>
                    </td>
                    <td>{order.priority_kind.startsWith('prebuilt') ? 'Ready' : order.components_ready_at ? new Date(order.components_ready_at).toLocaleDateString('en-GB') : 'ETA unknown'}</td>
                    <td>
                      <span
                        className={styles.statusBadge}
                        style={{
                          backgroundColor:
                            statusColors[order.status] || '#9ca3af',
                        }}
                      >
                        {formatStatus(order.status)}
                      </span>
                    </td>
                    <td className={styles.price}>£{order.customer_price.toFixed(2)}</td>
                    <td className={styles.daysElapsed}>{order.days_elapsed}d</td>
                    <td>
                      <Link
                        href={`/orders/${order.id}`}
                        className={styles.actionBtn}
                      >
                        View Details
                      </Link>
                      <button type="button" onClick={() => void previewPortal(order.id)} className={styles.actionBtn} style={{ marginLeft: 8 }}>
                        View Portal
                      </button>
                    </td>
                  </tr>
                ))}
                {orders.length === 0 && (
                  <tr><td colSpan={8} className={styles.emptyState}>No active orders match this filter.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className={styles.pagination}>
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className={styles.paginationBtn}
            >
              Previous
            </button>
            <span className={styles.pageInfo}>
              Page {page + 1} of {Math.max(1, Math.ceil(total / pageSize))} ({total} total)
            </span>
            <button
              onClick={() =>
                setPage(
                  Math.min(
                    Math.ceil(total / pageSize) - 1,
                    page + 1
                  )
                )
              }
              disabled={page >= Math.ceil(total / pageSize) - 1}
              className={styles.paginationBtn}
            >
              Next
            </button>
          </div>
        </>
      )
      )}
    </div>
  );
}

function CalendarException({ entry, label }: { entry: CalendarEntry; label: string }) {
  return <Link href={entry.href} className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-700 bg-slate-950/50 px-3 py-2 text-xs hover:border-cyan-300/50"><span><strong>{entry.reference}</strong> · {entry.customer} · {entry.channel}</span><span className="font-semibold text-slate-300">{label}</span></Link>;
}

function localDate(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function mondayOf(value: Date) {
  const date = new Date(value.getFullYear(), value.getMonth(), value.getDate());
  date.setDate(date.getDate() - ((date.getDay() + 6) % 7));
  return localDate(date);
}

function addDays(value: string, amount: number) {
  const date = new Date(`${value}T12:00:00`);
  date.setDate(date.getDate() + amount);
  return localDate(date);
}

function formatDate(value: string) {
  return new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
}
