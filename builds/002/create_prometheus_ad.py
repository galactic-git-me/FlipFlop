from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import math, random, subprocess

ROOT = Path(__file__).resolve().parent
MEDIA = ROOT / 'Media'
OUT = ROOT / 'social-ad'
OUT.mkdir(exist_ok=True)
W, H = 1080, 1350
BG = (5, 10, 17)
GOLD = (255, 172, 53)
BLUE = (56, 150, 255)
WHITE = (246, 248, 252)
MUTED = (167, 181, 199)
FONT_DIR = Path('C:/Windows/Fonts')

def font(name, size):
    return ImageFont.truetype(str(FONT_DIR / name), size)

def rr(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def base_frame(frame=0):
    im = Image.new('RGB', (W, H), BG)
    # Low-key blue/orange atmosphere, kept behind the typography.
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((-330, 180, 440, 950), fill=(255, 105, 24, 80))
    gd.ellipse((650, 70, 1410, 890), fill=(17, 91, 255, 78))
    glow = glow.filter(ImageFilter.GaussianBlur(145))
    im = Image.alpha_composite(im.convert('RGBA'), glow).convert('RGB')
    # Fine, quiet technical grid.
    grid = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(grid)
    for x in range(0, W, 72): d.line((x, 0, x, H), fill=(110, 151, 193, 13), width=1)
    for y in range(0, H, 72): d.line((0, y, W, y), fill=(110, 151, 193, 11), width=1)
    im = Image.alpha_composite(im.convert('RGBA'), grid).convert('RGB')
    return im

def compose(frame=0, animate=False):
    im = base_frame(frame)
    draw = ImageDraw.Draw(im)

    # Brand lockup: use the supplied genuine FlipFlop logo artwork.
    logo = Image.open(ROOT / 'Performance' / 'assets' / 'logo.png').convert('RGBA')
    logo.thumbnail((92, 92), Image.Resampling.LANCZOS)
    logo = logo.crop(logo.getbbox())
    # Logo art includes its own dark glow, so keep a quiet dark tile behind it.
    rr(draw, (48, 38, 164, 154), 18, (7, 13, 22))
    im.paste(logo, (60, 50), logo)
    draw = ImageDraw.Draw(im)
    draw.text((181, 64), 'FLIPFLOP  /  THE FIRST BUILD', font=font('arial.ttf', 20), fill=WHITE)
    draw.text((181, 94), 'BEAUTIFUL MACHINES. BUILT TO BE ADMIRED.', font=font('arial.ttf', 14), fill=MUTED)
    rr(draw, (820, 53, 1031, 103), 20, (8, 15, 25), outline=(78, 98, 121), width=1)
    draw.text((850, 68), 'BLACK FRIDAY', font=font('arialbd.ttf', 16), fill=WHITE)

    # Headline.
    draw.text((54, 183), 'MEET', font=font('arialbd.ttf', 25), fill=GOLD)
    draw.text((50, 210), 'PROMETHEUS', font=font('arialbd.ttf', 67), fill=WHITE, stroke_width=1, stroke_fill=(50, 71, 94))
    draw.text((57, 292), 'Your next-level gaming rig has arrived.', font=font('arial.ttf', 24), fill=MUTED)

    # Showcase panel and genuine full-res product photograph.
    panel = (35, 346, 1045, 880)
    rr(draw, panel, 28, (8, 14, 23), outline=(69, 104, 148), width=2)
    photo = Image.open(MEDIA / '1757491c53e246808aa45d69e2b48185.png').convert('RGB')
    # Contain the complete machine in a widescreen product showcase.
    pw, ph = 960, 492
    scale = min(pw / photo.width, ph / photo.height)
    photo = photo.resize((round(photo.width * scale), round(photo.height * scale)), Image.Resampling.LANCZOS)
    canvas = Image.new('RGB', (pw, ph), (9, 17, 28))
    canvas.paste(photo, ((pw - photo.width) // 2, (ph - photo.height) // 2))
    photo = canvas
    im.paste(photo, ((W - pw) // 2, 362))
    # Soft vignette fades the real room photograph into the cinematic ad.
    fade = Image.new('RGBA', (W, 520), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fade)
    for i in range(100):
        alpha = int(215 * (1 - i / 100) ** 2)
        fd.line((35, i, 1045, i), fill=(5, 10, 17, alpha), width=1)
        fd.line((35, 520-i, 1045, 520-i), fill=(5, 10, 17, alpha), width=1)
    # Keep the photograph vivid; feather only its lower edge into the panel.
    for i in range(105):
        alpha = int(230 * (i / 104) ** 2)
        fd.line((60, 760 + i, 1020, 760 + i), fill=(5, 10, 17, alpha), width=1)
    im.paste(fade, (0, 346), fade)
    draw = ImageDraw.Draw(im)
    rr(draw, (65, 378, 289, 423), 17, (7, 12, 19, 226), outline=(255, 172, 53), width=1)
    draw.text((84, 390), 'BUILT TO PLAY. READY TO SHIP.', font=font('arialbd.ttf', 12), fill=WHITE)
    rr(draw, (792, 792, 1015, 844), 18, (8, 15, 26, 234), outline=(62, 151, 255), width=1)
    draw.text((819, 806), '7800X3D  +  RTX 3070', font=font('arialbd.ttf', 14), fill=(194, 224, 255))

    # Small technical proof points, distilled from the build's own records.
    cards = [(45, 'CPU', 'RYZEN 7', '7800X3D'), (299, 'GPU', 'GEFORCE RTX', '3070  ·  8GB'),
             (553, 'MEMORY', '32GB DDR5', '6400 MT/s'), (807, 'STORAGE', '1TB NVMe', 'FAST LOADS')]
    for x0, label, line1, line2 in cards:
        rr(draw, (x0, 903, x0 + 227, 1002), 18, (14, 22, 34), outline=(51, 76, 101), width=1)
        draw.text((x0 + 16, 916), label, font=font('arialbd.ttf', 13), fill=GOLD)
        draw.text((x0 + 16, 941), line1, font=font('arialbd.ttf', 16), fill=WHITE)
        draw.text((x0 + 16, 966), line2, font=font('arial.ttf', 14), fill=MUTED)

    # Offer card.
    rr(draw, (45, 1020, 1035, 1235), 24, (12, 19, 28), outline=(255, 172, 53), width=2)
    rr(draw, (68, 1040, 274, 1082), 17, (255, 172, 53))
    draw.text((91, 1051), 'BLACK FRIDAY', font=font('arialbd.ttf', 15), fill=(14, 15, 18))
    draw.text((78, 1097), 'RRP', font=font('arialbd.ttf', 14), fill=MUTED)
    old_box = draw.textbbox((78, 1115), '£1,780', font=font('arialbd.ttf', 35))
    draw.text((78, 1115), '£1,780', font=font('arialbd.ttf', 35), fill=(194, 200, 209))
    draw.line((old_box[0], 1136, old_box[2], 1136), fill=(255, 91, 82), width=4)
    draw.text((78, 1160), 'SAVE £381', font=font('arialbd.ttf', 18), fill=GOLD)
    draw.text((362, 1089), '£1,399', font=font('arialbd.ttf', 73), fill=WHITE)
    draw.text((369, 1170), '21.4% OFF', font=font('arialbd.ttf', 22), fill=(113, 194, 255))
    rr(draw, (806, 1053, 1005, 1113), 18, (115, 26, 22), outline=(255, 102, 78), width=1)
    draw.text((834, 1075), 'LAST ONE', font=font('arialbd.ttf', 18), fill=WHITE)
    draw.text((817, 1132), 'in stock*', font=font('arial.ttf', 18), fill=(255, 193, 184))

    # Delivery choice and clean CTA.
    draw.text((61, 1262), 'CHOOSE YOUR PACE', font=font('arialbd.ttf', 16), fill=WHITE)
    draw.text((61, 1290), 'Need it sooner? Choose next-business-day delivery at checkout. Prefer a bargain? Wait longer and pay less with Flexible delivery.', font=font('arial.ttf', 13), fill=MUTED)
    draw.text((777, 1260), 'SHOP THE FIRST BUILD  →', font=font('arialbd.ttf', 16), fill=GOLD)
    draw.text((935, 1315), 'theflipflop.shop', font=font('arialbd.ttf', 15), fill=WHITE)

    if animate:
        # A restrained parallax sweep plus animated orange/blue perimeter light.
        sweep_x = int(-380 + ((frame * 19) % 1570))
        overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        od.polygon([(sweep_x, 346), (sweep_x + 90, 346), (sweep_x + 380, 880), (sweep_x + 290, 880)], fill=(91, 174, 255, 14))
        od.rounded_rectangle((35, 346, 1045, 880), radius=28, outline=(70, 144, 255, 70 + (frame % 8) * 5), width=2)
        im = Image.alpha_composite(im.convert('RGBA'), overlay).convert('RGB')
    return im

def main():
    # Static 4:5 paid/social feed master.
    compose().save(OUT / 'prometheus-black-friday-1080x1350.png', optimize=True)
    # Short 9-second 720x900 animated feed/reel edit; slow cinematic sweep.
    frames_dir = OUT / 'frames'
    frames_dir.mkdir(exist_ok=True)
    for i in range(36):
        frame = compose(i, True).resize((720, 900), Image.Resampling.LANCZOS)
        frame.save(frames_dir / f'frame-{i:03}.png', optimize=True)
    ffmpeg = 'C:/Users/mclar/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1.2-full_build/bin/ffmpeg.exe'
    subprocess.run([ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-framerate', '4', '-i', str(frames_dir / 'frame-%03d.png'),
                    '-vf', 'fps=24,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-movflags', '+faststart',
                    str(OUT / 'prometheus-black-friday-animated.mp4')], check=True)

if __name__ == '__main__':
    main()
