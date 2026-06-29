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
}

export default function OrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [sortBy, setSortBy] = useState<string>('created_at');
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);

  const pageSize = 50;

  useEffect(() => {
    fetchOrders();
  }, [statusFilter, sortBy, page]);

  const fetchOrders = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      params.append('sort_by', sortBy);
      params.append('skip', String(page * pageSize));
      params.append('limit', String(pageSize));

      const res = await fetch(`/api/admin/orders?${params}`);
      const data = await res.json();
      setOrders(data.orders);
      setTotal(data.total);
    } catch (error) {
      console.error('Failed to fetch orders:', error);
    } finally {
      setLoading(false);
    }
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

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1>Order Queue</h1>
        <p>Manage PC builds from sourcing to delivery</p>
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

        <div className={styles.filterGroup}>
          <label htmlFor="sort-by">Sort By:</label>
          <select
            id="sort-by"
            value={sortBy}
            onChange={(e) => {
              setSortBy(e.target.value);
              setPage(0);
            }}
          >
            <option value="created_at">Created Date</option>
            <option value="status">Status</option>
            <option value="customer">Customer Name</option>
            <option value="price">Price (High to Low)</option>
          </select>
        </div>
      </div>

      {loading ? (
        <div className={styles.loading}>Loading orders...</div>
      ) : (
        <>
          <div className={styles.tableWrapper}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Order #</th>
                  <th>Customer</th>
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
                    </td>
                  </tr>
                ))}
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
              Page {page + 1} of {Math.ceil(total / pageSize)} ({total} total)
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
