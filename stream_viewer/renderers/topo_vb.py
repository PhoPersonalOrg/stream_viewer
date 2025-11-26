#  Copyright (C) 2014-2021 Syntrogi Inc dba Intheon. All rights reserved.

import numpy as np
from qtpy import QtCore
from visbrain.objects import TopoObj
from visbrain.utils import array2colormap, color2vb
from stream_viewer.renderers.data.base import RendererMergeDataSources
from stream_viewer.renderers.display.visbrain import VisbrainRenderer
import logging

# -----------------------------------------------------------------------------
# SciPy 1.14 removed interp2d which visbrain TopoObj uses in set_data via
# self._grid_interpolation. Patch TopoObj.set_data to avoid calling the
# interp2d-based path so Topo plots still work without SciPy pinning.
# -----------------------------------------------------------------------------
def _patch_visbrain_topo_set_data():
    try:
        # Avoid double patching
        if getattr(TopoObj, "_sv_set_data_patched", False):
            return

        def _safe_set_data(self, data, levels=None, level_colors='white', cmap='viridis',
                           clim=None, vmin=None, under='gray', vmax=None, over='red'):
            # Based on visbrain TopoObj.set_data, but without grid upsampling
            # that uses interp2d. We keep griddata and color mapping.
            xyz = self._xyz[self._keeponly]
            channels = list(np.array(self._channels)[self._keeponly])
            data = np.asarray(data, dtype=float).ravel()
            if len(data) == len(self):
                data = data[self._keeponly]

            # Channel markers (constant size to avoid dependency on visbrain.normalize)
            radius = np.full(data.shape, 20.0, dtype=float)
            self.chan_markers.set_data(pos=xyz, size=radius, edge_color='black',
                                       face_color=self._chan_mark_color,
                                       symbol=self._chan_mark_symbol)

            # Channel names
            if channels is not None:
                self.chan_text.text = channels
                self.chan_text.pos = xyz

            # Grid from scattered points
            pos_x, pos_y = xyz[:, 0], xyz[:, 1]
            xmin, xmax = pos_x.min(), pos_x.max()
            ymin, ymax = pos_y.min(), pos_y.max()
            xi = np.linspace(xmin, xmax, self._pix)
            yi = np.linspace(ymin, ymax, self._pix)
            xh, yi = np.meshgrid(xi, yi)
            grid = self._griddata(pos_x, pos_y, data, xh, yi)

            # Disc mask (no upsampling/interpolation)
            csize = max(self._pix, grid.shape[0])
            l = csize / 2  # noqa
            y, x = np.ogrid[-l:l, -l:l]
            mask = x ** 2 + y ** 2 < l ** 2
            nmask = np.invert(mask)

            # Colormap
            d_min, d_max = float(np.min(data)), float(np.max(data))
            _clim = (d_min, d_max) if clim is None else clim
            self._update_cbar_args(cmap, _clim, vmin, vmax, under, over)
            grid_color = array2colormap(grid, **self.to_kwargs())
            grid_color[nmask, -1] = 0.0
            self.disc.set_data(grid_color)
            # Note: levels/isocurves omitted for compatibility; not used by this app.

        TopoObj.set_data = _safe_set_data
        TopoObj._sv_set_data_patched = True
    except Exception:
        # If patching fails, we leave original behavior (may error on SciPy>=1.14)
        pass

# Apply the patch at import time
_patch_visbrain_topo_set_data()


logger = logging.getLogger(__name__)


class TopoVB(RendererMergeDataSources, VisbrainRenderer):

    # COMPAT_ICONTROL = ['TopoControlPanel']
    gui_kwargs = dict(VisbrainRenderer.gui_kwargs, **RendererMergeDataSources.gui_kwargs,
                      show_disc_colors=bool, show_head_colors=bool, show_disc_size=bool,
                      disc_size_min=float, disc_size_max=float, auto_color_scale=bool)

    def __init__(self,
                 # Overwrite defaults in RendererFormatData
                 show_chan_labels: bool = True,
                 # New kwargs
                 show_disc_colors: bool = True,
                 show_head_colors: bool = False,
                 show_disc_size: bool = False,
                 disc_size_min: float = 20.,
                 disc_size_max: float = 50.,
                 auto_color_scale: bool = True,
                 **kwargs):
        """
        Topoplot using visbrain.

        Args:
            show_disc_colors: Enable changing the colors of the electrode discs.
            show_head_colors: Enable interpolating coloring of the whole head.
            show_disc_size: Enable growing and shrinking electrode discs.
            disc_size_min: Minimum electrode disc size.
            disc_size_max: Maximum electrode disc size.
            **kwargs:
        """
        self._destroy_obj = True  # For topo plot we always destroy on reset_renderer
        self._b_keep = None
        self._show_disc_colors = show_disc_colors
        self._show_head_colors = show_head_colors
        self._show_disc_size = show_disc_size
        self._disc_size_min = disc_size_min
        self._disc_size_max = disc_size_max
        self._auto_color_scale = auto_color_scale
        self._last_cbar_limits = None
        # Make sure to pass overwritten kwarg defaults to super.
        super().__init__(show_chan_labels=show_chan_labels, **kwargs)
        self.reset_renderer()

    def _build_obj(self):
        # Whether or not a channel will be visualized according to gui widgets and init kwargs
        b_vis = self.chan_states['vis'].values if 'vis' in self.chan_states \
            else np.ones((len(self.chan_states)), dtype=bool)
        n_vis = np.sum(b_vis)
        # Whether or not a remaining (b_vis) channel will be visualized based on it having a known positions
        self._b_keep = np.zeros((n_vis,), dtype=bool)

        # Take a first pass at the channel labels. This may be used to infer channel positions.
        if 'name' in self.chan_states:
            chan_labels = self.chan_states['name'].values
        else:
            chan_labels = np.array([f"Ch{_}" for _ in range(len(self.chan_states))], dtype=object)
        chan_labels = chan_labels[b_vis]

        # Calculated positions
        pos = np.zeros((n_vis, 3))
        if 'pos' in self.chan_states:
            # If chan_states has 'pos', use all non-nan positions.
            vis_pos = self.chan_states.loc[b_vis, 'pos']
            self._b_keep = (~vis_pos.isna()).values
            pos[self._b_keep, :] = np.stack(vis_pos.loc[self._b_keep].values)
        elif 'name' in self.chan_states:
            # Try to guess from channel names.
            pos, self._b_keep = TopoObj._get_coordinates_from_name(chan_labels)
        if not np.any(self._b_keep):
            logger.error("chan_states must contain 'pos' field with coordinates"
                         " or 'name' field with known channel labels.")
            return

        # Build placeholder data the same length as visible channels; TopoObj
        # will internally select valid channels using its own keeponly mask.
        dummy_data = np.zeros((n_vis,))
        if self.show_head_colors:
            dummy_data[:] = (self.lower_limit + self.upper_limit) / 2
            dummy_data[0] = self.lower_limit
            dummy_data[-1] = self.upper_limit
        else:
            dummy_data[:] = self.lower_limit - 1
        line_color = 'black'
        if (isinstance(self.bg_color, str) and self.bg_color == 'black') or\
                (hasattr(self.bg_color, 'rgba') and not np.any(self.bg_color.rgba[:3])):
            line_color = 'white'

        # Important: pass channel names so visbrain derives coordinates in the
        # expected spherical system and applies its transforms. Do NOT pass our
        # precomputed xyz from the template here, or they will be treated as
        # cartesian and collapse along an axis.
        self._obj = TopoObj('topo', dummy_data,
                            line_color=line_color,
                            channels=(chan_labels if self._show_chan_labels else np.full(n_vis, '')),
                            cmap=self.color_set)

    def reset_renderer(self, **kwargs):
        if len(self.chan_states) == 0:
            return
        super().reset_renderer(**kwargs)

        # If the base VisbrainRenderer couldn't build an object (e.g. because
        # there were no valid positions or channel labels), bail out early.
        if self._obj is None:
            logger.warning(
                "TopoVB.reset_renderer: underlying visbrain object is None; "
                "skipping grid preparation and disc setup for this reset."
            )
            return

        # Disable interpolation paths that rely on SciPy interp2d
        if hasattr(self._obj, '_interp'):
            self._obj._interp = None

        self._prepare_grid()

        if not self.show_head_colors:
            # Solid color for the main disc
            grid = np.zeros(self._g_grid.shape[:-1])
            if self._obj._interp is not None:
                grid = self._obj._grid_interpolation(grid)
            bg_color = self.bg_color.rgba if hasattr(self.bg_color, 'rgba') else color2vb(self.bg_color)
            grid_color = grid[:, :, None] + bg_color
            grid_color[self._nmask, -1] = 0.
            self._obj.disc.set_data(grid_color)

    def _prepare_grid(self):
        # Guard against cases where _build_obj failed and did not set self._obj.
        if self._obj is None or not hasattr(self._obj, "_xyz"):
            logger.warning(
                "TopoVB._prepare_grid: self._obj is not fully initialized; "
                "skipping grid computation."
            )
            return

        x, y = self._obj._xyz[:, 0], self._obj._xyz[:, 1]
        xi = np.linspace(x.min(), x.max(), self._obj._pix)
        yi = np.linspace(y.min(), y.max(), self._obj._pix)
        xh, yi = np.meshgrid(xi, yi)

        xy = x.ravel() + y.ravel() * -1j
        d = xy[None, :] * np.ones((len(xy), 1))
        d = np.abs(d - d.T)
        n = d.shape[0]
        d.flat[::n + 1] = 1.

        self._g_chans = (d * d) * (np.log(d) - 1.)
        self._g_chans.flat[::n + 1] = 0.

        xy = xy.T

        d = np.abs((xh - 1j * yi)[..., None] - xy[None, ...])
        b_dzero = d == 0
        d[b_dzero] = 1
        self._g_grid = (d * d) * (np.log(d) - 1)
        self._g_grid[b_dzero] = 0

        g_dim = self._g_grid.shape[0]
        if self._obj._interp is not None:
            tmp = self._obj._grid_interpolation(self._g_grid[..., 0])
            g_dim = tmp.shape[0]

        csize = max(self._obj._pix, g_dim)
        # Variables :
        l = csize / 2  # noqa
        y, x = np.ogrid[-l:l, -l:l]
        mask = x ** 2 + y ** 2 < l ** 2
        self._nmask = np.invert(mask)

    @property
    def native_widget(self):
        return self.sc.canvas.native

    def update_visualization(self, data: np.ndarray, timestamps: np.ndarray):
        # We inherit from RendererMergeDataSources which returns a single source, and it's never markers.
        # timestamps = timestamps[0]
        # data = data[0]
        if timestamps.size == 0:
            return None

        # By the time data gets here, it has already been selected for 'vis' channels.

        data = data[self._b_keep, -1]
        data = data.astype(float).ravel()

        # Auto color scaling to current data range (avoids constant-color markers)
        if self._auto_color_scale and data.size > 0 and np.all(np.isfinite(data)):
            d_min = float(np.min(data))
            d_max = float(np.max(data))
            if not self._last_cbar_limits or (abs(d_min - self._last_cbar_limits[0]) > 1e-9 or
                                              abs(d_max - self._last_cbar_limits[1]) > 1e-9):
                if d_max <= d_min:
                    d_max = d_min + np.finfo(np.float32).eps
                self._obj._update_cbar_args(self.color_set, (d_min, d_max),
                                            None, None, None, None)
                self._last_cbar_limits = (d_min, d_max)

        # Minimal reproduction of self._obj.set_data(data, cmap=self.color_set)

        # Channel Markers - do the minimal work from self._obj.chan_markers.set_data
        if self.show_disc_size:
            # We can't user visbrain normalize because that normalizes to data range,
            # we want to scale so lower_limit:upper_limit is mapped to _disc_size_min:_disc_size_max
            radius = np.clip(data, self.lower_limit, self.upper_limit)
            coef = (self._disc_size_max - self._disc_size_min) / (self.upper_limit - self.lower_limit)
            np.subtract(radius, self.lower_limit, out=radius)
            np.multiply(radius, coef, out=radius)
            np.add(radius, self._disc_size_min, out=radius)
        else:
            radius = np.full(len(data), (self._disc_size_min + self._disc_size_max) / 2 )
        self._obj.chan_markers._data['a_size'] = radius
        self._obj.chan_markers._vbo.set_data(self._obj.chan_markers._data)

        if self.show_disc_colors:
            self._obj.chan_markers._data['a_bg_color'] = array2colormap(x=data, **self._obj.to_kwargs())

        self._obj.chan_markers.update()

        if self.show_head_colors:
            weights = np.linalg.solve(self._g_chans, data.ravel())
            grid = self._g_grid.dot(weights)
            if self._obj._interp is not None:
                grid = self._obj._grid_interpolation(grid)
            grid_color = array2colormap(grid, **self._obj.to_kwargs())
            grid_color[self._nmask, -1] = 0.
            self._obj.disc.set_data(grid_color)

    @property
    def auto_color_scale(self):
        return self._auto_color_scale

    @auto_color_scale.setter
    def auto_color_scale(self, value: bool):
        self._auto_color_scale = bool(value)
        # No reset required; takes effect on next update.

    @property
    def show_disc_colors(self):
        return self._show_disc_colors

    @show_disc_colors.setter
    def show_disc_colors(self, value):
        self._show_disc_colors = value
        self.reset_renderer(reset_channel_labels=True)

    @QtCore.Slot(int)
    def discColor_stateChanged(self, state):
        self.show_disc_colors = state > 0

    @property
    def show_disc_size(self):
        return self._show_disc_size

    @show_disc_size.setter
    def show_disc_size(self, value):
        self._show_disc_size = value
        self.reset_renderer(reset_channel_labels=True)

    @QtCore.Slot(int)
    def discSize_stateChanged(self, state):
        self.show_disc_size = state > 0

    @property
    def show_head_colors(self):
        return self._show_head_colors

    @show_head_colors.setter
    def show_head_colors(self, value):
        self._show_head_colors = value
        self.reset_renderer(reset_channel_labels=True)

    @QtCore.Slot(int)
    def headColor_stateChanged(self, state):
        self.show_head_colors = state > 0

    @property
    def disc_size_min(self):
        return self._disc_size_min

    @disc_size_min.setter
    def disc_size_min(self, value):
        self._disc_size_min = value

    @property
    def disc_size_max(self):
        return self._disc_size_max

    @disc_size_max.setter
    def disc_size_max(self, value):
        self._disc_size_max = value
