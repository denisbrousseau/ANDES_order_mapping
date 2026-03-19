# ANDES Order Mapping

Visualization tool for spectral order traces of the ANDES spectrograph (H-band, R4 grating, V35 configuration).

## Description

`spectral_order_plotting.py` parses an order mapping file that defines the position and geometry of echelle spectral orders on a detector focal plane. Each order is represented as a filled polygon bounded by its upper and lower slit edges, and the plot shows how the orders are distributed across the detector surface.

The script produces a plot with:
- **Filled order traces** showing the physical footprint of each spectral order on the detector
- **Order numbers** labeled to the right of the detector boundary
- **Wavelength labels** (5 evenly spaced along each order) in nm
- **Detector boundary** drawn as a 30.7 mm × 30.7 mm square
- **X/Y tick marks** in mm

## Input File Format

The order mapping file is a tab-separated text file with the following columns:

| Column | Description |
|--------|-------------|
| `ORDER` | Echelle order number |
| `Wavelength (nm)` | Wavelength at this position |
| `X0`, `Y0` | Center trace coordinates (mm) |
| `X1`, `Y1` | Lower edge coordinates (mm) |
| `X2`, `Y2` | Upper edge coordinates (mm) |

Each order contains multiple rows sampling the trace along the dispersion direction. The filled polygon for each order is constructed from the lower edge (`X1`, `Y1`) and upper edge (`X2`, `Y2`) coordinate sequences.

## Usage

```bash
python spectral_order_plotting.py
```

The plot is displayed interactively and saved as `order_map.png` in the working directory.

## Dependencies

```bash
pip install numpy matplotlib pandas
```

## Output

The plot covers orders 68–83 of the H-band, spanning approximately 1452–1797 nm across a 61.4 mm × 61.4 mm detector area (coordinates ranging from ±30.7 mm).
