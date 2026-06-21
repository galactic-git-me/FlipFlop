// pc-flipper-customer/lib/api.ts
import type { PublicCase, PublicPlaybook, PublicSlotWithVariants, AvailableWeek } from "./types";

// All fetches in this file run inside Server Components — relative paths don't work
// from the server process, so we use BACKEND_URL directly to hit the backend.
const API = process.env.BACKEND_URL ?? "http://localhost:4311";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API}${path}`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

export async function getPlaybooks(): Promise<PublicPlaybook[]> {
  return get<PublicPlaybook[]>("/api/public/playbooks");
}

export async function getPlaybookSlots(playbookId: number): Promise<PublicSlotWithVariants[]> {
  return get<PublicSlotWithVariants[]>(`/api/public/playbooks/${playbookId}/slots`);
}

export async function getCases(): Promise<PublicCase[]> {
  return get<PublicCase[]>("/api/public/cases");
}

// STUB — replaced by real endpoint in Subsystem 2
export async function getAvailableWeeks(): Promise<AvailableWeek[]> {
  const today = new Date();
  // Return 3 stub weeks starting from next week
  return Array.from({ length: 3 }, (_, i) => {
    const d = new Date(today);
    d.setDate(d.getDate() + 7 * (i + 1));
    // ISO week number
    const jan1 = new Date(d.getFullYear(), 0, 1);
    const weekNum = Math.ceil(((d.getTime() - jan1.getTime()) / 86400000 + jan1.getDay() + 1) / 7);
    const week = `${d.getFullYear()}-W${String(weekNum).padStart(2, "0")}`;
    const week_start = d.toISOString().split("T")[0];
    return { week, week_start, available: 3 - i, capacity: 3 };
  });
}
