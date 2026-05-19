"use client";

import { useEffect } from "react";

const FRAME_COUNT = 24;
const START_FRAME = 1; // starts at 01.png (equivalent to "1.png" sequence start)
const FRAME_MS = 120;

function framePath(i: number): string {
  return `/pics/logo_animation/${String(i).padStart(2, "0")}.png`;
}

function setFavicon(href: string): void {
  const rels = ["icon", "shortcut icon", "apple-touch-icon"];
  for (const rel of rels) {
    let el = document.head.querySelector(`link[rel="${rel}"]`) as HTMLLinkElement | null;
    if (!el) {
      el = document.createElement("link");
      el.rel = rel;
      document.head.appendChild(el);
    }
    el.href = href;
  }
}

export function FaviconAnimator() {
  useEffect(() => {
    let idx = START_FRAME;
    setFavicon(framePath(idx));

    const id = window.setInterval(() => {
      idx = (idx + 1) % FRAME_COUNT;
      setFavicon(framePath(idx));
    }, FRAME_MS);

    return () => window.clearInterval(id);
  }, []);

  return null;
}

