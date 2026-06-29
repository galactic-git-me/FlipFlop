/**
 * Admin API client for order management endpoints
 */

export interface Order {
  id: number;
  order_id: string;
  customer_name: string;
  customer_email: string;
  status: string;
  customer_price: number;
  component_costs: number;
  profit?: number;
  promised_delivery_date: string;
  actual_delivery_date?: string;
  created_at: string;
  updated_at: string;
  sourcing_started_at?: string;
  sourcing_approved_at?: string;
  building_started_at?: string;
  building_completed_at?: string;
  qa_started_at?: string;
  qa_passed_at?: string;
  shipped_at?: string;
  delivered_at?: string;
  tracking_number?: string;
  carrier?: string;
  estimated_delivery?: string;
}

export interface ChecklistItem {
  item: string;
  completed: boolean;
  notes?: string;
  updated_at?: string;
}

export interface OrderPhoto {
  id: number;
  stage: string;
  photo_url: string;
  notes?: string;
  created_at: string;
}

export interface OrderDetail {
  order: Order;
  checklist: {
    build: ChecklistItem[];
    qa: ChecklistItem[];
  };
  photos: OrderPhoto[];
}

export interface Metrics {
  total_active: number;
  orders_by_status: Record<string, number>;
  average_build_time_days: number;
  late_orders: number;
  customer_satisfaction_avg?: number;
}

const API_BASE_URL = '/api/admin';

/**
 * List all orders with optional filters
 */
export async function listOrders(
  status?: string,
  dateFrom?: string,
  dateTo?: string,
  budgetMin?: number,
  budgetMax?: number,
  sortBy: string = 'created_at',
  skip: number = 0,
  limit: number = 50
) {
  const params = new URLSearchParams();
  if (status) params.append('status', status);
  if (dateFrom) params.append('date_from', dateFrom);
  if (dateTo) params.append('date_to', dateTo);
  if (budgetMin !== undefined) params.append('budget_min', String(budgetMin));
  if (budgetMax !== undefined) params.append('budget_max', String(budgetMax));
  params.append('sort_by', sortBy);
  params.append('skip', String(skip));
  params.append('limit', String(limit));

  const response = await fetch(`${API_BASE_URL}/orders?${params}`);
  if (!response.ok) throw new Error('Failed to fetch orders');
  return response.json();
}

/**
 * Get single order detail with checklists and photos
 */
export async function getOrderDetail(orderId: number | string): Promise<OrderDetail> {
  const response = await fetch(`${API_BASE_URL}/orders/${orderId}`);
  if (!response.ok) throw new Error('Failed to fetch order detail');
  return response.json();
}

/**
 * Update order status
 */
export async function updateOrderStatus(
  orderId: number,
  status: string,
  notes?: string
) {
  const response = await fetch(`${API_BASE_URL}/orders/${orderId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, notes: notes || null }),
  });
  if (!response.ok) throw new Error('Failed to update order status');
  return response.json();
}

/**
 * Update or create checklist item
 */
export async function updateChecklistItem(
  orderId: number,
  section: 'build' | 'qa',
  item: string,
  completed: boolean,
  notes?: string
) {
  const response = await fetch(`${API_BASE_URL}/orders/${orderId}/checklist/${section}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ item, completed, notes: notes || null }),
  });
  if (!response.ok) throw new Error('Failed to update checklist');
  return response.json();
}

/**
 * Update shipping information
 */
export async function updateShipping(
  orderId: number,
  trackingNumber: string,
  carrier: string,
  estimatedDelivery: string
) {
  const response = await fetch(`${API_BASE_URL}/orders/${orderId}/shipping`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tracking_number: trackingNumber,
      carrier,
      estimated_delivery: estimatedDelivery,
    }),
  });
  if (!response.ok) throw new Error('Failed to update shipping');
  return response.json();
}

/**
 * Get dashboard metrics
 */
export async function getMetrics(): Promise<Metrics> {
  const response = await fetch(`${API_BASE_URL}/metrics`);
  if (!response.ok) throw new Error('Failed to fetch metrics');
  return response.json();
}
