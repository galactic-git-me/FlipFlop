'use client';

import { Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Configurator3D } from '@/components/configurator/Configurator3D';
import { ComponentPicker } from '@/components/configurator/ComponentPicker';
import { PricingSidebar } from '@/components/configurator/PricingSidebar';
import { useConfiguratorStore } from '@/lib/configurator-store';
import '@/components/configurator/configurator.css';

function ConfiguratorPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const budget = parseFloat(searchParams.get('budget') || '1200');

  const components = useConfiguratorStore((state) => ({
    cpu_id: state.cpu_id,
    gpu_id: state.gpu_id,
    ram_id: state.ram_id,
    ssd_id: state.ssd_id,
    psu_id: state.psu_id,
    case_id: state.case_id,
    cooler_id: state.cooler_id,
  }));

  const handleContinue = () => {
    // Navigate to payment page or order confirmation
    router.push('/order/summary');
  };

  return (
    <div className="configurator-container">
      <div className="configurator-viewport">
        <Configurator3D components={components} />
      </div>

      <div className="configurator-sidebar">
        <h2>Build Your PC</h2>

        <div className="component-pickers">
          <ComponentPicker componentType="cpu" label="Processor" />
          <ComponentPicker componentType="gpu" label="Graphics Card" />
          <ComponentPicker componentType="ram" label="Memory" />
          <ComponentPicker componentType="ssd" label="Storage" />
          <ComponentPicker componentType="psu" label="Power Supply" />
          <ComponentPicker componentType="case" label="Case" />
          <ComponentPicker componentType="cooler" label="CPU Cooler" />
        </div>

        <PricingSidebar budget={budget} onContinue={handleContinue} />
      </div>
    </div>
  );
}

export default function ConfiguratorPage() {
  return (
    <Suspense
      fallback={
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100vh',
            backgroundColor: '#0f1419',
            color: '#e8eaf0',
          }}
        >
          <div>Loading configurator...</div>
        </div>
      }
    >
      <ConfiguratorPageContent />
    </Suspense>
  );
}
