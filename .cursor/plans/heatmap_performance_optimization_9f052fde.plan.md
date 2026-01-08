---
name: Heatmap Performance Optimization
overview: Optimize the HeatmapPG renderer to reduce CPU usage and improve frame rate by implementing configurable update rates, data downsampling, better update skipping, memory optimizations, and spectrogram computation improvements.
todos: []
---

# Heatmap Performance Optimization Plan

## Current Performance Bottlenecks

The `HeatmapPG` renderer has several performance issues:

1. **High update frequency**: 60 Hz timer forces spectrogram computation every 16.67ms
2. **Expensive spectrogram computation**: `scipy.signal.spectrogram` runs on full buffer data every update
3. **No data downsampling**: Processes entire buffer even when only small portion is new
4. **Memory allocation**: Heatmap concatenation in Scroll mode causes frequent allocations
5. **Redundant computations**: Some updates occur even when no new data is available

## Optimization Strategy

### 1. Configurable Update Rate

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- Add `update_rate_hz` parameter (default: 30 Hz for spectrograms, configurable)
- Override `restart_timer()` to use custom interval
- Update `TIMER_INTERVAL` class variable or instance variable
- Add to `gui_kwargs` for control panel integration

**Benefits**: Reduces CPU load by 50% while maintaining smooth visualization (30 Hz is sufficient for spectrograms)

### 2. Enhanced Update Skipping

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- Improve `has_new_data` detection in `update_visualization()` (lines 1153-1171)
- Skip entire update cycle if no new data detected early
- Add minimum time delta check to avoid processing tiny timestamp changes
- Skip spectrogram computation if buffer hasn't changed significantly

**Benefits**: Eliminates unnecessary work when data stream is slow or paused

### 3. Data Downsampling Before Spectrogram

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- Add optional `max_samples_per_spectrogram` parameter
- In `_compute_spectrogram()`, downsample input signal if it exceeds threshold
- Use `scipy.signal.resample` or decimation for downsampling
- Preserve recent data (take last N samples) rather than random sampling

**Benefits**: Reduces spectrogram computation time by 50-75% for high sample rates

### 4. Memory Optimization for Scroll Mode

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- In `_update_heatmap_columns()` (line 813), use pre-allocated chunks instead of concatenation
- Pre-allocate heatmap in larger chunks (e.g., 100 columns at a time)
- Use `np.empty()` with pre-allocation strategy
- Consider circular buffer approach for very long sessions

**Benefits**: Reduces memory fragmentation and allocation overhead

### 5. Float32 Precision Optimization

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- Convert heatmap arrays to `float32` instead of `float64` (default)
- Update `SourceState.heatmap` initialization (line 423)
- Convert display arrays to float32 before sending to remote process
- Update `_prepare_display_heatmap()` to use float32

**Benefits**: Reduces memory usage by 50% and speeds up array operations

### 6. Spectrogram Computation Optimization

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- Cache FFT window function (avoid recomputing each time)
- Use `nperseg` that's power of 2 when possible (faster FFT)
- Add parameter validation to ensure reasonable `nperseg`/`noverlap` ratios
- Consider using `scipy.signal.stft` with optimized parameters

**Benefits**: 10-20% faster spectrogram computation

### 7. Batch Update Optimization

**File**: `stream_viewer/stream_viewer/renderers/heatmap_pg.py`

- Accumulate small column updates and process in batches
- Only update image display when significant changes occur
- Use dirty flag to track when display update is needed

**Benefits**: Reduces remote process communication overhead

## Implementation Details

### Key Changes to `heatmap_pg.py`:

1. **Constructor additions**:

- `update_rate_hz: float = 30.0` parameter
- `max_samples_per_spectrogram: Optional[int] = None` parameter
- Store as instance variables

2. **Timer override**:

- Override `restart_timer()` to use `update_rate_hz`
- Calculate interval: `int(1000.0 / self._update_rate_hz)`

3. **Early exit in `update_visualization()`**:

- Check for new data before any processing
- Return early if no new data detected

4. **Downsampling in `_compute_spectrogram()`**:

- Check if `x.size > max_samples_per_spectrogram`
- Downsample using `scipy.signal.decimate` or similar
- Adjust `srate` parameter accordingly

5. **Memory optimization**:

- Pre-allocate heatmap chunks in Scroll mode
- Use `np.empty()` with explicit dtype=np.float32

6. **Float32 conversion**:

- Update all heatmap array creation to use `dtype=np.float32`
- Ensure compatibility with pyqtgraph (it supports float32)

## Testing Considerations

- Verify visualization quality at 30 Hz (should be smooth)
- Test with various sample rates (low and high)
- Ensure memory usage doesn't grow unbounded in Scroll mode
- Validate that downsampling doesn't affect frequency resolution significantly
- Test with multiple data sources simultaneously

## Performance Targets

- **CPU reduction**: 40-60% lower CPU usage
- **Frame rate**: Maintain smooth 30 Hz (or configured rate)
- **Memory**: 50% reduction in memory usage (float32)
- **Latency**: No significant increase (< 50ms total)

## Backward Compatibility

- All optimizations are additive (new parameters with sensible defaults)