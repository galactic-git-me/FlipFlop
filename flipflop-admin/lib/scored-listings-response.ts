/** Accept both the pre-pagination API and the new paged response during a backend restart. */
export function normalizeScoredListingsResponse<T>(data: unknown): { items: T[]; hasMore: boolean; legacy: boolean } {
  if (Array.isArray(data)) return { items: data as T[], hasMore: false, legacy: true };
  if (data && typeof data === "object" && "items" in data && Array.isArray(data.items)) {
    return { items: data.items as T[], hasMore: "has_more" in data && data.has_more === true, legacy: false };
  }
  throw new Error("Unexpected scored-listings response from the API");
}
