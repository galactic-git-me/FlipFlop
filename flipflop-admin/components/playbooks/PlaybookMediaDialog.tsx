"use client";
import { useMemo } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import dynamic from "next/dynamic";
import type { BookCell } from "@/lib/playbook-book";
const Photos = dynamic(() => import("./PlaybookPhotos"), { loading: () => <p role="status">Loading product photos…</p> });
export default function PlaybookMediaDialog({ cell, onClose }: { cell: BookCell; onClose: () => void }) {
  const variantIds = useMemo(() => [...new Set((cell.offer?.components ?? []).filter(part => !part.role.startsWith("os")).map(part => part.variant_id))], [cell.offer]);
  return <Dialog.Root open onOpenChange={open => { if (!open) onClose(); }}><Dialog.Portal>
    <Dialog.Overlay className="fixed inset-0 z-[100] bg-black/75" />
    <Dialog.Content className="fixed inset-2 z-[101] flex flex-col overflow-hidden rounded-xl border border-cyan-400/40 bg-[#0b1119] text-slate-100 sm:inset-6">
      <header className="flex items-start justify-between gap-3 border-b border-white/15 p-4">
        <div><Dialog.Title className="text-lg font-semibold">{cell.name} · Photos &amp; 3D models</Dialog.Title><Dialog.Description className="text-sm text-slate-400">{cell.customer_type} · {cell.budget_tier}. You approve the photos and the finished models. Approved product media is shared across builds.</Dialog.Description></div>
        <Dialog.Close className="rounded border border-white/20 px-3 py-2 text-sm">Close</Dialog.Close>
      </header>
      <div className="flex-1 overflow-auto">{variantIds.length ? <Photos variantIds={variantIds} /> : <p className="p-6">The system has not linked this build’s physical components yet.</p>}</div>
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>;
}
