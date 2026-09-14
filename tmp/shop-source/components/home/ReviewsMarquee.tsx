'use client';

import type { PublicReview } from "@/lib/types";
import PixelCard from "@/components/ui/PixelCard";
import { useReveal } from "./useReveal";

function Header() {
  const { ref, visible } = useReveal<HTMLDivElement>();
  return (
    <h2
      ref={ref}
      className="text-2xl sm:text-3xl font-bold mb-3"
      style={{
        fontFamily: "var(--font-serif)",
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(20px)',
        transition: 'opacity 600ms var(--ease-out), transform 600ms var(--ease-out)',
      }}
    >
      What customers say
    </h2>
  );
}

function ReviewCard({ review, index }: { review: PublicReview; index: number }) {
  const { ref, visible } = useReveal<HTMLDivElement>();
  const variant = index % 2 === 0 ? "orange" : "blue";

  return (
    <div
      ref={ref}
      className="shrink-0"
      style={{
        width: '20rem',
        opacity: visible ? 1 : 0,
        transform: visible ? 'translateY(0)' : 'translateY(24px)',
        transition: `opacity 600ms var(--ease-out) ${(index % 4) * 90}ms, transform 600ms var(--ease-out) ${(index % 4) * 90}ms`,
      }}
    >
      <PixelCard variant={variant} className={`pixel-card--${variant}`}>
        <div className="p-5 text-left">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2" aria-label={`${review.stars} out of 5 stars`}>
              {Array.from({ length: 5 }, (_, star) => {
                const value = star + 1;
                if (review.stars >= value) return <span key={star} aria-hidden="true" className="text-base leading-none text-amber-300">★</span>;
                if (review.stars >= value - 0.5) return <span key={star} aria-hidden="true" className="bg-gradient-to-r from-amber-300 from-50% to-white/20 to-50% bg-clip-text text-base leading-none text-transparent">★</span>;
                return <span key={star} aria-hidden="true" className="text-base leading-none text-white/25">☆</span>;
              })}
            </div>
            {review.avatar_url ? (
              <img src={review.avatar_url} alt="" className="h-8 w-8 rounded-full border border-white/15 object-cover" />
            ) : (
              <span aria-hidden="true" className="grid h-8 w-8 place-items-center rounded-full bg-white/10 text-xs font-semibold text-primary">
                {review.author.slice(0, 1)}
              </span>
            )}
          </div>
          <p className="text-sm text-secondary leading-relaxed mb-3">&ldquo;{review.quote}&rdquo;</p>
          <p className="text-xs font-semibold">{review.author} <span className="text-tertiary font-normal">· {review.location}</span></p>
          <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-tertiary">{review.is_sample ? "Sample review" : review.source}</p>
        </div>
      </PixelCard>
    </div>
  );
}

export default function ReviewsMarquee({ reviews }: { reviews: PublicReview[] }) {
  return (
    <section className="max-w-5xl mx-auto px-4 py-24 text-center">
      <Header />

      {reviews.length === 0 ? (
        <p className="text-secondary">
          Reviews are on their way — we&apos;re setting up our review integrations. Check back soon.
        </p>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {reviews.map((r, i) => (
            <ReviewCard key={r.id} review={r} index={i} />
          ))}
        </div>
      )}
    </section>
  );
}
