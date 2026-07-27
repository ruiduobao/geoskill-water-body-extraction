"""Tests for water-body-extraction auto place-buffer behavior (Phase 1+)."""
import importlib.util
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, ".."))
SCRIPTS = os.path.join(PROJECT_ROOT, "scripts")

# Load the hyphenated module
_spec = importlib.util.spec_from_file_location(
    "water_body_extraction", os.path.join(SCRIPTS, "water-body-extraction.py")
)
wbe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wbe)


def test_resolve_place_auto_buffer_city():
    """市级 place 应当用 0.6° buffer（覆盖城市 + 周边）。

    Phase 1+ (2026-07-26): mock wbe._geoskill_aoi（顶部 import 的 _geoskill_core.aoi）。
    """
    mock_aoi = MagicMock(
        resolve_place=MagicMock(return_value=MagicMock(
            bbox_wgs84=[103.4, 30.1, 104.7, 31.3],
            centroid_wgs84=[104.0, 30.7],
            resolver="mock", confidence=0.9, query="成都市", ambiguity=[], notes="",
        ))
    )
    with patch.object(wbe, "_geoskill_aoi", mock_aoi):
        wbe._resolve_place("成都市")
        mock_aoi.resolve_place.assert_called_once()
        call_args = mock_aoi.resolve_place.call_args
        if call_args is not None and "buffer_deg" in (call_args[1] or {}):
            assert call_args[1]["buffer_deg"] == 0.6


def test_resolve_place_auto_buffer_district():
    """区级 place 应当用 0.15° buffer。"""
    mock_aoi = MagicMock(
        resolve_place=MagicMock(return_value=MagicMock(
            bbox_wgs84=[116.4, 39.9, 116.6, 40.0],
            centroid_wgs84=[116.5, 39.95],
            resolver="mock", confidence=0.9, query="朝阳区", ambiguity=[], notes="",
        ))
    )
    with patch.object(wbe, "_geoskill_aoi", mock_aoi):
        wbe._resolve_place("朝阳区")
        mock_aoi.resolve_place.assert_called_once()
        call_args = mock_aoi.resolve_place.call_args
        if call_args is not None and "buffer_deg" in (call_args[1] or {}):
            assert call_args[1]["buffer_deg"] == 0.15


def test_resolve_place_auto_buffer_province():
    """省级 place 应当用 5° buffer。"""
    mock_aoi = MagicMock(
        resolve_place=MagicMock(return_value=MagicMock(
            bbox_wgs84=[97.4, 26.0, 108.5, 34.3],
            centroid_wgs84=[103.0, 30.2],
            resolver="mock", confidence=0.9, query="四川省", ambiguity=[], notes="",
        ))
    )
    with patch.object(wbe, "_geoskill_aoi", mock_aoi):
        wbe._resolve_place("四川省")
        call_args = mock_aoi.resolve_place.call_args
        if call_args is not None and "buffer_deg" in (call_args[1] or {}):
            assert call_args[1]["buffer_deg"] == 5.0


def test_resolve_place_explicit_buffer():
    """用户显式给 buffer → 应当传透到 aoi.resolve_place。"""
    mock_aoi = MagicMock(
        resolve_place=MagicMock(return_value=MagicMock(
            bbox_wgs84=[103.4, 30.1, 104.7, 31.3],
            centroid_wgs84=[104.0, 30.7],
            resolver="mock", confidence=0.9, query="成都市", ambiguity=[], notes="",
        ))
    )
    with patch.object(wbe, "_geoskill_aoi", mock_aoi):
        wbe._resolve_place("成都市", buffer_deg=0.3)
        call_args = mock_aoi.resolve_place.call_args
        if call_args is not None and "buffer_deg" in (call_args[1] or {}):
            assert call_args[1]["buffer_deg"] == 0.3


def test_place_buffer_deg_in_help():
    """--help should mention --place-buffer-deg."""
    import subprocess
    out = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS, "water-body-extraction.py"),
         "extract", "--help"],
        capture_output=True, text=True, timeout=15,
    )
    combined = out.stdout + out.stderr
    assert "--place-buffer-deg" in combined
