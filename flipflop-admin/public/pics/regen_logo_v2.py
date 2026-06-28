#!/usr/bin/env python3.10
"""
FlipFlop logo recolor v2 — correct dot detection via frame differencing.

Orbital + chip → 45° linear gradient #0061FF → #60EFFF
Dot            → radial gradient     #FF0F7B (centre) → #F89B29 (edge)
Video          → slow orbit + quick flash on return, looping
"""

import os, math, subprocess
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

SRC        = "/home/mac/CODING/FlipFlop/pc-flipper/public/pics/logo_animation"
OUT_FRAMES = "/home/mac/CODING/FlipFlop/pc-flipper/public/pics/logo_animation_v2"
FLASH_DIR  = "/home/mac/CODING/FlipFlop/pc-flipper/public/pics/logo_animation_v2_flash"
VIDEO_OUT  = "/home/mac/CODING/FlipFlop/pc-flipper/public/pics/flipflop_logo.mp4"
WEBM_OUT   = "/home/mac/CODING/FlipFlop/pc-flipper/public/pics/flipflop_logo.webm"

os.makedirs(OUT_FRAMES, exist_ok=True)
os.makedirs(FLASH_DIR, exist_ok=True)

# ── gradient colours ──────────────────────────────────────────────────────────

def hsl(h, s, l):
    c = (1 - abs(2*l - 1)) * s
    x = c * (1 - abs((h/60) % 2 - 1))
    m = l - c/2
    if   h < 60:  r,g,b = c,x,0
    elif h < 120: r,g,b = x,c,0
    elif h < 180: r,g,b = 0,c,x
    elif h < 240: r,g,b = 0,x,c
    elif h < 300: r,g,b = x,0,c
    else:         r,g,b = c,0,x
    return np.array([(r+m)*255, (g+m)*255, (b+m)*255], dtype=np.float32)

ORB_START = hsl(217, 1.00, 0.50)   # #0061FF
ORB_END   = hsl(186, 1.00, 0.69)   # #60EFFF
DOT_IN    = hsl(333, 1.00, 0.53)   # #FF0F7B
DOT_OUT   = hsl( 33, 0.94, 0.57)   # #F89B29

DOT_RADIUS = 15  # pixels

# ── helpers ───────────────────────────────────────────────────────────────────

def teal_mask_np(rgb_uint8):
    """Float 0-1 mask for teal/cyan hues in the logo."""
    r, g, b = rgb_uint8[:,:,0].astype(np.float32), \
               rgb_uint8[:,:,1].astype(np.float32), \
               rgb_uint8[:,:,2].astype(np.float32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    delta = mx - mn + 1e-6
    hue = np.zeros_like(r)
    mr, mg, mb_ = (mx==r), (mx==g), (mx==b)
    hue[mr]  = (60 * ((g[mr]  - b[mr])  / delta[mr]))  % 360
    hue[mg]  =  60 * ((b[mg]  - r[mg])  / delta[mg])   + 120
    hue[mb_] =  60 * ((r[mb_] - g[mb_]) / delta[mb_])  + 240
    sat = np.where(mx > 0, delta/mx, 0)
    val = mx / 255.0
    return ((hue >= 150) & (hue <= 200) & (sat > 0.25) & (val > 0.20)).astype(np.float32)

def orbital_gradient(w, h):
    """45° linear gradient image (h,w,3) float."""
    xs = np.linspace(0, 1, w, dtype=np.float32)
    ys = np.linspace(0, 1, h, dtype=np.float32)
    xx, yy = np.meshgrid(xs, ys)
    t = np.clip((xx + yy) / 2.0, 0, 1)[:,:,None]
    return ORB_START * (1-t) + ORB_END * t

def dot_radial_patch(radius):
    """Returns (2r+1, 2r+1, 3) float patch of radial gradient + alpha mask."""
    d = 2*radius + 1
    patch = np.zeros((d, d, 3), dtype=np.float32)
    alpha = np.zeros((d, d), dtype=np.float32)
    for dy in range(-radius, radius+1):
        for dx in range(-radius, radius+1):
            dist = math.sqrt(dx*dx + dy*dy)
            if dist <= radius:
                t = np.clip(dist / radius, 0, 1)
                col = DOT_IN * (1-t) + DOT_OUT * t
                patch[dy+radius, dx+radius] = col
                alpha[dy+radius, dx+radius] = 1.0
    return patch, alpha

DOT_PATCH, DOT_ALPHA = dot_radial_patch(DOT_RADIUS)

# ── load all original frames, compute average to detect dot positions ─────────

print("Loading frames and computing average...")
raw_frames = []
for i in range(24):
    raw_frames.append(np.array(Image.open(f"{SRC}/{i:02d}.png").convert("RGBA"), dtype=np.float32))

avg = np.mean(raw_frames, axis=0)   # (h,w,4) — static parts bright, dot smeared

def find_dot_pos(frame_arr, avg_arr):
    """Return (cx, cy) of dot by comparing frame to average."""
    diff = (frame_arr[:,:,:3] - avg_arr[:,:,:3]).sum(axis=2)
    positive = (diff > 15) & (frame_arr[:,:,3] > 200)
    ys, xs = np.where(positive)
    if len(xs) == 0:
        return (256, 256)
    return (int(xs.mean()), int(ys.mean()))

print("Detecting dot positions...")
dot_positions = []
for i in range(24):
    pos = find_dot_pos(raw_frames[i], avg)
    dot_positions.append(pos)
    print(f"  Frame {i:02d}: dot at {pos}")

# ── process each frame ────────────────────────────────────────────────────────

h, w = raw_frames[0].shape[:2]
grad = orbital_gradient(w, h)  # (h,w,3) pre-computed

def process_frame(frame_arr, dot_cx, dot_cy, dst_path):
    rgb  = frame_arr[:,:,:3]
    alph = frame_arr[:,:,3:4]

    # 1. Teal mask → apply orbital gradient
    mask = teal_mask_np(rgb.astype(np.uint8))
    mask3 = mask[:,:,None]
    out = rgb * (1 - mask3) + grad * mask3

    # 2. Paint dot radial gradient on top at detected position
    r = DOT_RADIUS
    y0, y1 = dot_cy - r, dot_cy + r + 1
    x0, x1 = dot_cx - r, dot_cx + r + 1
    # Clamp to image bounds
    py0 = max(0, -y0); py1 = DOT_PATCH.shape[0] - max(0, y1-h)
    px0 = max(0, -x0); px1 = DOT_PATCH.shape[1] - max(0, x1-w)
    iy0, iy1 = max(0, y0), min(h, y1)
    ix0, ix1 = max(0, x0), min(w, x1)

    da = DOT_ALPHA[py0:py1, px0:px1, None]
    dp = DOT_PATCH[py0:py1, px0:px1]
    out[iy0:iy1, ix0:ix1] = out[iy0:iy1, ix0:ix1] * (1 - da) + dp * da

    # 3. Glow around dot
    glow_img = Image.new("RGBA", (w, h), (0,0,0,0))
    gd = ImageDraw.Draw(glow_img)
    gd.ellipse([dot_cx-r-6, dot_cy-r-6, dot_cx+r+6, dot_cy+r+6],
               fill=(255, 80, 150, 80))
    glow_arr = np.array(glow_img.filter(ImageFilter.GaussianBlur(radius=8)), dtype=np.float32)
    ga = glow_arr[:,:,3:4] / 255.0
    grgb = glow_arr[:,:,:3]
    out = out * (1 - ga) + grgb * ga

    rgba_out = np.concatenate([np.clip(out, 0, 255), alph], axis=2).astype(np.uint8)
    Image.fromarray(rgba_out, "RGBA").save(dst_path)

print("\nProcessing frames...")
for i in range(24):
    cx, cy = dot_positions[i]
    process_frame(raw_frames[i], cx, cy, f"{OUT_FRAMES}/{i:02d}.png")
    print(f"  {i:02d}.png done")

print("Frames done.")

# ── flash frames (dot returns to start position = frame 00) ──────────────────

def make_flash(base_rgba, dot_cx, dot_cy, intensity, dst_path):
    rgb  = base_rgba[:,:,:3].copy().astype(np.float32)
    alph = base_rgba[:,:,3:4]
    # 1. Bright burst of orbital color over teal pixels
    mask  = teal_mask_np(rgb.astype(np.uint8))
    flash = np.array([96, 239, 255], dtype=np.float32)
    rgb   = np.clip(rgb + flash * mask[:,:,None] * intensity, 0, 255)
    # 2. Radial glow from centre
    xs = np.arange(w, dtype=np.float32) - w//2
    ys_arr = np.arange(h, dtype=np.float32) - h//2
    xx, yy = np.meshgrid(xs, ys_arr)
    radial = np.exp(-(xx**2 + yy**2) / (2*(w*0.22)**2))[:,:,None]
    rgb = np.clip(rgb + 100 * intensity * radial, 0, 255)
    # 3. Dot itself flashes white → pink
    t_flash = max(0, 1 - intensity)
    r = DOT_RADIUS + int(intensity * 6)
    patch_f, alpha_f = dot_radial_patch(r)
    flash_dot = patch_f * (1-t_flash) + np.array([255,255,255],dtype=np.float32) * t_flash
    y0, y1 = dot_cy-r, dot_cy+r+1
    x0, x1 = dot_cx-r, dot_cx+r+1
    py0 = max(0,-y0); py1 = patch_f.shape[0] - max(0,y1-h)
    px0 = max(0,-x0); px1 = patch_f.shape[1] - max(0,x1-w)
    iy0,iy1 = max(0,y0), min(h,y1)
    ix0,ix1 = max(0,x0), min(w,x1)
    da = alpha_f[py0:py1, px0:px1, None]
    dp = flash_dot[py0:py1, px0:px1]
    rgb[iy0:iy1, ix0:ix1] = rgb[iy0:iy1, ix0:ix1] * (1-da) + dp * da

    out = np.concatenate([np.clip(rgb,0,255), alph], axis=2).astype(np.uint8)
    Image.fromarray(out, "RGBA").save(dst_path)

# Base frame for flash = frame 00 (dot at origin, right side)
base_frame = np.array(Image.open(f"{OUT_FRAMES}/00.png").convert("RGBA"), dtype=np.float32)
fx0, fy0 = dot_positions[0]

# Flash curve: ramp up then decay
flash_intensities = [0.25, 0.55, 0.85, 1.0, 0.85, 0.55, 0.30, 0.15]
for fi, lv in enumerate(flash_intensities):
    make_flash(base_frame, fx0, fy0, lv, f"{FLASH_DIR}/flash_{fi:02d}.png")

print(f"{len(flash_intensities)} flash frames done.")

# ── build video ───────────────────────────────────────────────────────────────

concat_path = f"{OUT_FRAMES}/concat.txt"
with open(concat_path, "w") as f:
    # Slow orbit: ~4 seconds total for 24 frames → ~0.167s each
    for i in range(24):
        f.write(f"file '{OUT_FRAMES}/{i:02d}.png'\n")
        f.write("duration 0.167\n")
    # Flash burst at ~18 fps
    for fi in range(len(flash_intensities)):
        f.write(f"file '{FLASH_DIR}/flash_{fi:02d}.png'\n")
        f.write("duration 0.056\n")
    # Brief hold on frame 00 before loop
    f.write(f"file '{OUT_FRAMES}/00.png'\n")
    f.write("duration 0.25\n")
    # ffmpeg concat needs a trailing entry without duration
    f.write(f"file '{OUT_FRAMES}/00.png'\n")

cmd = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0",
    "-i", concat_path,
    "-vf", "scale=512:512,format=yuv420p",
    "-c:v", "libx264", "-crf", "16", "-preset", "slow",
    "-movflags", "+faststart",
    VIDEO_OUT
]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode != 0:
    print("MP4 ffmpeg error:\n", r.stderr[-2000:])
else:
    print(f"\nMP4 saved → {VIDEO_OUT}")

# Transparent WebM
cmd2 = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0",
    "-i", concat_path,
    "-vf", "scale=512:512",
    "-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "22",
    "-pix_fmt", "yuva420p",
    WEBM_OUT
]
r2 = subprocess.run(cmd2, capture_output=True, text=True)
if r2.returncode != 0:
    print("WebM ffmpeg error:\n", r2.stderr[-1000:])
else:
    print(f"WebM saved  → {WEBM_OUT}")
