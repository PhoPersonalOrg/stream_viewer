"""
SpectrogramControlPanel - Control panel for SpectrogramPG renderer.

Provides controls for:
- Channel selection (which channels to average for spectrogram)
- Frequency range (fmin, fmax)
- FFT parameters (nperseg, overlap ratio)
- Colormap selection
"""

from qtpy import QtWidgets, QtCore
from stream_viewer.widgets.time_series import TimeSeriesControl


class SpectrogramControlPanel(TimeSeriesControl):
    """
    Control panel for SpectrogramPG renderer.
    
    Extends TimeSeriesControl with spectrogram-specific controls:
    - Channel selection tree for spectrogram averaging
    - Frequency range spinboxes
    - FFT parameter controls
    """
    
    def __init__(self, renderer, name="SpectrogramControlPanel", **kwargs):
        super().__init__(renderer, name=name, **kwargs)
    
    def _init_widgets(self):
        super()._init_widgets()
        
        row_ix = self._last_row
        
        # Separator
        row_ix += 1
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.layout().addWidget(separator, row_ix, 0, 1, 3)
        
        # Spectrogram Settings Header
        row_ix += 1
        header = QtWidgets.QLabel("Spectrogram Settings")
        header.setStyleSheet("font-weight: bold;")
        self.layout().addWidget(header, row_ix, 0, 1, 3)
        
        # Channel Selection for Spectrogram
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Avg Channels"), row_ix, 0, 1, 1)
        _tree = QtWidgets.QTreeWidget()
        _tree.setObjectName("SpectrogramChans_TreeWidget")
        _tree.setHeaderHidden(True)
        _tree.setFrameShape(QtWidgets.QFrame.Box)
        _tree.setMaximumHeight(120)
        tli = QtWidgets.QTreeWidgetItem(_tree)
        tli.setText(0, "Select Channels")
        tli.setExpanded(True)
        _tree.addTopLevelItem(tli)
        self.layout().addWidget(_tree, row_ix, 1, 1, 2)
        
        # Select All / None buttons
        row_ix += 1
        btn_layout = QtWidgets.QHBoxLayout()
        _select_all_btn = QtWidgets.QPushButton("All")
        _select_all_btn.setObjectName("SelectAll_Button")
        _select_all_btn.setMaximumWidth(50)
        btn_layout.addWidget(_select_all_btn)
        
        _select_none_btn = QtWidgets.QPushButton("None")
        _select_none_btn.setObjectName("SelectNone_Button")
        _select_none_btn.setMaximumWidth(50)
        btn_layout.addWidget(_select_none_btn)
        btn_layout.addStretch()
        
        btn_widget = QtWidgets.QWidget()
        btn_widget.setLayout(btn_layout)
        self.layout().addWidget(btn_widget, row_ix, 1, 1, 2)
        
        # Frequency Range
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Min Freq (Hz)"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QDoubleSpinBox()
        _spinbox.setObjectName("FMin_SpinBox")
        _spinbox.setMinimum(0.1)
        _spinbox.setMaximum(1000.0)
        _spinbox.setSingleStep(1.0)
        _spinbox.setDecimals(1)
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 2)
        
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Max Freq (Hz)"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QDoubleSpinBox()
        _spinbox.setObjectName("FMax_SpinBox")
        _spinbox.setMinimum(0.1)
        _spinbox.setMaximum(1000.0)
        _spinbox.setSingleStep(1.0)
        _spinbox.setDecimals(1)
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 2)
        
        # FFT Parameters
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("FFT Size"), row_ix, 0, 1, 1)
        _combo = QtWidgets.QComboBox()
        _combo.setObjectName("FFTSize_ComboBox")
        _combo.addItems(["64", "128", "256", "512", "1024", "2048"])
        self.layout().addWidget(_combo, row_ix, 1, 1, 2)
        
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Overlap %"), row_ix, 0, 1, 1)
        _slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        _slider.setObjectName("Overlap_Slider")
        _slider.setMinimum(0)
        _slider.setMaximum(90)
        _slider.setSingleStep(10)
        _slider.setTickInterval(10)
        _slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.layout().addWidget(_slider, row_ix, 1, 1, 1)
        
        _overlap_label = QtWidgets.QLabel("50%")
        _overlap_label.setObjectName("Overlap_Label")
        _overlap_label.setMinimumWidth(35)
        self.layout().addWidget(_overlap_label, row_ix, 2, 1, 1)
        
        self._last_row = row_ix
    
    def reset_widgets(self, renderer):
        super().reset_widgets(renderer)
        
        # Spectrogram channel selection tree
        _tree = self.findChild(QtWidgets.QTreeWidget, name="SpectrogramChans_TreeWidget")
        if _tree is not None:
            try:
                _tree.itemChanged.disconnect()
            except TypeError:
                pass
            
            tli = _tree.topLevelItem(0)
            if tli is not None:
                # Clear existing children
                tli.takeChildren()
                
                # Get channel info from renderer
                if hasattr(renderer, 'get_channel_names'):
                    channels = renderer.get_channel_names(src_ix=0)
                    for idx, name, is_selected in channels:
                        item = QtWidgets.QTreeWidgetItem(tli)
                        item.setText(0, name)
                        item.setData(0, QtCore.Qt.UserRole, idx)  # Store index
                        item.setCheckState(0, QtCore.Qt.Checked if is_selected else QtCore.Qt.Unchecked)
                
                tli.setExpanded(True)
            
            _tree.itemChanged.connect(self._on_spectrogram_channel_changed)
        
        # Select All button
        _select_all_btn = self.findChild(QtWidgets.QPushButton, name="SelectAll_Button")
        if _select_all_btn is not None:
            try:
                _select_all_btn.clicked.disconnect()
            except TypeError:
                pass
            _select_all_btn.clicked.connect(self._on_select_all_clicked)
        
        # Select None button
        _select_none_btn = self.findChild(QtWidgets.QPushButton, name="SelectNone_Button")
        if _select_none_btn is not None:
            try:
                _select_none_btn.clicked.disconnect()
            except TypeError:
                pass
            _select_none_btn.clicked.connect(self._on_select_none_clicked)
        
        # Frequency range
        _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="FMin_SpinBox")
        if _spinbox is not None:
            try:
                _spinbox.valueChanged.disconnect()
            except TypeError:
                pass
            _spinbox.blockSignals(True)
            if hasattr(renderer, 'fmin_hz'):
                _spinbox.setValue(renderer.fmin_hz)
            _spinbox.blockSignals(False)
            _spinbox.valueChanged.connect(self._on_fmin_changed)
        
        _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="FMax_SpinBox")
        if _spinbox is not None:
            try:
                _spinbox.valueChanged.disconnect()
            except TypeError:
                pass
            _spinbox.blockSignals(True)
            if hasattr(renderer, 'fmax_hz'):
                _spinbox.setValue(renderer.fmax_hz)
            _spinbox.blockSignals(False)
            _spinbox.valueChanged.connect(self._on_fmax_changed)
        
        # FFT Size
        _combo = self.findChild(QtWidgets.QComboBox, name="FFTSize_ComboBox")
        if _combo is not None:
            try:
                _combo.currentTextChanged.disconnect()
            except TypeError:
                pass
            _combo.blockSignals(True)
            if hasattr(renderer, 'nperseg'):
                idx = _combo.findText(str(renderer.nperseg))
                if idx >= 0:
                    _combo.setCurrentIndex(idx)
            _combo.blockSignals(False)
            _combo.currentTextChanged.connect(self._on_fft_size_changed)
        
        # Overlap slider
        _slider = self.findChild(QtWidgets.QSlider, name="Overlap_Slider")
        _label = self.findChild(QtWidgets.QLabel, name="Overlap_Label")
        if _slider is not None:
            try:
                _slider.valueChanged.disconnect()
            except TypeError:
                pass
            _slider.blockSignals(True)
            if hasattr(renderer, 'overlap_ratio'):
                overlap_pct = int(renderer.overlap_ratio * 100)
                _slider.setValue(overlap_pct)
                if _label is not None:
                    _label.setText(f"{overlap_pct}%")
            _slider.blockSignals(False)
            _slider.valueChanged.connect(self._on_overlap_changed)
    
    def _on_spectrogram_channel_changed(self, item, column):
        """Handle spectrogram channel selection change."""
        renderer = self._renderer
        if not hasattr(renderer, 'set_selected_channels'):
            return
        
        # Collect all checked channel indices
        _tree = self.findChild(QtWidgets.QTreeWidget, name="SpectrogramChans_TreeWidget")
        if _tree is None:
            return
        
        tli = _tree.topLevelItem(0)
        if tli is None:
            return
        
        selected_indices = set()
        for i in range(tli.childCount()):
            child = tli.child(i)
            if child.checkState(0) == QtCore.Qt.Checked:
                idx = child.data(0, QtCore.Qt.UserRole)
                if idx is not None:
                    selected_indices.add(idx)
        
        renderer.set_selected_channels(src_ix=0, channel_indices=selected_indices)
    
    def _on_select_all_clicked(self):
        """Select all channels for spectrogram averaging."""
        _tree = self.findChild(QtWidgets.QTreeWidget, name="SpectrogramChans_TreeWidget")
        if _tree is None:
            return
        
        tli = _tree.topLevelItem(0)
        if tli is None:
            return
        
        _tree.blockSignals(True)
        for i in range(tli.childCount()):
            child = tli.child(i)
            child.setCheckState(0, QtCore.Qt.Checked)
        _tree.blockSignals(False)
        
        # Trigger update
        self._on_spectrogram_channel_changed(None, 0)
    
    def _on_select_none_clicked(self):
        """Deselect all channels for spectrogram averaging."""
        _tree = self.findChild(QtWidgets.QTreeWidget, name="SpectrogramChans_TreeWidget")
        if _tree is None:
            return
        
        tli = _tree.topLevelItem(0)
        if tli is None:
            return
        
        _tree.blockSignals(True)
        for i in range(tli.childCount()):
            child = tli.child(i)
            child.setCheckState(0, QtCore.Qt.Unchecked)
        _tree.blockSignals(False)
        
        # Trigger update
        self._on_spectrogram_channel_changed(None, 0)
    
    def _on_fmin_changed(self, value):
        """Handle fmin frequency change."""
        renderer = self._renderer
        if hasattr(renderer, 'fmin_hz'):
            renderer.fmin_hz = value
    
    def _on_fmax_changed(self, value):
        """Handle fmax frequency change."""
        renderer = self._renderer
        if hasattr(renderer, 'fmax_hz'):
            renderer.fmax_hz = value
    
    def _on_fft_size_changed(self, text):
        """Handle FFT size change."""
        renderer = self._renderer
        if hasattr(renderer, 'nperseg'):
            try:
                renderer.nperseg = int(text)
            except ValueError:
                pass
    
    def _on_overlap_changed(self, value):
        """Handle overlap slider change."""
        # Update label
        _label = self.findChild(QtWidgets.QLabel, name="Overlap_Label")
        if _label is not None:
            _label.setText(f"{value}%")
        
        # Update renderer
        renderer = self._renderer
        if hasattr(renderer, 'overlap_ratio'):
            renderer.overlap_ratio = value / 100.0

