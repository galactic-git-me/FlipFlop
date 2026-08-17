"use client";

import { useEffect, useRef, useState } from "react";
import { PriceSparkline } from "./PriceSparkline";
import { PriceHistoryModal } from "./PriceHistoryModal";

interface PriceObservation {
  observed_at: string;
  delivered_price: number;
}

interface PriceHistorySparklineProps {
  listingId: string;
  listingTitle?: string;
}

export function PriceHistorySparkline({ listingId, listingTitle }: PriceHistorySparklineProps) {
  const [listingPrices, setListingPrices] = useState<PriceObservation[]>([]);
  const [cpkPrices, setCpkPrices] = useState<PriceObservation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [shouldLoad, setShouldLoad] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = containerRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShouldLoad(true);
          observer.disconnect();
        }
      },
      { rootMargin: "240px" },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!shouldLoad) return;
    const controller = new AbortController();
    const fetchPriceHistory = async () => {
      try {
        const url = `/api/listings/${encodeURIComponent(listingId)}/price-history`;
        const response = await fetch(url, { signal: controller.signal });
        if (response.ok) {
          const data = await response.json();
          setListingPrices(data.listingPrices || []);
          setCpkPrices(data.cpkPrices || []);
        } else {
          setHasError(true);
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return;
        console.error(`Error fetching price history for ${listingId}:`, error);
        setHasError(true);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPriceHistory();
    return () => controller.abort();
  }, [listingId, shouldLoad]);

  if (!shouldLoad) {
    return <div ref={containerRef} className="h-8 w-[112px]" aria-hidden="true" />;
  }

  if (isLoading) {
    return <div ref={containerRef}><span className="block h-7 w-24 animate-pulse rounded bg-slate-700" aria-label="Loading price history" /></div>;
  }

  if (hasError) {
    return <div ref={containerRef}><span className="text-xs text-amber-400" title="Price history could not be loaded">Unavailable</span></div>;
  }

  return (
    <div ref={containerRef}>
      <button
        type="button"
        onClick={() => setShowModal(true)}
        className="cursor-pointer rounded-md px-1 py-0.5 transition-colors hover:bg-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
        title="Blue: this listing · Orange: CPK market · Click for details"
        aria-label={`Open price history for ${listingTitle || listingId}`}
      >
        <PriceSparkline
          listingPrices={listingPrices}
          cpkPrices={cpkPrices}
          width={104}
          height={32}
        />
      </button>
      {showModal && (
        <PriceHistoryModal
          listingId={listingId}
          listingTitle={listingTitle}
          listingPrices={listingPrices}
          cpkPrices={cpkPrices}
          onClose={() => setShowModal(false)}
        />
      )}
    </div>
  );
}
