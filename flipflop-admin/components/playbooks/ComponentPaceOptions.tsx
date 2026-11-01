import type { PlaybookOffer } from '@/lib/playbook-proposals';
import { bookMoney } from '@/lib/playbook-book';

const paces = [['fast_track', 'Fast Track'], ['standard', 'Standard'], ['flexible', 'Flexible']] as const;

export default function ComponentPaceOptions({ offer }: { offer: PlaybookOffer }) {
  return <section aria-label="Component sourcing by customer pace" className="space-y-3">
    <h4 className="font-medium text-cyan-200">Customer chooses the pace</h4>
    <p className="text-xs text-slate-400">Each pace sources the same selected specification. Flexible has no promised delivery date. Supplier prices below are per unit; the build quote includes quantities and operating costs.</p>
    <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-left text-xs">
      <thead><tr><th scope="col" className="p-2">Component</th>{paces.map(([mode, label]) => <th key={mode} scope="col" className="p-2">{label}</th>)}</tr></thead>
      <tbody>{offer.components.map(part => <tr key={part.role} className="border-t border-white/10">
        <th scope="row" className="p-2 font-normal">{part.title}{(part.quantity ?? 1) > 1 && ` × ${part.quantity}`}</th>
        {paces.map(([mode]) => {
          const choice = offer.component_pace_options?.[mode]?.find(row => row.role === part.role);
          return <td key={mode} className="p-2 align-top">{choice?.available ? <ul className="space-y-2">{choice.sources.map(source => <li key={`${source.url}-${source.observation_id ?? ''}`}>
            <a href={source.url} target="_blank" rel="noopener noreferrer" className="text-cyan-200 underline">{source.source ?? 'Supplier'} · {bookMoney(source.item_gbp)}</a>
            <span className="block text-slate-400">{mode === 'flexible' ? 'No promised delivery date' : `Supplier arrival: ${source.delivery_working_days} working days`} · postage {source.postage_verified ? bookMoney(source.delivery_gbp) : '£0 fallback (unconfirmed)'}</span>
          </li>)}</ul> : <span className="text-amber-200">{choice?.reason ?? 'Sourcing assessment pending'}</span>}</td>;
        })}
      </tr>)}</tbody>
    </table></div>
    <div className="grid gap-2 sm:grid-cols-3">{paces.map(([mode, label]) => {
      const quote = offer.delivery_products[mode];
      return <div key={mode} className="rounded border border-white/10 p-3 text-xs"><strong>{label}</strong><p>{quote?.available ? bookMoney(quote.recommended_price_gbp) : 'Unavailable'}</p><p className="text-slate-400">{mode === 'flexible' ? 'No promised delivery date' : quote?.delivery_working_days != null ? `${quote.delivery_working_days} working days` : 'Timing not confirmed'}</p>{!quote?.available && <p className="mt-1 text-amber-200">{quote?.reason}</p>}</div>;
    })}</div>
  </section>;
}
