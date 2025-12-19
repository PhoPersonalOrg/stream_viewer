from qtpy import QtWidgets, QtCore
from stream_viewer.widgets.time_series import TimeSeriesControl


class HeatmapControlPanel(TimeSeriesControl):
    """
    Control panel for HeatmapPG renderer with Apply/Revert buttons.
    
    This panel adds spectrogram-specific controls and uses an Apply/Revert
    pattern to prevent expensive reset operations from blocking the UI.
    """
    
    def __init__(self, renderer, name="HeatmapControlPanel", **kwargs):
        super().__init__(renderer, name=name, **kwargs)
        # Store last applied values for revert
        self._applied_values = {}
        self._pending_values = {}
        
    def _init_widgets(self):
        super()._init_widgets()
        
        row_ix = self._last_row
        
        # Separator
        row_ix += 1
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        self.layout().addWidget(separator, row_ix, 0, 1, 2)
        
        # Spectrogram Settings Group
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Spectrogram Settings"), row_ix, 0, 1, 2)
        
        # fmin_hz spinbox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Min Freq (Hz)"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QDoubleSpinBox()
        _spinbox.setObjectName("FMin_SpinBox")
        _spinbox.setMinimum(0.1)
        _spinbox.setMaximum(1000.0)
        _spinbox.setSingleStep(1.0)
        _spinbox.setDecimals(1)
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 1)
        
        # fmax_hz spinbox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("Max Freq (Hz)"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QDoubleSpinBox()
        _spinbox.setObjectName("FMax_SpinBox")
        _spinbox.setMinimum(0.1)
        _spinbox.setMaximum(1000.0)
        _spinbox.setSingleStep(1.0)
        _spinbox.setDecimals(1)
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 1)
        
        # nperseg spinbox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("N Per Seg"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QSpinBox()
        _spinbox.setObjectName("NPerSeg_SpinBox")
        _spinbox.setMinimum(8)
        _spinbox.setMaximum(4096)
        _spinbox.setSingleStep(64)
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 1)
        
        # noverlap spinbox
        row_ix += 1
        self.layout().addWidget(QtWidgets.QLabel("N Overlap"), row_ix, 0, 1, 1)
        _spinbox = QtWidgets.QSpinBox()
        _spinbox.setObjectName("NOverlap_SpinBox")
        _spinbox.setMinimum(0)
        _spinbox.setMaximum(4096)
        _spinbox.setSingleStep(32)
        self.layout().addWidget(_spinbox, row_ix, 1, 1, 1)
        
        # Apply/Revert buttons
        row_ix += 1
        button_layout = QtWidgets.QHBoxLayout()
        _apply_btn = QtWidgets.QPushButton("Apply")
        _apply_btn.setObjectName("Apply_Button")
        _apply_btn.setEnabled(False)  # Disabled until there are pending changes
        button_layout.addWidget(_apply_btn)
        
        _revert_btn = QtWidgets.QPushButton("Revert")
        _revert_btn.setObjectName("Revert_Button")
        _revert_btn.setEnabled(False)  # Disabled until there are pending changes
        button_layout.addWidget(_revert_btn)
        
        button_widget = QtWidgets.QWidget()
        button_widget.setLayout(button_layout)
        self.layout().addWidget(button_widget, row_ix, 0, 1, 2)
        
        # Re-sync to Present button (only enabled in Scroll mode when manually scrolled)
        row_ix += 1
        _resync_btn = QtWidgets.QPushButton("← Re-sync to Present")
        _resync_btn.setObjectName("Resync_Button")
        _resync_btn.setEnabled(False)  # Disabled by default
        self.layout().addWidget(_resync_btn, row_ix, 0, 1, 2)
        
        self._last_row = row_ix
        
    def reset_widgets(self, renderer):
        super().reset_widgets(renderer)
        
        # Store current applied values
        self._applied_values = {
            'fmin_hz': renderer.fmin_hz,
            'fmax_hz': renderer.fmax_hz,
            'nperseg': renderer.nperseg,
            'noverlap': renderer.noverlap,
        }
        self._pending_values = {}
        
        # fmin_hz spinbox
        _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="FMin_SpinBox")
        if _spinbox is not None:
            try:
                _spinbox.valueChanged.disconnect()
            except TypeError:
                pass
            _spinbox.blockSignals(True)
            _spinbox.setValue(renderer.fmin_hz)
            _spinbox.blockSignals(False)
            _spinbox.valueChanged.connect(self._on_fmin_changed)
        
        # fmax_hz spinbox
        _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="FMax_SpinBox")
        if _spinbox is not None:
            try:
                _spinbox.valueChanged.disconnect()
            except TypeError:
                pass
            _spinbox.blockSignals(True)
            _spinbox.setValue(renderer.fmax_hz)
            _spinbox.blockSignals(False)
            _spinbox.valueChanged.connect(self._on_fmax_changed)
        
        # nperseg spinbox
        _spinbox = self.findChild(QtWidgets.QSpinBox, name="NPerSeg_SpinBox")
        if _spinbox is not None:
            try:
                _spinbox.valueChanged.disconnect()
            except TypeError:
                pass
            _spinbox.blockSignals(True)
            _spinbox.setValue(renderer.nperseg)
            _spinbox.blockSignals(False)
            _spinbox.valueChanged.connect(self._on_nperseg_changed)
        
        # noverlap spinbox
        _spinbox = self.findChild(QtWidgets.QSpinBox, name="NOverlap_SpinBox")
        if _spinbox is not None:
            try:
                _spinbox.valueChanged.disconnect()
            except TypeError:
                pass
            _spinbox.blockSignals(True)
            _spinbox.setValue(renderer.noverlap)
            _spinbox.blockSignals(False)
            _spinbox.valueChanged.connect(self._on_noverlap_changed)
        
        # Apply button
        _apply_btn = self.findChild(QtWidgets.QPushButton, name="Apply_Button")
        if _apply_btn is not None:
            try:
                _apply_btn.clicked.disconnect()
            except TypeError:
                pass
            _apply_btn.clicked.connect(self._on_apply_clicked)
            _apply_btn.setEnabled(False)
        
        # Revert button
        _revert_btn = self.findChild(QtWidgets.QPushButton, name="Revert_Button")
        if _revert_btn is not None:
            try:
                _revert_btn.clicked.disconnect()
            except TypeError:
                pass
            _revert_btn.clicked.connect(self._on_revert_clicked)
            _revert_btn.setEnabled(False)
        
        # Re-sync button
        _resync_btn = self.findChild(QtWidgets.QPushButton, name="Resync_Button")
        if _resync_btn is not None:
            try:
                _resync_btn.clicked.disconnect()
            except TypeError:
                pass
            _resync_btn.clicked.connect(self._on_resync_clicked)
            self._update_resync_button_state()
        
        # Connect to mode changes to update re-sync button state
        # Note: mode_currentTextChanged is already connected in parent class,
        # so we add our update as an additional connection
        _combo = self.findChild(QtWidgets.QComboBox, name="Mode_ComboBox")
        if _combo is not None:
            # Add our update handler (don't disconnect existing one)
            _combo.currentTextChanged.connect(self._update_resync_button_state)
    
    def _on_fmin_changed(self, value):
        """Handle fmin_hz change - store as pending if different from applied."""
        applied = self._applied_values.get('fmin_hz')
        if applied is not None:
            if abs(value - applied) < 1e-6:
                # Value matches applied, remove from pending
                self._pending_values.pop('fmin_hz', None)
            else:
                # Value differs, add to pending
                self._pending_values['fmin_hz'] = value
        else:
            # No applied value yet, add to pending
            self._pending_values['fmin_hz'] = value
        self._update_button_states()
    
    def _on_fmax_changed(self, value):
        """Handle fmax_hz change - store as pending if different from applied."""
        applied = self._applied_values.get('fmax_hz')
        if applied is not None:
            if abs(value - applied) < 1e-6:
                # Value matches applied, remove from pending
                self._pending_values.pop('fmax_hz', None)
            else:
                # Value differs, add to pending
                self._pending_values['fmax_hz'] = value
        else:
            # No applied value yet, add to pending
            self._pending_values['fmax_hz'] = value
        self._update_button_states()
    
    def _on_nperseg_changed(self, value):
        """Handle nperseg change - store as pending if different from applied."""
        applied = self._applied_values.get('nperseg')
        if applied is not None:
            if value == applied:
                # Value matches applied, remove from pending
                self._pending_values.pop('nperseg', None)
            else:
                # Value differs, add to pending
                self._pending_values['nperseg'] = value
        else:
            # No applied value yet, add to pending
            self._pending_values['nperseg'] = value
        self._update_button_states()
    
    def _on_noverlap_changed(self, value):
        """Handle noverlap change - store as pending if different from applied."""
        applied = self._applied_values.get('noverlap')
        if applied is not None:
            if value == applied:
                # Value matches applied, remove from pending
                self._pending_values.pop('noverlap', None)
            else:
                # Value differs, add to pending
                self._pending_values['noverlap'] = value
        else:
            # No applied value yet, add to pending
            self._pending_values['noverlap'] = value
        self._update_button_states()
    
    def _update_button_states(self):
        """Update Apply/Revert button enabled states based on pending changes."""
        has_pending = len(self._pending_values) > 0
        # Use findChildren with recursive search to ensure we find the buttons
        _apply_btn = None
        _revert_btn = None
        for btn in self.findChildren(QtWidgets.QPushButton):
            if btn.objectName() == "Apply_Button":
                _apply_btn = btn
            elif btn.objectName() == "Revert_Button":
                _revert_btn = btn
        
        if _apply_btn is not None:
            _apply_btn.setEnabled(has_pending)
        if _revert_btn is not None:
            _revert_btn.setEnabled(has_pending)
    
    def _on_apply_clicked(self):
        """Apply pending changes to renderer."""
        if not self._pending_values:
            return
        
        renderer = self._renderer
        
        # Apply each pending value
        for key, value in self._pending_values.items():
            if hasattr(renderer, key):
                setattr(renderer, key, value)
                self._applied_values[key] = value
        
        # Clear pending values
        self._pending_values = {}
        self._update_button_states()
    
    def _on_revert_clicked(self):
        """Revert to last applied values."""
        if not self._pending_values:
            return
        
        # Restore widgets to applied values
        for key in list(self._pending_values.keys()):
            if key in self._applied_values:
                value = self._applied_values[key]
                
                # Update the corresponding widget
                if key == 'fmin_hz':
                    _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="FMin_SpinBox")
                    if _spinbox is not None:
                        _spinbox.blockSignals(True)
                        _spinbox.setValue(value)
                        _spinbox.blockSignals(False)
                elif key == 'fmax_hz':
                    _spinbox = self.findChild(QtWidgets.QDoubleSpinBox, name="FMax_SpinBox")
                    if _spinbox is not None:
                        _spinbox.blockSignals(True)
                        _spinbox.setValue(value)
                        _spinbox.blockSignals(False)
                elif key == 'nperseg':
                    _spinbox = self.findChild(QtWidgets.QSpinBox, name="NPerSeg_SpinBox")
                    if _spinbox is not None:
                        _spinbox.blockSignals(True)
                        _spinbox.setValue(value)
                        _spinbox.blockSignals(False)
                elif key == 'noverlap':
                    _spinbox = self.findChild(QtWidgets.QSpinBox, name="NOverlap_SpinBox")
                    if _spinbox is not None:
                        _spinbox.blockSignals(True)
                        _spinbox.setValue(value)
                        _spinbox.blockSignals(False)
        
        # Clear pending values
        self._pending_values = {}
        self._update_button_states()
    
    def _on_resync_clicked(self):
        """Handle re-sync button click - re-sync view to present time."""
        renderer = self._renderer
        if hasattr(renderer, 'sync_to_present'):
            renderer.sync_to_present()
            self._update_resync_button_state()
    
    def _update_resync_button_state(self):
        """Update re-sync button enabled state based on plot mode and sync state."""
        _resync_btn = self.findChild(QtWidgets.QPushButton, name="Resync_Button")
        if _resync_btn is not None:
            renderer = self._renderer
            # Only enable in Scroll mode and when manually scrolled
            is_scroll_mode = (hasattr(renderer, 'plot_mode') and 
                            renderer.plot_mode == "Scroll")
            is_manually_scrolled = (hasattr(renderer, 'is_manually_scrolled') and 
                                   renderer.is_manually_scrolled)
            _resync_btn.setEnabled(is_scroll_mode and is_manually_scrolled)

