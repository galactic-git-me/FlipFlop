'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
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
}

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);

  const pageSize = 50;

  useEffect(() => {
    fetchOrders();
  }, [statusFilter, page]);

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

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1>Order Priority Queue</h1>
        <p>Active orders by delivery commitment. Pre-built ties use customer spend; curated and custom ties use component arrival, then spend.</p>
      </div>

      <div className={styles.controls}>
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

      </div>

      {loading ? (
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
      )}
    </div>
  );
}
