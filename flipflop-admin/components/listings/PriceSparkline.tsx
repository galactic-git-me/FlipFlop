/**
 * PriceSparkline - Tiny inline price chart for listing rows
 * Shows 7-14 days of price history as a minimal line chart
 */

interface PriceObservation {
  observed_at: string;
  delivered_price: number;
}

interface PriceSparklineProps {
  prices: PriceObservation[];
  width?: number;
  height?: number;
  className?: string;
}

export function PriceSparkline({
  prices,
  width = 60,
  height = 24,
  className = '',
}: PriceSparklineProps) {
  if (!prices || prices.length === 0) {
    return <span className="text-xs text-gray-400">—</span>;
  }

  // Sort by date (oldest first)
  const sorted = [...prices].sort(
    (a, b) => new Date(a.observed_at).getTime() - new Date(b.observed_at).getTime()
  );

  const values = sorted.map((p) => p.delivered_price);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1; // Prevent division by zero

  // Generate SVG path points
  const points = values
    .map((value, idx) => {
      const x = (idx / (values.length - 1 || 1)) * width;
      const y = height - ((value - min) / range) * (height - 4) - 2; // Small padding
      return `${x},${y}`;
    })
    .join(' ');

  // Determine color based on trend
  const current = values[values.length - 1];
  const previous = values[0];
  const priceChange = current - previous;
  const trendColor =
    priceChange < -0.01 ? '#10b981' : // Green (price dropped = better deal)
    priceChange > 0.01 ? '#ef4444' : // Red (price went up)
    '#6b7280'; // Gray (stable)

  return (
    <div
      className={`flex items-center justify-center ${className}`}
      title={`£${previous.toFixed(2)} → £${current.toFixed(2)} (${Math.abs(priceChange).toFixed(2)})`}
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
          opacity="0.5"
        />

        {/* Price line */}
        <polyline
          points={points}
          fill="none"
          stroke={trendColor}
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Current price dot */}
        {values.length > 0 && (
          <circle
            cx={width}
            cy={height - ((current - min) / range) * (height - 4) - 2}
            r="1.5"
            fill={trendColor}
          />
        )}
      </svg>
    </div>
  );
}
