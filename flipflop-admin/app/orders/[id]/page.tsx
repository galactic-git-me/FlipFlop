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
    cancellation_requested_at: string | null;
    cancellation_status: string | null;
    refund_id: string | null;
    cancelled_at: string | null;
    benchmark_results: Record<string, unknown> | null;
    change_request?: {
      status: string;
      request_text?: string;
      requested_at?: string;
      proposed_specs?: Record<string, unknown> | null;
      proposed_customer_price?: number | null;
      customer_message?: string | null;
      internal_note?: string | null;
    } | null;
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
  const [benchmarkJson, setBenchmarkJson] = useState('');
  const [benchmarkConfirmed, setBenchmarkConfirmed] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [changeSpecs, setChangeSpecs] = useState('');
  const [changePrice, setChangePrice] = useState('');
  const [changeMessage, setChangeMessage] = useState('');
  const [changeInternalNote, setChangeInternalNote] = useState('');

  useEffect(() => {
    fetchOrder();
  }, [orderId]);

  const fetchOrder = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/orders/${orderId}`);
      const data = await res.json();
      setOrder(data);
      setBenchmarkJson(JSON.stringify(data.order?.benchmark_results ?? { test_date: '', test_setup: '', results: [] }, null, 2));
      setChangeSpecs(JSON.stringify(data.order?.change_request?.proposed_specs ?? {}, null, 2));
      setChangePrice(data.order?.change_request?.proposed_customer_price != null ? String(data.order.change_request.proposed_customer_price) : '');
      setChangeMessage(data.order?.change_request?.customer_message ?? '');
      setChangeInternalNote(data.order?.change_request?.internal_note ?? '');
    } catch (error) {
      console.error('Failed to fetch order:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!order) return;
    setUpdating(true);
    setActionError(null);
    try {
      const res = await fetch(`/api/admin/orders/${order.order.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Could not update status (${res.status})`);
      }
      await fetchOrder();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Failed to update status.');
    } finally {
      setUpdating(false);
    }
  };

  const reviewBuildChange = async (action: 'quote' | 'reject') => {
    if (!order) return;
    setUpdating(true);
    setActionError(null);
    try {
      if (changeMessage.trim().length < 12) throw new Error('Write a customer-facing explanation of at least 12 characters.');
      let proposed_specs: Record<string, unknown> | undefined;
      if (action === 'quote') {
        const parsed = JSON.parse(changeSpecs);
        if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw new Error('Revised specification must be a JSON object.');
        proposed_specs = parsed as Record<string, unknown>;
        if (!changePrice || !Number.isFinite(Number(changePrice)) || Number(changePrice) <= 0) throw new Error('Enter a valid revised customer price.');
      }
      const response = await fetch(`/api/admin/orders/${order.order.id}/change-request`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, proposed_specs, proposed_customer_price: action === 'quote' ? Number(changePrice) : undefined, customer_message: changeMessage, internal_note: changeInternalNote }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.detail || `Could not ${action} this request.`);
      await fetchOrder();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Could not review this request.');
    } finally {
      setUpdating(false);
    }
  };

  const saveBenchmarkEvidence = async () => {
    if (!order || !benchmarkConfirmed) return;
    setUpdating(true);
    setActionError(null);
    try {
      const benchmark_results = JSON.parse(benchmarkJson);
      const res = await fetch(`/api/admin/orders/${order.order.id}/build-evidence`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ benchmark_results, confirm_measured_results: true }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.detail || `Could not save build evidence (${res.status})`);
      setBenchmarkConfirmed(false);
      await fetchOrder();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : 'Enter valid benchmark JSON and try again.');
    } finally {
      setUpdating(false);
    }
  };

  const reconcileRefund = async () => {
    if (!order) return;
    setUpdating(true);
    try {
      const res = await fetch(`/api/admin/orders/${order.order.id}/refund/reconcile`, { method: 'POST' });
      if (res.ok) await fetchOrder();
    } catch (error) {
      console.error('Failed to reconcile refund:', error);
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
        {actionError && <div role="alert" className={styles.alert}>{actionError}</div>}
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
                  disabled={updating || !!o.cancellation_requested_at || o.status === 'cancelled'}
                  className={styles.select}
                >
                  <option value="awaiting_sourcing">Awaiting Sourcing</option>
                  <option value="parts_ordered">Parts Ordered</option>
                  <option value="building">Building</option>
                  <option value="qa">QA</option>
                  <option value="ready_to_ship">Ready to Ship</option>
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

            {o.cancellation_requested_at && (
              <div className={styles.alert}>
                <strong>Cancellation / refund: {o.cancellation_status || 'pending'}</strong>
                <p>Requested {new Date(o.cancellation_requested_at).toLocaleString()}</p>
                {o.refund_id && <p>Provider refund: {o.refund_id}</p>}
                {o.cancelled_at && <p>Cancelled {new Date(o.cancelled_at).toLocaleString()}</p>}
                {o.refund_id && o.status !== 'cancelled' && (
                  <button onClick={reconcileRefund} disabled={updating} className={styles.button}>
                    Recheck existing refund
                  </button>
                )}
                {!o.refund_id && <p>No provider refund ID is recorded. Check Stripe before taking any manual action.</p>}
              </div>
            )}

            {o.change_request && <div className={styles.alert}>
              <strong>Customer build-change request: {o.change_request.status.replace(/_/g, ' ')}</strong>
              {o.change_request.requested_at && <p>Received {new Date(o.change_request.requested_at).toLocaleString()}</p>}
              {o.change_request.request_text && <p className={styles.sectionHint}>{o.change_request.request_text}</p>}
              {o.change_request.status === 'requested' && <div className={styles.section}>
                <label className={styles.gridItem}>Revised specification JSON
                  <textarea value={changeSpecs} onChange={event => setChangeSpecs(event.target.value)} rows={8} spellCheck={false} className={styles.textarea} aria-label="Revised specification JSON" />
                </label>
                <label className={styles.gridItem}>Revised total price (£)
                  <input type="number" min="0.01" step="0.01" value={changePrice} onChange={event => setChangePrice(event.target.value)} className={styles.textarea} />
                </label>
                <label className={styles.gridItem}>Message to customer
                  <textarea value={changeMessage} onChange={event => setChangeMessage(event.target.value)} rows={3} className={styles.textarea} />
                </label>
                <label className={styles.gridItem}>Internal review note
                  <textarea value={changeInternalNote} onChange={event => setChangeInternalNote(event.target.value)} rows={2} className={styles.textarea} />
                </label>
                <p className={styles.sectionHint}>Quoting pauses sourcing. This records a proposal only; it does not update the paid order or settle a price difference.</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  <button type="button" onClick={() => void reviewBuildChange('quote')} disabled={updating} className={styles.button}>Prepare customer quote</button>
                  <button type="button" onClick={() => void reviewBuildChange('reject')} disabled={updating} className={styles.button}>Decline request</button>
                </div>
              </div>}
              {o.change_request.customer_message && <p>{o.change_request.customer_message}</p>}
              {o.change_request.proposed_customer_price != null && <p>Proposed customer total: £{o.change_request.proposed_customer_price.toFixed(2)}</p>}
            </div>}

            {['building', 'qa', 'ready_to_ship'].includes(o.status) && (
              <div className={styles.alert}>
                <strong>Measured build benchmarks</strong>
                <p>Enter results measured on this physical build. Include the test date, test setup, and results; these are required before the order can enter Ready to Ship.</p>
                <textarea
                  value={benchmarkJson}
                  onChange={(event) => { setBenchmarkJson(event.target.value); setBenchmarkConfirmed(false); }}
                  rows={10}
                  spellCheck={false}
                  aria-label="Measured benchmark results as JSON"
                  className={styles.textarea}
                />
                <label className={styles.checkboxLabel}>
                  <input type="checkbox" checked={benchmarkConfirmed} onChange={(event) => setBenchmarkConfirmed(event.target.checked)} />
                  I confirm these results were measured on this build.
                </label>
                <button onClick={saveBenchmarkEvidence} disabled={updating || !benchmarkConfirmed} className={styles.button}>
                  {updating ? 'Saving…' : 'Save measured results'}
                </button>
              </div>
            )}

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
                  disabled={updating || !!o.cancellation_requested_at || o.status === 'cancelled'}
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

            {!o.delivered_at && !o.shipped_at && <p className={styles.sectionHint}>Record physical handover in Dispatch Centre after courier, insurance, and evidence checks are complete.</p>}
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
