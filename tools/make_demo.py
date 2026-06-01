#!/usr/bin/env python3
"""Render an animated demo GIF of an auto-improve run (score climbing over iterations).

Reads a results/<tag>.tsv (the climb log improve.py writes) and animates the score
climbing point-by-point — green keeps, red discards, gold retries — themed to match the
Rust plot in ../plot. Output is a looping GIF for the README.

    pip install matplotlib pillow
    python3 tools/make_demo.py                       # uses tools/sample-climb.tsv
    python3 tools/make_demo.py results/email.tsv     # any run's TSV
    python3 tools/make_demo.py --preview             # also dump the final frame as PNG

Not a runtime dependency of auto-improve — a maintainer tool for regenerating assets/demo.gif.
"""
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# palette mirrors plot/src/main.rs
BG, ACCENT, GREEN, RED, GOLD, DIM, INK = (
    "#070810", "#66c2fc", "#76d99a", "#fa737f", "#fcbd63", "#858fb3", "#e0e8f7")
STATUS_COLOR = {"baseline": GREEN, "keep": GREEN, "discard": RED, "crash": GOLD}


def load(path):
    """Parse a climb TSV into points with a 'shown' score that holds on discard/crash."""
    with open(path, newline="") as f:
        rows = [r for r in csv.DictReader(f, delimiter="\t") if r.get("status")]
    pts, shown = [], 0.0
    for r in rows:
        score = float(str(r["score"]).lstrip("+") or 0)
        status = r["status"].strip()
        if status in ("baseline", "keep"):
            shown = score
        pts.append({"it": int(float(r["iteration"])), "y": shown, "status": status})
    # keep only the last run if the file accumulated several
    last_base = max((i for i, p in enumerate(pts) if p["status"] == "baseline"), default=0)
    return pts[last_base:]


def frames_for(pts, seg=11, head=6, tail=18):
    """A reveal schedule: (n_full, t) — n_full points shown, t in (0,1] eases to the next."""
    seq = [(1, 0.0)] * head
    for i in range(len(pts) - 1):
        seq += [(i + 1, (k + 1) / seg) for k in range(seg)]
    seq += [(len(pts), 0.0)] * tail
    return seq


def render(tsv, out, preview=False):
    pts = load(tsv)
    if len(pts) < 2:
        sys.exit(f"need >=2 rows in {tsv}")
    base, top = pts[0]["y"], max(p["y"] for p in pts)
    ys = [p["y"] for p in pts]
    ymin, ymax = max(0, min(ys) - 6), min(100, max(ys) + 6)
    xmax = max(1, len(pts) - 1)
    seq = frames_for(pts)

    fig = plt.figure(figsize=(8.4, 3.6), dpi=100)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0.06, 0.13, 0.62, 0.62])
    sax = fig.add_axes([0.70, 0.0, 0.30, 1.0]); sax.axis("off")

    def draw(state):
        n_full, t = state
        for a in (ax,):
            a.clear(); a.set_facecolor(BG)
        ax.set_xlim(-0.25, xmax + 0.25); ax.set_ylim(ymin, ymax)
        for s in ("top", "right", "left", "bottom"):
            ax.spines[s].set_visible(False)
        ax.set_xticks([]); ax.set_yticks([])
        ax.text(-0.18, ymax, f"{int(ymax)}", color=DIM, fontsize=8, va="top", ha="right")
        ax.text(-0.18, ymin, f"{int(ymin)}", color=DIM, fontsize=8, va="bottom", ha="right")
        ax.axhline(ymin, color="#222838", lw=1); ax.axvline(-0.22, color="#222838", lw=1)

        xs = [p["it"] for p in pts[:n_full]]
        sc = [p["y"] for p in pts[:n_full]]
        cur = sc[-1]
        if t > 0 and n_full < len(pts):
            nxt = pts[n_full]
            ex = (n_full - 1) + t
            cur = sc[-1] + (nxt["y"] - sc[-1]) * t
            xs2, sc2 = xs + [ex], sc + [cur]
        else:
            xs2, sc2 = xs, sc
        ax.plot(xs2, sc2, color=ACCENT, lw=2.6, solid_capstyle="round", zorder=2)
        for p in pts[:n_full]:
            c = STATUS_COLOR.get(p["status"], ACCENT)
            ax.scatter([p["it"]], [p["y"]], s=190, color=c, alpha=0.14, zorder=3)
            ax.scatter([p["it"]], [p["y"]], s=46, color=c, zorder=4)
        # leading dot
        lc = GREEN
        ax.scatter([xs2[-1]], [sc2[-1]], s=300, color=lc, alpha=0.12, zorder=3)
        ax.scatter([xs2[-1]], [sc2[-1]], s=70, color=lc, zorder=5,
                   edgecolors=BG, linewidths=1.5)

        # side panel: wordmark + big climbing score + legend
        sax.clear(); sax.axis("off"); sax.set_xlim(0, 1); sax.set_ylim(0, 1)
        sax.text(0.04, 0.93, "auto-improve", color=INK, fontsize=15,
                 fontweight="bold", va="top", family="monospace")
        sax.text(0.04, 0.80, "score vs iteration", color=DIM, fontsize=9, va="top")
        sax.text(0.04, 0.50, f"{int(round(cur))}", color=GREEN, fontsize=46,
                 fontweight="bold", va="center", family="monospace")
        sax.text(0.46, 0.50, f"from {int(base)}\n+{int(round(cur - base))} pts",
                 color=DIM, fontsize=10, va="center")
        sax.text(0.04, 0.12, "● keep   ● discard   ● retry", color=DIM, fontsize=8)
        for frag, col, x in (("keep", GREEN, 0.04), ("discard", RED, 0.255), ("retry", GOLD, 0.50)):
            sax.text(x, 0.12, "●", color=col, fontsize=8, va="baseline")

    # header on the plot
    def update(i):
        draw(seq[i])

    anim = FuncAnimation(fig, update, frames=len(seq), interval=70)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    anim.save(out, writer=PillowWriter(fps=14))
    print(f"wrote {out}  ({len(seq)} frames)")
    if preview:
        draw(seq[-1])
        png = os.path.splitext(out)[0] + "_preview.png"
        fig.savefig(png, facecolor=BG)
        print(f"wrote {png}")
    plt.close(fig)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    preview = "--preview" in sys.argv
    tsv = args[0] if args else os.path.join(HERE, "sample-climb.tsv")
    render(tsv, os.path.join(ROOT, "assets", "demo.gif"), preview=preview)
