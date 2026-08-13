"use client";

import { ManualBuild } from "@/lib/api";
import { Zap } from "lucide-react";
import { useState } from "react";

interface Props {
  build: ManualBuild;
  onUpdate: (config: Partial<ManualBuild>) => Promise<void>;
  saving?: boolean;
}

export function EbayOffersSection({ build, onUpdate, saving }: Props) {
  const [allowOffers, setAllowOffers] = useState(build.allow_offers ?? true);
  const [autoRejectBelow, setAutoRejectBelow] = useState(build.auto_reject_below_price?.toString() ?? "");
  const [returnDays, setReturnDays] = useState((build.return_days ?? 30).toString());

  const handleSave = async () => {
    await onUpdate({
      allow_offers: allowOffers,
      auto_reject_below_price: autoRejectBelow ? parseFloat(autoRejectBelow) : null,
      return_days: parseInt(returnDays, 10),
    });
  };

  const hasChanges =
    allowOffers !== (build.allow_offers ?? true) ||
    (autoRejectBelow ? parseFloat(autoRejectBelow) : null) !== (build.auto_reject_below_price ?? null) ||
    parseInt(returnDays, 10) !== (build.return_days ?? 30);

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800 p-4 space-y-4">
      <div className="flex items-center gap-2 mb-4">
        <Zap className="w-5 h-5 text-amber-400" />
        <h3 className="text-sm font-semibold text-slate-100">Offers & Returns</h3>
      </div>

      {/* Allow Offers Toggle */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-300">Accept Offers</label>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setAllowOffers(!allowOffers)}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              allowOffers ? "bg-blue-600" : "bg-slate-600"
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                allowOffers ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
          <span className="text-xs text-slate-400">{allowOffers ? "Enabled" : "Disabled"}</span>
        </div>
      </div>

      {/* Auto-Reject Below Price */}
      {allowOffers && (
        <div className="space-y-2">
          <label className="text-xs font-semibold text-slate-300">
            Auto-Reject Offers Below (optional)
          </label>
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">£</span>
            <input
              type="number"
              value={autoRejectBelow}
              onChange={(e) => setAutoRejectBelow(e.target.value)}
              placeholder="Leave empty for no minimum"
              className="flex-1 rounded bg-slate-700 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 border border-slate-600 focus:border-blue-500 focus:outline-none"
            />
          </div>
          <p className="text-xs text-slate-500">
            Offers below this amount will be automatically rejected
          </p>
        </div>
      )}

      {/* Return Policy */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-slate-300">Return Period</label>
        <select
          value={returnDays}
          onChange={(e) => setReturnDays(e.target.value)}
          className="w-full rounded bg-slate-700 px-3 py-2 text-sm text-slate-100 border border-slate-600 focus:border-blue-500 focus:outline-none"
        >
          <option value="0">No Returns</option>
          <option value="14">14 Days</option>
          <option value="30">30 Days</option>
          <option value="60">60 Days</option>
        </select>
      </div>

      {/* Save Button */}
      {hasChanges && (
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full rounded bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed px-4 py-2 text-sm font-semibold text-white transition"
        >
          {saving ? "Saving..." : "Save Settings"}
        </button>
      )}
    </div>
  );
}
