from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Dict, Tuple

import numpy as np
import mne
from mne.channels.montage import DigMontage
import logging

from stream_viewer.renderers.data.base import RendererMergeDataSources
from stream_viewer.renderers.display.pyvista import PyVistaRenderer

logger = logging.getLogger(__name__)

# Reuse Pho's montage helpers
try:
    # Requires the sibling repo to be available on PYTHONPATH (already a workspace path)
    from phopymnehelper.anatomy_and_electrodes import ElectrodeHelper
    active_electrode_man: ElectrodeHelper = ElectrodeHelper.init_EpocX_montage()
    emotiv_epocX_montage: DigMontage = active_electrode_man.active_montage

except Exception:  # pragma: no cover
    ElectrodeHelper = None  # type: ignore[assignment]

try:
    import pyvista as pv
    import pyvistaqt as pvqt
    PYVISTA_AVAILABLE = True
except ImportError:
    PYVISTA_AVAILABLE = False
    pv = None
    pvqt = None


# Default head mesh path from notebook
# DEFAULT_HEAD_MESH_PATH = Path(r"C:/Users/pho/repos/EmotivEpoc/PhoOfflineEEGAnalysis/src/phoofflineeeganalysis/resources/ElectrodeLayouts/head_bem_1922V_fill.stl")
DEFAULT_HEAD_MESH_PATH = Path(r"C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/resources/ElectrodeLayouts/simplified/head_bem_1922V_fill_fixed.stl")
DEFAULT_ELECTRODE_LAYOUT = Path(r"C:/Users/pho/repos/EmotivEpoc/ACTIVE_DEV/PhoPyMNEHelper/src/phopymnehelper/resources/ElectrodeLayouts/brainstorm_electrode_positions_PhoHAle_eeg_subjectspacemm.tsv")

class TopoMNE(RendererMergeDataSources, PyVistaRenderer):
    """
    MNE-based 3D head mesh visualization with PyVista, structured consistently with other visualizers.
    Displays a 3D head mesh with electrode positions and supports real-time data updates.
    """

    COMPAT_ICONTROL = ['TopoMNEControlPanel']
    gui_kwargs = dict(PyVistaRenderer.gui_kwargs, **RendererMergeDataSources.gui_kwargs,
                      montage_path=str, head_mesh_path=str, mesh_opacity=float,
                      cone_radius=float, cone_height=float, show_labels=bool,
                      electrode_offset_y=float, electrode_offset_z=float)

    def __init__(self,
                 show_chan_labels: bool = True,
                 montage_path: Optional[str] = None,
                 head_mesh_path: Optional[str] = None,
                 mesh_opacity: float = 0.9,
                 cone_radius: float = 0.005,
                 cone_height: float = 0.01,
                 show_labels: bool = True,
                 electrode_offset_y: float = -0.04,
                 electrode_offset_z: float = 0.052,
                 **kwargs):
        """
        Args:
            show_chan_labels: Show channel labels on the plot.
            montage_path: Optional path to electrode positions file (.tsv recommended).
            head_mesh_path: Path to STL head mesh file. Defaults to built-in path if None.
            mesh_opacity: Opacity of the head mesh (0.0 to 1.0).
            cone_radius: Radius of electrode cone glyphs in meters.
            cone_height: Height of electrode cone glyphs in meters.
            show_labels: Show text labels for electrode names.
            electrode_offset_y: Y-axis offset for electrode positions (meters).
            electrode_offset_z: Z-axis offset for electrode positions (meters).
            **kwargs: Standard renderer kwargs.
        """
        if not PYVISTA_AVAILABLE:
            raise RuntimeError("pyvista and pyvistaqt are required for TopoMNE")
        
        self._destroy_obj = True
        self._montage_path = Path(montage_path).expanduser().resolve() if montage_path else DEFAULT_ELECTRODE_LAYOUT
        self._head_mesh_path = Path(head_mesh_path).expanduser().resolve() if head_mesh_path else DEFAULT_HEAD_MESH_PATH
        self._mesh_opacity = mesh_opacity
        self._cone_radius = cone_radius
        self._cone_height = cone_height
        self._show_labels = show_labels
        self._electrode_offset_y = electrode_offset_y
        self._electrode_offset_z = electrode_offset_z
        
        self._visible_labels: Optional[np.ndarray] = None
        self._montage: Optional[mne.channels.DigMontage] = None
        self._head_mesh: Optional[pv.PolyData] = None
        self._electrode_points: Optional[np.ndarray] = None
        self._electrode_names: Optional[list] = None
        self._nearest_points: Optional[np.ndarray] = None
        self._normals: Optional[np.ndarray] = None
        self._mesh_actor = None
        self._electrode_actor = None
        self._label_actors = []
        self._b_keep: Optional[np.ndarray] = None
        
        super().__init__(show_chan_labels=show_chan_labels, **kwargs)
        self.reset_renderer()

    # -------------------- Montage building -------------------- #
    @staticmethod
    def _build_montage_from_path(electrode_positions_path: Path) -> mne.channels.DigMontage:
        if ElectrodeHelper is None:
            raise RuntimeError("phopymnehelper not available; required for montage building.")

        if electrode_positions_path.suffix.lower() == ".tsv":
            return ElectrodeHelper.montage_from_subjece_space_mm_tsv(electrode_positions_path)

        if hasattr(ElectrodeHelper, "create_complete_montage_workflow"):
            return ElectrodeHelper.create_complete_montage_workflow(electrode_positions_path)  # type: ignore[attr-defined]

        helper = ElectrodeHelper.init_EpocX_montage(electrode_positions_path)
        return helper.active_montage

    @staticmethod
    def _default_montage() -> mne.channels.DigMontage:
        if ElectrodeHelper is None:
            raise RuntimeError("phopymnehelper not available; required for default montage.")
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

    def _load_and_prepare_head_mesh(self) -> Optional[pv.PolyData]:
        """Load STL mesh, scale from mm to m if needed, and center at origin."""
        try:
            if not self._head_mesh_path.exists():
                logger.warning(f"Head mesh path does not exist: {self._head_mesh_path}")
                return None
            
            mesh = pv.read(str(self._head_mesh_path))
            logger.info(f"Loaded STL mesh with {mesh.n_points} vertices and {mesh.n_cells} faces.")
            
            # Convert from mm → m if needed
            if np.max(np.abs(mesh.points)) > 0.1:  # heuristic threshold
                mesh.points *= 1e-3
                logger.info("Scaled mesh from mm to meters")
            
            # Center mesh at origin
            mesh_center = mesh.center
            mesh.translate(-np.array(mesh_center), inplace=True)
            logger.info(f"Mesh centered at origin (shifted by {-np.array(mesh_center)})")
            
            # Compute normals for finding electrode surface points
            mesh = mesh.compute_normals(point_normals=True, cell_normals=False, consistent_normals=True)
            
            return mesh
        except Exception as e:
            logger.error(f"Failed to load head mesh: {e}")
            return None

    def _compute_electrode_surface_points(self, electrode_points: np.ndarray, mesh: pv.PolyData) -> Tuple[np.ndarray, np.ndarray]:
        """Find nearest surface points and normals for each electrode."""
        nearest_points = np.zeros_like(electrode_points)
        normals = np.zeros_like(electrode_points)
        
        for i, electrode_point in enumerate(electrode_points):
            # Find closest vertex on mesh
            closest_vertex_idx = mesh.find_closest_point(electrode_point)
            closest_point = mesh.points[closest_vertex_idx]
            
            # Get normal at the closest vertex
            normal = mesh.point_normals[closest_vertex_idx]
            
            nearest_points[i] = closest_point
            normals[i] = normal
        
        return nearest_points, normals

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
        except Exception as e:
            logger.warning(f"Failed to build montage: {e}")
            montage = None

        self._montage = montage
        self._visible_labels = self._compute_visible_labels()

        # Load head mesh
        self._head_mesh = self._load_and_prepare_head_mesh()

        # Get electrode positions from montage
        if self._montage is not None:
            try:
                ch_pos: Dict[str, Sequence[float]] = dict(self._montage.get_positions()["ch_pos"] or {})
                if ch_pos and self._visible_labels is not None:
                    # Filter to visible channels
                    visible_set = set(self._visible_labels.tolist())
                    ch_pos = {k: v for k, v in ch_pos.items() if k in visible_set}
                
                if ch_pos:
                    electrode_points = np.array(list(ch_pos.values()))
                    electrode_names = list(ch_pos.keys())
                    
                    # Apply offsets (from notebook)
                    electrode_points[:, 1] += self._electrode_offset_y
                    electrode_points[:, 2] += self._electrode_offset_z
                    
                    self._electrode_points = electrode_points
                    self._electrode_names = electrode_names
                    self._b_keep = np.ones(len(electrode_points), dtype=bool)
                else:
                    self._electrode_points = None
                    self._electrode_names = None
                    self._b_keep = None
            except Exception as e:
                logger.warning(f"Failed to extract electrode positions: {e}")
                self._electrode_points = None
                self._electrode_names = None
                self._b_keep = None
        else:
            self._electrode_points = None
            self._electrode_names = None
            self._b_keep = None

        # Compute nearest surface points if we have both mesh and electrodes
        if self._head_mesh is not None and self._electrode_points is not None:
            self._nearest_points, self._normals = self._compute_electrode_surface_points(
                self._electrode_points, self._head_mesh)
        else:
            self._nearest_points = None
            self._normals = None

        # Create or update PyVista plotter
        if self._plotter is None:
            # Create new plotter - BackgroundPlotter creates its own window by default
            # We need to embed it in our layout
            self._plotter = pvqt.BackgroundPlotter(show=False, auto_update=False)
            # Get the Qt widget from the plotter and add to layout
            plotter_widget = self._plotter.interactor
            if plotter_widget is not None:
                # Remove any existing widget from layout first
                while self._layout.count():
                    item = self._layout.takeAt(0)
                    if item.widget():
                        item.widget().setParent(None)
                self._layout.addWidget(plotter_widget)
        else:
            # Clear existing actors but keep plotter
            self._plotter.clear()
            self._label_actors = []
        
        # Set background color
        bg_rgb = self._pyvista_color_from_str(self.bg_color)
        self._plotter.set_background(bg_rgb)
        self._plotter.show_axes()

        # Add head mesh
        if self._head_mesh is not None:
            self._mesh_actor = self._plotter.add_mesh(
                self._head_mesh,
                color='lightgray',
                opacity=self._mesh_opacity,
                show_edges=False
            )
        else:
            # Show placeholder text
            self._plotter.add_text("Head mesh not available", font_size=12, color='white')

        # Add electrode glyphs
        if self._nearest_points is not None and self._normals is not None:
            # Create PolyData with points and normals
            electrode_glyphs = pv.PolyData(self._nearest_points)
            electrode_glyphs['normals'] = self._normals
            
            # Create cone glyphs oriented along normals
            cone = pv.Cone(radius=self._cone_radius, height=self._cone_height, resolution=8)
            self._electrode_actor = self._plotter.add_mesh(
                electrode_glyphs.glyph(orient='normals', scale=False, factor=1.0, geom=cone),
                color='red',
                show_edges=False
            )
            
            # Add text labels
            if self._show_labels and self._electrode_names is not None:
                self._label_actors = []
                for i, name in enumerate(self._electrode_names):
                    label_actor = self._plotter.add_point_labels(
                        self._nearest_points[i:i+1],
                        [name],
                        font_size=10,
                        text_color='black',
                        point_color='red',
                        always_visible=True,
                        shape_opacity=0.0
                    )
                    self._label_actors.append(label_actor)
        elif self._electrode_points is not None:
            # Electrodes available but no mesh - show at original positions
            electrode_glyphs = pv.PolyData(self._electrode_points)
            cone = pv.Cone(radius=self._cone_radius, height=self._cone_height, resolution=8)
            self._electrode_actor = self._plotter.add_mesh(
                electrode_glyphs.glyph(scale=False, factor=1.0, geom=cone),
                color='red',
                show_edges=False
            )

    def update_visualization(self, data: np.ndarray, timestamps: np.ndarray):
        """Update electrode colors based on incoming data values."""
        if timestamps.size == 0 or self._electrode_actor is None or self._b_keep is None:
            return None

        # Filter data to visible electrodes
        data = data[self._b_keep, -1]
        data = data.astype(float).ravel()

        if data.size == 0 or not np.all(np.isfinite(data)):
            return None

        # Map data values to colors using matplotlib colormap
        try:
            import matplotlib.pyplot as plt
            import matplotlib.colors as mcolors
            
            # Normalize data to [0, 1] range based on lower/upper limits
            range_val = self.upper_limit - self.lower_limit
            if range_val <= 0:
                range_val = 1.0
            data_normalized = np.clip(
                (data - self.lower_limit) / range_val,
                0.0, 1.0
            )
            
            # Get colormap - try to use color_set, fallback to viridis
            try:
                if hasattr(plt.cm, self.color_set):
                    cmap = plt.get_cmap(self.color_set)
                else:
                    cmap = plt.get_cmap('viridis')
            except Exception:
                cmap = plt.get_cmap('viridis')
            
            # Map normalized values to colors (RGBA, 0-1 range)
            colors = cmap(data_normalized)
            
            # Convert to RGB for PyVista (drop alpha, use 0-1 range)
            colors_rgb = colors[:, :3]
            
            # Update electrode actor colors
            if self._nearest_points is not None:
                electrode_glyphs = pv.PolyData(self._nearest_points)
                electrode_glyphs['normals'] = self._normals
                electrode_glyphs['colors'] = (colors_rgb * 255).astype(np.uint8)
                
                cone = pv.Cone(radius=self._cone_radius, height=self._cone_height, resolution=8)
                
                # Remove old actor and add new one with colors
                self._plotter.remove_actor(self._electrode_actor)
                self._electrode_actor = self._plotter.add_mesh(
                    electrode_glyphs.glyph(orient='normals', scale=False, factor=1.0, geom=cone),
                    scalars='colors',
                    rgb=True,
                    show_edges=False
                )
        except Exception as e:
            logger.warning(f"Failed to update electrode colors: {e}")

    # -------------------- Properties exposed via Widgets -------------------- #
    @property
    def montage_path(self) -> Optional[str]:
        return None if self._montage_path is None else str(self._montage_path)

    @montage_path.setter
    def montage_path(self, value: Optional[str]):
        self._montage_path = Path(value).expanduser().resolve() if value else None
        self.reset_renderer(reset_channel_labels=True)

    @property
    def head_mesh_path(self) -> str:
        return str(self._head_mesh_path)

    @head_mesh_path.setter
    def head_mesh_path(self, value: str):
        self._head_mesh_path = Path(value).expanduser().resolve()
        self.reset_renderer(reset_channel_labels=True)

    @property
    def mesh_opacity(self) -> float:
        return self._mesh_opacity

    @mesh_opacity.setter
    def mesh_opacity(self, value: float):
        self._mesh_opacity = float(np.clip(value, 0.0, 1.0))
        self.reset_renderer(reset_channel_labels=False)

    @property
    def cone_radius(self) -> float:
        return self._cone_radius

    @cone_radius.setter
    def cone_radius(self, value: float):
        self._cone_radius = float(value)
        self.reset_renderer(reset_channel_labels=False)

    @property
    def cone_height(self) -> float:
        return self._cone_height

    @cone_height.setter
    def cone_height(self, value: float):
        self._cone_height = float(value)
        self.reset_renderer(reset_channel_labels=False)

    @property
    def show_labels(self) -> bool:
        return self._show_labels

    @show_labels.setter
    def show_labels(self, value: bool):
        self._show_labels = bool(value)
        self.reset_renderer(reset_channel_labels=True)

    @property
    def electrode_offset_y(self) -> float:
        return self._electrode_offset_y

    @electrode_offset_y.setter
    def electrode_offset_y(self, value: float):
        self._electrode_offset_y = float(value)
        self.reset_renderer(reset_channel_labels=True)

    @property
    def electrode_offset_z(self) -> float:
        return self._electrode_offset_z

    @electrode_offset_z.setter
    def electrode_offset_z(self, value: float):
        self._electrode_offset_z = float(value)
        self.reset_renderer(reset_channel_labels=True)
