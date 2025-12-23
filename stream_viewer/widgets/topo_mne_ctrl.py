from qtpy import QtWidgets, QtCore
from stream_viewer.widgets.interface import IControlPanel
from pathlib import Path


class TopoMNEControlPanel(IControlPanel):
    """
    A panel of configuration widgets for configuring a TopoMNE renderer.
    This widget assumes the renderer is an instance of TopoMNE.

    TODO: the folloinwg controls aren't relevant: ["Lower Limit", "Upper Limit", "Highpass Cutoff", "Lower Limit"]
    """
    def __init__(self, renderer, name="TopoMNEControlPanelWidget", **kwargs):
        super().__init__(renderer, name=name, **kwargs)  # Will call _init_widgets and reset_widgets

    def _init_widgets(self):
        super()._init_widgets()

        # Continue filling in the grid of widgets
        row_ix = self._last_row

        # Separator
        row_ix += 1
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.layout().addWidget(separator, row_ix, 0, 1, 2)

        # Head Mesh Path
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Head Mesh Path"), row_ix, 0, 1, 1)
        mesh_path_layout = QtWidgets.QHBoxLayout()
        _line_edit = QtWidgets.QLineEdit()
        _line_edit.setObjectName("HeadMeshPath_LineEdit")
        _line_edit.setReadOnly(True)
        mesh_path_layout.addWidget(_line_edit)
        _button = QtWidgets.QPushButton("Browse...")
        _button.setObjectName("HeadMeshPath_Button")
        mesh_path_layout.addWidget(_button)
        mesh_path_widget = QtWidgets.QWidget()
        mesh_path_widget.setLayout(mesh_path_layout)
        self.layout().addWidget(mesh_path_widget, row_ix, 1, 1, 1)

        # Montage Path
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Montage Path"), row_ix, 0, 1, 1)
        montage_path_layout = QtWidgets.QHBoxLayout()
        _line_edit = QtWidgets.QLineEdit()
        _line_edit.setObjectName("MontagePath_LineEdit")
        _line_edit.setReadOnly(True)
        montage_path_layout.addWidget(_line_edit)
        _button = QtWidgets.QPushButton("Browse...")
        _button.setObjectName("MontagePath_Button")
        montage_path_layout.addWidget(_button)
        montage_path_widget = QtWidgets.QWidget()
        montage_path_widget.setLayout(montage_path_layout)
        self.layout().addWidget(montage_path_widget, row_ix, 1, 1, 1)

        # Mesh Opacity
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Mesh Opacity"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QDoubleSpinBox()
        _spinbox.setObjectName("MeshOpacity_SpinBox")
        _spinbox.setMinimum(0.0)
        _spinbox.setMaximum(1.0)
        _spinbox.setSingleStep(0.1)
        _spinbox.setDecimals(2)
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 1)

        # Cone Radius
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Cone Radius (m)"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QDoubleSpinBox()
        _spinbox.setObjectName("ConeRadius_SpinBox")
        _spinbox.setMinimum(0.001)
        _spinbox.setMaximum(0.1)
        _spinbox.setSingleStep(0.001)
        _spinbox.setDecimals(4)
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 1)

        # Cone Height
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Cone Height (m)"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QDoubleSpinBox()
        _spinbox.setObjectName("ConeHeight_SpinBox")
        _spinbox.setMinimum(0.001)
        _spinbox.setMaximum(0.1)
        _spinbox.setSingleStep(0.001)
        _spinbox.setDecimals(4)
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 1)

        # Show Labels checkbox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Show Labels"), row_ix, 0, 1, 1)
        _checkbox = QtWidgets.QCheckBox()
        _checkbox.setObjectName("ShowLabels_CheckBox")
        self.layout().addWidget(_checkbox, row_ix, 1, 1, 1)

        # Electrode Offset Y
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Electrode Offset Y (m)"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QDoubleSpinBox()
        _spinbox.setObjectName("ElectrodeOffsetY_SpinBox")
        _spinbox.setMinimum(-0.2)
        _spinbox.setMaximum(0.2)
        _spinbox.setSingleStep(0.01)
        _spinbox.setDecimals(3)
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 1)

        # Electrode Offset Z
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Electrode Offset Z (m)"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QDoubleSpinBox()
        _spinbox.setObjectName("ElectrodeOffsetZ_SpinBox")
        _spinbox.setMinimum(-0.2)
        _spinbox.setMaximum(0.2)
        _spinbox.setSingleStep(0.01)
        _spinbox.setDecimals(3)
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 1)

        self._last_row = row_ix

    def reset_widgets(self, renderer):
        super().reset_widgets(renderer)

        # Head Mesh Path
        _line_edit = self.findChild(QtWidgets.QLineEdit, name="HeadMeshPath_LineEdit")
        _button = self.findChild(QtWidgets.QPushButton, name="HeadMeshPath_Button")
        if _line_edit is not None and _button is not None:
            _line_edit.setText(renderer.head_mesh_path)
            try:
                _button.clicked.disconnect()
            except TypeError:
                pass
            _button.clicked.connect(lambda: self._on_browse_head_mesh(renderer))

        # Montage Path
        _line_edit = self.findChild(QtWidgets.QLineEdit, name="MontagePath_LineEdit")
        _button = self.findChild(QtWidgets.QPushButton, name="MontagePath_Button")
        if _line_edit is not None and _button is not None:
            current_path = renderer.montage_path or ""
            _line_edit.setText(current_path)
            try:
                _button.clicked.disconnect()
            except TypeError:
                pass
            _button.clicked.connect(lambda: self._on_browse_montage(renderer))

        # Mesh Opacity
        _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="MeshOpacity_SpinBox")
        if _spinbox is not None:
            try:
                _spinbox.valueChanged.disconnect()
            except TypeError:
                pass
            _spinbox.setValue(renderer.mesh_opacity)
            _spinbox.valueChanged.connect(lambda v: setattr(renderer, 'mesh_opacity', v))

        # Cone Radius
        _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="ConeRadius_SpinBox")
        if _spinbox is not None:
            try:
                _spinbox.valueChanged.disconnect()
            except TypeError:
                pass
            _spinbox.setValue(renderer.cone_radius)
            _spinbox.valueChanged.connect(lambda v: setattr(renderer, 'cone_radius', v))

        # Cone Height
        _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="ConeHeight_SpinBox")
        if _spinbox is not None:
            try:
                _spinbox.valueChanged.disconnect()
            except TypeError:
                pass
            _spinbox.setValue(renderer.cone_height)
            _spinbox.valueChanged.connect(lambda v: setattr(renderer, 'cone_height', v))

        # Show Labels
        _checkbox = self.findChild(QtWidgets.QCheckBox, name="ShowLabels_CheckBox")
        if _checkbox is not None:
            try:
                _checkbox.stateChanged.disconnect()
            except TypeError:
                pass
            _checkbox.setChecked(renderer.show_labels)
            _checkbox.stateChanged.connect(self._on_show_labels_changed)

        # Electrode Offset Y
        _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="ElectrodeOffsetY_SpinBox")
        if _spinbox is not None:
            try:
                _spinbox.valueChanged.disconnect()
            except TypeError:
                pass
            _spinbox.setValue(renderer.electrode_offset_y)
            _spinbox.valueChanged.connect(lambda v: setattr(renderer, 'electrode_offset_y', v))

        # Electrode Offset Z
        _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="ElectrodeOffsetZ_SpinBox")
        if _spinbox is not None:
            try:
                _spinbox.valueChanged.disconnect()
            except TypeError:
                pass
            _spinbox.setValue(renderer.electrode_offset_z)
            _spinbox.valueChanged.connect(lambda v: setattr(renderer, 'electrode_offset_z', v))

    def _on_browse_head_mesh(self, renderer):
        """Open file dialog to select head mesh STL file."""
        current_path = Path(renderer.head_mesh_path) if renderer.head_mesh_path else Path.home()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Head Mesh File", str(current_path),
            "STL Files (*.stl);;All Files (*)"
        )
        if path:
            renderer.head_mesh_path = path
            _line_edit = self.findChild(QtWidgets.QLineEdit, name="HeadMeshPath_LineEdit")
            if _line_edit is not None:
                _line_edit.setText(path)

    def _on_browse_montage(self, renderer):
        """Open file dialog to select montage file."""
        current_path = None
        if renderer.montage_path:
            current_path = Path(renderer.montage_path).parent
        else:
            current_path = Path.home()
        
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Select Montage File", str(current_path),
            "TSV Files (*.tsv);;All Files (*)"
        )
        if path:
            renderer.montage_path = path
            _line_edit = self.findChild(QtWidgets.QLineEdit, name="MontagePath_LineEdit")
            if _line_edit is not None:
                _line_edit.setText(path)

    def _on_show_labels_changed(self, state):
        """Handle show labels checkbox state change."""
        renderer = self._renderer
        renderer.show_labels = state > 0

