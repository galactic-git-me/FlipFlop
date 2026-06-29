'use client';

import { Suspense } from 'react';
import { OrderSummary } from '@/components/order-summary/OrderSummary';

function OrderSummaryPageContent() {
  return <OrderSummary />;
}

export default function OrderSummaryPage() {
  return (
    <Suspense fallback={<div>Loading order summary...</div>}>
      <OrderSummaryPageContent />
    </Suspense>
  );
}
