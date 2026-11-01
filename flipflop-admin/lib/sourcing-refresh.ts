/** Refresh only the data used by the selected sourcing tab. */
export async function loadSourcingRefresh<TListings, TQueue>(
  tab: string,
  listingsUrl: string,
  request: <T>(url: string) => Promise<T | null>,
) {
  const [listingsData, queueData] = await Promise.all([
    tab === "listings" ? request<TListings>(listingsUrl) : Promise.resolve(null),
    request<TQueue>("/api/gem-radar/queue-status"),
  ]);
  const failedEndpoints = [
    ...(tab === "listings" && !listingsData ? ["Listings"] : []),
    ...(!queueData ? ["Processing queue"] : []),
  ];
  return { listingsData, queueData, failedEndpoints };
}
