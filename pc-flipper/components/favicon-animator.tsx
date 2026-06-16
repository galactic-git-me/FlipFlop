"use client";

import { useEffect } from "react";

const FRAME_COUNT = 24;
const START_FRAME = 1; // starts at 01.png (equivalent to "1.png" sequence start)
const FRAME_MS = 120;

function framePath(i: number): string {
  return `/pics/logo_animation/${String(i).padStart(2, "0")}.png`;
}

const ANIM_ATTR = "data-favicon-animator";

function setFavicon(href: string): void {
  // Only remove elements we previously injected — never touch React-managed head nodes.
  document.head.querySelectorAll(`link[${ANIM_ATTR}]`).forEach((el) => el.remove());

  const rels = ["icon", "shortcut icon", "apple-touch-icon"];
  for (const rel of rels) {
    const el = document.createElement("link");
    el.rel = rel;
    el.type = "image/png";
    el.href = href;
    el.setAttribute(ANIM_ATTR, "true");
    document.head.appendChild(el);
  }
}

export function FaviconAnimator() {
  useEffect(() => {
    let idx = START_FRAME;
    let tick = 0;
    setFavicon(`${framePath(idx)}?v=${tick}`);

    const id = window.setInterval(() => {
      idx = (idx + 1) % FRAME_COUNT;
      tick += 1;
      setFavicon(`${framePath(idx)}?v=${tick}`);
    }, FRAME_MS);

    return () => window.clearInterval(id);
  }, []);

  return null;
}
