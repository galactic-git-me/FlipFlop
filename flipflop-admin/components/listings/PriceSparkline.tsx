/**
 * PriceSparkline - Tiny inline price chart for listing rows
 * Shows 7-14 days of price history as two-line comparison chart
 */

interface PriceObservation {
  observed_at: string;
  delivered_price: number;
}

interface PriceSparklineProps {
  listingPrices: PriceObservation[];
  cpkPrices?: PriceObservation[];
  width?: number;
  height?: number;
  className?: string;
}

export function PriceSparkline({
  listingPrices,
  cpkPrices,
  width = 80,
  height = 28,
  className = '',
}: PriceSparklineProps) {
  if (!listingPrices || listingPrices.length === 0) {
    return <span className="text-xs text-gray-400">—</span>;
  }

  // Sort by date (oldest first)
  const sortedListing = [...listingPrices].sort(
    (a, b) => new Date(a.observed_at).getTime() - new Date(b.observed_at).getTime()
  );

  const sortedCpk = cpkPrices
    ? [...cpkPrices].sort(
        (a, b) => new Date(a.observed_at).getTime() - new Date(b.observed_at).getTime()
      )
    : [];

  // Calculate min/max across both datasets
  const allValues = [
    ...sortedListing.map((p) => p.delivered_price),
    ...sortedCpk.map((p) => p.delivered_price),
  ];
  const min = Math.min(...allValues);
  const max = Math.max(...allValues);
  const range = max - min || 1;

  // Generate SVG path points for listing prices (blue)
  const listingPoints = (sortedListing.length === 1 ? [sortedListing[0], sortedListing[0]] : sortedListing)
    .map((p, idx) => {
      const x = (idx / (sortedListing.length - 1 || 1)) * width;
      const y = height - ((p.delivered_price - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(' ');

  // Generate SVG path points for CPK prices (orange)
  const cpkPoints = (sortedCpk.length === 1 ? [sortedCpk[0], sortedCpk[0]] : sortedCpk)
    .map((p, idx) => {
      const x = (idx / (sortedCpk.length - 1 || 1)) * width;
      const y = height - ((p.delivered_price - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(' ');

  // Determine trend color for listing
  const listingCurrent = sortedListing[sortedListing.length - 1].delivered_price;
  const listingPrevious = sortedListing[0].delivered_price;
  const listingChange = listingCurrent - listingPrevious;
  const listingTrendColor =
    listingChange < -0.01 ? '#3b82f6' : // Blue (price dropped)
    listingChange > 0.01 ? '#3b82f6' : // Blue (stable or up, still this listing)
    '#3b82f6'; // Blue (this listing)

  return (
    <div
      className={`flex items-center justify-center ${className}`}
      title="Blue: this listing | Orange: market average"
    >
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="overflow-visible"
      >
        {/* Grid line at middle */}
        <line
          x1="0"
          y1={height / 2}
          x2={width}
          y2={height / 2}
          stroke="#e5e7eb"
          strokeWidth="0.5"
          opacity="0.3"
        />

        {/* CPK price line (orange, if available) */}
        {cpkPoints && (
          <>
            <polyline
              points={cpkPoints}
              fill="none"
              stroke="#f97316"
              strokeWidth="1.75"
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity="0.6"
            />
            {sortedCpk.length > 0 && (
              <circle
                cx={width}
                cy={height - ((sortedCpk[sortedCpk.length - 1].delivered_price - min) / range) * (height - 4) - 2}
                r="1"
                fill="#f97316"
                opacity="0.6"
              />
            )}
          </>
        )}

        {/* Listing price line (blue) */}
        <polyline
          points={listingPoints}
          fill="none"
          stroke={listingTrendColor}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Current listing price dot */}
        {sortedListing.length > 0 && (
          <circle
            cx={width}
            cy={height - ((listingCurrent - min) / range) * (height - 4) - 2}
            r="1.5"
            fill={listingTrendColor}
          />
        )}
      </svg>
    </div>
  );
}
