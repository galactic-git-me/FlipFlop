'use client';

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import styles from './order-detail.module.css';

interface OrderDetail {
  order: {
    id: number;
    order_id: string;
    customer_name: string;
    customer_email: string;
    status: string;
    customer_price: number;
    component_costs: number;
    profit: number;
    promised_delivery_date: string;
    actual_delivery_date: string | null;
    created_at: string;
    sourcing_started_at: string | null;
    sourcing_approved_at: string | null;
    building_started_at: string | null;
    building_completed_at: string | null;
    qa_started_at: string | null;
    qa_passed_at: string | null;
    shipped_at: string | null;
    delivered_at: string | null;
    tracking_number: string | null;
    carrier: string | null;
    estimated_delivery: string | null;
  };
  checklist: {
    build: Array<{ item: string; completed: boolean; notes: string | null; updated_at: string | null }>;
    qa: Array<{ item: string; completed: boolean; notes: string | null; updated_at: string | null }>;
  };
  photos: Array<{ id: number; stage: string; photo_url: string; notes: string | null; created_at: string }>;
}

type TabType = 'overview' | 'sourcing' | 'build' | 'qa' | 'shipping';

const DEFAULT_BUILD_CHECKLIST = [
  'Parts received & checked',
  'CPU installed',
  'GPU installed',
  'RAM installed',
  'SSD installed',
  'Cooler installed',
  'Cables managed',
  'First power-on test',
];

const DEFAULT_QA_CHECKLIST = [
  'Boot test (Windows/Linux)',
  'BIOS version check',
  'RAM test (MemTest86)',
  'GPU stress test (3DMark)',
  'Storage test (CrystalDiskInfo)',
  'Temperature monitoring (30 min idle, 10 min load)',
  'Package & padding inspect',
  'All cables included',
  'Welcome guide printed',
  'License key enclosed',
];

export default function OrderDetailPage() {
  const params = useParams();
  const orderId = params.id as string;

  const [order, setOrder] = useState<OrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    fetchOrder();
  }, [orderId]);

  const fetchOrder = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/orders/${orderId}`);
      const data = await res.json();
      setOrder(data);
    } catch (error) {
      console.error('Failed to fetch order:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!order) return;
    setUpdating(true);
    try {
      const res = await fetch(`/api/admin/orders/${order.order.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });

      if (res.ok) {
        await fetchOrder();
      }
    } catch (error) {
      console.error('Failed to update status:', error);
    } finally {
      setUpdating(false);
    }
  };

  const handleChecklistUpdate = async (
    section: 'build' | 'qa',
    item: string,
    completed: boolean,
    notes?: string
  ) => {
    if (!order) return;
    setUpdating(true);
    try {
      const res = await fetch(`/api/admin/orders/${order.order.id}/checklist/${section}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item, completed, notes: notes || null }),
      });

      if (res.ok) {
        await fetchOrder();
      }
    } catch (error) {
      console.error('Failed to update checklist:', error);
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return <div className={styles.loading}>Loading order details...</div>;
  }

  if (!order) {
    return <div className={styles.error}>Order not found</div>;
  }

  const { order: o, checklist, photos } = order;

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <h1>Order #{o.order_id}</h1>
          <p>{o.customer_name} ({o.customer_email})</p>
        </div>
        <div className={styles.headerStats}>
          <div className={styles.stat}>
            <span className={styles.label}>Total Price</span>
            <span className={styles.value}>£{o.customer_price.toFixed(2)}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.label}>Profit</span>
            <span className={styles.value}>£{(o.profit || 0).toFixed(2)}</span>
          </div>
          <div className={styles.stat}>
            <span className={styles.label}>Status</span>
            <span className={styles.statusBadge}>{formatStatus(o.status)}</span>
          </div>
        </div>
      </div>

      <div className={styles.tabs}>
        {(['overview', 'sourcing', 'build', 'qa', 'shipping'] as TabType[]).map((tab) => (
          <button
            key={tab}
            className={`${styles.tab} ${activeTab === tab ? styles.active : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {formatTab(tab)}
          </button>
        ))}
      </div>

      <div className={styles.content}>
        {activeTab === 'overview' && (
          <div className={styles.section}>
            <h2>Order Overview</h2>
            <div className={styles.grid}>
              <div className={styles.gridItem}>
                <label>Customer Name</label>
                <p>{o.customer_name}</p>
              </div>
              <div className={styles.gridItem}>
                <label>Customer Email</label>
                <p>{o.customer_email}</p>
              </div>
              <div className={styles.gridItem}>
                <label>Current Status</label>
                <select
                  value={o.status}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  disabled={updating}
                  className={styles.select}
                >
                  <option value="awaiting_sourcing">Awaiting Sourcing</option>
                  <option value="parts_ordered">Parts Ordered</option>
                  <option value="building">Building</option>
                  <option value="qa">QA</option>
                  <option value="ready_to_ship">Ready to Ship</option>
                  <option value="shipped">Shipped</option>
                  <option value="completed">Completed</option>
                </select>
              </div>
              <div className={styles.gridItem}>
                <label>Order Date</label>
                <p>{new Date(o.created_at).toLocaleDateString()}</p>
              </div>
              <div className={styles.gridItem}>
                <label>Promised Delivery</label>
                <p>{new Date(o.promised_delivery_date).toLocaleDateString()}</p>
              </div>
              <div className={styles.gridItem}>
                <label>Actual Delivery</label>
                <p>{o.actual_delivery_date ? new Date(o.actual_delivery_date).toLocaleDateString() : 'Not yet'}</p>
              </div>
            </div>

            <div className={styles.timeline}>
              <h3>Order Timeline</h3>
              <div className={styles.timelineItems}>
                {[
                  { label: 'Sourcing Started', date: o.sourcing_started_at },
                  { label: 'Sourcing Approved', date: o.sourcing_approved_at },
                  { label: 'Building Started', date: o.building_started_at },
                  { label: 'Building Completed', date: o.building_completed_at },
                  { label: 'QA Started', date: o.qa_started_at },
                  { label: 'QA Passed', date: o.qa_passed_at },
                  { label: 'Shipped', date: o.shipped_at },
                  { label: 'Delivered', date: o.delivered_at },
                ].map((item) => (
                  <div key={item.label} className={styles.timelineItem}>
                    <span className={styles.timelineLabel}>{item.label}</span>
                    <span className={styles.timelineDate}>
                      {item.date ? new Date(item.date).toLocaleString() : '—'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'sourcing' && (
          <div className={styles.section}>
            <h2>Sourcing Phase</h2>
            <p className={styles.sectionHint}>
              Manage parts ordering and inventory allocation for this build.
            </p>
            {o.sourcing_approved_at ? (
              <div className={styles.alert + ' ' + styles.success}>
                Sourcing completed on {new Date(o.sourcing_approved_at).toLocaleString()}
              </div>
            ) : (
              <div className={styles.alert}>
                <button
                  onClick={() => handleStatusChange('parts_ordered')}
                  disabled={updating}
                  className={styles.button}
                >
                  Approve Sourcing & Start Building
                </button>
              </div>
            )}
          </div>
        )}

        {activeTab === 'build' && (
          <div className={styles.section}>
            <h2>Build Checklist</h2>
            <div className={styles.checklistContainer}>
              {DEFAULT_BUILD_CHECKLIST.map((item) => {
                const checked =
                  checklist.build.find((c) => c.item === item)?.completed ||
                  false;
                const notes =
                  checklist.build.find((c) => c.item === item)?.notes || '';

                return (
                  <div key={item} className={styles.checklistItem}>
                    <label className={styles.checkboxLabel}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) =>
                          handleChecklistUpdate('build', item, e.target.checked)
                        }
                        disabled={updating}
                        className={styles.checkbox}
                      />
                      <span>{item}</span>
                    </label>
                    {checked && (
                      <p className={styles.checklistNote}>✓ Completed</p>
                    )}
                  </div>
                );
              })}
            </div>

            <div className={styles.buildPhotos}>
              <h3>Build Photos</h3>
              {photos.length > 0 ? (
                <div className={styles.photoGrid}>
                  {photos.map((photo) => (
                    <div key={photo.id} className={styles.photoCard}>
                      <img src={photo.photo_url} alt={photo.stage} />
                      <p className={styles.photoStage}>{photo.stage}</p>
                      {photo.notes && <p className={styles.photoNotes}>{photo.notes}</p>}
                    </div>
                  ))}
                </div>
              ) : (
                <p className={styles.noData}>No photos uploaded yet</p>
              )}
            </div>

            {checklist.build.every((c) => c.completed) && (
              <button
                onClick={() => handleStatusChange('qa')}
                disabled={updating}
                className={styles.button + ' ' + styles.primary}
              >
                All Build Steps Complete - Move to QA
              </button>
            )}
          </div>
        )}

        {activeTab === 'qa' && (
          <div className={styles.section}>
            <h2>QA Checklist</h2>
            <div className={styles.checklistContainer}>
              {DEFAULT_QA_CHECKLIST.map((item) => {
                const checked =
                  checklist.qa.find((c) => c.item === item)?.completed ||
                  false;

                return (
                  <div key={item} className={styles.checklistItem}>
                    <label className={styles.checkboxLabel}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) =>
                          handleChecklistUpdate('qa', item, e.target.checked)
                        }
                        disabled={updating}
                        className={styles.checkbox}
                      />
                      <span>{item}</span>
                    </label>
                    {checked && (
                      <p className={styles.checklistNote}>✓ Passed</p>
                    )}
                  </div>
                );
              })}
            </div>

            {checklist.qa.every((c) => c.completed) && (
              <button
                onClick={() => handleStatusChange('ready_to_ship')}
                disabled={updating}
                className={styles.button + ' ' + styles.primary}
              >
                QA Passed - Ready to Ship
              </button>
            )}
          </div>
        )}

        {activeTab === 'shipping' && (
          <div className={styles.section}>
            <h2>Shipping & Delivery</h2>
            {o.tracking_number ? (
              <div className={styles.shippingInfo}>
                <div className={styles.gridItem}>
                  <label>Tracking Number</label>
                  <p>{o.tracking_number}</p>
                </div>
                <div className={styles.gridItem}>
                  <label>Carrier</label>
                  <p>{o.carrier || '—'}</p>
                </div>
                <div className={styles.gridItem}>
                  <label>Shipped</label>
                  <p>
                    {o.shipped_at
                      ? new Date(o.shipped_at).toLocaleString()
                      : '—'}
                  </p>
                </div>
                <div className={styles.gridItem}>
                  <label>Estimated Delivery</label>
                  <p>
                    {o.estimated_delivery
                      ? new Date(o.estimated_delivery).toLocaleDateString()
                      : '—'}
                  </p>
                </div>
              </div>
            ) : (
              <p className={styles.noData}>Shipping info not yet added</p>
            )}

            {!o.delivered_at && o.tracking_number && (
              <button
                onClick={() => handleStatusChange('shipped')}
                disabled={updating}
                className={styles.button + ' ' + styles.primary}
              >
                Mark as Shipped
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function formatStatus(status: string): string {
  return status
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

function formatTab(tab: string): string {
  const labels: Record<string, string> = {
    overview: 'Overview',
    sourcing: 'Sourcing',
    build: 'Build',
    qa: 'QA',
    shipping: 'Shipping',
  };
  return labels[tab] || tab;
}
