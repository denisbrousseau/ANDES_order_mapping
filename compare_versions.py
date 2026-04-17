"""
Compare V29 vs V35 spectral order traces for H, J, and Y bands.
Overlays both versions on the same detector plot per band.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon, Rectangle
import pandas as pd


def parse_order_file(filepath):
    df = pd.read_csv(filepath, sep='\t')
    orders = {}
    for order_num, group in df.groupby('ORDER'):
        orders[order_num] = group.reset_index(drop=True)
    return orders


def add_orders_to_ax(ax, orders, color, alpha=0.5, linecolor=None, zorder_offset=0):
    if linecolor is None:
        linecolor = color
    for order_num, group in orders.items():
        x1 = group['X1'].values
        y1 = group['Y1'].values
        x2 = group['X2'].values
        y2 = group['Y2'].values
        poly_x = np.concatenate([x1, x2[::-1]])
        poly_y = np.concatenate([y1, y2[::-1]])
        patch = Polygon(np.column_stack([poly_x, poly_y]),
                        closed=True, facecolor=color, alpha=alpha,
                        edgecolor=linecolor, linewidth=0.8, zorder=2 + zorder_offset)
        ax.add_patch(patch)


def compute_order_stats(orders_a, orders_b, label_a, label_b):
    """Return per-order centroid shift between two configurations."""
    common = sorted(set(orders_a) & set(orders_b))
    rows = []
    for o in common:
        y0_a = orders_a[o]['Y0'].mean()
        y0_b = orders_b[o]['Y0'].mean()
        x0_a = orders_a[o]['X0'].mean()
        x0_b = orders_b[o]['X0'].mean()
        rows.append({'ORDER': o,
                     f'Y0_mean_{label_a}': y0_a,
                     f'Y0_mean_{label_b}': y0_b,
                     'dY (mm)': y0_b - y0_a,
                     'dX (mm)': x0_b - x0_a})
    return rows


def plot_comparison(band, file_v29, file_v35, output_path, detector_half=30.7):
    orders_v29 = parse_order_file(file_v29)
    orders_v35 = parse_order_file(file_v35)

    fig, axes = plt.subplots(1, 3, figsize=(20, 8), facecolor='white')
    fig.suptitle(f'ANDES {band}-band: V29 vs V35 Order Trace Comparison', fontsize=14, fontweight='bold')

    # --- Panel 1: V29 only ---
    ax = axes[0]
    ax.set_facecolor('white')
    add_orders_to_ax(ax, orders_v29, color='steelblue', alpha=0.7, linecolor='navy')
    _add_detector_and_labels(ax, orders_v29, detector_half, label_offset_color='navy')
    ax.set_title('V29', fontsize=12)
    _format_ax(ax, detector_half)

    # --- Panel 2: V35 only ---
    ax = axes[1]
    ax.set_facecolor('white')
    add_orders_to_ax(ax, orders_v35, color='tomato', alpha=0.7, linecolor='darkred')
    _add_detector_and_labels(ax, orders_v35, detector_half, label_offset_color='darkred')
    ax.set_title('V35', fontsize=12)
    _format_ax(ax, detector_half)

    # --- Panel 3: Overlay ---
    ax = axes[2]
    ax.set_facecolor('white')
    add_orders_to_ax(ax, orders_v29, color='steelblue', alpha=0.45, linecolor='navy', zorder_offset=0)
    add_orders_to_ax(ax, orders_v35, color='tomato', alpha=0.45, linecolor='darkred', zorder_offset=1)
    rect = Rectangle((-detector_half, -detector_half),
                     2 * detector_half, 2 * detector_half,
                     linewidth=2, edgecolor='black', facecolor='none', zorder=0)
    ax.add_patch(rect)
    patch_v29 = mpatches.Patch(facecolor='steelblue', alpha=0.7, label='V29')
    patch_v35 = mpatches.Patch(facecolor='tomato', alpha=0.7, label='V35')
    ax.legend(handles=[patch_v29, patch_v35], loc='lower right', fontsize=10)
    ax.set_title('Overlay (V29 blue, V35 red)', fontsize=12)
    _format_ax(ax, detector_half)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_path}")

    # Print centroid shift summary
    stats = compute_order_stats(orders_v29, orders_v35, 'V29', 'V35')
    dy_vals = [r['dY (mm)'] for r in stats]
    dx_vals = [r['dX (mm)'] for r in stats]
    print(f"\n  {band}-band centroid shift V35 − V29 (over {len(stats)} orders):")
    print(f"    dY: mean={np.mean(dy_vals):+.3f} mm, range=[{min(dy_vals):+.3f}, {max(dy_vals):+.3f}] mm")
    print(f"    dX: mean={np.mean(dx_vals):+.3f} mm, range=[{min(dx_vals):+.3f}, {max(dx_vals):+.3f}] mm")


def _add_detector_and_labels(ax, orders, detector_half, label_offset_color='black'):
    rect = Rectangle((-detector_half, -detector_half),
                     2 * detector_half, 2 * detector_half,
                     linewidth=2, edgecolor='black', facecolor='none', zorder=0)
    ax.add_patch(rect)
    for order_num, group in orders.items():
        y0 = group['Y0'].values
        ax.text(detector_half + 0.5, y0[len(group) // 2], str(order_num),
                ha='left', va='center', fontsize=7, color=label_offset_color, zorder=5)


def _format_ax(ax, detector_half):
    margin = 1.5
    ax.set_xlim(-detector_half - margin, detector_half + 3)
    ax.set_ylim(-detector_half - margin, detector_half + margin)
    ax.set_aspect('equal')
    ticks = np.arange(-30, 31, 10)
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.tick_params(labelsize=8)
    ax.set_xlabel('X (mm)', fontsize=10)
    ax.set_ylabel('Y (mm)', fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)


if __name__ == '__main__':
    base = os.path.dirname(os.path.abspath(__file__))

    bands = [
        ('H', 'ANDES_V29_Hband_orders.txt', 'ANDES_YS_H_R4_V35_orders.txt'),
        ('J', 'ANDES_V29_Jband_orders.txt', 'ANDES_YS_J_R4_V35_orders.txt'),
        ('Y', 'ANDES_V29_Yband_orders.txt', 'ANDES_YS_Y_R4_V35_orders.txt'),
    ]

    for band, v29_file, v35_file in bands:
        plot_comparison(
            band,
            os.path.join(base, v29_file),
            os.path.join(base, v35_file),
            os.path.join(base, f'order_map_comparison_{band}.png'),
        )
