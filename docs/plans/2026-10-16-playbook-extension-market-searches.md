# Playbook build searches in FlipFlopXtension

Implemented backend-owned build search feed, Settings sync and pre-sweep sync,
all ten Standard vendors, separate eBay sold/live capture, selected-BOM identity
and role-scoped ASIN/CPK tags. Broad and motherboard searches retain build
coverage without requiring board names in every listing title. Current canonical
coverage is 24 builds; search count is derived, not fixed to 28.

Browser captures append candidates to existing cell market reviews. The backend
rejects stale BOM targets and non-eBay sold submissions, records source URLs,
keeps sold and asking prices separate, and blocks missing postage/sold markers,
wrong condition, best-offer ambiguity and mismatched title anchors. No source
tag can bypass existing commercial, compatibility or publication approvals.

Verified: live local GET returned 24 targets with ASIN/CPK tags; 25 backend
tests passed, 44 extension tests passed, extension typecheck/lint passed, DEV
package built at `C:\Users\mclar\CODING\FlipFlopXtension\dist\dev`.
The built Settings page was also rendered in a browser harness using isolated
mock Chrome storage and a preview-only CORS transport shim. Its sync called the
real local feed, displayed "Synced 48 Playbook search terms", and produced 48
managed read-only queries. This does not verify the installed extension or its
real storage. API CORS configuration was not changed.
Not verified: actual installed extension Settings, a fresh authenticated sold
scrape, each vendor's live end-to-end coverage, or production deployment.
DEV requires reload, then Settings -> Sync Playbook build searches (also synced
before scans). LIVE release must coordinate API and extension versions.
