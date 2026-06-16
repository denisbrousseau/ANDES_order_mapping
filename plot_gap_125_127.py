"""
Zoomed plot of ANDES Y-band orders 125–127 to visualise the inter-order gaps.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon, Rectangle
import matplotlib.patheffects as pe

from spectral_order_plotting import parse_order_file, center_orders, PIXEL_SIZE_MM

XLSX = (
    "/Users/denisbrousseau/Library/CloudStorage/"
    "OneDrive-UniversitéLaval/Projets en cours/ANDES/ANDES_V36_YJH.xlsx"
)
TARGET_ORDERS = [125, 126, 127]
OUTPUT = os.path.join(os.path.dirname(__file__), "gap_orders_125_127_Yband.pdf")

# ── colour palette ────────────────────────────────────────────────────────────
ORDER_FACE   = "lightgray"
ORDER_EDGE   = "gray"
GAP_COLOUR   = "#e04040"

# ── load & filter ─────────────────────────────────────────────────────────────
def load_yband_orders(xlsx_path, sheet="Y-band"):
    import pandas as pd
    df = pd.read_excel(xlsx_path, sheet_name=sheet)
    # normalise column names
    df.columns = [c.replace(" (mm)", "").replace(" (nm)", " (nm)") for c in df.columns]
    df = df.rename(columns={
        "Wavelenght (nm)": "Wavelength (nm)",
        "Wavelength (nm) (nm)": "Wavelength (nm)",   # guard double-strip
        "Geo. Sampling (pixels)": "Sampling (pixels)",
        "Geo. sampling (pixels)": "Sampling (pixels)",
        "R (FWHM sampling)": "R",
    })
    # fix any remaining " (nm)" not caught above
    df.columns = [c.replace(" (nm)", "") if c not in ("Wavelength (nm)",) else c
                  for c in df.columns]
    orders = {}
    for num, grp in df.groupby("ORDER"):
        orders[num] = grp.reset_index(drop=True)
    return orders


all_orders = load_yband_orders(XLSX)
orders = {k: v for k, v in all_orders.items() if k in TARGET_ORDERS}
print(f"Loaded orders: {sorted(orders)}")

# ── geometry helpers ──────────────────────────────────────────────────────────
def order_x_extent(g):
    return g["X1"].values.min(), g["X2"].values.max()


# Compute per-row gap: bottom edge of upper order (Y2_a) minus top edge of lower order (Y1_b).
# Positive = real gap; negative = overlap.
# Orders a and b have slightly different X0 grids; pair by row index (close enough for 11 pts).
gaps = {}
for a, b in zip(TARGET_ORDERS[:-1], TARGET_ORDERS[1:]):
    ga, gb = orders[a], orders[b]
    n = min(len(ga), len(gb))
    gap_mm_arr = ga["Y2"].values[:n] - gb["Y1"].values[:n]   # Y2_upper - Y1_lower
    gap_px_arr = gap_mm_arr / PIXEL_SIZE_MM
    # representative annotation point: row nearest X0 = 0
    ref_i = np.argmin(np.abs(ga["X0"].values[:n]))
    gaps[(a, b)] = {
        "y_bot_a": ga["Y2"].values[ref_i],
        "y_top_b": gb["Y1"].values[ref_i],
        "x_ref":   ga["X0"].values[ref_i],
        "gap_mm_ref": gap_mm_arr[ref_i],
        "gap_px_min": gap_px_arr.min(),
        "gap_px_max": gap_px_arr.max(),
        "gap_px_mean": gap_px_arr.mean(),
    }
    print(f"Gap {a}→{b}: {gap_mm_arr[ref_i]*1000:.0f} µm at X≈0  "
          f"| range [{gap_px_arr.min():.1f}, {gap_px_arr.max():.1f}] px")

# ── plot ──────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 7), facecolor="white")
ax.set_facecolor("white")

x_all_min, x_all_max = np.inf, -np.inf
y_all_min, y_all_max = np.inf, -np.inf

for order_num in TARGET_ORDERS:
    g = orders[order_num]
    x0 = g["X0"].values
    y0 = g["Y0"].values
    x1 = g["X1"].values; y1 = g["Y1"].values
    x2 = g["X2"].values; y2 = g["Y2"].values
    wavelengths = g["Wavelength (nm)"].values
    sampling    = g["Sampling (pixels)"].values if "Sampling (pixels)" in g.columns else None
    # filled polygon — light gray like the main order plots
    poly_x = np.concatenate([x1, x2[::-1]])
    poly_y = np.concatenate([y1, y2[::-1]])
    patch = Polygon(
        np.column_stack([poly_x, poly_y]),
        closed=True, facecolor=ORDER_FACE, alpha=0.8,
        edgecolor=ORDER_EDGE, linewidth=0.8, zorder=2,
    )
    ax.add_patch(patch)

    # order label on the right (bold black, consistent with main plots)
    ax.text(x0[-1] + 0.4, y0[len(g) // 2], str(order_num),
            ha="left", va="center", fontsize=11, fontweight="bold",
            color="black", zorder=5)

    # wavelength ticks at 5 evenly-spaced positions
    for idx in np.linspace(0, len(g) - 1, 5).astype(int):
        ax.plot([x1[idx], x2[idx]], [y1[idx], y2[idx]],
                color="black", linewidth=2, solid_capstyle="round", zorder=4)
        xmid = (x1[idx] + x2[idx]) / 2
        ymid = y0[idx]
        ax.text(xmid, ymid + 0.25, f"{wavelengths[idx]:.1f} nm",
                ha="center", va="bottom", fontsize=7.5, color="black", zorder=5)
        if sampling is not None:
            ax.text(xmid, ymid - 0.35, f"{sampling[idx]:.2f} px",
                    ha="center", va="top", fontsize=7, color="dimgray", zorder=5)

    x_all_min = min(x_all_min, x1.min(), x2.min())
    x_all_max = max(x_all_max, x1.max(), x2.max())
    y_all_min = min(y_all_min, y2.min())
    y_all_max = max(y_all_max, y1.max())

# ── gap annotations ───────────────────────────────────────────────────────────
# Shade the gap region between adjacent orders and annotate on the right side.
for (a, b), info in gaps.items():
    ga, gb  = orders[a], orders[b]
    n       = min(len(ga), len(gb))
    # Gap polygon: bottom edge of upper order (x2_a, y2_a) forward,
    #              then top edge of lower order (x1_b, y1_b) reversed.
    gp_x = np.concatenate([ga["X2"].values[:n], gb["X1"].values[:n][::-1]])
    gp_y = np.concatenate([ga["Y2"].values[:n], gb["Y1"].values[:n][::-1]])
    gap_patch = Polygon(
        np.column_stack([gp_x, gp_y]),
        closed=True, facecolor=GAP_COLOUR, alpha=0.30,
        edgecolor=GAP_COLOUR, linewidth=1.0, linestyle="--", zorder=3,
    )
    ax.add_patch(gap_patch)

    # Side annotation at x_all_max + 1
    gap_px_mn = info["gap_px_min"]
    gap_px_mx = info["gap_px_max"]
    gap_mm    = info["gap_mm_ref"]
    y_bot_a   = info["y_bot_a"]
    y_top_b   = info["y_top_b"]
    x_anno    = x_all_max + 1.2
    # Horizontal guide lines from the gap edges to the annotation
    for yy in (y_bot_a, y_top_b):
        ax.plot([ga["X2"].values[np.argmin(np.abs(ga["X0"].values))], x_anno],
                [yy, yy], color=GAP_COLOUR, lw=0.8, linestyle=":", zorder=5)
    ax.annotate(
        "", xy=(x_anno, y_top_b), xytext=(x_anno, y_bot_a),
        arrowprops=dict(arrowstyle="<->", color=GAP_COLOUR, lw=1.8),
        zorder=6,
    )
    y_mid_gap = (y_bot_a + y_top_b) / 2
    label = (f"{a}↔{b} gap\n"
             f"{gap_mm*1000:.0f} µm\n"
             f"[{gap_px_mn:.1f}–{gap_px_mx:.1f} px]")
    ax.text(x_anno + 0.3, y_mid_gap, label,
            ha="left", va="center", fontsize=9, color=GAP_COLOUR,
            fontweight="bold", zorder=6,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=GAP_COLOUR,
                      alpha=0.90, lw=1))

# ── axes & decoration ─────────────────────────────────────────────────────────
x_pad = 1.5
y_pad = 0.6
ax.set_xlim(x_all_min - x_pad, x_all_max + 7)
ax.set_ylim(y_all_min - y_pad, y_all_max + y_pad)
ax.set_aspect("equal")

ax.set_xlabel("X (mm)", fontsize=12)
ax.set_ylabel("Y (mm)", fontsize=12)
ax.set_title("ANDES Y-band V36 — Orders 125–127 (inter-order gap)", fontsize=13)
ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

handles = [
    mpatches.Patch(facecolor=ORDER_FACE, edgecolor=ORDER_EDGE, label="Spectral order"),
    mpatches.Patch(facecolor=GAP_COLOUR, alpha=0.40, edgecolor=GAP_COLOUR,
                   linestyle="--", label="Inter-order gap"),
]
ax.legend(handles=handles, loc="upper left", fontsize=10)

plt.tight_layout()
plt.savefig(OUTPUT, dpi=150, bbox_inches="tight")
print(f"Saved → {OUTPUT}")
plt.show()
