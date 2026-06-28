#!/usr/bin/env python3.10
"""
Recolor FlipFlop logo animation frames and build a video.

Orbital/chip  → linear gradient 45° : #0061FF → #60EFFF
Dot           → radial gradient      : #FF0F7B (centre) → #F89B29 (edge)
Video         → slow orbit, then quick "flash" burst when dot returns, loop.
"""

import os
import shutil
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SRC = "/home/mac/CODING/FlipFlop/pc-flipper/public/pics/logo_animation"
OUT_FRAMES = "/home/mac/CODING/FlipFlop/pc-flipper/public/pics/logo_animation_v2"
VIDEO_OUT  = "/home/mac/CODING/FlipFlop/pc-flipper/public/pics/flipflop_logo.mp4"

os.makedirs(OUT_FRAMES, exist_ok=True)

# ── colour helpers ────────────────────────────────────────────────────────────

def hsl_to_rgb(h, s, l):
    """h 0-360, s 0-1, l 0-1  →  (r,g,b) 0-255 ints"""
    s_val = s
    l_val = l
    c = (1 - abs(2 * l_val - 1)) * s_val
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l_val - c / 2
    if   h < 60:  r,g,b = c,x,0
    elif h < 120: r,g,b = x,c,0
    elif h < 180: r,g,b = 0,c,x
    elif h < 240: r,g,b = 0,x,c
    elif h < 300: r,g,b = x,0,c
    else:         r,g,b = c,0,x
    return (int((r+m)*255), int((g+m)*255), int((b+m)*255))

# Gradient stops (normalised 0-1)
ORBITAL_START = np.array(hsl_to_rgb(217, 1.0, 0.50), dtype=np.float32)  # #0061FF
ORBITAL_END   = np.array(hsl_to_rgb(186, 1.0, 0.69), dtype=np.float32)  # #60EFFF
DOT_CENTRE    = np.array(hsl_to_rgb(333, 1.0, 0.53), dtype=np.float32)  # #FF0F7B
DOT_EDGE      = np.array(hsl_to_rgb( 33, 0.94, 0.57), dtype=np.float32) # #F89B29

def orbital_gradient_color(x, y, w, h):
    """45° linear gradient colour for pixel (x,y) in image of size (w,h)."""
    t = (x / w + y / h) / 2.0          # 0→1 along 45°
    t = np.clip(t, 0.0, 1.0)
    return ORBITAL_START * (1 - t) + ORBITAL_END * t

def dot_radial_color(dx, dy, radius):
    """Radial gradient colour; dx,dy = offset from dot centre, radius = dot radius."""
    r = math.sqrt(dx*dx + dy*dy)
    t = np.clip(r / max(radius, 1), 0.0, 1.0)
    return DOT_CENTRE * (1 - t) + DOT_EDGE * t

# ── detect teal mask ──────────────────────────────────────────────────────────

def teal_mask(img_np):
    """
    Returns a float mask (0-1) for pixels that are the teal orbital/chip colour.
    Works in HSV space: hue ~160-200°, high saturation, medium-high value.
    """
    r = img_np[:,:,0].astype(np.float32)
    g = img_np[:,:,1].astype(np.float32)
    b = img_np[:,:,2].astype(np.float32)

    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    delta = mx - mn + 1e-6

    # Hue
    hue = np.zeros_like(r)
    mask_r = (mx == r)
    mask_g = (mx == g)
    mask_b = (mx == b)
    hue[mask_r] = (60 * ((g[mask_r] - b[mask_r]) / delta[mask_r])) % 360
    hue[mask_g] = 60 * ((b[mask_g] - r[mask_g]) / delta[mask_g]) + 120
    hue[mask_b] = 60 * ((r[mask_b] - g[mask_b]) / delta[mask_b]) + 240

    sat = np.where(mx > 0, delta / mx, 0)
    val = mx / 255.0

    # Teal: hue 150-195, sat>0.3, val>0.25
    in_hue = (hue >= 150) & (hue <= 200)
    in_sat = sat > 0.30
    in_val = val > 0.25

    return (in_hue & in_sat & in_val).astype(np.float32)

def find_dot_center(mask):
    """
    Find the dot (the small bright circular blob separate from the main orbital).
    We split the mask into connected components by checking where the teal is
    in a relatively small cluster away from the bulk.
    Returns (cx, cy, radius) or None.
    """
    from PIL import Image as _I
    # Convert mask to binary PIL image and find contours via simple blob detection
    ys, xs = np.where(mask > 0.5)
    if len(xs) == 0:
        return None

    # Use a simple approach: find the tightest cluster of teal pixels
    # The dot should be a compact circle ~10-20px radius
    # Use a sliding window: find centroid of smallest cluster
    # Actually: erode then find isolated blobs
    m_img = _I.fromarray((mask * 255).astype(np.uint8), 'L')
    eroded = m_img.filter(ImageFilter.MinFilter(9))  # erode by 4px
    e_np = np.array(eroded)
    ey, ex = np.where(e_np > 127)
    if len(ex) == 0:
        return None

    # The eroded teal should give us the "thick" parts; subtract to find thin orbital
    # But for the dot we want the densest compact region
    # Simple: use a grid of candidate centres, find the one with most teal in 20px radius
    h, w = mask.shape
    best_score = 0
    best_cx, best_cy = 0, 0
    step = 4
    for cy_c in range(0, h, step):
        for cx_c in range(0, w, step):
            y0, y1 = max(0, cy_c-20), min(h, cy_c+20)
            x0, x1 = max(0, cx_c-20), min(w, cx_c+20)
            patch = mask[y0:y1, x0:x1]
            score = patch.sum()
            if score > best_score:
                best_score = score
                best_cx, best_cy = cx_c, cy_c

    # Refine: centroid of teal within 25px of best
    ys2, xs2 = np.where(mask > 0.5)
    dists = np.sqrt((xs2 - best_cx)**2 + (ys2 - best_cy)**2)
    near = dists < 25
    if near.sum() == 0:
        return None
    cx = int(xs2[near].mean())
    cy = int(ys2[near].mean())
    radius = 12
    return cx, cy, radius

# ── per-frame processing ──────────────────────────────────────────────────────

def process_frame(src_path, dst_path):
    img = Image.open(src_path).convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    rgb = arr[:,:,:3]
    alpha = arr[:,:,3:4]
    h, w = rgb.shape[:2]

    # 1. Build teal mask
    mask = teal_mask(rgb.astype(np.uint8))

    # 2. Build 45° gradient image (same size)
    xs = np.arange(w, dtype=np.float32)
    ys = np.arange(h, dtype=np.float32)
    xx, yy = np.meshgrid(xs, ys)
    t = np.clip((xx / w + yy / h) / 2.0, 0, 1)[:,:,None]   # (h,w,1)
    grad_orbital = ORBITAL_START[None,None,:] * (1 - t) + ORBITAL_END[None,None,:] * t  # (h,w,3)

    # 3. Find dot in this frame and build radial gradient override
    dot_info = find_dot_center(mask)
    dot_mask = np.zeros((h, w), dtype=np.float32)
    dot_grad = np.zeros((h, w, 3), dtype=np.float32)

    if dot_info is not None:
        cx, cy, radius = dot_info
        dot_radius = 16  # paint a clean circle
        for dy in range(-dot_radius - 2, dot_radius + 3):
            for dx in range(-dot_radius - 2, dot_radius + 3):
                px, py = cx + dx, cy + dy
                if 0 <= px < w and 0 <= py < h:
                    dist = math.sqrt(dx*dx + dy*dy)
                    if dist <= dot_radius:
                        dot_mask[py, px] = 1.0
                        col = dot_radial_color(dx, dy, dot_radius)
                        dot_grad[py, px] = col

    # 4. Blend: teal pixels → gradient, dot pixels → dot gradient (priority)
    #    We apply as: out = mask * grad_orbital, then override with dot
    out = rgb.copy()
    mask3 = mask[:,:,None]
    out = out * (1 - mask3) + grad_orbital * mask3

    dot_mask3 = dot_mask[:,:,None]
    out = out * (1 - dot_mask3) + dot_grad * dot_mask3

    # 5. Reconstruct RGBA
    out_rgba = np.concatenate([np.clip(out, 0, 255), alpha], axis=2).astype(np.uint8)
    Image.fromarray(out_rgba, "RGBA").save(dst_path)
    return dot_info


print("Processing 24 animation frames...")
dot_positions = []
for i in range(24):
    src = f"{SRC}/{i:02d}.png"
    dst = f"{OUT_FRAMES}/{i:02d}.png"
    dot_info = process_frame(src, dst)
    dot_positions.append(dot_info)
    print(f"  {i:02d}.png done  dot={dot_info}")

print("All frames processed.")

# ── generate flash frames (when dot completes one orbit) ──────────────────────

def make_flash_frame(base_frame_path, intensity, dst_path):
    """Overlay a bright white-blue flash on the logo area."""
    img = Image.open(base_frame_path).convert("RGBA")
    arr = np.array(img, dtype=np.float32)
    flash_col = np.array([96, 239, 255], dtype=np.float32)  # #60EFFF cyan
    alpha = arr[:,:,3:4]
    rgb = arr[:,:,:3]

    # Flash: blend towards the cyan colour over the bright teal mask
    mask = teal_mask(rgb.astype(np.uint8))
    mask3 = mask[:,:,None]
    flashed = rgb + flash_col[None,None,:] * mask3 * intensity
    out = np.clip(flashed, 0, 255)

    # Also add a global brightness boost in the centre
    h, w = rgb.shape[:2]
    cx, cy = w//2, h//2
    xs = np.arange(w, dtype=np.float32) - cx
    ys = np.arange(h, dtype=np.float32) - cy
    xx, yy = np.meshgrid(xs, ys)
    radial = np.exp(-(xx**2 + yy**2) / (2 * (w*0.2)**2))[:,:,None]
    out = np.clip(out + 80 * intensity * radial, 0, 255)

    out_rgba = np.concatenate([out, alpha], axis=2).astype(np.uint8)
    Image.fromarray(out_rgba, "RGBA").save(dst_path)

# Base for flash = frame 00 (dot at origin/right side of orbit)
base = f"{OUT_FRAMES}/00.png"
flash_dir = f"{OUT_FRAMES}_flash"
os.makedirs(flash_dir, exist_ok=True)

flash_levels = [0.3, 0.7, 1.0, 0.7, 0.3, 0.1]
for fi, lv in enumerate(flash_levels):
    make_flash_frame(base, lv, f"{flash_dir}/flash_{fi:02d}.png")

print("Flash frames done.")

# ── build video with ffmpeg ───────────────────────────────────────────────────
# Sequence:
#   frames 00-23 at 6 fps (slow orbit, 4 s)
#   flash frames  at 18 fps (quick flash, ~0.3 s)
#   repeat

# Write a concat file listing all frames with durations
concat_path = f"{OUT_FRAMES}/concat.txt"
with open(concat_path, "w") as f:
    # Slow orbit (24 frames, each shown for 1/6 s)
    for i in range(24):
        f.write(f"file '{OUT_FRAMES}/{i:02d}.png'\n")
        f.write("duration 0.1667\n")
    # Flash burst
    for fi in range(len(flash_levels)):
        f.write(f"file '{flash_dir}/flash_{fi:02d}.png'\n")
        f.write("duration 0.055\n")
    # Hold on frame 00 briefly before loop
    f.write(f"file '{OUT_FRAMES}/00.png'\n")
    f.write("duration 0.2\n")
    # ffmpeg concat demuxer needs the last entry without duration
    f.write(f"file '{OUT_FRAMES}/00.png'\n")

import subprocess
cmd = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0",
    "-i", concat_path,
    "-vf", "scale=512:512,format=yuv420p",
    "-c:v", "libx264",
    "-crf", "18",
    "-preset", "slow",
    "-movflags", "+faststart",
    "-loop", "0",
    VIDEO_OUT
]
result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode != 0:
    print("ffmpeg stderr:", result.stderr[-2000:])
else:
    print(f"\nVideo saved → {VIDEO_OUT}")

# Also make a transparent animated WebM (better for web use)
WEBM_OUT = VIDEO_OUT.replace(".mp4", ".webm")
cmd2 = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0",
    "-i", concat_path,
    "-vf", "scale=512:512",
    "-c:v", "libvpx-vp9",
    "-b:v", "0", "-crf", "30",
    "-pix_fmt", "yuva420p",
    WEBM_OUT
]
result2 = subprocess.run(cmd2, capture_output=True, text=True)
if result2.returncode != 0:
    print("webm ffmpeg stderr:", result2.stderr[-1000:])
else:
    print(f"WebM saved  → {WEBM_OUT}")
