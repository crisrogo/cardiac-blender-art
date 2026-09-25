"""
EP video, stage 3: assemble the rendered beat into the final video.

    python compose_ep_video.py <look_dir> <black|white> <out.mp4> [--beats 3] [--label "HCM patient 1"]
    python compose_ep_video.py <look_dir> <black|white> <out.png> --still <t_ms>
    python compose_ep_video.py <look_dir> white <out.mp4> --plain [--slow 5 --cl 800 --beats 3]
    python compose_ep_video.py <look_dir> white <out.mp4> --mech [--beats 6]
    python compose_ep_video.py <look_dir> white <out.mp4> --arrhythmia [--beats 1]

--mech encodes what `render_ep_video.py mech` planned (meta_mech.json +
raw_mech/): EP and contraction together, timing fixed at render time.

--plain is the heart alone (no text) at its real cycle length, `--slow` times slower
than real time, each video frame motion-blurred from the 1-ms renders it covers.

<look_dir> is <case>/ep_<sample>/<style>_<finish> as written by
`render_ep_video.py beat` (raw/f_NNNN.png RGBA + meta.json). The heart is put on
the background at 1920x1080, with a ms clock, a beat timeline (atria / AV delay /
ventricles with a playhead) and, for the map style, one CARTO colour bar per region.

Timeline per beat: rest -> activation (1 sim ms per frame by default) -> map held ->
map fades back to rest -> short rest. Diastole is compressed (the beat is not at
real cycle length); the slow-motion factor is printed under the clock.
Encodes with ffmpeg (on PATH), streaming raw frames — nothing large touches disk.
"""
import argparse
import json
import os
import subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1920, 1080, 30
FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")


def font(name, size):
    try:
        return ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    except OSError:
        return ImageFont.load_default()


F_CLOCK = font("consola.ttf", 64)
F_LABEL = font("segoeuisl.ttf", 30)
F_SMALL = font("segoeuisl.ttf", 24)
F_HEAD = font("segoeuib.ttf", 30)


def lin_to_srgb(c):
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def ramp_image(stops, w, h):
    """Colour bar as Blender's ColorRamp draws it (linear interpolation in linear RGB)."""
    pos = np.array([s[0] for s in stops]); col = srgb_to_lin(np.array([s[1] for s in stops]))
    x = np.linspace(0, 1, w)
    rgb = np.stack([np.interp(x, pos, col[:, k]) for k in range(3)], 1)
    row = (np.clip(lin_to_srgb(rgb), 0, 1) * 255).astype(np.uint8)
    return Image.fromarray(np.repeat(row[None], h, 0), "RGB")


class Composer:
    def __init__(self, look_dir, bg, label):
        self.dir = look_dir
        self.meta = json.load(open(os.path.join(look_dir, "meta.json")))
        self.bg = (0, 0, 0) if bg == "black" else (255, 255, 255)
        self.fg = (235, 235, 235) if bg == "black" else (25, 25, 28)
        self.dim = (120, 120, 124) if bg == "black" else (140, 140, 146)
        self.label = label
        m = self.meta
        self.av = m["av_delay"]; self.rng = m["at_range"]; self.end = m["end_ms"]
        self.map = m["style"] == "map"
        self.cache = {}

    def heart(self, name):
        if name not in self.cache:
            self.cache.clear()                                     # frames are read in order
            im = Image.open(os.path.join(self.dir, "raw", name)).convert("RGBA")
            if im.size != (H, H):
                im = im.resize((H, H), Image.LANCZOS)
            self.cache[name] = im
        return self.cache[name]

    def frame(self, name, t_ms):
        img = Image.new("RGB", (W, H), self.bg)
        img.paste(self.heart(name), (300, 0), self.heart(name))
        d = ImageDraw.Draw(img)
        t = max(0.0, t_ms)

        # clock + slow-motion factor
        d.text((80, 70), f"t = {t:3.0f} ms", font=F_CLOCK, fill=self.fg)
        slow = 1000.0 / (FPS * self.meta["ms_per_frame"])
        d.text((84, 150), f"{slow:.0f}\u00d7 slower than real time", font=F_SMALL, fill=self.dim)
        if self.label:
            d.text((80, H - 120), self.label, font=F_HEAD, fill=self.fg)
            d.text((80, H - 80), "Reaction\u2013eikonal activation times", font=F_SMALL, fill=self.dim)

        x0, x1 = 1480, 1840
        # beat timeline: atria bar, AV-delay marker, ventricles bar, playhead
        y = 110
        d.text((x0, y - 50), "Beat timeline", font=F_HEAD, fill=self.fg)
        span = max(self.end, 1.0)
        sx = lambda ms: x0 + (x1 - x0) * ms / span
        for (a, b), nm, yy in (((0, self.rng[0][1]), "Atria", y + 10),
                               ((self.av, self.av + self.rng[1][1]), "Ventricles", y + 70)):
            live = a <= t <= b
            d.rounded_rectangle((sx(a), yy + 30, sx(b), yy + 44), 7,
                                fill=self.fg if (live or t > b) else self.dim)
            d.text((sx(a) + (8 if a > 0 else 0), yy - 4), nm, font=F_SMALL, fill=self.fg if live else self.dim)
        d.line((sx(self.av), y + 30, sx(self.av), y + 124), fill=self.dim, width=2)
        d.text((sx(self.av) + 6, y + 126), f"AV delay {self.av:.0f} ms", font=F_SMALL, fill=self.dim)
        px = sx(min(t, span))
        d.line((px, y + 20, px, y + 124), fill=(230, 60, 40), width=4)

        if self.map:
            stops = [(p, tuple(c)) for p, c in self.meta["carto"]]
            bar = ramp_image(stops, x1 - x0, 26)
            yy = 390
            d.text((x0, yy - 50), "Activation time", font=F_HEAD, fill=self.fg)
            for (lo, hi), nm, off in ((self.rng[0], "Atria", 0.0), (self.rng[1], "Ventricles", self.av)):
                img.paste(bar, (x0, yy + 40))
                d.rectangle((x0, yy + 40, x1, yy + 66), outline=self.dim)
                d.text((x0, yy), nm, font=F_LABEL, fill=self.fg)
                d.text((x0, yy + 72), f"{lo:.0f}", font=F_SMALL, fill=self.dim)
                s = f"{hi:.0f} ms"
                d.text((x1 - d.textlength(s, font=F_SMALL), yy + 72), s, font=F_SMALL, fill=self.dim)
                loc = t - off                                       # this region's own clock
                if lo <= loc <= hi:
                    mx = x0 + (x1 - x0) * (loc - lo) / max(hi - lo, 1e-3)
                    d.polygon([(mx - 9, yy + 30), (mx + 9, yy + 30), (mx, yy + 42)], fill=self.fg)
                yy += 170
            d.text((x0, yy - 50), "early", font=F_SMALL, fill=self.dim)
            d.text((x1 - d.textlength("late", font=F_SMALL), yy - 50), "late", font=F_SMALL, fill=self.dim)
        return img

    def timeline(self, beats):
        m = self.meta; n = m["n_frames"]; mpf = m["ms_per_frame"]
        one = [("f_0000.png", 0.0)] * int(0.4 * FPS)
        one += [(f"f_{i:04d}.png", (i - 1) * mpf) for i in range(n)]
        last_t = (n - 2) * mpf
        if self.map:
            one += [(f"f_{n - 1:04d}.png", last_t)] * int(1.6 * FPS)
            fades = sorted(f for f in os.listdir(os.path.join(self.dir, "raw")) if f.startswith("fade_"))
            one += [(f, last_t) for f in fades for _ in range(2)]
        one += [("f_0000.png", 0.0)] * int(0.2 * FPS)
        return one * beats


class PlainComposer:
    """Only the heart, no text, beats at their real cycle length, played `slow` times
    slower than real time. Each video frame averages the 1-ms renders its shutter
    covers (motion blur), so any speed can be cut from one render."""
    def __init__(self, look_dir, bg, slow, cl, shutter, lead):
        self.dir = look_dir
        self.meta = json.load(open(os.path.join(look_dir, "meta.json")))
        self.bg = np.array((0, 0, 0) if bg == "black" else (255, 255, 255), np.float32)
        self.dt = 1000.0 / (FPS * slow)                 # sim ms per video frame
        self.cl, self.shutter, self.lead = cl, shutter, lead
        self.cache = {}

    def raw(self, t):
        """Composited render at sim time t (ms from atrial onset); rest outside the beat."""
        m = self.meta
        i = int(round(t / m["ms_per_frame"])) + 1
        if i < 1 or i >= m["n_frames"]:
            i = 0
        if i not in self.cache:
            if len(self.cache) > 48:
                self.cache.pop(next(iter(self.cache)))
            im = np.asarray(Image.open(os.path.join(self.dir, "raw", f"f_{i:04d}.png")).convert("RGBA"),
                            np.float32)
            a = im[..., 3:] / 255.0
            self.cache[i] = im[..., :3] * a + self.bg * (1 - a)
        return self.cache[i]

    def frame(self, k):
        t_end = (k * self.dt) % self.cl - self.lead
        n = max(1, int(round(self.shutter * self.dt / self.meta["ms_per_frame"])))
        acc = sum(self.raw(t_end - j * self.meta["ms_per_frame"]) for j in range(n)) / n
        heart = Image.fromarray(np.clip(acc + 0.5, 0, 255).astype(np.uint8), "RGB")
        if heart.size != (H, H):
            heart = heart.resize((H, H), Image.LANCZOS)
        img = Image.new("RGB", (W, H), tuple(int(x) for x in self.bg))
        img.paste(heart, ((W - H) // 2, 0))
        return img


class MechComposer:
    """Heart only, following the timeline `render_ep_video.py mech` planned: each
    video frame is the average of the renders listed for it (motion blur)."""
    def __init__(self, look_dir, bg, kind="mech"):
        self.dir, self.kind = look_dir, kind
        self.meta = json.load(open(os.path.join(look_dir, f"meta_{kind}.json")))
        self.bg = np.array((0, 0, 0) if bg == "black" else (255, 255, 255), np.float32)
        self.cache = {}

    def raw(self, key):
        if key not in self.cache:
            if len(self.cache) > 12:
                self.cache.pop(next(iter(self.cache)))
            name = key if isinstance(key, str) else f"t_{key:05d}"     # arrhythmia keys are names
            im = np.asarray(Image.open(os.path.join(self.dir, f"raw_{self.kind}", name + ".png")).convert("RGBA"),
                            np.float32)
            a = im[..., 3:] / 255.0
            self.cache[key] = im[..., :3] * a + self.bg * (1 - a)
        return self.cache[key]

    def frame(self, keys):
        acc = sum(self.raw(k) for k in keys) / len(keys)
        heart = Image.fromarray(np.clip(acc + 0.5, 0, 255).astype(np.uint8), "RGB")
        if heart.size != (H, H):
            heart = heart.resize((H, H), Image.LANCZOS)
        img = Image.new("RGB", (W, H), tuple(int(x) for x in self.bg))
        img.paste(heart, ((W - H) // 2, 0))
        return img


def encode(frames, n, out):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "18", "-preset", "medium",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for img in frames:
        p.stdin.write(img.tobytes())
    p.stdin.close(); p.wait()
    print(f"[compose] {out}: {n} frames, {n / FPS:.1f} s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("look_dir"); ap.add_argument("bg", choices=["black", "white"]); ap.add_argument("out")
    ap.add_argument("--beats", type=int, default=None, help="default 6 for --mech, else 3")
    ap.add_argument("--label", default="")
    ap.add_argument("--still", type=float, default=None)
    ap.add_argument("--plain", action="store_true", help="heart only, real cycle length, see --slow/--cl")
    ap.add_argument("--slow", type=float, default=5.0, help="--plain: times slower than real time")
    ap.add_argument("--cl", type=float, default=800.0, help="--plain: cycle length (ms)")
    ap.add_argument("--shutter", type=float, default=0.5, help="--plain: fraction of a frame blurred")
    ap.add_argument("--lead", type=float, default=150.0, help="--plain: rest (ms) before each activation")
    ap.add_argument("--mech", action="store_true", help="EP + contraction, as planned by `render_ep_video.py mech`")
    ap.add_argument("--arrhythmia", action="store_true",
                    help="the randomised loop planned by `render_ep_video.py arrhythmia` (already N beats)")
    a = ap.parse_args()
    if a.beats is None:
        a.beats = 1 if a.arrhythmia else 6 if a.mech else 3
    if a.mech or a.arrhythmia:
        c = MechComposer(a.look_dir, a.bg, "arrhythmia" if a.arrhythmia else "mech")
        tl = c.meta["timeline"] * a.beats
        encode((c.frame(keys) for keys in tl), len(tl), a.out)
        return
    if a.plain:
        c = PlainComposer(a.look_dir, a.bg, a.slow, a.cl, a.shutter, a.lead)
        n = int(round(a.beats * a.cl / c.dt))
        if a.still is not None:
            c.frame(int(round((a.still + a.lead) / c.dt))).save(a.out)
            return
        encode((c.frame(k) for k in range(n)), n, a.out)
        return
    c = Composer(a.look_dir, a.bg, a.label)
    if a.still is not None:
        i = int(round(a.still / c.meta["ms_per_frame"])) + 1
        c.frame(f"f_{i:04d}.png", a.still).save(a.out)
        return
    tl = c.timeline(a.beats)
    encode((c.frame(name, t) for name, t in tl), len(tl), a.out)


if __name__ == "__main__":
    main()
