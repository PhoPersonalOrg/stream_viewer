#  Copyright (C) 2014-2021 Syntrogi Inc dba Intheon. All rights reserved.

"""
EEG Power Band Visualization with Global Field Power (GFP).

Displays real-time GFP for four standard EEG frequency bands (Theta, Alpha, Beta, Gamma)
as stacked subplots with linked time axes and bootstrap confidence intervals, inspired by MNE's
time_frequency_global_field_power example.

Reference: https://mne.tools/stable/auto_examples/time_frequency/time_frequency_global_field_power.html

Computation vs display (integration)
--------------------------------------
**Pure signal processing** (shared): band-pass filtering, GFP, baseline correction,
and bootstrap CIs live in ``phopymnehelper.analysis.computations.gfp_band_power`` so the
same math can drive timeline detail renderers without importing stream_viewer.

**stream_viewer-only**: timer via :class:`~stream_viewer.renderers.display.pyqtgraph.PGRenderer`,
buffered multi-source data from :class:`~stream_viewer.renderers.data.base.RendererDataTimeSeries.fetch_data`,
``plot_mode`` (Sweep vs Scroll time wrapping), pyqtgraph layout (stacked ``PlotItem``s, linked x-axes),
and y-axis auto-range throttling.

Orchestration entry point for each frame: :meth:`LinePowerVis.update_visualization`.
"""

from typing import Optional

import numpy as np
from qtpy import QtGui
import pyqtgraph as pg
from phopymnehelper.analysis.computations.gfp_band_power import BAND_COLORS_RGB as BAND_COLORS, STANDARD_EEG_FREQUENCY_BANDS as FREQUENCY_BANDS, bandpass_filter_channels, baseline_rescale, bootstrap_gfp_ci, global_field_power
from stream_viewer.renderers.data.base import RendererDataTimeSeries
from stream_viewer.renderers.display.pyqtgraph import PGRenderer


class LinePowerVis(RendererDataTimeSeries, PGRenderer):
    """
    Pyqtgraph-based renderer for EEG power band visualization with Global Field Power (GFP).

    Displays GFP (sum of squares across channels) for four standard frequency bands
    as stacked subplots with synchronized/linked time axes:
    - Theta (4-7 Hz)
    - Alpha (8-12 Hz)
    - Beta (13-25 Hz)
    - Gamma (30-45 Hz)

    Each band is displayed in its own subplot with bootstrap confidence intervals
    shown as shaded regions around the GFP line.
    """
    COMPAT_ICONTROL = ['LinePowerControlPanel']
    plot_modes = ["Sweep", "Scroll"]
    gui_kwargs = dict(
        RendererDataTimeSeries.gui_kwargs,
        **PGRenderer.gui_kwargs,
        filter_order=int,
        n_bootstrap=int,
        baseline_start=float,
        baseline_end=float,
        show_confidence=bool,
        line_width=float,
        antialias=bool,
    )

    def __init__(
        self,
        # Override inherited
        auto_scale: str = 'none',
        show_chan_labels: bool = False,
        color_set: str = 'viridis',
        # New parameters
        filter_order: int = 4,
        n_bootstrap: int = 100,
        baseline_start: Optional[float] = None,
        baseline_end: float = 0.0,
        show_confidence: bool = False,
        line_width: float = 0.5,
        antialias: bool = True,
        **kwargs
    ):
        """
        EEG Power Band Visualization with Global Field Power.

        Args:
            filter_order: Order of the Butterworth bandpass filter.
            n_bootstrap: Number of bootstrap iterations for confidence intervals.
            baseline_start: Start time (in seconds from buffer start) for baseline correction.
                           None means from the beginning of the buffer.
            baseline_end: End time (in seconds from buffer start) for baseline correction.
            show_confidence: Whether to display bootstrap confidence interval regions.
            line_width: Width of the GFP lines.
            antialias: Enable anti-aliasing for smoother lines.
            **kwargs: Additional arguments passed to parent classes.
        """
        self._filter_order = filter_order
        self._n_bootstrap = n_bootstrap
        self._baseline_start = baseline_start
        self._baseline_end = baseline_end
        self._show_confidence = show_confidence
        self._line_width = line_width
        self._antialias = antialias

        # Set _auto_scale early to avoid race conditions during initialization
        self._auto_scale = auto_scale

        self._widget = pg.GraphicsLayoutWidget()
        self._plot_widgets = []  # One PlotWidget per band
        self._curves = []  # One PlotCurveItem per band
        self._fill_items = []  # One FillBetweenItem per band for confidence intervals
        self._ci_upper_curves = []  # Upper CI boundary curves
        self._ci_lower_curves = []  # Lower CI boundary curves

        # Cache for filter coefficients (avoid recomputing each frame)
        self._filter_cache = {}
        self._last_srate = None
        
        # Track y-axis ranges for each band to prevent continuous rescaling
        self._y_ranges = {}  # band_idx -> (min, max)
        self._range_update_counter = 0  # Counter to throttle range updates

        super().__init__(
            auto_scale=auto_scale,
            show_chan_labels=show_chan_labels,
            color_set=color_set,
            **kwargs
        )
        self.reset_renderer()

    def reset_renderer(self, reset_channel_labels=True):
        """Reset and rebuild the visualization."""
        self._widget.clear()
        self._widget.setBackground(self.parse_color_str(self.bg_color))
        self._plot_widgets = []
        self._curves = []
        self._fill_items = []
        self._ci_upper_curves = []
        self._ci_lower_curves = []
        self._filter_cache = {}
        self._last_srate = None
        self._y_ranges = {}  # Reset y-axis ranges
        self._range_update_counter = 0

        if len(self.chan_states) == 0 or len(self._data_sources) == 0:
            return

        labelStyle = {'color': '#FFF', 'font-size': str(self.font_size) + 'pt'}

        font = QtGui.QFont("Arial", int(self.font_size - 2))

        # Get initial time vector
        if len(self._buffers) > 0 and self._buffers[0]._data.size > 0:
            n_samples = self._buffers[0]._data.shape[-1]
            srate = self._data_sources[0].data_stats.get('srate', 1.0) or 1.0
            t_vec = np.arange(n_samples, dtype=float) / srate
        else:
            t_vec = np.linspace(0, self.duration, 100)

        # Create stacked subplots - one per frequency band (reversed order so Gamma is at top)
        n_bands = len(FREQUENCY_BANDS)
        for band_idx, (band_name, fmin, fmax) in enumerate(FREQUENCY_BANDS):
            # Create subplot for this band
            pw = self._widget.addPlot(row=band_idx, col=0, antialias=self._antialias)
            pw.showGrid(x=True, y=True, alpha=0.3)
            pw.setXRange(0, self.duration)

            # Set y-range based on limits (disable auto-range to prevent jerky updates)
            if self.auto_scale != 'none':
                # Set initial range from limits, will be updated from data in update_visualization
                pw.setYRange(self.lower_limit, self.upper_limit)
                pw.disableAutoRange(axis='y')  # Disable continuous auto-scaling
                self._y_ranges[band_idx] = (self.lower_limit, self.upper_limit)
            else:
                pw.setYRange(self.lower_limit, self.upper_limit)
                pw.disableAutoRange(axis='y')
                self._y_ranges[band_idx] = (self.lower_limit, self.upper_limit)

            pw.getAxis("bottom").setTickFont(font)
            pw.getAxis("left").setTickFont(font)

            # Y-axis label with band name and frequency range
            pw.setLabel('left', f'{band_name}\n({fmin}-{fmax}Hz)', **labelStyle)

            # Hide x-axis labels for all but the bottom plot
            if band_idx < n_bands - 1:
                pw.getAxis("bottom").setStyle(showValues=False)
            else:
                pw.setLabel('bottom', 'Time', units='s', **labelStyle)

            self._plot_widgets.append(pw)

            # Create curves for this band
            color = BAND_COLORS[band_idx]
            pen = pg.mkPen(color=color, width=self._line_width)

            # Main GFP curve
            curve = pg.PlotCurveItem(
                t_vec, np.zeros_like(t_vec),
                pen=pen,
                connect='finite',
                name=f'{band_name} ({fmin}-{fmax}Hz)'
            )
            pw.addItem(curve)
            self._curves.append(curve)

            if self._show_confidence:
                # Create invisible curves for CI boundaries
                ci_color = (*color, 80)  # Semi-transparent
                ci_pen = pg.mkPen(color=ci_color, width=0)

                ci_upper = pg.PlotCurveItem(t_vec, np.zeros_like(t_vec), pen=ci_pen)
                ci_lower = pg.PlotCurveItem(t_vec, np.zeros_like(t_vec), pen=ci_pen)

                # Fill between CI curves
                fill_brush = pg.mkBrush(color=(*color, 50))
                fill_item = pg.FillBetweenItem(ci_lower, ci_upper, brush=fill_brush)

                pw.addItem(ci_upper)
                pw.addItem(ci_lower)
                pw.addItem(fill_item)

                self._ci_upper_curves.append(ci_upper)
                self._ci_lower_curves.append(ci_lower)
                self._fill_items.append(fill_item)

        # Link all x-axes to the bottom plot for synchronized panning/zooming
        if len(self._plot_widgets) > 1:
            bottom_pw = self._plot_widgets[-1]
            for pw in self._plot_widgets[:-1]:
                pw.setXLink(bottom_pw)

        # Reduce spacing between subplots
        self._widget.ci.setSpacing(2.)

    def update_visualization(self, data, timestamps) -> None:
        """Update the visualization with new data."""
        if not any([np.any(_) for _ in timestamps[0]]):
            return

        if len(self._plot_widgets) == 0:
            return

        # Aggregate data from all sources
        all_data = []
        srate = None

        for src_ix in range(len(data)):
            dat, _ = data[src_ix]
            ts, _ = timestamps[src_ix]

            if dat.size == 0:
                continue

            all_data.append(dat)

            if srate is None:
                srate = self._data_sources[src_ix].data_stats.get('srate', 0.0) or 0.0

        if len(all_data) == 0 or srate <= 0:
            return

        # Combine all channel data
        combined_data = np.vstack(all_data) if len(all_data) > 1 else all_data[0]
        n_samples = combined_data.shape[1]

        # Create time vector
        t_vec = np.arange(n_samples, dtype=float) / srate

        # Check if sample rate changed (invalidate filter cache)
        if self._last_srate != srate:
            self._filter_cache = {}
            self._last_srate = srate

        # Process each frequency band
        for band_idx, (band_name, fmin, fmax) in enumerate(FREQUENCY_BANDS):
            # Skip bands that exceed Nyquist frequency
            if fmin >= srate / 2:
                continue

            filtered_data = bandpass_filter_channels(combined_data, fmin, fmax, srate, self._filter_order, self._filter_cache)
            gfp = global_field_power(filtered_data)
            gfp = baseline_rescale(gfp, t_vec, self._baseline_start, self._baseline_end)

            # Handle sweep/scroll mode for time display
            if self.plot_mode == "Sweep":
                display_t = t_vec % self.duration
            else:
                display_t = t_vec

            # Update main curve
            if band_idx < len(self._curves):
                self._curves[band_idx].setData(display_t, gfp)

            # Update confidence intervals if enabled
            if self._show_confidence and band_idx < len(self._ci_upper_curves):
                ci_low, ci_up = bootstrap_gfp_ci(filtered_data, self._n_bootstrap)
                ci_low = baseline_rescale(ci_low, t_vec, self._baseline_start, self._baseline_end)
                ci_up = baseline_rescale(ci_up, t_vec, self._baseline_start, self._baseline_end)

                self._ci_lower_curves[band_idx].setData(display_t, gfp - ci_low)
                self._ci_upper_curves[band_idx].setData(display_t, gfp + ci_up)
            
            # Update y-axis range when auto_scale is enabled (but only when range changes significantly)
            if self.auto_scale != 'none' and band_idx < len(self._plot_widgets):
                # Compute current data range
                if np.isfinite(gfp).any():
                    data_min = float(np.nanmin(gfp))
                    data_max = float(np.nanmax(gfp))
                    
                    # Add small padding (5% on each side)
                    data_range = data_max - data_min
                    if data_range > 0:
                        padding = data_range * 0.05
                        new_min = data_min - padding
                        new_max = data_max + padding
                    else:
                        # Handle case where all values are the same
                        new_min = data_min - abs(data_min) * 0.1 if data_min != 0 else -1.0
                        new_max = data_max + abs(data_max) * 0.1 if data_max != 0 else 1.0
                    
                    # Only update if range has changed significantly (more than 10% change)
                    if band_idx in self._y_ranges:
                        old_min, old_max = self._y_ranges[band_idx]
                        old_range = old_max - old_min
                        new_range = new_max - new_min
                        
                        # Check if min or max changed significantly
                        min_change = abs(new_min - old_min) / max(abs(old_range), 1e-10)
                        max_change = abs(new_max - old_max) / max(abs(old_range), 1e-10)
                        
                        if min_change > 0.1 or max_change > 0.1 or old_range == 0:
                            # Significant change, update the range
                            self._plot_widgets[band_idx].setYRange(new_min, new_max)
                            self._y_ranges[band_idx] = (new_min, new_max)
                    else:
                        # First time, set the range
                        self._plot_widgets[band_idx].setYRange(new_min, new_max)
                        self._y_ranges[band_idx] = (new_min, new_max)

    # ------------------------------ #
    # Properties
    # ------------------------------ #

    @property
    def filter_order(self):
        return self._filter_order

    @filter_order.setter
    def filter_order(self, value):
        self._filter_order = max(1, int(value))
        self._filter_cache = {}  # Invalidate cache

    @property
    def n_bootstrap(self):
        return self._n_bootstrap

    @n_bootstrap.setter
    def n_bootstrap(self, value):
        self._n_bootstrap = max(10, int(value))

    @property
    def baseline_start(self):
        return self._baseline_start

    @baseline_start.setter
    def baseline_start(self, value):
        self._baseline_start = value

    @property
    def baseline_end(self):
        return self._baseline_end

    @baseline_end.setter
    def baseline_end(self, value):
        self._baseline_end = value

    @property
    def show_confidence(self):
        return self._show_confidence

    @show_confidence.setter
    def show_confidence(self, value):
        self._show_confidence = value
        self.reset_renderer(reset_channel_labels=False)

    @property
    def line_width(self):
        return self._line_width

    @line_width.setter
    def line_width(self, value):
        self._line_width = value
        self.reset_renderer(reset_channel_labels=False)

    @property
    def antialias(self):
        return self._antialias

    @antialias.setter
    def antialias(self, value):
        self._antialias = value
        self.reset_renderer(reset_channel_labels=False)

