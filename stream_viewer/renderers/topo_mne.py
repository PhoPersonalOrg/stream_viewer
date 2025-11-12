from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Dict

import numpy as np
import mne
from mne.channels.montage import DigMontage


# Matplotlib embedding
import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from stream_viewer.renderers.data.base import RendererMergeDataSources
from stream_viewer.renderers.display.matplotlib import MPLRenderer


# Reuse Pho's montage helpers
try:
    # Requires the sibling repo to be available on PYTHONPATH (already a workspace path)
    from phoofflineeeganalysis.analysis.anatomy_and_electrodes import ElectrodeHelper
        
    active_electrode_man: ElectrodeHelper = ElectrodeHelper.init_EpocX_montage()
    emotiv_epocX_montage: DigMontage = active_electrode_man.active_montage

except Exception:  # pragma: no cover
    ElectrodeHelper = None  # type: ignore[assignment]



class TopoMNE(RendererMergeDataSources, MPLRenderer):
    """
    MNE-based head/sensor view, structured consistently with other visualizers.
    """

    # Keep GUI consistency with other renderers
    gui_kwargs = dict(MPLRenderer.gui_kwargs, **RendererMergeDataSources.gui_kwargs,
                      montage_path=str, view_kind=str, show_axes=bool)

    def __init__(self,
                 show_chan_labels: bool = True,
                 montage_path: Optional[str] = None,
                 view_kind: str = "3d",
                 show_axes: bool = True,
                 **kwargs):
        """
        Args:
            show_chan_labels: Show channel labels on the plot (where supported).
            montage_path: Optional path to electrode positions file (.tsv recommended).
            view_kind: '3d' (default) or 'top' for 2D sensor view.
            show_axes: Show axes in the Matplotlib figure.
            **kwargs: Standard renderer kwargs.
        """
        self._destroy_obj = True
        self._montage_path = Path(montage_path).expanduser().resolve() if montage_path else None
        self._view_kind = view_kind
        self._show_axes = show_axes
        self._visible_labels: Optional[np.ndarray] = None
        self._montage: Optional[mne.channels.DigMontage] = None
        super().__init__(show_chan_labels=show_chan_labels, **kwargs)
        self.reset_renderer()

    # -------------------- Montage building -------------------- #
    @staticmethod
    def _build_montage_from_path(electrode_positions_path: Path) -> mne.channels.DigMontage:
        if ElectrodeHelper is None:
            raise RuntimeError("phoofflineeeganalysis not available; required for montage building.")

        if electrode_positions_path.suffix.lower() == ".tsv":
            return ElectrodeHelper.montage_from_subjece_space_mm_tsv(electrode_positions_path)

        if hasattr(ElectrodeHelper, "create_complete_montage_workflow"):
            return ElectrodeHelper.create_complete_montage_workflow(electrode_positions_path)  # type: ignore[attr-defined]

        helper = ElectrodeHelper.init_EpocX_montage(electrode_positions_path)
        return helper.active_montage

    @staticmethod
    def _default_montage() -> mne.channels.DigMontage:
        if ElectrodeHelper is None:
            raise RuntimeError("phoofflineeeganalysis not available; required for default montage.")
        helper = ElectrodeHelper.init_EpocX_montage()
        return helper.active_montage

    def _compute_visible_labels(self) -> np.ndarray:
        if 'name' in self.chan_states:
            labels = self.chan_states['name'].values
        else:
            labels = np.array([f"Ch{_}" for _ in range(len(self.chan_states))], dtype=object)
        if 'vis' in self.chan_states:
            labels = labels[self.chan_states['vis'].values]
        return labels

    # -------------------- Rendering lifecycle -------------------- #
    def reset_renderer(self, reset_channel_labels=True):
        if len(self.chan_states) == 0:
            return

        # Resolve montage
        try:
            if self._montage_path is not None:
                assert self._montage_path.exists(), f"{self._montage_path} not found"
                montage = self._build_montage_from_path(self._montage_path)
            else:
                montage = self._default_montage()
        except Exception:
            # If montage build fails, create an empty figure to avoid crashing UI
            montage = None

        self._montage = montage
        self._visible_labels = self._compute_visible_labels()

        # Build a figure
        fig = Figure(figsize=(6, 6), facecolor=self._mpl_facecolor_from_str(self.bg_color))
        ax = fig.add_subplot(111, projection=None)
        ax.axis("on" if self._show_axes else "off")
        ax.set_aspect("equal")

        # If montage available, draw using MNE helper; otherwise draw placeholder text
        if self._montage is not None:
            # Filter montage channels to visible ones if possible
            try:
                ch_pos: Dict[str, Sequence[float]] = dict(self._montage.get_positions()["ch_pos"] or {})
                if ch_pos and self._visible_labels is not None:
                    ch_pos = {k: v for k, v in ch_pos.items() if k in set(self._visible_labels.tolist())}
                    filtered = mne.channels.make_dig_montage(ch_pos=ch_pos,
                                                             nasion=self._montage.nasion,
                                                             lpa=self._montage.lpa,
                                                             rpa=self._montage.rpa,
                                                             coord_frame="head")
                else:
                    filtered = self._montage
            except Exception:
                filtered = self._montage

            # Use MNE's montage plotting on our axes
            try:
                # mne defaults to creating its own fig; instead, plot onto our axes when possible
                # Fallback to standard montage.plot if ax-based plotting is not provided
                _ = filtered.plot(kind=self._view_kind, show=False)
                # Transfer artists onto our figure by drawing the returned figure onto canvas as an image
                # Simpler: close the temp fig and re-call onto our fig if method exists
                try:
                    matplotlib.pyplot.close(_)
                except Exception:
                    pass
                # Draw simple 2D sensor scatter as a fallback that respects visible labels
                pos = filtered.get_positions()
                ch_xy = []
                ch_names = []
                for name, xyz in (pos["ch_pos"] or {}).items():
                    # Simple orthographic projection to XY (meters)
                    ch_xy.append([xyz[0], xyz[1]])
                    ch_names.append(name)
                if len(ch_xy) > 0:
                    ch_xy = np.asarray(ch_xy, dtype=float)
                    ax.scatter(ch_xy[:, 0], ch_xy[:, 1], c="w", s=60, edgecolors="k", zorder=3)
                    if self.show_chan_labels:
                        for i, nm in enumerate(ch_names):
                            ax.text(ch_xy[i, 0], ch_xy[i, 1], nm, color="w", fontsize=9,
                                    ha="left", va="center")
                    ax.set_title("MNE Montage (XY projection)")
                    ax.set_xlabel("X (m)")
                    ax.set_ylabel("Y (m)")
                    # Head circle hint
                    r = max(np.linalg.norm(ch_xy, axis=1).max(), 0.09)
                    circ = matplotlib.patches.Circle((0, 0), r, fill=False, color="w", alpha=0.3, lw=1.0, zorder=1)
                    ax.add_patch(circ)
                    ax.set_xlim(-r * 1.1, r * 1.1)
                    ax.set_ylim(-r * 1.1, r * 1.1)
                    ax.invert_yaxis()  # match common head-top plotting convention
                else:
                    ax.text(0.5, 0.5, "No channel positions", color="w", ha="center", va="center",
                            transform=ax.transAxes)
            except Exception:
                ax.text(0.5, 0.5, "Failed to plot montage", color="w", ha="center", va="center",
                        transform=ax.transAxes)
        else:
            ax.text(0.5, 0.5, "Montage not available", color="w", ha="center", va="center",
                    transform=ax.transAxes)

        # Replace canvas in container
        if self._canvas is not None:
            self._layout.removeWidget(self._canvas)
            self._canvas.setParent(None)
            self._canvas.deleteLater()
            self._canvas = None
        self._canvas = FigureCanvas(fig)
        self._layout.addWidget(self._canvas)
        self._canvas.draw_idle()

    def update_visualization(self, data: np.ndarray, timestamps: np.ndarray):
        # Static montage view; no per-sample updates required.
        return None

    # -------------------- Properties exposed via Widgets -------------------- #
    @property
    def montage_path(self) -> Optional[str]:
        return None if self._montage_path is None else str(self._montage_path)

    @montage_path.setter
    def montage_path(self, value: Optional[str]):
        self._montage_path = Path(value).expanduser().resolve() if value else None
        self.reset_renderer(reset_channel_labels=True)

    @property
    def view_kind(self) -> str:
        return self._view_kind

    @view_kind.setter
    def view_kind(self, value: str):
        self._view_kind = value
        self.reset_renderer(reset_channel_labels=False)

    @property
    def show_axes(self) -> bool:
        return self._show_axes

    @show_axes.setter
    def show_axes(self, value: bool):
        self._show_axes = value
        self.reset_renderer(reset_channel_labels=False)

