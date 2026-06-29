'use client';

import React, { useState, useEffect } from 'react';
import styles from './metrics.module.css';

interface Metrics {
  total_active: number;
  orders_by_status: Record<string, number>;
  average_build_time_days: number;
  late_orders: number;
  customer_satisfaction_avg: number | null;
}

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchMetrics = async () => {
    try {
      const res = await fetch('/api/admin/metrics');
      const data = await res.json();
      setMetrics(data);
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div className={styles.loading}>Loading metrics...</div>;
  }

  if (!metrics) {
    return <div className={styles.error}>Failed to load metrics</div>;
  }

  const statusOrder = [
    'awaiting_sourcing',
    'parts_ordered',
    'building',
    'qa',
    'ready_to_ship',
    'shipped',
    'completed',
  ];

  const statusLabels: Record<string, string> = {
    awaiting_sourcing: 'Awaiting Sourcing',
    parts_ordered: 'Parts Ordered',
    building: 'Building',
    qa: 'QA',
    ready_to_ship: 'Ready to Ship',
    shipped: 'Shipped',
    completed: 'Completed',
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

  // Calculate percentages for funnel chart
  const totalOrders = Object.values(metrics.orders_by_status).reduce(
    (sum, count) => sum + count,
    0
  );

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1>Admin Metrics Dashboard</h1>
        <p>Key performance indicators for order management</p>
      </div>

      <div className={styles.kpiGrid}>
        <div className={styles.kpiCard}>
          <h3>Active Orders</h3>
          <p className={styles.kpiValue}>{metrics.total_active}</p>
          <span className={styles.kpiLabel}>Currently in progress</span>
        </div>

        <div className={styles.kpiCard}>
          <h3>Avg Build Time</h3>
          <p className={styles.kpiValue}>{metrics.average_build_time_days.toFixed(1)}</p>
          <span className={styles.kpiLabel}>days from order to delivery</span>
        </div>

        <div className={styles.kpiCard}>
          <h3>Late Orders</h3>
          <p className={styles.kpiValue + ' ' + (metrics.late_orders > 0 ? styles.warning : '')}>
            {metrics.late_orders}
          </p>
          <span className={styles.kpiLabel}>beyond 14-day SLA</span>
        </div>

        <div className={styles.kpiCard}>
          <h3>Satisfaction Rating</h3>
          <p className={styles.kpiValue}>
            {metrics.customer_satisfaction_avg
              ? metrics.customer_satisfaction_avg.toFixed(1)
              : '—'}
          </p>
          <span className={styles.kpiLabel}>avg customer rating</span>
        </div>
      </div>

      <div className={styles.chartsGrid}>
        <div className={styles.chart}>
          <h2>Order Status Distribution</h2>
          <div className={styles.statusBars}>
            {statusOrder.map((status) => {
              const count = metrics.orders_by_status[status] || 0;
              const percentage = totalOrders > 0 ? (count / totalOrders) * 100 : 0;
              return (
                <div key={status} className={styles.barItem}>
                  <div className={styles.barLabel}>
                    <span className={styles.statusName}>{statusLabels[status]}</span>
                    <span className={styles.barCount}>{count}</span>
                  </div>
                  <div className={styles.barContainer}>
                    <div
                      className={styles.bar}
                      style={{
                        width: `${percentage}%`,
                        backgroundColor: statusColors[status],
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className={styles.chart}>
          <h2>Order Pipeline Funnel</h2>
          <div className={styles.funnel}>
            {statusOrder.map((status, index) => {
              const count = metrics.orders_by_status[status] || 0;
              const width = 100 - index * (100 / statusOrder.length);
              return (
                <div
                  key={status}
                  className={styles.funnelSegment}
                  style={{
                    width: `${width}%`,
                    backgroundColor: statusColors[status],
                  }}
                >
                  <span className={styles.funnelLabel}>
                    {statusLabels[status]} ({count})
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className={styles.summaryTable}>
        <h2>Detailed Status Breakdown</h2>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Status</th>
              <th>Count</th>
              <th>Percentage</th>
            </tr>
          </thead>
          <tbody>
            {statusOrder.map((status) => {
              const count = metrics.orders_by_status[status] || 0;
              const percentage = totalOrders > 0 ? ((count / totalOrders) * 100).toFixed(1) : '0';
              return (
                <tr key={status}>
                  <td>
                    <span
                      className={styles.statusDot}
                      style={{ backgroundColor: statusColors[status] }}
                    />
                    {statusLabels[status]}
                  </td>
                  <td className={styles.centerText}>{count}</td>
                  <td className={styles.centerText}>{percentage}%</td>
                </tr>
              );
            })}
            <tr className={styles.totalRow}>
              <td>Total</td>
              <td className={styles.centerText}>{totalOrders}</td>
              <td className={styles.centerText}>100%</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className={styles.alerts}>
        {metrics.late_orders > 0 && (
          <div className={styles.alertBox + ' ' + styles.warning}>
            <span className={styles.alertIcon}>⚠️</span>
            <div>
              <p className={styles.alertTitle}>Late Orders Alert</p>
              <p className={styles.alertText}>
                {metrics.late_orders} order{metrics.late_orders !== 1 ? 's' : ''} are
                beyond the 14-day SLA. Review and prioritize these builds.
              </p>
            </div>
          </div>
        )}

        {metrics.total_active === 0 && (
          <div className={styles.alertBox + ' ' + styles.info}>
            <span className={styles.alertIcon}>ℹ️</span>
            <div>
              <p className={styles.alertTitle}>No Active Orders</p>
              <p className={styles.alertText}>
                All orders have been completed. Great work!
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
