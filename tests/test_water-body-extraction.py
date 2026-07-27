#!/usr/bin/env python3
"""Tests for water-body-extraction."""

import sys
import os
import unittest
import tempfile
import json
import importlib.util

import numpy as np
import rasterio

# Load the script module (filename has hyphen, so use importlib)
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "water-body-extraction.py")
spec = importlib.util.spec_from_file_location("water_body_extraction", SCRIPT_PATH)
wbe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wbe)

compute_ndwi = wbe.compute_ndwi
compute_mndwi = wbe.compute_mndwi
otsu_threshold = wbe.otsu_threshold
validate_sensor = wbe.validate_sensor
validate_index = wbe.validate_index
VALID_SENSORS = wbe.VALID_SENSORS
VALID_INDEXES = wbe.VALID_INDEXES


class TestValidation(unittest.TestCase):
    """Test input validation."""

    def test_validate_sensor_valid(self):
        for s in ["landsat8", "landsat9", "sentinel2", "LANDSAT8", "Sentinel2"]:
            self.assertIn(validate_sensor(s), VALID_SENSORS)

    def test_validate_sensor_invalid(self):
        with self.assertRaises(ValueError):
            validate_sensor("modis")

    def test_validate_index_valid(self):
        for idx in ["ndwi", "mndwi", "NDWI", "MNDWI"]:
            self.assertIn(validate_index(idx), VALID_INDEXES)

    def test_validate_index_invalid(self):
        with self.assertRaises(ValueError):
            validate_index("ndvi")


class TestIndices(unittest.TestCase):
    """Test index computation."""

    def test_ndwi_basic(self):
        green = np.array([0.5, 0.3, 0.1], dtype=np.float32)
        nir = np.array([0.1, 0.3, 0.5], dtype=np.float32)
        result = compute_ndwi(green, nir)
        # NDWI = (0.5-0.1)/(0.5+0.1) = 0.667
        self.assertAlmostEqual(result[0], 0.6667, places=3)
        # NDWI = (0.1-0.5)/(0.1+0.5) = -0.667
        self.assertAlmostEqual(result[2], -0.6667, places=3)

    def test_mndwi_basic(self):
        green = np.array([0.5, 0.3, 0.1], dtype=np.float32)
        swir = np.array([0.1, 0.3, 0.5], dtype=np.float32)
        result = compute_mndwi(green, swir)
        self.assertAlmostEqual(result[0], 0.6667, places=3)
        self.assertAlmostEqual(result[2], -0.6667, places=3)

    def test_ndwi_division_by_zero(self):
        green = np.array([0.0, 0.5], dtype=np.float32)
        nir = np.array([0.0, 0.5], dtype=np.float32)
        result = compute_ndwi(green, nir)
        self.assertEqual(result[0], 0.0)  # Should not crash
        self.assertAlmostEqual(result[1], 0.0, places=5)

    def test_ndwi_2d_array(self):
        green = np.random.rand(100, 100).astype(np.float32)
        nir = np.random.rand(100, 100).astype(np.float32)
        result = compute_ndwi(green, nir)
        self.assertEqual(result.shape, (100, 100))


class TestOtsu(unittest.TestCase):
    """Test Otsu threshold computation."""

    def test_otsu_bimodal(self):
        """Otsu should find threshold between two peaks."""
        np.random.seed(42)
        # Create bimodal distribution: water (high values) and land (low values)
        water = np.random.normal(0.6, 0.1, 5000)
        land = np.random.normal(-0.2, 0.1, 5000)
        data = np.concatenate([water, land]).astype(np.float32)
        np.clip(data, -1, 1, out=data)

        thresh = otsu_threshold(data)
        # Threshold should be between the two peaks
        self.assertGreater(thresh, 0.0)
        self.assertLess(thresh, 0.5)

    def test_otsu_empty(self):
        """Otsu should handle empty/invalid data."""
        data = np.array([np.nan, np.inf], dtype=np.float32)
        thresh = otsu_threshold(data)
        self.assertEqual(thresh, 0.0)

    def test_otsu_uniform(self):
        """Otsu on uniform data."""
        data = np.full(1000, 0.5, dtype=np.float32)
        thresh = otsu_threshold(data)
        # Should return some value without crashing
        self.assertIsInstance(thresh, float)


class TestCLI(unittest.TestCase):
    """Test CLI argument parsing."""

    def test_help_runs(self):
        """Verify --help doesn't crash."""
        parser = wbe.build_parser()
        self.assertIsNotNone(parser)


class TestFormatFlag(unittest.TestCase):
    """Tests for the --format (geojson / shapefile) flag on the vector output."""

    def setUp(self):
        import tempfile
        self.tmpdir = tempfile.mkdtemp(prefix="wbe_fmt_")
        # Make a tiny synthetic mask with a single water polygon
        self.mask = np.zeros((20, 20), dtype=np.uint8)
        self.mask[5:15, 5:15] = 1
        self.transform = rasterio.Affine(0.001, 0.0, 116.0, 0.0, -0.001, 40.0)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_vector_driver_geojson(self):
        self.assertEqual(wbe._vector_driver("geojson"), "GeoJSON")
        self.assertEqual(wbe._vector_driver("GeoJSON"), "GeoJSON")

    def test_vector_driver_shapefile(self):
        self.assertEqual(wbe._vector_driver("shapefile"), "ESRI Shapefile")

    def test_vector_driver_invalid_raises(self):
        with self.assertRaises(ValueError):
            wbe._vector_driver("kml")

    def test_vectorize_mask_geojson(self):
        import fiona
        out = os.path.join(self.tmpdir, "water.json")
        stats = wbe.vectorize_mask(self.mask, self.transform, "EPSG:4326", out,
                                    fmt="geojson")
        # Path should have .geojson extension
        self.assertTrue(os.path.exists(stats["output"]))
        self.assertTrue(stats["output"].endswith(".geojson"))
        # GeoJSON is a single file
        self.assertEqual(stats["vector_features"], 1)
        self.assertEqual(stats["vector_format"], "geojson")
        with fiona.open(stats["output"]) as src:
            self.assertEqual(src.driver, "GeoJSON")
            self.assertEqual(len(src), 1)

    def test_vectorize_mask_shapefile(self):
        import fiona
        out = os.path.join(self.tmpdir, "water")
        stats = wbe.vectorize_mask(self.mask, self.transform, "EPSG:4326", out,
                                    fmt="shapefile")
        # Path should have .shp extension
        self.assertTrue(os.path.exists(stats["output"]))
        self.assertTrue(stats["output"].endswith(".shp"))
        # Shapefile produces several sidecar files
        sidecars = [".shp", ".shx", ".dbf"]
        for ext in sidecars:
            self.assertTrue(
                os.path.exists(stats["output"][:-4] + ext),
                f"missing sidecar: {ext}",
            )
        self.assertEqual(stats["vector_features"], 1)
        self.assertEqual(stats["vector_format"], "shapefile")
        with fiona.open(stats["output"]) as src:
            self.assertEqual(src.driver, "ESRI Shapefile")
            self.assertEqual(len(src), 1)

    def test_vectorize_mask_preserves_explicit_geojson_ext(self):
        out = os.path.join(self.tmpdir, "explicit.geojson")
        stats = wbe.vectorize_mask(self.mask, self.transform, "EPSG:4326", out,
                                    fmt="geojson")
        self.assertEqual(stats["output"], out)

    def test_extract_help_lists_format(self):
        import subprocess
        out = subprocess.run(
            [sys.executable, SCRIPT_PATH, "extract", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        text = out.stdout + out.stderr
        self.assertIn("--format", text)
        self.assertIn("geojson", text)
        self.assertIn("shapefile", text)

    def test_batch_help_lists_format(self):
        import subprocess
        out = subprocess.run(
            [sys.executable, SCRIPT_PATH, "batch", "--help"],
            capture_output=True, text=True, timeout=10,
        )
        text = out.stdout + out.stderr
        self.assertIn("--format", text)

    def test_format_default_is_geojson(self):
        parser = wbe.build_parser()
        args = parser.parse_args([
            "extract", "-i", "x.tif", "--vector", "v.json",
        ])
        self.assertEqual(args.format, "geojson")

    def test_format_shapefile_choice(self):
        parser = wbe.build_parser()
        args = parser.parse_args([
            "extract", "-i", "x.tif", "--vector", "v",
            "--format", "shapefile",
        ])
        self.assertEqual(args.format, "shapefile")


if __name__ == "__main__":
    unittest.main()
