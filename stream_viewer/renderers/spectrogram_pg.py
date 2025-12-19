"""
SpectrogramPG - A clean, performant real-time spectrogram renderer.

This renderer provides a scrolling spectrogram visualization using PyQtGraph.
It averages across user-selected channels (default: first 2 visible channels)
and displays the frequency spectrum over time.
"""

from dataclasses import dataclass, field
import json
import logging
from typing import List, Optional, Set, Tuple
import warnings

import numpy as np
from qtpy import QtGui, QtWidgets
import pyqtgraph as pg
from scipy import signal

from stream_viewer.renderers.data.base import RendererDataTimeSeries
from stream_viewer.renderers.display.pyqtgraph import PGRenderer


logger = logging.getLogger(__name__)

# Constants
DEFAULT_DB_FLOOR = -80.0      # Default dB value for empty/invalid data
DEFAULT_DB_CEILING = 0.0      # Default dB ceiling
EPSILON = 1e-12               # Small epsilon to prevent log(0)
MIN_NPERSEG = 16              # Minimum FFT segment size
MIN_SRATE = 1.0               # Minimum valid sampling rate (Hz)
DEFAULT_MAX_CHANNELS = 2      # Default number of channels to select


@dataclass
class SpectrogramState:
    """State container for spectrogram computation and display."""
    heatmap: Optional[np.ndarray] = None       # (n_freqs, n_time_cols) - the spectrogram data
    freq_bins: Optional[np.ndarray] = None     # Frequency axis values (Hz)
    freq_mask: Optional[np.ndarray] = None     # Boolean mask for frequency range
    n_time_cols: int = 0                       # Number of time columns in heatmap
    hop_samples: int = 1                       # Samples per time column
    last_write_idx: Optional[int] = None       # Last processed buffer write index
    sample_carry: int = 0                      # Carry-over samples between updates
    global_min: float = DEFAULT_DB_FLOOR       # Tracked minimum dB value
    global_max: float = DEFAULT_DB_CEILING     # Tracked maximum dB value
    
    def reset(self):
        """Reset state to initial values."""
        self.heatmap = None
        self.freq_bins = None
        self.freq_mask = None
        self.n_time_cols = 0
        self.hop_samples = 1
        self.last_write_idx = None
        self.sample_carry = 0
        self.global_min = DEFAULT_DB_FLOOR
        self.global_max = DEFAULT_DB_CEILING


class SpectrogramPG(RendererDataTimeSeries, PGRenderer):
    """
    Real-time scrolling spectrogram renderer using PyQtGraph.
    
    This renderer computes and displays spectrograms by averaging across 
    user-selected channels. It uses a simple scroll visualization where
    new data appears on the right and old data scrolls left.
    
    Features:
    - Real-time STFT-based spectrogram computation
    - Manual channel selection (default: first 2 visible channels)
    - Efficient scroll updates (shift-and-append)
    - Automatic dB scaling with global min/max tracking
    - Configurable frequency range and FFT parameters
    
    Args:
        auto_scale: Auto-scaling mode ('none', 'by-channel', 'by-stream')
        show_chan_labels: Whether to show channel labels
        color_set: Colormap name for the heatmap
        ylabel: Custom y-axis label text
        fmin_hz: Minimum frequency to display (Hz)
        fmax_hz: Maximum frequency to display (Hz)
        nperseg: FFT segment size (samples)
        overlap_ratio: Overlap between segments (0.0 to 0.9)
        max_selected_channels: Maximum channels to auto-select initially
    """
    
    COMPAT_ICONTROL = ['SpectrogramControlPanel']
    plot_modes = ["Scroll"]  # Scroll only for simplicity and stability
    
    gui_kwargs = dict(
        RendererDataTimeSeries.gui_kwargs,
        **PGRenderer.gui_kwargs,
        ylabel=str,
        fmin_hz=float,
        fmax_hz=float,
        nperseg=int,
        overlap_ratio=float,
        max_selected_channels=int,
    )

    def __init__(self,
                 # Inherited/overrides
                 auto_scale: str = 'none',
                 show_chan_labels: bool = False,
                 color_set: str = 'viridis',
                 # New parameters
                 ylabel: Optional[str] = None,
                 fmin_hz: float = 1.0,
                 fmax_hz: float = 45.0,
                 nperseg: int = 256,
                 overlap_ratio: float = 0.5,
                 max_selected_channels: int = DEFAULT_MAX_CHANNELS,
                 **kwargs):
        
        self._ylabel = ylabel
        self._fmin_hz = float(fmin_hz)
        self._fmax_hz = float(fmax_hz)
        self._nperseg = int(nperseg)
        self._overlap_ratio = float(np.clip(overlap_ratio, 0.0, 0.9))
        self._max_selected_channels = int(max_selected_channels)
        
        # Selected channel indices (per source) - will be initialized on reset
        self._selected_channels: List[Set[int]] = []
        
        # Main widget and plot items
        self._widget = pg.GraphicsLayoutWidget()
        self._plot_items: List[Optional[pg.PlotItem]] = []
        self._image_items: List[Optional[pg.ImageItem]] = []
        
        # Per-source state
        self._source_states: List[SpectrogramState] = []
        
        # Cached colormap LUT
        self._cached_lut: Optional[np.ndarray] = None
        self._cached_color_set: Optional[str] = None
        
        # Initialize parent classes
        super().__init__(
            show_chan_labels=show_chan_labels,
            color_set=color_set,
            plot_mode="Scroll",  # Force scroll mode
            **kwargs
        )
        self.reset_renderer()

    # ========================================
    # Lifecycle / Layout
    # ========================================
    
    def reset_renderer(self, reset_channel_labels: bool = True) -> None:
        """Reset the renderer and rebuild the display."""
        # Clear existing plots
        self._widget.clear()
        self._widget.setBackground(self.parse_color_str(self.bg_color))
        
        n_sources = len(self._data_sources)
        
        # Initialize/reset per-source storage
        self._plot_items = [None] * n_sources
        self._image_items = [None] * n_sources
        
        # Initialize source states
        while len(self._source_states) < n_sources:
            self._source_states.append(SpectrogramState())
        self._source_states = self._source_states[:n_sources]
        for state in self._source_states:
            state.reset()
        
        # Initialize selected channels for each source
        while len(self._selected_channels) < n_sources:
            self._selected_channels.append(set())
        self._selected_channels = self._selected_channels[:n_sources]
        
        if len(self.chan_states) == 0:
            return
        
        labelStyle = {'color': '#FFF', 'font-size': str(self.font_size) + 'pt'}
        
        last_row = 0
        for src_ix, src in enumerate(self._data_sources):
            ch_states = self.chan_states[self.chan_states['src'] == src.identifier]
            n_vis_src = ch_states['vis'].sum()
            if n_vis_src == 0:
                continue
            
            # Auto-select first N visible channels if not already selected
            if not self._selected_channels[src_ix]:
                vis_indices = ch_states[ch_states['vis']].index.tolist()
                n_select = min(self._max_selected_channels, len(vis_indices))
                self._selected_channels[src_ix] = set(vis_indices[:n_select])
            
            # Create plot item
            pw = self._widget.addPlot(row=src_ix, col=0)
            self._plot_items[src_ix] = pw
            last_row = src_ix
            
            # Configure plot appearance
            pw.showGrid(x=True, y=True, alpha=0.3)
            font = QtGui.QFont()
            font.setPointSize(self.font_size - 2)
            
            # X-axis setup
            pw.setXRange(0, self.duration)
            pw.getAxis("bottom").setTickFont(font)
            
            # Y-axis setup (frequency)
            yax = pw.getAxis('left')
            yax.setTickFont(font)
            pw.setYRange(self._fmin_hz, self._fmax_hz)
            pw.setLimits(yMin=self._fmin_hz, yMax=self._fmax_hz)
            
            # Lock y-axis (frequency), allow x-axis scrolling
            vb = pw.getViewBox()
            if vb is not None:
                vb.setMouseEnabled(x=True, y=False)
            
            # Label
            stream_name = json.loads(src.identifier)['name']
            ylabel = self._ylabel or f"{stream_name} (Hz)"
            pw.setLabel('left', ylabel, **labelStyle)
            
            # Create image item for spectrogram
            img = pg.ImageItem(axisOrder='row-major')
            pw.addItem(img)
            self._image_items[src_ix] = img
        
        # Configure bottom axis label
        if last_row >= 0 and self._plot_items[last_row] is not None:
            bottom_pw = self._plot_items[last_row]
            bottom_pw.setLabel('bottom', 'Time', units='s', **labelStyle)
            bottom_pw.getAxis("bottom").setStyle(showValues=True)
            
            # Link all plots to bottom plot for synchronized zooming
            for src_ix, pw in enumerate(self._plot_items):
                if pw is not None and src_ix != last_row:
                    pw.setXLink(bottom_pw)

    # ========================================
    # Channel Selection API
    # ========================================
    
    def get_channel_names(self, src_ix: int = 0) -> List[Tuple[int, str, bool]]:
        """
        Get list of channels for a source with their selection state.
        
        Returns:
            List of (index, name, is_selected) tuples
        """
        if src_ix >= len(self._data_sources):
            return []
        
        src = self._data_sources[src_ix]
        ch_states = self.chan_states[self.chan_states['src'] == src.identifier]
        visible_channels = ch_states[ch_states['vis']]
        
        result = []
        for idx, row in visible_channels.iterrows():
            is_selected = idx in self._selected_channels[src_ix]
            result.append((idx, row['name'], is_selected))
        
        return result
    
    def set_selected_channels(self, src_ix: int, channel_indices: Set[int]) -> None:
        """
        Set which channels are selected for averaging.
        
        Args:
            src_ix: Source index
            channel_indices: Set of channel indices to select
        """
        if src_ix < len(self._selected_channels):
            self._selected_channels[src_ix] = set(channel_indices)
            # Reset the spectrogram state to recompute with new channels
            if src_ix < len(self._source_states):
                self._source_states[src_ix].reset()

    def get_selected_channels(self, src_ix: int = 0) -> Set[int]:
        """Get currently selected channel indices for a source."""
        if src_ix < len(self._selected_channels):
            return self._selected_channels[src_ix].copy()
        return set()

    # ========================================
    # Spectrogram Computation
    # ========================================
    
    def _get_selected_data(self, buff_data: np.ndarray, src_ix: int) -> Optional[np.ndarray]:
        """
        Extract and average data from selected channels.
        
        Args:
            buff_data: Full buffer data (n_channels, n_samples)
            src_ix: Source index
            
        Returns:
            Averaged 1D signal or None if no valid data
        """
        if buff_data.size == 0 or buff_data.ndim != 2:
            return None
        
        # Get selected channel indices (relative to visible channels in buffer)
        src = self._data_sources[src_ix]
        ch_states = self.chan_states[self.chan_states['src'] == src.identifier]
        visible_indices = ch_states[ch_states['vis']].index.tolist()
        
        selected = self._selected_channels.get(src_ix, set()) if src_ix < len(self._selected_channels) else set()
        
        # Map global indices to buffer row indices
        buffer_rows = []
        for i, global_idx in enumerate(visible_indices):
            if global_idx in selected:
                buffer_rows.append(i)
        
        if not buffer_rows:
            # Fallback: use first channel
            buffer_rows = [0] if buff_data.shape[0] > 0 else []
        
        if not buffer_rows:
            return None
        
        # Validate buffer rows
        buffer_rows = [r for r in buffer_rows if r < buff_data.shape[0]]
        if not buffer_rows:
            return None
        
        # Extract and average selected channels
        selected_data = buff_data[buffer_rows, :]
        
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=RuntimeWarning)
            with np.errstate(invalid='ignore'):
                averaged = np.nanmean(selected_data, axis=0)
        
        # Replace NaN with zeros for FFT
        if not np.isfinite(averaged).any():
            return None
        
        averaged = np.nan_to_num(averaged, nan=0.0)
        return averaged
    
    def _compute_spectrogram(self, x: np.ndarray, srate: float) -> Optional[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
        """
        Compute STFT spectrogram.
        
        Args:
            x: Input signal (1D)
            srate: Sampling rate (Hz)
            
        Returns:
            (frequencies, times, power_dB) or None if computation fails
        """
        if x.size == 0 or srate < MIN_SRATE:
            return None
        
        # Adjust parameters if signal is too short
        nperseg = min(self._nperseg, x.size)
        nperseg = max(MIN_NPERSEG, nperseg)
        noverlap = int(nperseg * self._overlap_ratio)
        noverlap = max(0, min(noverlap, nperseg - 1))
        
        try:
            f, t, Sxx = signal.spectrogram(
                x, fs=float(srate),
                nperseg=int(nperseg),
                noverlap=int(noverlap),
                scaling='density',
                mode='psd'
            )
        except Exception as e:
            logger.debug(f"Spectrogram computation failed: {e}")
            return None
        
        if Sxx.size == 0:
            return None
        
        # Convert to dB
        with np.errstate(invalid='ignore', divide='ignore'):
            Pxx = 10.0 * np.log10(Sxx + EPSILON)
        
        return (f, t, Pxx)
    
    def _ensure_state_initialized(self, src_ix: int, srate: float, f: np.ndarray, Pxx: np.ndarray) -> bool:
        """
        Initialize source state if needed.
        
        Returns True if state is ready for use.
        """
        if src_ix >= len(self._source_states):
            return False
        
        state = self._source_states[src_ix]
        
        # Initialize frequency mask
        if state.freq_mask is None and f is not None and f.size > 0:
            mask = (f >= self._fmin_hz) & (f <= self._fmax_hz)
            if not np.any(mask):
                mask = np.ones_like(f, dtype=bool)
            state.freq_mask = mask
            state.freq_bins = f[mask]
        
        # Initialize hop size and column count
        if state.hop_samples == 1 and srate >= MIN_SRATE:
            nperseg = min(self._nperseg, int(srate * self.duration))
            nperseg = max(MIN_NPERSEG, nperseg)
            noverlap = int(nperseg * self._overlap_ratio)
            state.hop_samples = max(1, nperseg - noverlap)
            
            # Calculate number of time columns for the display duration
            n_samples = int(srate * self.duration)
            state.n_time_cols = max(1, 1 + (n_samples - nperseg) // state.hop_samples)
        
        # Initialize heatmap array
        if state.heatmap is None and state.freq_mask is not None and state.n_time_cols > 0:
            n_freqs = int(np.sum(state.freq_mask))
            if n_freqs > 0:
                state.heatmap = np.full((n_freqs, state.n_time_cols), DEFAULT_DB_FLOOR, dtype=np.float32)
                return True
        
        return state.heatmap is not None
    
    def _calculate_new_columns(self, src_ix: int, buf) -> int:
        """Calculate number of new columns based on buffer progress."""
        state = self._source_states[src_ix]
        
        if not hasattr(buf, '_write_idx') or buf._data.ndim != 2:
            return 0
        
        buf_len = buf._data.shape[1]
        if buf_len == 0:
            return 0
        
        curr_idx = int(buf._write_idx)
        prev_idx = state.last_write_idx
        
        if prev_idx is None:
            state.last_write_idx = curr_idx
            return 0
        
        # Handle circular buffer wrap-around
        delta = (curr_idx - prev_idx) % buf_len
        state.last_write_idx = curr_idx
        state.sample_carry += delta
        
        # Convert samples to columns
        hop = max(1, state.hop_samples)
        new_cols = state.sample_carry // hop
        state.sample_carry %= hop
        
        return int(new_cols)
    
    def _update_heatmap_scroll(self, state: SpectrogramState, P_new: np.ndarray, n_new_cols: int) -> None:
        """Update heatmap with scroll behavior: shift left, append right."""
        if state.heatmap is None or n_new_cols <= 0:
            return
        
        heat = state.heatmap
        n_cols = heat.shape[1]
        
        # Limit new columns to available data
        n_new_cols = min(n_new_cols, P_new.shape[1], n_cols)
        
        if n_new_cols >= n_cols:
            # Replace entire heatmap
            heat[:, :] = P_new[:, -n_cols:]
        else:
            # Scroll: shift left and append new data on right
            heat[:, :-n_new_cols] = heat[:, n_new_cols:]
            heat[:, -n_new_cols:] = P_new[:, -n_new_cols:]
        
        # Update global min/max (excluding floor values)
        valid_mask = heat > (DEFAULT_DB_FLOOR + 1.0)
        if np.any(valid_mask):
            current_min = float(np.min(heat[valid_mask]))
            current_max = float(np.max(heat[valid_mask]))
            if np.isfinite(current_min):
                state.global_min = min(state.global_min, current_min)
            if np.isfinite(current_max):
                state.global_max = max(state.global_max, current_max)
    
    def _get_colormap_lut(self) -> np.ndarray:
        """Get cached colormap lookup table."""
        if self._cached_lut is None or self._cached_color_set != self.color_set:
            self._cached_lut = self.get_colormap(self.color_set, 256)
            self._cached_color_set = self.color_set
        return self._cached_lut

    # ========================================
    # Update Loop
    # ========================================
    
    def update_visualization(self, data: np.ndarray, timestamps: np.ndarray) -> None:
        """Update the spectrogram display with new data."""
        if not any(np.any(ts) for ts in timestamps[0]):
            return
        
        lut = self._get_colormap_lut()
        
        for src_ix in range(len(data)):
            if src_ix >= len(self._plot_items) or self._plot_items[src_ix] is None:
                continue
            
            pw = self._plot_items[src_ix]
            img = self._image_items[src_ix] if src_ix < len(self._image_items) else None
            if img is None:
                continue
            
            buf = self._buffers[src_ix]
            buff_data = buf._data
            
            if buff_data.size == 0:
                continue
            
            state = self._source_states[src_ix]
            
            # Get sampling rate
            srate = self._data_sources[src_ix].data_stats.get('srate', 0.0) or 0.0
            if srate < MIN_SRATE:
                continue
            
            # Get averaged signal from selected channels
            x = self._get_selected_data(buff_data, src_ix)
            if x is None:
                continue
            
            # Compute spectrogram
            spec_result = self._compute_spectrogram(x, srate)
            if spec_result is None:
                continue
            
            f, t, Pxx = spec_result
            
            # Initialize state if needed
            if not self._ensure_state_initialized(src_ix, srate, f, Pxx):
                continue
            
            # Apply frequency mask
            if state.freq_mask is not None:
                P_masked = Pxx[state.freq_mask, :]
            else:
                P_masked = Pxx
            
            # Calculate new columns and update heatmap
            n_new_cols = self._calculate_new_columns(src_ix, buf)
            if n_new_cols > 0:
                self._update_heatmap_scroll(state, P_masked, n_new_cols)
            
            # Prepare display data
            if state.heatmap is None:
                continue
            
            display = state.heatmap.copy()
            
            # Determine color levels
            if state.global_max > state.global_min:
                levels = (state.global_min, state.global_max)
            else:
                levels = (DEFAULT_DB_FLOOR, DEFAULT_DB_CEILING)
            
            # Get time range from buffer
            if buf._tvec.size > 0:
                t_min = float(np.nanmin(buf._tvec))
                t_max = float(np.nanmax(buf._tvec))
                if np.isfinite(t_min) and np.isfinite(t_max) and t_max > t_min:
                    time_start = t_min
                    time_width = t_max - t_min
                else:
                    time_start = 0.0
                    time_width = float(self.duration)
            else:
                time_start = 0.0
                time_width = float(self.duration)
            
            # Update x-axis range
            pw.setXRange(time_start, time_start + time_width)
            
            # Update image
            img.setImage(display, levels=levels, autoLevels=False)
            img.setLookupTable(lut)
            img.setRect(pg.QtCore.QRectF(
                time_start, float(self._fmin_hz),
                time_width, float(self._fmax_hz - self._fmin_hz)
            ))

    # ========================================
    # Properties
    # ========================================
    
    @property
    def ylabel(self) -> Optional[str]:
        return self._ylabel
    
    @ylabel.setter
    def ylabel(self, value: Optional[str]) -> None:
        self._ylabel = value
        self.reset_renderer(reset_channel_labels=True)
    
    @property
    def fmin_hz(self) -> float:
        return self._fmin_hz
    
    @fmin_hz.setter
    def fmin_hz(self, value: float) -> None:
        self._fmin_hz = float(value)
        # Reset frequency mask for all sources
        for state in self._source_states:
            state.freq_mask = None
            state.freq_bins = None
            state.heatmap = None
        # Update y-axis range
        for pw in self._plot_items:
            if pw is not None:
                pw.setYRange(self._fmin_hz, self._fmax_hz)
                pw.setLimits(yMin=self._fmin_hz, yMax=self._fmax_hz)
    
    @property
    def fmax_hz(self) -> float:
        return self._fmax_hz
    
    @fmax_hz.setter
    def fmax_hz(self, value: float) -> None:
        self._fmax_hz = float(value)
        for state in self._source_states:
            state.freq_mask = None
            state.freq_bins = None
            state.heatmap = None
        for pw in self._plot_items:
            if pw is not None:
                pw.setYRange(self._fmin_hz, self._fmax_hz)
                pw.setLimits(yMin=self._fmin_hz, yMax=self._fmax_hz)
    
    @property
    def nperseg(self) -> int:
        return self._nperseg
    
    @nperseg.setter
    def nperseg(self, value: int) -> None:
        self._nperseg = max(MIN_NPERSEG, int(value))
        for state in self._source_states:
            state.reset()
    
    @property
    def overlap_ratio(self) -> float:
        return self._overlap_ratio
    
    @overlap_ratio.setter
    def overlap_ratio(self, value: float) -> None:
        self._overlap_ratio = float(np.clip(value, 0.0, 0.9))
        for state in self._source_states:
            state.reset()
    
    @property
    def max_selected_channels(self) -> int:
        return self._max_selected_channels
    
    @max_selected_channels.setter
    def max_selected_channels(self, value: int) -> None:
        self._max_selected_channels = max(1, int(value))
    
    @property
    def color_set(self) -> str:
        return super().color_set
    
    @color_set.setter
    def color_set(self, value: str) -> None:
        # Invalidate cached LUT
        self._cached_lut = None
        self._cached_color_set = None
        # Call parent setter
        super(SpectrogramPG, type(self)).color_set.fset(self, value)  # type: ignore

