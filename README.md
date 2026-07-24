# water-body-extraction

Automatic water body extraction from satellite imagery using NDWI and MNDWI indices.

## Features

- NDWI / MNDWI computation
- Otsu automatic thresholding
- Batch processing
- Vector output (GeoJSON)
- Supports Landsat 8/9 and Sentinel-2

## Installation

### Option 1: ClawHub
```bash
clawhub install water-body-extraction
```

### Option 2: Manual
```bash
git clone https://github.com/ruiduobao/water-body-extraction.git
cd water-body-extraction
pip install -r requirements.txt
```

### Option 3: Claude Code / skills.sh
```bash
claude skills install water-body-extraction
```

## Quick Start

```bash
# Extract water from a Landsat 8 image
python scripts/water-body-extraction.py extract \
  -i LC08_L1TP.tif --sensor landsat8 --index mndwi \
  -o water_mask.tif --vector water.geojson

# Batch process
python scripts/water-body-extraction.py batch \
  -d ./images/ --sensor sentinel2 --index ndwi \
  -o ./masks/ --vector-dir ./vectors/
```

## Dependencies

```
rasterio>=1.3.0
numpy>=1.21.0
scipy>=1.7.0
shapely>=1.8.0
fiona>=1.8.0
tqdm>=4.64.0
```

## Data Source

Local raster processing — uses pre-downloaded satellite imagery. No external API calls.

## License

MIT-0 (Public Domain)

---

# 中文说明

使用 NDWI / MNDWI 指数从卫星影像自动提取水体。

## 功能

- NDWI / MNDWI 计算
- Otsu 自动阈值
- 批量处理
- 矢量输出（GeoJSON）
- 支持 Landsat 8/9 和 Sentinel-2

## 安装

### 方式一：ClawHub
```bash
clawhub install water-body-extraction
```

### 方式二：手动安装
```bash
git clone https://github.com/ruiduobao/water-body-extraction.git
cd water-body-extraction
pip install -r requirements.txt
```

### 方式三：Claude Code / skills.sh
```bash
claude skills install water-body-extraction
```

## 快速开始

```bash
# 从 Landsat 8 影像提取水体
python scripts/water-body-extraction.py extract \
  -i LC08_L1TP.tif --sensor landsat8 --index mndwi \
  -o water_mask.tif --vector water.geojson

# 批量处理
python scripts/water-body-extraction.py batch \
  -d ./images/ --sensor sentinel2 --index ndwi \
  -o ./masks/ --vector-dir ./vectors/
```

## 数据来源

本地栅格处理 — 使用预下载的卫星影像，无外部 API 调用。

## 许可证

MIT-0 (Public Domain)
