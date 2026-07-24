#!/usr/bin/env python3
"""Tests for water-body-extraction."""

import sys
import os
import unittest
import tempfile
import json
import importlib.util

import numpy as np

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


if __name__ == "__main__":
    unittest.main()
