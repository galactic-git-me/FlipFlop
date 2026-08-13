// Dependency-free fuzzy matching for client-side filtering (e.g. the
// listings table's title search). Not a full edit-distance implementation —
// prioritises being cheap to run on every keystroke over every listing:
// exact substring first, then partial multi-word matches, then a
// character-subsequence fallback so small typos still surface results.
export function fuzzyScore(query: string, text: string): number {
  const q = query.trim().toLowerCase();
  const t = text.toLowerCase();
  if (!q) return 1;
  if (t.includes(q)) return 1;

  const qWords = q.split(/\s+/).filter(Boolean);
  const matchedWords = qWords.filter((w) => t.includes(w));
  if (matchedWords.length === qWords.length) return 0.85;
  if (matchedWords.length > 0) return 0.5 * (matchedWords.length / qWords.length);

  let ti = 0;
  for (const ch of q) {
    ti = t.indexOf(ch, ti);
    if (ti === -1) return 0;
    ti++;
  }
  return 0.3;
}

export function fuzzyMatches(query: string, text: string): boolean {
  return fuzzyScore(query, text) > 0;
}
