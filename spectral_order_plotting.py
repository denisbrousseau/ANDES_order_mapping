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


PIXEL_SIZE_MM = 0.015  # 15 µm H4RG detector pixel size


def normalize_columns(df):
    """Strip unit labels like ' (mm)' from column names for uniform access.
    Also normalizes FWHM-based columns to the standard Sampling/R names."""
    df.columns = [c.replace(' (mm)', '') for c in df.columns]
    # Fix typo variant of wavelength column
    if 'Wavelenght (nm)' in df.columns:
        df = df.rename(columns={'Wavelenght (nm)': 'Wavelength (nm)'})
    # Prefer geometric sampling (accept both capitalisation variants)
    for geo_col in ('Geo. sampling (pixels)', 'Geo. Sampling (pixels)'):
        if geo_col in df.columns:
            df = df.rename(columns={geo_col: 'Sampling (pixels)'})
            break
    # Accept both FWHM column name variants
    for fwhm_col in ('Gaussian FWHM (pixels)', 'FWHM (pixels)'):
        if fwhm_col in df.columns:
            df = df.rename(columns={fwhm_col: 'FWHM (pixels)'})
            break
    # Use FWHM resolution, fall back to geo., then PSF-fit resolution
    if 'R (FWHM sampling)' in df.columns:
        df = df.rename(columns={'R (FWHM sampling)': 'R'})
    elif 'R (Geo. sampling)' in df.columns:
        df = df.rename(columns={'R (Geo. sampling)': 'R'})
    elif 'Resolution R' in df.columns:
        df = df.rename(columns={'Resolution R': 'R'})
    return df


def compute_resolution(group):
    """
    Compute spectral resolution R = λ / (sampling * dispersion) for each row.
    Dispersion (nm/pixel) is estimated via central differences of wavelength vs X0.
    Pixel size = 15 µm = 0.015 mm.
    """
    lam = group['Wavelength (nm)'].values
    x0 = group['X0'].values
    samp = group['Sampling (pixels)'].values
    n = len(lam)
    R = np.empty(n)
    for i in range(n):
        if i == 0:
            dlam = abs(lam[0] - lam[1])
            dx_mm = abs(x0[1] - x0[0])
        elif i == n - 1:
            dlam = abs(lam[-2] - lam[-1])
            dx_mm = abs(x0[-1] - x0[-2])
        else:
            dlam = abs(lam[i - 1] - lam[i + 1])
            dx_mm = abs(x0[i + 1] - x0[i - 1])
        dispersion = dlam * PIXEL_SIZE_MM / dx_mm  # nm/pixel
        R[i] = round(lam[i] / (samp[i] * dispersion))
    return R.astype(int)


HEADERLESS_COLUMNS = [
    'ORDER', 'Wavelength (nm)',
    'X0', 'Y0', 'X1', 'Y1', 'X2', 'Y2',
    'Sampling (pixels)',
    'FWHM (pixels)',
    'R (Geo. sampling)',
    'R (FWHM sampling)',
]


def _is_headerless(filepath):
    """Return True if the file contains headerless numeric data.
    Skips Zemax preamble lines (e.g. 'Executing ...') before deciding."""
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                float(line.split()[0])
                return True
            except ValueError:
                continue  # skip non-numeric preamble lines
    return False


def _detect_ncols(filepath):
    """Return the column count of the first numeric data line."""
    with open(filepath) as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()
            try:
                float(parts[0])
                return len(parts)
            except ValueError:
                continue
    return len(HEADERLESS_COLUMNS)


def parse_order_file(filepath, sheet_name=None):
    if filepath.endswith('.xlsx') or filepath.endswith('.xls'):
        df = pd.read_excel(filepath, sheet_name=sheet_name)
    elif _is_headerless(filepath):
        ncols = min(_detect_ncols(filepath), len(HEADERLESS_COLUMNS))
        col_names = HEADERLESS_COLUMNS[:ncols]
        df = pd.read_csv(filepath, sep=r'\s+', header=None,
                         names=col_names, usecols=range(ncols))
        df.columns = col_names
    else:
        df = pd.read_csv(filepath, sep='\t')
    df = normalize_columns(df)
    if df['ORDER'].dtype == float:
        df['ORDER'] = df['ORDER'].astype(int)
    orders = {}
    for order_num, group in df.groupby('ORDER'):
        group = group.reset_index(drop=True)
        if 'R' not in group.columns:
            group = group.copy()
            group['R'] = compute_resolution(group)
        orders[order_num] = group
    return orders


DETECTOR_SIZE_MM = 4096 * PIXEL_SIZE_MM  # 61.44 mm (4k × 15 µm)


DETECTOR_HALF_MM = DETECTOR_SIZE_MM / 2  # 30.72 mm


def detector_bounds(orders):
    """Return standard ±30.72 mm detector boundary (4096 px × 15 µm)."""
    h = DETECTOR_HALF_MM
    return -h, h, -h, h


def center_orders(orders):
    """Shift all coordinates so the center of the order distribution is at the origin."""
    all_x0 = np.concatenate([g['X0'].values for g in orders.values()])
    all_y0 = np.concatenate([g['Y0'].values for g in orders.values()])
    x_shift = -(all_x0.min() + all_x0.max()) / 2
    y_shift = -(all_y0.min() + all_y0.max()) / 2
    if abs(x_shift) < 0.1 and abs(y_shift) < 0.1:
        return orders  # already centered
    centered = {}
    for order_num, group in orders.items():
        g = group.copy()
        for col in ('X0', 'X1', 'X2'):
            g[col] = g[col] + x_shift
        for col in ('Y0', 'Y1', 'Y2'):
            g[col] = g[col] + y_shift
        centered[order_num] = g
    return centered


def plot_order_traces(orders, title, output_path, show_resolution=True, wavelength_only=False):
    x_min, x_max, y_min, y_max = detector_bounds(orders)
    width_mm = x_max - x_min
    height_mm = y_max - y_min
    aspect = height_mm / width_mm
    fig_w = 12
    fig, ax = plt.subplots(figsize=(fig_w, fig_w * aspect), facecolor='white')
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
        label_fs = 11 if wavelength_only else 9
        ax.text(x_max + 0.8, y0[len(group) // 2], str(order_num),
                ha='left', va='center', fontsize=label_fs, fontweight='bold',
                color='black', zorder=5)

        # 5 wavelength labels + slit lines evenly spaced along the order
        indices = np.linspace(0, len(group) - 1, 5).astype(int)
        wl_fs = 13 if wavelength_only else 9

        # Draw all slit marks first
        for idx in indices:
            ax.plot([x1[idx], x2[idx]], [y1[idx], y2[idx]],
                    color='black', linewidth=2, solid_capstyle='round', zorder=4)

        # The labeled slit with the highest X gets its annotation on the left
        rightmost_labeled = indices[np.argmax(x0[indices])]

        for k, idx in enumerate(indices):
            if wavelength_only:
                # Local trace direction at this slit for text rotation
                if k < len(indices) - 1:
                    ddx = x0[indices[k + 1]] - x0[idx]
                    ddy = y0[indices[k + 1]] - y0[idx]
                else:
                    ddx = x0[idx] - x0[indices[k - 1]]
                    ddy = y0[idx] - y0[indices[k - 1]]
                angle = np.degrees(np.arctan2(ddy, ddx))
                ax.text(x0[idx], y0[idx], f'{wavelengths[idx]:.1f}',
                        ha='center', va='center', fontsize=wl_fs, color='black',
                        rotation=angle, rotation_mode='anchor', zorder=5)
            else:
                y_mid = y0[idx]
                x_slit = (x1[idx] + x2[idx]) / 2
                if idx == rightmost_labeled:
                    x_label = x_slit - 0.3
                    ha = 'right'
                else:
                    x_label = x_slit + 0.3
                    ha = 'left'
                ax.text(x_label, y_mid + 0.5, f'{wavelengths[idx]:.1f}',
                        ha=ha, va='center', fontsize=wl_fs, color='black', zorder=5)
                ax.text(x_label, y_mid - 0.3, f'({sampling[idx]:.2f})',
                        ha=ha, va='center', fontsize=8, color='black', zorder=5)
                if show_resolution and resolution is not None:
                    ax.text(x_label, y_mid - 1.1, f'R={resolution[idx]:,}',
                            ha=ha, va='center', fontsize=8, color='dimgray',
                            fontweight='bold', zorder=5)

    # Detector boundary
    rect = Rectangle((x_min, y_min), width_mm, height_mm,
                     linewidth=2, edgecolor='black', facecolor='white', zorder=0)
    ax.add_patch(rect)

    # Axis limits, ticks, labels
    margin = 1.5
    ax.set_xlim(x_min - margin, x_max + 4)
    ax.set_ylim(y_min - margin, y_max + margin)
    ax.set_aspect('equal')

    tick_step = 5
    ax.set_xticks(np.arange(int(x_min), int(x_max) + 1, tick_step))
    ax.set_yticks(np.arange(int(y_min), int(y_max) + 1, tick_step))
    ax.tick_params(labelsize=9)
    ax.set_xlabel('X (mm)', fontsize=12)
    ax.set_ylabel('Y (mm)', fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5, zorder=1)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.show()


PLOT_DIR = os.path.dirname(os.path.abspath(__file__))


def derive_title_and_output(filepath, band=None):
    name = os.path.basename(filepath)
    # Multi-band xlsx (e.g. ANDES_V36_YJH.xlsx) with explicit --band selection
    m_multi = re.match(r'ANDES_(V\d+)_([A-Z]+)\.xlsx?', name, re.IGNORECASE)
    if m_multi and band:
        version = m_multi.group(1)
        title   = f'ANDES {band.upper()}-band {version} — Spectral Order Traces'
        output  = os.path.join(os.path.dirname(filepath),
                               f'{version}_sampling_{band.capitalize()}band.pdf')
        return title, output
    # ANDES_<Band>band_<Ver>.xlsx  →  V35_sampling_Hband.pdf  (mirrors V36_sampling_Hband.pdf)
    m_xlsx = re.match(r'ANDES_([\w]+)band_(V\d+)\.xlsx?', name, re.IGNORECASE)
    if m_xlsx:
        band    = m_xlsx.group(1).capitalize()
        version = m_xlsx.group(2)
        title   = f'ANDES {band}-band {version} — Spectral Order Traces'
        output  = os.path.join(os.path.dirname(filepath),
                               f'{version}_sampling_{band}band.pdf')
        return title, output
    m = re.match(r'ANDES_(YS)_(\w+)_R4_V35_orders\.txt', name)
    if m:
        band = m.group(2)
        title = f'ANDES YS {band}-band R4 V35 — Spectral Order Traces'
        output = os.path.join(os.path.dirname(filepath), f'order_map_{band}.png')
        return title, output
    m2 = re.match(r'ANDES_(\w+)_band_(V\d+)_XY_sampling\.txt', name)
    if m2:
        band = m2.group(1)
        version = m2.group(2)
        title = f'ANDES {band}-band {version} — Spectral Order Traces'
        output = os.path.join(PLOT_DIR, f'order_map_{band}_{version}.png')
        return title, output
    # ANDES_V36_H_XY.txt  →  ANDES H-band V36 — Spectral Order Traces
    m3 = re.match(r'ANDES_(V\d+)_([A-Z])_XY\.txt', name, re.IGNORECASE)
    if m3:
        version = m3.group(1)
        band    = m3.group(2).upper()
        title   = f'ANDES {band}-band {version} — Spectral Order Traces'
        output  = os.path.join(PLOT_DIR, f'{version}_sampling_{band}band.png')
        return title, output
    m4 = re.match(r'ANDES_([\w]+)_(V\d+)_(\w+)\.txt', name)
    if m4:
        band = m4.group(1)
        version = m4.group(2)
        tag = m4.group(3)
        title = f'ANDES {band} {version} {tag} — Spectral Order Traces'
        output = os.path.join(PLOT_DIR, f'order_map_{band}_{version}_{tag}.png')
        return title, output
    stem = re.sub(r'\.(txt|xlsx?)$', '', name)
    title = stem.replace('_', ' ')
    output = os.path.join(PLOT_DIR, stem + '.png')
    return title, output


def main():
    args = sys.argv[1:]
    show_resolution = '--no-resolution' not in args
    args = [a for a in args if a != '--no-resolution']
    wavelength_only = '--wavelength-only' in args
    args = [a for a in args if a != '--wavelength-only']
    band = None
    for i, a in enumerate(args):
        if a == '--band' and i + 1 < len(args):
            band = args[i + 1]
    args = [a for i, a in enumerate(args)
            if a != '--band' and (i == 0 or args[i - 1] != '--band')]
    y_offset = 0.0
    for i, a in enumerate(args):
        if a == '--y-offset' and i + 1 < len(args):
            y_offset = float(args[i + 1])
    args = [a for i, a in enumerate(args)
            if a != '--y-offset' and (i == 0 or args[i - 1] != '--y-offset')]
    XY_DEFAULT = os.path.expanduser(
        "~/Library/CloudStorage/OneDrive-UniversitéLaval"
        "/Projets en cours/ANDES/ANDES_V36_H_XY.txt"
    )
    filepath = args[0] if args else XY_DEFAULT
    # Map band name to sheet name for multi-band xlsx files
    sheet_name = None
    if band and (filepath.endswith('.xlsx') or filepath.endswith('.xls')):
        import openpyxl
        wb = openpyxl.load_workbook(filepath, read_only=True)
        sheets = wb.sheetnames
        wb.close()
        band_upper = band.upper()
        for s in sheets:
            if band_upper in s.upper():
                sheet_name = s
                break
        if sheet_name is None:
            print(f"Warning: no sheet matching '{band}' found in {sheets}; loading default sheet.")
    orders = parse_order_file(filepath, sheet_name=sheet_name)
    print(f"Loaded {len(orders)} spectral orders: {sorted(orders.keys())}")
    orders = center_orders(orders)
    if y_offset:
        for order_num, group in orders.items():
            for col in ('Y0', 'Y1', 'Y2'):
                group[col] = group[col] + y_offset
    title, output_path = derive_title_and_output(filepath, band=band)
    plot_order_traces(orders, title, output_path,
                     show_resolution=show_resolution, wavelength_only=wavelength_only)



if __name__ == "__main__":
    main()
