export async function readJsonResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  try {
    return JSON.parse(text) as T;
  } catch {
    const summary = text.trim().replace(/\s+/g, " ").slice(0, 180);
    throw new Error(
      summary
        ? `Server error (${response.status}): ${summary}`
        : `Server returned an empty response (${response.status})`,
    );
  }
}
