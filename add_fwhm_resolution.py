import numpy as np
import os, sys, shutil
from scipy.optimize import curve_fit

ANDES_DIR   = "/Users/denisbrousseau/Library/CloudStorage/OneDrive-UniversitéLaval/Projets en cours/ANDES"
IMG_PITCH_MM = 0.005
SENSOR_PX_MM = 0.015

data_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ANDES_DIR, "data")
xy_file  = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ANDES_DIR, "ANDES_V36_Hband.txt")

# ---------- helpers ----------------------------------------------------------

def load_slit_image(path):
    """Load slit image grid of any square size from a Zemax histogram listing."""
    rows = []
    n_cols = None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 2:
                continue
            try:
                vals = [float(p) for p in parts]
            except ValueError:
                continue
            if n_cols is None:
                n_cols = len(vals)
            if len(vals) == n_cols:
                rows.append(vals)
    return np.array(rows)

def gaussian(x, amp, mu, sigma, bg):
    return amp * np.exp(-0.5 * ((x - mu) / sigma) ** 2) + bg

def fit_lsf(lsf):
    x = np.arange(len(lsf))
    p0 = [lsf.max(), x[np.argmax(lsf)], 2.0, lsf.min()]
    popt, _ = curve_fit(gaussian, x, lsf, p0=p0, maxfev=10000)
    sigma    = abs(popt[2])
    fwhm_img = 2.0 * np.sqrt(2.0 * np.log(2.0)) * sigma
    return fwhm_img * IMG_PITCH_MM / SENSOR_PX_MM

def parse_name(stem):
    if not stem.startswith("R"):
        return None, None
    digits = stem[1:]
    if len(digits) < 2:
        return None, None
    if len(digits) >= 3:
        field2 = int(digits[-2:])
        order2 = int(digits[:-2]) if digits[:-2] else None
        if field2 in (10, 11) and order2 is not None and order2 >= 50:
            return order2, field2
    field1 = int(digits[-1])
    order1 = int(digits[:-1]) if digits[:-1] else None
    if 1 <= field1 <= 9 and order1 is not None and order1 >= 50:
        return order1, field1
    return None, None

# ---------- step 1: compute FWHM from slit image files -----------------------

fwhm_dict = {}
failed    = []
for fname in sorted(os.listdir(data_dir)):
    if not fname.endswith(".txt"):
        continue
    order, field = parse_name(fname[:-4])
    if order is None:
        continue
    img = load_slit_image(os.path.join(data_dir, fname))
    if img.shape[0] == 0:
        failed.append(fname)
        continue
    lsf = img.sum(axis=0)
    try:
        fwhm_dict[(order, field)] = fit_lsf(lsf)
    except Exception as e:
        failed.append(f"{fname}: {e}")

print(f"Slit image files processed: {len(fwhm_dict)} ok, {len(failed)} failed")

# ---------- step 2: read XY file, assign field index by row order ------------

xy_rows     = []
order_counts = {}
with open(xy_file, "r") as f:
    for line in f:
        cols = line.strip().split()
        if len(cols) < 9:
            continue
        try:
            order = int(float(cols[0]))
        except ValueError:
            continue  # skip header lines like "Executing ..."
        order_counts[order] = order_counts.get(order, 0) + 1
        field = order_counts[order]
        xy_rows.append({
            "order": order, "field": field,
            "lam": float(cols[1]),
            "X0":  float(cols[2]), "Y0": float(cols[3]),
            "X1":  float(cols[4]), "Y1": float(cols[5]),
            "X2":  float(cols[6]), "Y2": float(cols[7]),
            "geo": float(cols[8]),
            "_raw": "\t".join(cols[:9]),
        })

# ---------- step 3: dispersion dλ/dX per order via np.gradient --------------

by_order = {}
for r in xy_rows:
    by_order.setdefault(r["order"], []).append(r)

disp_map = {}
for order, rows in by_order.items():
    lams = np.array([r["lam"] for r in rows])
    x0s  = np.array([r["X0"]  for r in rows])
    dlam_dx = np.gradient(lams, x0s)
    for i, r in enumerate(rows):
        disp_map[(order, r["field"])] = abs(dlam_dx[i])

# ---------- step 4: write updated file ---------------------------------------

backup = xy_file.replace(".txt", "_backup.txt")
shutil.copy(xy_file, backup)
print(f"Backup saved: {backup}")

missing = 0
with open(xy_file, "w") as f:
    for r in xy_rows:
        key     = (r["order"], r["field"])
        fwhm_px = fwhm_dict.get(key)
        disp    = disp_map.get(key, 0)

        if fwhm_px is not None and disp > 0:
            r_geo  = round(r["lam"] / (r["geo"]  * SENSOR_PX_MM * disp))
            r_fwhm = round(r["lam"] / (fwhm_px   * SENSOR_PX_MM * disp))
        else:
            fwhm_px = float("nan")
            r_geo = r_fwhm = 0
            missing += 1

        f.write(f"{r['_raw']}\t{fwhm_px:.9f}\t{r_geo}\t{r_fwhm}\n")

print(f"Updated: {xy_file}")
print(f"Columns added: FWHM (px), R_geo, R_fwhm")
if missing:
    print(f"  WARNING: {missing} rows had no matching slit image or zero dispersion")

# ---------- summary ----------------------------------------------------------

fwhm_vals = [fwhm_dict[k] for k in fwhm_dict]
print(f"\nFWHM summary (sensor px): min={np.min(fwhm_vals):.3f}  "
      f"max={np.max(fwhm_vals):.3f}  mean={np.mean(fwhm_vals):.3f}")
