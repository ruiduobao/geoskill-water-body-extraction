#!/usr/bin/env python3
"""
water-body-extraction: Automatic water body extraction from satellite imagery
using NDWI and MNDWI indices.

Privacy Disclosure:
  - This tool performs LOCAL processing only.
  - NO data is sent to any external server.
  - NO API calls are made.
  - All input files remain on your machine.

License: MIT-0 (Public Domain)
Data Source: Local raster processing (pre-downloaded satellite imagery)
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import numpy as np
except ImportError:
    print("ERROR: numpy is required. Install with: pip install numpy>=1.21.0")
    sys.exit(1)

try:
    import rasterio
    from rasterio.transform import Affine
except ImportError:
    print("ERROR: rasterio is required. Install with: pip install rasterio>=1.3.0")
    sys.exit(1)

try:
    from scipy import ndimage
except ImportError:
    ndimage = None  # Optional for Otsu

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable


# ─── Band configurations ────────────────────────────────────────────────────

SENSOR_BANDS = {
    "landsat8": {"green": 3, "nir": 5, "swir": 6, "name": "Landsat 8"},
    "landsat9": {"green": 3, "nir": 5, "swir": 6, "name": "Landsat 9"},
    "sentinel2": {"green": 3, "nir": 8, "swir": 11, "name": "Sentinel-2"},
}

VALID_SENSORS = list(SENSOR_BANDS.keys())
VALID_INDEXES = ["ndwi", "mndwi"]
VALID_METHODS = ["otsu", "manual"]


# ─── Utility functions ───────────────────────────────────────────────────────

def validate_sensor(sensor: str) -> str:
    sensor = sensor.lower().strip()
    if sensor not in VALID_SENSORS:
        raise ValueError(
            f"Unsupported sensor '{sensor}'. Choose from: {', '.join(VALID_SENSORS)}"
        )
    return sensor


def validate_index(index: str) -> str:
    index = index.lower().strip()
    if index not in VALID_INDEXES:
        raise ValueError(
            f"Unsupported index '{index}'. Choose from: {', '.join(VALID_INDEXES)}"
        )
    return index


def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Compute NDWI = (Green - NIR) / (Green + NIR)"""
    denominator = green + nir
    # Avoid division by zero
    with np.errstate(divide='ignore', invalid='ignore'):
        ndwi = np.where(denominator != 0, (green - nir) / denominator, 0.0)
    return ndwi.astype(np.float32)


def compute_mndwi(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """Compute MNDWI = (Green - SWIR) / (Green + SWIR)"""
    denominator = green + swir
    with np.errstate(divide='ignore', invalid='ignore'):
        mndwi = np.where(denominator != 0, (green - swir) / denominator, 0.0)
    return mndwi.astype(np.float32)


def otsu_threshold(image: np.ndarray) -> float:
    """
    Compute optimal threshold using Otsu's method.
    Falls back to 0.0 if computation fails.
    """
    # Remove NaN and Inf values
    valid = image[np.isfinite(image)]
    if valid.size == 0:
        print("WARNING: No valid pixels found. Using threshold=0.0")
        return 0.0

    try:
        # Use histogram-based Otsu
        nbins = 256
        hist, bin_edges = np.histogram(valid.flatten(), bins=nbins)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        # Otsu's method
        total = hist.sum()
        if total == 0:
            return 0.0

        sum_total = np.dot(bin_centers, hist)
        sum_bg = 0.0
        weight_bg = 0
        max_variance = 0.0
        threshold = 0.0

        for i in range(nbins):
            weight_bg += hist[i]
            if weight_bg == 0:
                continue
            weight_fg = total - weight_bg
            if weight_fg == 0:
                break

            sum_bg += bin_centers[i] * hist[i]
            mean_bg = sum_bg / weight_bg
            mean_fg = (sum_total - sum_bg) / weight_fg

            variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
            if variance > max_variance:
                max_variance = variance
                threshold = bin_centers[i]

        return threshold

    except Exception as e:
        print(f"WARNING: Otsu computation failed ({e}). Using threshold=0.0")
        return 0.0


def vectorize_mask(mask: np.ndarray, transform: Affine, crs, output_path: str) -> dict:
    """Convert binary mask to vector GeoJSON."""
    try:
        from shapely.geometry import shape, mapping
        import fiona
        from fiona.crs import from_epsg
    except ImportError as e:
        print(f"WARNING: Vector output requires shapely and fiona: {e}")
        return {}

    try:
        from rasterio import features

        shapes = features.shapes(mask.astype(np.uint8), transform=transform)
        geoms = []
        for geom, val in shapes:
            if val == 1:
                geoms.append(shape(geom))

        if not geoms:
            print("WARNING: No water bodies found for vectorization.")
            return {}

        # Write GeoJSON
        schema = {
            "geometry": "Polygon",
            "properties": {"id": "int", "area": "float"},
        }

        with fiona.open(output_path, "w", driver="GeoJSON", crs=crs, schema=schema) as dst:
            for i, geom in enumerate(geoms):
                dst.write({
                    "geometry": mapping(geom),
                    "properties": {"id": i, "area": geom.area},
                })

        return {"vector_features": len(geoms), "output": output_path}

    except Exception as e:
        print(f"WARNING: Vectorization failed: {e}")
        return {}


def get_band_data(dataset, band_num: int) -> np.ndarray:
    """Read a specific band (1-indexed)."""
    if band_num > dataset.count:
        raise ValueError(
            f"Band {band_num} not available. Dataset has {dataset.count} bands."
        )
    return dataset.read(band_num).astype(np.float32)


# ─── Core processing ─────────────────────────────────────────────────────────

def process_single_image(
    input_path: str,
    sensor: str,
    index: str,
    threshold: float = None,
    output_path: str = None,
    vector_path: str = None,
    method: str = "otsu",
) -> dict:
    """Process a single image and extract water bodies."""

    # Read input
    with rasterio.open(input_path) as src:
        bands = SENSOR_BANDS[sensor]
        green = get_band_data(src, bands["green"])

        if index == "ndwi":
            nir = get_band_data(src, bands["nir"])
            water_index = compute_ndwi(green, nir)
        else:  # mndwi
            swir = get_band_data(src, bands["swir"])
            water_index = compute_mndwi(green, swir)

        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs

    # Determine threshold
    if threshold is not None:
        thresh = threshold
    elif method == "otsu":
        thresh = otsu_threshold(water_index)
    else:
        thresh = 0.0

    print(f"  Using threshold: {thresh:.4f}")

    # Generate binary mask
    water_mask = (water_index > thresh).astype(np.uint8)

    # Statistics
    total_pixels = water_mask.size
    water_pixels = int(water_mask.sum())
    water_pct = (water_pixels / total_pixels * 100) if total_pixels > 0 else 0

    stats = {
        "input": input_path,
        "sensor": sensor,
        "index": index,
        "threshold": round(thresh, 4),
        "total_pixels": total_pixels,
        "water_pixels": water_pixels,
        "water_percentage": round(water_pct, 2),
    }

    # Write raster output
    if output_path:
        profile.update(
            dtype="uint8",
            count=1,
            compress="lzw",
        )
        with rasterio.open(output_path, "w", **profile) as dst:
            dst.write(water_mask, 1)
        stats["output_raster"] = output_path
        print(f"  Raster mask saved: {output_path}")

    # Vectorize
    if vector_path:
        vec_stats = vectorize_mask(water_mask, transform, crs, vector_path)
        stats.update(vec_stats)
        if vec_stats:
            print(f"  Vector saved: {vector_path}")

    return stats


def cmd_extract(args):
    """Handle extract subcommand."""
    sensor = validate_sensor(args.sensor)
    index = validate_index(args.index)

    if not os.path.isfile(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    threshold = getattr(args, "threshold", None)
    method = getattr(args, "method", "otsu")

    print(f"Processing: {args.input}")
    print(f"  Sensor: {SENSOR_BANDS[sensor]['name']}")
    print(f"  Index: {index.upper()}")

    stats = process_single_image(
        input_path=args.input,
        sensor=sensor,
        index=index,
        threshold=threshold,
        output_path=args.output,
        vector_path=args.vector,
        method=method,
    )

    print(f"\nResults:")
    print(f"  Water pixels: {stats['water_pixels']:,} ({stats['water_percentage']:.2f}%)")

    if args.json:
        print(json.dumps(stats, indent=2))


def cmd_batch(args):
    """Handle batch subcommand."""
    sensor = validate_sensor(args.sensor)
    index = validate_index(args.index)

    if not os.path.isdir(args.input_dir):
        print(f"ERROR: Input directory not found: {args.input_dir}")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)
    if args.vector_dir:
        os.makedirs(args.vector_dir, exist_ok=True)

    # Find all GeoTIFF files
    tif_files = sorted(
        list(Path(args.input_dir).glob("*.tif"))
        + list(Path(args.input_dir).glob("*.tiff"))
    )

    if not tif_files:
        print(f"ERROR: No GeoTIFF files found in {args.input_dir}")
        sys.exit(1)

    print(f"Found {len(tif_files)} images to process")

    all_stats = []
    for tif_file in tqdm(tif_files, desc="Processing"):
        stem = tif_file.stem
        output_path = os.path.join(args.output_dir, f"{stem}_water_mask.tif")
        vector_path = None
        if args.vector_dir:
            vector_path = os.path.join(args.vector_dir, f"{stem}_water.geojson")

        try:
            stats = process_single_image(
                input_path=str(tif_file),
                sensor=sensor,
                index=index,
                threshold=getattr(args, "threshold", None),
                output_path=output_path,
                vector_path=vector_path,
                method=getattr(args, "method", "otsu"),
            )
            all_stats.append(stats)
        except Exception as e:
            print(f"  ERROR processing {tif_file.name}: {e}")
            all_stats.append({"input": str(tif_file), "error": str(e)})

    # Summary
    successful = [s for s in all_stats if "error" not in s]
    print(f"\nBatch complete: {len(successful)}/{len(tif_files)} successful")

    if args.json:
        print(json.dumps(all_stats, indent=2))


def cmd_threshold(args):
    """Handle threshold subcommand — only compute and display threshold."""
    sensor = validate_sensor(args.sensor)
    index = validate_index(args.index)
    method = args.method.lower().strip()

    if not os.path.isfile(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        sys.exit(1)

    with rasterio.open(args.input) as src:
        bands = SENSOR_BANDS[sensor]
        green = get_band_data(src, bands["green"])

        if index == "ndwi":
            nir = get_band_data(src, bands["nir"])
            water_index = compute_ndwi(green, nir)
        else:
            swir = get_band_data(src, bands["swir"])
            water_index = compute_mndwi(green, swir)

    if method == "otsu":
        thresh = otsu_threshold(water_index)
    elif method == "manual":
        thresh = args.threshold if args.threshold is not None else 0.0
    else:
        print(f"ERROR: Unknown method '{method}'. Choose from: {', '.join(VALID_METHODS)}")
        sys.exit(1)

    # Statistics at this threshold
    water_pixels = int((water_index > thresh).sum())
    total_pixels = water_index.size
    water_pct = water_pixels / total_pixels * 100 if total_pixels > 0 else 0

    stats = {
        "input": args.input,
        "sensor": sensor,
        "index": index,
        "method": method,
        "threshold": round(thresh, 4),
        "water_pixels": water_pixels,
        "water_percentage": round(water_pct, 2),
    }

    print(f"\nThreshold Analysis:")
    print(f"  Method: {method}")
    print(f"  Threshold: {thresh:.4f}")
    print(f"  Water pixels: {water_pixels:,} ({water_pct:.2f}%)")

    if args.json:
        print(json.dumps(stats, indent=2))


# ─── CLI Setup ───────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="water-body-extraction",
        description="Automatic water body extraction from satellite imagery using NDWI/MNDWI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Privacy: This tool processes all data locally. No data is sent to external servers.

Examples:
  %(prog)s extract -i image.tif --sensor landsat8 --index mndwi -o mask.tif
  %(prog)s threshold -i image.tif --sensor sentinel2 --index ndwi --method otsu
  %(prog)s batch -d ./images/ --sensor landsat8 --index mndwi -o ./masks/
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── extract ──
    p_extract = subparsers.add_parser("extract", help="Extract water bodies from a single image")
    p_extract.add_argument("-i", "--input", required=True, help="Input multi-band GeoTIFF path")
    p_extract.add_argument("--sensor", required=True, choices=VALID_SENSORS,
                           help="Sensor type")
    p_extract.add_argument("--index", required=True, choices=VALID_INDEXES,
                           help="Water index to compute (ndwi or mndwi)")
    p_extract.add_argument("-o", "--output", help="Output raster mask path")
    p_extract.add_argument("--vector", help="Output vector GeoJSON path")
    p_extract.add_argument("--threshold", type=float, default=None,
                           help="Manual threshold (default: Otsu auto)")
    p_extract.add_argument("--method", default="otsu", choices=VALID_METHODS,
                           help="Threshold method (default: otsu)")
    p_extract.add_argument("--json", action="store_true", help="Output statistics as JSON")
    p_extract.set_defaults(func=cmd_extract)

    # ── batch ──
    p_batch = subparsers.add_parser("batch", help="Batch process multiple images")
    p_batch.add_argument("-d", "--input-dir", required=True, help="Input directory with GeoTIFFs")
    p_batch.add_argument("--sensor", required=True, choices=VALID_SENSORS, help="Sensor type")
    p_batch.add_argument("--index", required=True, choices=VALID_INDEXES, help="Water index")
    p_batch.add_argument("-o", "--output-dir", required=True, help="Output directory for masks")
    p_batch.add_argument("--vector-dir", help="Output directory for vectors")
    p_batch.add_argument("--threshold", type=float, default=None, help="Manual threshold")
    p_batch.add_argument("--method", default="otsu", choices=VALID_METHODS,
                         help="Threshold method")
    p_batch.add_argument("--json", action="store_true", help="Output statistics as JSON")
    p_batch.set_defaults(func=cmd_batch)

    # ── threshold ──
    p_thresh = subparsers.add_parser("threshold", help="Analyze threshold for water extraction")
    p_thresh.add_argument("-i", "--input", required=True, help="Input GeoTIFF path")
    p_thresh.add_argument("--sensor", required=True, choices=VALID_SENSORS, help="Sensor type")
    p_thresh.add_argument("--index", required=True, choices=VALID_INDEXES, help="Water index")
    p_thresh.add_argument("--method", default="otsu", choices=VALID_METHODS,
                          help="Threshold method")
    p_thresh.add_argument("--threshold", type=float, default=None,
                          help="Manual threshold value (for --method manual)")
    p_thresh.add_argument("--json", action="store_true", help="Output as JSON")
    p_thresh.set_defaults(func=cmd_threshold)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except ValueError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except rasterio.errors.RasterioError as e:
        print(f"ERROR: Raster I/O error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
