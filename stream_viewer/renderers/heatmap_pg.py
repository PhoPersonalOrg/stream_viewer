from collections import deque, namedtuple
import json
import numpy as np
from qtpy import QtGui
import pyqtgraph as pg
from scipy import signal
from stream_viewer.renderers.data.base import RendererDataTimeSeries
from stream_viewer.renderers.display.pyqtgraph import PGRenderer


MarkerMap = namedtuple('MarkerMap', ['source_id', 'timestamp', 'item'])


class HeatmapPG(RendererDataTimeSeries, PGRenderer):
    """
    Pyqtgraph-based 2D spectrogram (heatmap) renderer analogous to LinePG, rendering one
    averaged-across-channels spectrogram per data source. Supports Sweep and Scroll modes.
    """
    plot_modes = ["Sweep", "Scroll"]
    gui_kwargs = dict(
        RendererDataTimeSeries.gui_kwargs,
        **PGRenderer.gui_kwargs,
        ylabel_as_title=bool,
        ylabel_width=int,
        ylabel=str,
        fmin_hz=float,
        fmax_hz=float,
        nperseg=int,
        noverlap=int,
    )

    def __init__(self,
                 # inherited/overrides
                 auto_scale: str = 'none',
                 show_chan_labels: bool = True,
                 color_set: str = 'viridis',
                 # new
                 ylabel_as_title: bool = False,
                 ylabel_width: int = None,
                 ylabel: str = None,
                 fmin_hz: float = 1.0,
                 fmax_hz: float = 40.0,
                 nperseg: int = 256,
                 noverlap: int = 128,
                 **kwargs):
        self._ylabel_as_title = ylabel_as_title
        self._ylabel_width = ylabel_width
        self._ylabel = ylabel
        self._requested_auto_scale = auto_scale.lower()

        # spectrogram parameters
        self._fmin_hz = float(fmin_hz)
        self._fmax_hz = float(fmax_hz)
        self._nperseg = int(nperseg)
        self._noverlap = int(noverlap)

        self._widget = pg.GraphicsLayoutWidget()
        self._do_yaxis_sync = False
        self._src_last_marker_time = []
        self._marker_texts_pool = deque()
        self._marker_info = deque()
        self._t_expired = -np.inf
        self._image_items = []

        super().__init__(show_chan_labels=show_chan_labels, color_set=color_set, **kwargs)
        self.reset_renderer()

    # ------------------------------ #
    # Lifecycle / layout
    # ------------------------------ #
    def reset_renderer(self, reset_channel_labels=True):
        self._widget.clear()
        self._widget.setBackground(self.parse_color_str(self.bg_color))
        self._src_last_marker_time = [-np.inf for _ in range(len(self._data_sources))]
        self._image_items = []

        if len(self.chan_states) == 0:
            return

        labelStyle = {'color': '#FFF', 'font-size': str(self.font_size) + 'pt'}

        # Requested auto-scale maps to actual behavior; for heatmaps, pyqtgraph levels handle scaling
        if self._requested_auto_scale == 'all':
            self._auto_scale = 'none'
        else:
            self._auto_scale = self._requested_auto_scale

        row_offset = -1
        last_row = 0
        for src_ix, src in enumerate(self._data_sources):
            ch_states = self.chan_states[self.chan_states['src'] == src.identifier]
            n_vis_src = ch_states['vis'].sum()
            if n_vis_src == 0:
                continue

            row_offset += 1
            pw = self._widget.addPlot(row=row_offset, col=0, antialias=True)
            last_row = row_offset
            pw.showGrid(x=True, y=True, alpha=0.3)

            font = QtGui.QFont()
            font.setPointSize(self.font_size - 2)
            pw.setXRange(0, self.duration)
            pw.getAxis("bottom").setTickFont(font)
            pw.getAxis("bottom").setStyle(showValues=self.ylabel_as_title)

            yax = pw.getAxis('left')
            yax.setTickFont(font)
            stream_ylabel = json.loads(src.identifier)['name']
            if 'unit' in ch_states and ch_states['unit'].nunique() == 1:
                stream_ylabel = stream_ylabel + ' (%s)' % ch_states['unit'].iloc[0]
            pw.setLabel('top' if self.ylabel_as_title else 'left', self._ylabel or stream_ylabel, **labelStyle)
            if self.ylabel_as_title:
                pw.getAxis("top").setStyle(showValues=False)

            # Create the image item for spectrogram; attach color LUT later on first update
            img = pg.ImageItem(axisOrder='row-major')
            pw.addItem(img)
            self._image_items.append(img)

            # Y axis range (frequency)
            pw.setYRange(self._fmin_hz, self._fmax_hz)

        # Bottom axis label and link x-axes
        bottom_pw = self._widget.getItem(last_row, 0)
        if bottom_pw is not None:
            bottom_pw.setLabel('bottom', 'Time', units='s', **labelStyle)
            bottom_pw.getAxis("bottom").setStyle(showValues=True)
            for row_ix in range(last_row):
                pw = self._widget.getItem(row_ix, 0)
                if pw is None:
                    break
                pw.setXLink(bottom_pw)

        self._widget.ci.setSpacing(10. if self.ylabel_as_title else 0.)
        self._do_yaxis_sync = True

    def sync_y_axes(self):
        max_width = self._ylabel_width or 0.
        for src_ix in range(len(self._data_sources)):
            pw = self._widget.getItem(src_ix, 0)
            if pw is None:
                break
            yax = pw.getAxis('left')
            max_width = max(max_width, yax.minimumWidth())

        for src_ix in range(len(self._data_sources)):
            pw = self._widget.getItem(src_ix, 0)
            if pw is None:
                break
            pw.getAxis('left').setWidth(max_width)
        self._do_yaxis_sync = False

    # ------------------------------ #
    # Update loop
    # ------------------------------ #
    def update_visualization(self, data: np.ndarray, timestamps: np.ndarray) -> None:
        if not any([np.any(_) for _ in timestamps[0]]):
            return

        # Prepare LUT for heatmap colors (once)
        lut = self.get_colormap(self.color_set, 256)

        for src_ix in range(len(data)):
            pw = self._widget.getItem(src_ix, 0)
            if pw is None:
                return

            dat, mrk = data[src_ix]
            ts, mrk_ts = timestamps[src_ix]

            # Align axis label widths if needed
            if self._do_yaxis_sync:
                self.sync_y_axes()

            # Spectrogram from buffered latest window
            if self._buffers[src_ix]._data.size:
                # Average across visible channels (ignore NaNs)
                buff_data = self._buffers[src_ix]._data
                if buff_data.size == 0 or buff_data.shape[1] == 0:
                    x = np.array([], dtype=float)
                else:
                    x = np.nanmean(buff_data, axis=0)
                    x = np.nan_to_num(x, nan=0.0)

                # Need a valid sampling rate
                srate = self._data_sources[src_ix].data_stats.get('srate', 0.0) or 0.0
                if srate <= 0.0:
                    # Cannot compute proper spectrogram without a rate; skip
                    pass
                else:
                    nperseg = max(8, min(self._nperseg, x.size))
                    noverlap = max(0, min(self._noverlap, nperseg - 1))
                    try:
                        f, t, Sxx = signal.spectrogram(
                            x, fs=float(srate), nperseg=int(nperseg), noverlap=int(noverlap),
                            scaling='density', mode='psd'
                        )
                    except Exception:
                        f, t, Sxx = np.array([]), np.array([]), np.array([[]])

                    if Sxx.size:
                        # Convert to dB
                        Pxx = 10.0 * np.log10(Sxx + 1e-12)
                        # Crop frequency range
                        f_mask = (f >= float(self._fmin_hz)) & (f <= float(self._fmax_hz))
                        if np.any(f_mask):
                            f_use = f[f_mask]
                            P_use = Pxx[f_mask, :]
                        else:
                            f_use, P_use = f, Pxx

                        # Map to [0, duration] seconds for current window
                        # Use the buffer tvec to compute relative time if available; else normalize t
                        if self._buffers[src_ix]._tvec.size:
                            t0 = self._buffers[src_ix]._tvec[0]
                            t1 = self._buffers[src_ix]._tvec[-1]
                            dur = max(1e-6, (t1 - t0))
                            # Stretch t to 0..duration based on actual window duration; clamp to configured duration
                            t_scale = (t / max(np.max(t), 1e-6)) * min(self.duration, dur)
                            t_use = t_scale
                        else:
                            # Normalize spectrogram internal time to 0..duration
                            t_norm = (t - (t[0] if len(t) else 0.0))
                            t_use = (t_norm / max(t_norm[-1], 1e-6)) * self.duration if len(t_norm) else t_norm

                        # Compute explicit levels for float image types
                        if self._auto_scale != 'none':
                            vmin = np.nanmin(P_use) if P_use.size else -120.0
                            vmax = np.nanmax(P_use) if P_use.size else 0.0
                            if not np.isfinite(vmin) or not np.isfinite(vmax) or (vmax <= vmin):
                                vmin, vmax = -120.0, 0.0
                        else:
                            # Use renderer limits as dB levels when auto_scale == 'none'
                            vmin, vmax = float(self.lower_limit), float(self.upper_limit)
                            if not np.isfinite(vmin) or not np.isfinite(vmax) or (vmax <= vmin):
                                vmin, vmax = -120.0, 0.0

                        # Update image
                        img = self._image_items[src_ix]
                        img.setImage(P_use, levels=(float(vmin), float(vmax)), autoLevels=False)
                        img.setLookupTable(lut)
                        # Rect maps image to plot coordinates: (x, y, w, h)
                        img.setRect(pg.QtCore.QRectF(0.0, float(self._fmin_hz),
                                                     float(self.duration),
                                                     float(self._fmax_hz - self._fmin_hz)))

            # Update expiry threshold
            if not self._buffers[src_ix]._tvec.size:
                continue
            lead_t = self._buffers[src_ix]._tvec[self._buffers[src_ix]._write_idx]
            self._t_expired = max(lead_t - self._duration, self._t_expired)

            # Remove expired markers
            if isinstance(pw.items[-1], pg.TextItem):
                while (len(self._marker_info) > 0) and (self._marker_info[0].timestamp < self._t_expired):
                    pop_info = self._marker_info.popleft()
                    pw.removeItem(pop_info[2])
                    self._marker_texts_pool.append(pop_info[2])

            # Add new markers
            if mrk.size:
                b_new = mrk_ts > self._src_last_marker_time[src_ix]
                for _t, _m in zip(mrk_ts[b_new], mrk[b_new]):
                    if len(self._marker_texts_pool) > 0:
                        text = self._marker_texts_pool.popleft()
                        text.setText(_m)
                    else:
                        text = pg.TextItem(text=_m, angle=90)
                        font = QtGui.QFont()
                        font.setPointSize(self.font_size + 2.0)
                        text.setFont(font)

                    # Place at bottom of frequency range
                    text.setPos((_t % self.duration), float(self._fmin_hz))
                    pw.addItem(text)
                    self._marker_info.append(MarkerMap(src_ix, _t, text))

                if np.any(b_new):
                    self._src_last_marker_time[src_ix] = mrk_ts[b_new][-1]

    # ------------------------------ #
    # Properties
    # ------------------------------ #
    @property
    def ylabel_as_title(self):
        return self._ylabel_as_title

    @ylabel_as_title.setter
    def ylabel_as_title(self, value):
        self._ylabel_as_title = value
        self.reset_renderer(reset_channel_labels=True)

    @property
    def ylabel_width(self):
        return self._ylabel_width

    @ylabel_width.setter
    def ylabel_width(self, value):
        self._ylabel_width = value
        self.reset_renderer(reset_channel_labels=True)

    @property
    def fmin_hz(self):
        return self._fmin_hz

    @fmin_hz.setter
    def fmin_hz(self, value):
        self._fmin_hz = float(value)
        self.reset_renderer(reset_channel_labels=False)

    @property
    def fmax_hz(self):
        return self._fmax_hz

    @fmax_hz.setter
    def fmax_hz(self, value):
        self._fmax_hz = float(value)
        self.reset_renderer(reset_channel_labels=False)

    @property
    def nperseg(self):
        return self._nperseg

    @nperseg.setter
    def nperseg(self, value):
        self._nperseg = int(value)
        self.reset_renderer(reset_channel_labels=False)

    @property
    def noverlap(self):
        return self._noverlap

    @noverlap.setter
    def noverlap(self, value):
        self._noverlap = int(value)
        self.reset_renderer(reset_channel_labels=False)

    @RendererDataTimeSeries.auto_scale.setter
    def auto_scale(self, value):
        self._requested_auto_scale = value.lower()
        self.reset_renderer(reset_channel_labels=False)


