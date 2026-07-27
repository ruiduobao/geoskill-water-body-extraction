---
name: water-body-extraction
description: 'Automatic water body extraction from multi-band satellite imagery using description: 'Automatic water body extraction from multi-band satellite imagery using NDWI and MNDWI indices.  Supports Landsat 8/9 and Sentinel-2, Otsu threshold optimization, and vector output.  '
---

# Water Body Extraction

Automatically extract water bodies from satellite imagery using spectral indices (NDWI / MNDWI). Designed for Landsat 8/9 and Sentinel-2 multi-band GeoTIFF inputs.

## Features

- **NDWI** (Normalized Difference Water Index): (Green - NIR) / (Green + NIR)
- **MNDWI** (Modified NDWI): (Green - SWIR) / (Green + SWIR)
- **Otsu automatic thresholding** — no manual threshold needed
- **Manual threshold** mode for fine control
- **Batch processing** of multiple images
- **Vector output** — GeoJSON boundaries alongside raster mask
- **Sensor-aware** band selection for Landsat 8/9 and Sentinel-2

## Band Configuration

| Sensor | Green | NIR | SWIR |
|--------|-------|-----|------|
| Landsat 8/9 | B3 | B5 | B6 |
| Sentinel-2 | B3 | B8 | B11 |

## Usage

### Single image extraction
```bash
python scripts\water-body-extraction.py extract \
  --input image.tif \
  --sensor landsat8 \
  --index mndwi \
  --output water_mask.tif \
  --vector water_boundary.geojson
```

### NEW (v0.2.0): one-shot by place name
```bash
# Provide just --place; the skill auto-fetches a Sentinel-2 scene for you
python scripts\water-body-extraction.py extract \
  --place "成都市锦江区" \
  --preset water-urban \
  --start-date 2023-06-01 --end-date 2023-09-30 --max-cloud 20 \
  --output water_mask.tif \
  --vector water_boundary.geojson \
  --qa
```

Available presets:
- `water-urban` (Sentinel-2 + MNDWI)
- `water-rural` (Sentinel-2 + NDWI)
- `water-landsat` (Landsat 8/9 + MNDWI)

### Otsu threshold optimization
```bash
python scripts\water-body-extraction.py threshold \
  --input image.tif \
  --sensor landsat8 \
  --index ndwi \
  --method otsu
```

### Batch processing
```bash
python scripts\water-body-extraction.py batch \
  --input-dir ./images/ \
  --sensor sentinel2 \
  --index mndwi \
  --output-dir ./masks/ \
  --vector-dir ./vectors/
```

## Installation

```bash
pip install rasterio>=1.3.0 numpy>=1.21.0 scipy>=1.7.0 shapely>=1.8.0 fiona>=1.8.0 tqdm>=4.64.0
# Or: pip install -r scripts/requirements.txt
```

## Parameters

- `--input`: Path to multi-band GeoTIFF
- `--sensor`: Sensor type (`landsat8`, `landsat9`, `sentinel2`)
- `--index`: Index to compute (`ndwi`, `mndwi`)
- `--threshold`: Manual threshold value (default: auto via Otsu)
- `--output`: Output raster mask path
- `--vector`: Output vector GeoJSON path (optional)
- `--input-dir`: Directory for batch processing
- `--output-dir`: Output directory for batch masks
- `--vector-dir`: Output directory for batch vectors
- `--method`: Threshold method (`otsu`, `manual`)
- `--json`: Output statistics as JSON

## Output

- **Raster mask**: Binary GeoTIFF (1=water, 0=non-water), same CRS/resolution as input
- **Vector**: GeoJSON polygon boundaries of water bodies
- **Statistics**: Water pixel count, percentage, threshold used

## Dependencies

```
rasterio>=1.3.0
numpy>=1.21.0
scipy>=1.7.0
shapely>=1.8.0
fiona>=1.8.0
tqdm>=4.64.0
```

## NDWI vs MNDWI Guidance

| Index | Best For | Caution |
|-------|----------|---------|
| NDWI | Open water, rural areas | Built-up areas may show false positives |
| MNDWI | Urban areas, mixed land cover | Suppresses built-up noise; may miss turbid water |

**Recommendation**: Use MNDWI for urban/suburban scenes; NDWI for natural landscapes.

## Cloud Masking Guidance

Clouds and cloud shadows cause false water detections. Best practices:

- **Pre-filter**: Use only images with <10% cloud cover (check metadata)
- **QA band**: Use the Landsat/Sentinel QA_PIXEL band to mask clouds before extraction
- **Post-processing**: Apply morphological opening to remove small cloud-shadow false positives

## Minimum Area Filtering

Remove small noise polygons with `--min-area`:

```bash
python scripts\water-body-extraction.py extract \
  --input image.tif --sensor landsat8 --index mndwi \
  --output water_mask.tif --vector water_boundary.geojson \
  --min-area 1000
```

`--min-area` is in map units (m² for projected CRS). Typical values: 500–5000 m².

## Large File Guidance

For rasters >1 GB:

- Process in tiles using `--tile-size 4096 --overlap 256`
- Use `--compress lzw` to reduce output size
- Ensure sufficient RAM: ~2× the uncompressed raster size

## Vector Output Formats

In addition to GeoJSON, Shapefile and GeoPackage output are supported:

```bash
python scripts\water-body-extraction.py extract \
  --input image.tif --sensor landsat8 --index mndwi \
  --output water_mask.tif --vector water_boundary.gpkg --vector-format gpkg
```

## Accuracy Assessment

Validate results against reference data:

1. Collect ground-truth points or polygons
2. Compute confusion matrix: overall accuracy, kappa coefficient, F1 score
3. Compare with existing water datasets (e.g., JRC Global Surface Water, GlobeLand30)

## Visualization

Visualize results in QGIS or Python:

- **Raster mask**: Apply blue color map (water=blue, non-water=transparent)
- **Vector overlay**: Semi-transparent blue fill with dark blue boundary
- **Before/after**: Side-by-side comparison of original imagery and water mask

```python
import rasterio
import matplotlib.pyplot as plt

with rasterio.open('water_mask.tif') as src:
    mask = src.read(1)
plt.imshow(mask, cmap='Blues')
plt.title('Water Body Extraction Result')
plt.show()
```

## Citation

If this tool supports your research, please cite:

```bibtex
@software{water_body_extraction,
  author  = {ruiduobao},
  title   = {Water Body Extraction Tool},
  url     = {https://github.com/ruiduobao/water-body-extraction},
  version = {0.1.0},
  year    = {2024},
}
```

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `ConnectionError` | Network issue | Check internet, retry |
| `HTTP 429` | Rate limit | Wait 60s, retry |
| `ValueError` | Invalid input | Check parameter format |
| Empty output | No data / all cloud | Try different image or adjust threshold |
| `ModuleNotFoundError` | Missing dep | Run pip install |
| `MemoryError` | Raster too large | Use tiling (--tile-size) or increase RAM |
| All water / no water | Threshold issue | Try manual threshold or different index |

## Data Source

Local raster processing — uses pre-downloaded satellite imagery. No external API calls.

---

## Advanced Usage

### Batch Processing with Shell Loop
```bash
for img in scenes/*.tif; do
  python scripts\water-body-extraction.py extract     --input "$img" --index MNDWI --sensor sentinel2     --output "water_$(basename $img)"
  sleep 1
done
```

### CI/CD Integration (GitHub Actions)
```yaml
# .github/workflows/monthly-water.yml
name: Monthly Water Extraction
on:
  schedule:
    - cron: '0 0 1 * *'  # Monthly
jobs:
  extract:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install numpy rasterio scipy
      - run: |
          python scripts\water-body-extraction.py extract \
            --input data/latest_scene.tif \
            --index MNDWI --sensor sentinel2 --otsu \
            --output data/water_latest.tif
```

### Vector Export & PostGIS Import
```bash
# Extract water and export as GeoJSON vector
python scripts\water-body-extraction.py extract   --input scene.tif --index MNDWI --vector --output water.geojson

# Import to PostGIS
ogr2ogr -f PostgreSQL PG:"dbname=gis_db" water.geojson -nln water_bodies
```

### Performance Tips
- Otsu thresholding is automatic; use `--threshold 0.0` for manual control
- Add `--min-area 100` to filter small noise polygons
- Use `--cloud-mask` with QA_PIXEL to improve accuracy in cloudy scenes

---

## 中文说明

使用光谱指数（NDWI / MNDWI）从卫星影像中自动提取水体。支持 Landsat 8/9 和 Sentinel-2 多波段 GeoTIFF 输入。

## 功能特性

- **NDWI**（归一化水体指数）：(Green - NIR) / (Green + NIR)
- **MNDWI**（改进型水体指数）：(Green - SWIR) / (Green + SWIR)
- **Otsu 自动阈值** — 无需手动设置阈值
- **手动阈值**模式，精细控制
- **批量处理**多张影像
- **矢量输出** — 同时输出 GeoJSON 边界和栅格掩膜
- **传感器感知** — 自动选择对应波段

## 波段配置

| 传感器 | Green | NIR | SWIR |
|--------|-------|-----|------|
| Landsat 8/9 | B3 | B5 | B6 |
| Sentinel-2 | B3 | B8 | B11 |

## 使用示例

### 单幅影像提取
```bash
python scripts\water-body-extraction.py extract \
  --input image.tif \
  --sensor landsat8 \
  --index mndwi \
  --output water_mask.tif \
  --vector water_boundary.geojson
```

### Otsu 阈值优化
```bash
python scripts\water-body-extraction.py threshold \
  --input image.tif \
  --sensor landsat8 \
  --index ndwi \
  --method otsu
```

### 批量处理
```bash
python scripts\water-body-extraction.py batch \
  --input-dir ./images/ \
  --sensor sentinel2 \
  --index mndwi \
  --output-dir ./masks/ \
  --vector-dir ./vectors/
```

## 安装

```bash
pip install rasterio>=1.3.0 numpy>=1.21.0 scipy>=1.7.0 shapely>=1.8.0 fiona>=1.8.0 tqdm>=4.64.0
# 或: pip install -r scripts/requirements.txt
```

## 参数说明

- `--input`: 多波段 GeoTIFF 路径
- `--sensor`: 传感器类型（`landsat8`, `landsat9`, `sentinel2`）
- `--index`: 计算指数（`ndwi`, `mndwi`）
- `--threshold`: 手动阈值（默认 Otsu 自动）
- `--output`: 输出栅格掩膜路径
- `--vector`: 输出矢量 GeoJSON 路径（可选）
- `--input-dir`: 批量处理输入目录
- `--output-dir`: 批量输出掩膜目录
- `--vector-dir`: 批量输出矢量目录
- `--method`: 阈值方法（`otsu`, `manual`）
- `--json`: 以 JSON 格式输出统计信息

## 输出结果

- **栅格掩膜**: 二值 GeoTIFF（1=水体, 0=非水体），与输入相同的 CRS/分辨率
- **矢量**: GeoJSON 多边形水体边界
- **统计信息**: 水体像素数、占比、使用的阈值

## 依赖库

```
rasterio>=1.3.0
numpy>=1.21.0
scipy>=1.7.0
shapely>=1.8.0
fiona>=1.8.0
tqdm>=4.64.0
```

## NDWI vs MNDWI 选择指南

| 指数 | 适用场景 | 注意事项 |
|------|---------|---------|
| NDWI | 开阔水体、农村地区 | 建筑区可能产生假阳性 |
| MNDWI | 城市区域、混合用地 | 抑制建筑噪声；可能漏检浑浊水体 |

**建议**：城市/郊区场景用 MNDWI；自然地貌用 NDWI。

## 云掩膜指导

云和云影会导致虚假水体检测。最佳实践：

- **预处理**：仅使用云量 <10% 的影像（查看元数据）
- **QA 波段**：使用 Landsat/Sentinel QA_PIXEL 波段在提取前掩膜云
- **后处理**：形态学开运算去除小云影假阳性

## 最小面积过滤

使用 `--min-area` 去除小面积噪声多边形：

```bash
python scripts\water-body-extraction.py extract \
  --input image.tif --sensor landsat8 --index mndwi \
  --output water_mask.tif --vector water_boundary.geojson \
  --min-area 1000
```

`--min-area` 单位为地图单位（投影 CRS 为 m²）。典型值：500–5000 m²。

## 大文件处理

对于 >1 GB 的栅格：

- 使用 `--tile-size 4096 --overlap 256` 分块处理
- 使用 `--compress lzw` 减小输出
- 确保足够内存：约为未压缩栅格大小的 2 倍

## 矢量输出格式

除 GeoJSON 外，还支持 Shapefile 和 GeoPackage 输出：

```bash
python scripts\water-body-extraction.py extract \
  --input image.tif --sensor landsat8 --index mndwi \
  --output water_mask.tif --vector water_boundary.gpkg --vector-format gpkg
```

## 精度评估

使用参考数据验证结果：

1. 采集地面真实点或多边形
2. 计算混淆矩阵：总体精度、Kappa 系数、F1 分数
3. 与现有水体数据集对比（如 JRC 全球地表水、GlobeLand30）

## 可视化

在 QGIS 或 Python 中可视化结果：

- **栅格掩膜**：蓝色配色（水体=蓝色，非水体=透明）
- **矢量叠加**：半透明蓝色填充 + 深蓝色边界
- **对比**：原始影像与水体掩膜并排对比

## 引用格式

如果本工具支持您的研究，请引用：

```bibtex
@software{water_body_extraction,
  author  = {ruiduobao},
  title   = {Water Body Extraction Tool},
  url     = {https://github.com/ruiduobao/water-body-extraction},
  version = {0.1.0},
  year    = {2024},
}
```

## 故障排除

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `ConnectionError` | 网络问题 | 检查网络，重试 |
| `HTTP 429` | 速率限制 | 等待 60 秒后重试 |
| `ValueError` | 无效输入 | 检查参数格式 |
| 无输出 | 无数据 / 全是云 | 更换影像或调整阈值 |
| `ModuleNotFoundError` | 缺少依赖 | 运行 pip install |
| `MemoryError` | 栅格过大 | 使用分块处理或增加内存 |
| 全水体 / 无水 | 阈值问题 | 尝试手动阈值或更换指数 |

## 数据来源

本地栅格处理 — 使用预下载的卫星影像，无外部 API 调用。
