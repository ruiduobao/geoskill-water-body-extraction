# DEV.md — water-body-extraction

## Goal
Standalone Python CLI tool for automatic water body extraction from multi-band satellite imagery using NDWI and MNDWI indices.

## Data Source
Local raster processing — uses pre-downloaded satellite imagery (Landsat 8/9, Sentinel-2).

## Core Functions
1. **extract** — Single image water body extraction with NDWI/MNDWI
2. **batch** — Batch process multiple images
3. **threshold** — Optimize threshold using Otsu method or manual value

## Technical Design

### Indices
- NDWI = (Green - NIR) / (Green + NIR)
  - Landsat 8/9: (B3 - B5) / (B3 + B5)
  - Sentinel-2: (B3 - B8) / (B3 - B8)
- MNDWI = (Green - SWIR) / (Green + SWIR)
  - Landsat 8/9: (B3 - B6) / (B3 + B6)
  - Sentinel-2: (B3 - B11) / (B3 + B11)

### Processing Pipeline
1. Read multi-band GeoTIFF
2. Select bands based on sensor type
3. Compute index (NDWI or MNDWI)
4. Apply threshold (Otsu or manual)
5. Generate binary water mask
6. Optionally vectorize to GeoJSON

### Output
- Binary water mask GeoTIFF (1=water, 0=non-water)
- Vector boundaries GeoJSON (optional)
- Statistics (water pixel count, percentage)

### Dependencies
- rasterio (GeoTIFF I/O)
- numpy (array operations)
- scipy (Otsu threshold via skimage or custom)
- shapely + fiona (vector output)

### Error Handling
- Missing bands → clear error message
- Invalid sensor type → list supported sensors
- File not found → helpful path suggestion
- Singular matrix in Otsu → fallback to 0.0 threshold

## Verification Plan
1. `python scripts/water-body-extraction.py --help` works
2. `python scripts/water-body-extraction.py extract --help` works
3. Test with sample data if available
