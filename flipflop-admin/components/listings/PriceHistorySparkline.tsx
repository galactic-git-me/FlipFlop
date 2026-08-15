"use client";

import { useEffect, useState } from "react";
import { PriceSparkline } from "./PriceSparkline";
import { PriceHistoryModal } from "./PriceHistoryModal";

interface PriceObservation {
  observed_at: string;
  delivered_price: number;
}

interface PriceHistorySparklineProps {
  listingId: string;
}

export function PriceHistorySparkline({ listingId }: PriceHistorySparklineProps) {
  const [listingPrices, setListingPrices] = useState<PriceObservation[]>([]);
  const [cpkPrices, setCpkPrices] = useState<PriceObservation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    const fetchPriceHistory = async () => {
      try {
        const response = await fetch(
          `/api/listings/${encodeURIComponent(listingId)}/price-history`
        );
        if (response.ok) {
          const data = await response.json();
          setListingPrices(data.listingPrices || []);
          setCpkPrices(data.cpkPrices || []);
        }
      } catch (error) {
        console.error(`Failed to fetch price history for ${listingId}:`, error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPriceHistory();
  }, [listingId]);

  if (isLoading) {
    return <span className="text-xs text-gray-400">...</span>;
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setShowModal(true)}
        className="hover:opacity-75 transition cursor-pointer"
        title="Click to view detailed price history"
      >
        <PriceSparkline
          listingPrices={listingPrices}
          cpkPrices={cpkPrices}
          width={80}
          height={28}
        />
      </button>
      {showModal && (
        <PriceHistoryModal
          listingId={listingId}
          listingPrices={listingPrices}
          cpkPrices={cpkPrices}
          onClose={() => setShowModal(false)}
        />
      )}
    </>
  );
}
