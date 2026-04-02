"""
ANDES Order Mapping
Parses and visualizes spectral order traces on a detector.
"""

import sys
import os
import re
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle
import pandas as pd


def parse_order_file(filepath):
    df = pd.read_csv(filepath, sep='\t')
    orders = {}
    for order_num, group in df.groupby('ORDER'):
        orders[order_num] = group.reset_index(drop=True)
    return orders


def plot_order_traces(orders, title, output_path, detector_half=30.7):
    fig, ax = plt.subplots(figsize=(12, 12), facecolor='white')
    ax.set_facecolor('white')

    order_list = sorted(orders.keys())

    for order_num in order_list:
        group = orders[order_num]

        x0 = group['X0'].values
        y0 = group['Y0'].values
        x1 = group['X1'].values
        y1 = group['Y1'].values
        x2 = group['X2'].values
        y2 = group['Y2'].values
        wavelengths = group['Wavelength (nm)'].values
        sampling = group['Sampling (pixels)'].values
        resolution = group['R'].values if 'R' in group.columns else None

        # Build filled polygon: bottom edge (X1,Y1) forward, top edge (X2,Y2) reversed
        poly_x = np.concatenate([x1, x2[::-1]])
        poly_y = np.concatenate([y1, y2[::-1]])
        patch = Polygon(np.column_stack([poly_x, poly_y]),
                        closed=True, facecolor='lightgray', alpha=0.8,
                        edgecolor='gray', linewidth=0.8, zorder=2)
        ax.add_patch(patch)

        # Order number label at the far right of the plot
        ax.text(detector_half + 0.8, y0[len(group) // 2], str(order_num),
                ha='left', va='center', fontsize=9, fontweight='bold',
                color='black', zorder=5)

        # 5 wavelength labels + slit lines evenly spaced along the order
        indices = np.linspace(0, len(group) - 1, 5).astype(int)
        for idx in indices:
            # Bold slit line from lower to upper edge
            ax.plot([x1[idx], x2[idx]], [y1[idx], y2[idx]],
                    color='black', linewidth=2, solid_capstyle='round', zorder=4)
            # Wavelength and slit width labels: left side for rightmost position, right for others
            y_mid = y0[idx]
            if idx == indices[-1]:
                x_label = (x1[idx] + x2[idx]) / 2 - 0.3
                ha = 'right'
            else:
                x_label = (x1[idx] + x2[idx]) / 2 + 0.3
                ha = 'left'
            ax.text(x_label, y_mid + 0.5, f'{wavelengths[idx]:.1f}',
                    ha=ha, va='center', fontsize=9, color='black', zorder=5)
            ax.text(x_label, y_mid - 0.3, f'({sampling[idx]:.2f})',
                    ha=ha, va='center', fontsize=8, color='black', zorder=5)
            if resolution is not None:
                ax.text(x_label, y_mid - 1.1, f'R={resolution[idx]:,}',
                        ha=ha, va='center', fontsize=8, color='dimgray',
                        fontweight='bold', zorder=5)

    # Detector boundary
    rect = Rectangle((-detector_half, -detector_half),
                     2 * detector_half, 2 * detector_half,
                     linewidth=2, edgecolor='black', facecolor='white', zorder=0)
    ax.add_patch(rect)

    # Axis limits, ticks, labels
    margin = 1.5
    ax.set_xlim(-detector_half - margin, detector_half + 4)
    ax.set_ylim(-detector_half - margin, detector_half + margin)
    ax.set_aspect('equal')

    ticks = np.arange(-30, 31, 5)
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.tick_params(labelsize=9)
    ax.set_xlabel('X (mm)', fontsize=12)
    ax.set_ylabel('Y (mm)', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5, zorder=1)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.show()


def derive_title_and_output(filepath):
    name = os.path.basename(filepath)
    m = re.match(r'ANDES_(YS)_(\w+)_R4_V35_orders\.txt', name)
    if m:
        band = m.group(2)
        title = f'ANDES YS {band}-band R4 V35 — Spectral Order Traces'
        output = os.path.join(os.path.dirname(filepath), f'order_map_{band}.png')
    else:
        title = name.replace('_orders.txt', '').replace('_', ' ')
        output = os.path.join(os.path.dirname(filepath), name.replace('.txt', '.png'))
    return title, output


def main():
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'ANDES_YS_H_R4_V35_orders.txt'
    orders = parse_order_file(filepath)
    print(f"Loaded {len(orders)} spectral orders: {sorted(orders.keys())}")
    title, output_path = derive_title_and_output(filepath)
    plot_order_traces(orders, title, output_path)


if __name__ == "__main__":
    main()
