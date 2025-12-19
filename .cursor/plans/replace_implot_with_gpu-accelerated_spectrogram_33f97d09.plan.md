---
name: Replace ImPlot with GPU-Accelerated Spectrogram
overview: Remove the non-functional ImPlot implementation and replace it with a GPU-accelerated spectrogram renderer using PyTorch for computation and PyQtGraph for rendering, with CPU fallback support.
todos:
  - id: remove_implot_files
    content: Delete heatmap_implot.py and implot.py files
    status: completed
  - id: create_gpu_renderer
    content: Create heatmap_gpu.py with PyTorch-based GPU-accelerated spectrogram computation
    status: completed
    dependencies:
      - remove_implot_files
  - id: update_init
    content: Update __init__.py to remove HeatmapImPlot and add HeatmapGPU imports
    status: completed
    dependencies:
      - create_gpu_renderer
  - id: update_dependencies
    content: Add torch as optional dependency in pyproject.toml
    status: completed
---

# Replace ImPlot with GPU-Accelerated Spectrogram Renderer

## Overview

Remove the non-functional `heatmap_implot.py` and `implot.py` files and implement a new GPU-accelerated spectrogram renderer using PyTorch for STFT computation. The renderer will use PyQtGraph for visualization (consistent with existing `HeatmapPG`) and gracefully fall back to CPU computation when GPU is unavailable.

## Implementation Strategy

### 1. Remove ImPlot Files

- Delete `stream_viewer/stream_viewer/renderers/heatmap_implot.py`
- Delete `stream_viewer/stream_viewer/renderers/display/implot.py`
- Remove `HeatmapImPlot` import from `stream_viewer/stream_viewer/renderers/__init__.py`

### 2. Create GPU-Accelerated Spectrogram Renderer

Create new file: `stream_viewer/stream_viewer/renderers/heatmap_gpu.py`**Key Features:**

- Inherits from `RendererDataTimeSeries` and `PGRenderer` (same as `HeatmapPG`)
- Uses PyTorch `torch.stft` for GPU-accelerated spectrogram computation
- Falls back to `scipy.signal.spectrogram` when GPU unavailable
- Maintains same interface as `HeatmapPG` for compatibility with `HeatmapControlPanel`
- Reuses spectrogram logic structure from `HeatmapPG` but with GPU computation

**Architecture:**

```javascript
HeatmapGPU
├── RendererDataTimeSeries (data handling, buffers, timers)
├── PGRenderer (PyQtGraph display, colormaps)
└── GPU Spectrogram Computation
    ├── PyTorch STFT (primary, GPU-accelerated)
    └── SciPy spectrogram (fallback, CPU)
```

**Implementation Details:**

- Detect GPU availability at initialization
- Convert NumPy arrays to PyTorch tensors for GPU computation
- Use `torch.stft` with same parameters as `scipy.signal.spectrogram`
- Convert results back to NumPy for PyQtGraph rendering
- Maintain per-source state (same `SourceState` dataclass pattern)
- Support both Sweep and Scroll plot modes
- Handle frequency masking, column updates, and level locking

### 3. Update Dependencies

- Add `torch` as optional dependency in `pyproject.toml` (with version constraint)
- Keep existing dependencies (scipy for fallback, pyqtgraph for rendering)

### 4. Integration Points

- Register renderer in `stream_viewer/stream_viewer/renderers/__init__.py`
- Compatible with existing `HeatmapControlPanel` widget
- Uses same `COMPAT_ICONTROL = ['HeatmapControlPanel']` interface

## Files to Modify

1. **Delete:**

- `stream_viewer/stream_viewer/renderers/heatmap_implot.py`
- `stream_viewer/stream_viewer/renderers/display/implot.py`

2. **Create:**

- `stream_viewer/stream_viewer/renderers/heatmap_gpu.py` (new GPU-accelerated renderer)

3. **Modify:**

- `stream_viewer/stream_viewer/renderers/__init__.py` - Remove HeatmapImPlot import, add HeatmapGPU import
- `stream_viewer/pyproject.toml` - Add torch as optional dependency

## Technical Approach

### GPU Detection and Fallback

```python
try:
    import torch
    _has_torch = True
    _device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
except ImportError:
    _has_torch = False
    _device = None
```



### Spectrogram Computation

- Primary: Use `torch.stft()` on GPU tensors
- Fallback: Use `scipy.signal.spectrogram()` when PyTorch unavailable or GPU not present
- Maintain same output format (frequencies, times, power in dB)

### Rendering

- Use PyQtGraph `ImageItem` for heatmap display (same as `HeatmapPG`)
- Use `RemoteGraphicsView` for performance (same pattern as `HeatmapPG`)
- Reuse colormap and styling logic from `PGRenderer`

## Benefits

- GPU acceleration for real-time spectrogram computation
- Graceful degradation to CPU when GPU unavailable