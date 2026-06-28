import Link from "next/link";
import { CheckCircle } from "lucide-react";

interface Props {
  params: { reference: string };
}

export default function OrderConfirmationPage({ params }: Props) {
  return (
    <div className="max-w-lg mx-auto px-4 py-24 text-center">
      <CheckCircle
        size={48}
        className="mx-auto mb-6"
        style={{ color: "var(--color-accent)" }}
      />
      <h1 className="text-2xl font-bold mb-3" style={{ fontFamily: "var(--font-heading)" }}>
        Order received
      </h1>
      <p className="text-muted mb-2">Reference: <span className="font-mono font-bold text-white">{params.reference}</span></p>
      <p className="text-muted text-sm leading-relaxed mb-8">
        We&apos;ve received your order and will be in touch to confirm your build slot and delivery details.
        Check your email for a confirmation.
      </p>
      <p className="text-sm text-muted mb-6">
        Questions?{" "}
        <a href="mailto:hello@flipflop.co.uk" className="underline hover:text-white transition-colors">
          hello@flipflop.co.uk
        </a>
      </p>
      <Link href="/" className="text-sm text-muted hover:text-white transition-colors underline">
        ← Back to FlipFlop
      </Link>
    </div>
  );
}
