import os
import qtutils.icons

from PyQt5 import uic, QtWidgets, QtGui, QtCore
from PyQt5.QtCore import pyqtSignal

import pyqtgraph as pg

from .genicam_feature_tree_widget import GeniCamFeatureTreeDialog


class GeniCamWidget(QtWidgets.QWidget):
    # signals emitted by this widget to outside world
    on_continuous_requested = pyqtSignal()
    on_stop_requested = pyqtSignal()
    on_snap_requested = pyqtSignal()
    on_show_attribute_tree_requested = pyqtSignal()
    on_continuous_max_change_requested = pyqtSignal(float)
    on_change_attribute_requested = pyqtSignal(dict)

    # signals this widget received
    request_enter_continuous_mode = pyqtSignal()
    request_exit_continuous_mode = pyqtSignal()
    request_update_colormap = pyqtSignal(object)
    request_update_image = pyqtSignal(object)
    request_update_fps = pyqtSignal(float)
    request_update_max_fps = pyqtSignal(float)
    request_show_attribute_tree = pyqtSignal(dict)
    request_update_attribute_tree = pyqtSignal(dict)  # TODO

    def __init__(self, parent, device_name):
        super().__init__(parent)

        self.device_name = device_name

        ui_filepath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'blacs_tab.ui'
        )
        uic.loadUi(ui_filepath, self)

        # emit signals to outside world
        self.continuousButton.clicked.connect(lambda: self.on_continuous_requested.emit())
        self.stopButton.clicked.connect(lambda: self.on_stop_requested.emit())
        self.snapButton.clicked.connect(lambda: self.on_snap_requested.emit())
        self.attributesButton.clicked.connect(lambda: self.on_show_attribute_tree_requested.emit())
        self.noMaxButton.clicked.connect(self.on_reset_rate_clicked)
        self.maxRateSpinBox.valueChanged.connect(lambda max_rate: self.on_continuous_max_change_requested.emit(max_rate))

        # signal outside world sends to this widget
        self.request_update_image.connect(self.update_image)
        self.request_update_fps.connect(self.update_fps)
        self.request_update_colormap.connect(self.set_colormap)
        self.request_update_max_fps.connect(self.set_max_fps)
        self.request_enter_continuous_mode.connect(self.setup_continuous_mode)
        self.request_exit_continuous_mode.connect(self.exit_continuous_mode)
        self.request_show_attribute_tree.connect(self.show_attribute_tree_dialog)

        self.image = pg.ImageView()
        self.image.setSizePolicy(
            QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding
        )
        self.horizontalLayout.addWidget(self.image)

        self.stopButton.hide()
        self.maxRateSpinBox.hide()
        self.noMaxButton.hide()
        self.fpsLabel.hide()

        # Ensure the GUI reserves space for these widgets even if they are hidden.
        # This prevents the GUI jumping around when buttons are clicked:
        for widget in [
            self.stopButton,
            self.maxRateSpinBox,
            self.noMaxButton,
        ]:
            size_policy = widget.sizePolicy()
            if hasattr(size_policy, 'setRetainSizeWhenHidden'): # Qt 5.2+ only
                size_policy.setRetainSizeWhenHidden(True)
                widget.setSizePolicy(size_policy)

    @property
    def max_fps(self):
        return self.maxRateSpinBox.value()

    @property
    def colormap(self):
        return self.image.ui.histogram.gradient.saveState()

    def show_attribute_tree_dialog(self, attr_dict):
        self.attributesButton.setEnabled(False)
        self.attributes_dialog = GeniCamFeatureTreeDialog(self, self.device_name, attr_dict)
        self.attributes_dialog.finished.connect(self._cleanup_attribute_tree_dialog)
        self.attributes_dialog.on_attr_change_requested.connect(lambda _dict: self.on_change_attribute_requested.emit(_dict))
        self.request_update_attribute_tree.connect(self.attributes_dialog.updte_attributes)
        self.attributes_dialog.show()

    def _cleanup_attribute_tree_dialog(self, result):
        self.request_update_attribute_tree.disconnect()
        self.attribute_dialog = None
        self.attributesButton.setEnabled(True)

    def on_reset_rate_clicked(self):
        self.maxRateSpinBox.setValue(0)

    def update_image(self, image):
        if self.image.image is None:
            self.image.setImage(image.swapaxes(-1, -2))
        else:
            self.image.setImage(
                image.swapaxes(-1, -2), autoRange=False, autoLevels=False
            )

        # draw immediately
        QtGui.QApplication.instance().sendPostedEvents()

    def update_fps(self, fps):
        self.fpsLabel.setText(f"{fps:.01f} fps")

    def setup_continuous_mode(self):
        self.snapButton.setEnabled(False)
        self.attributesButton.setEnabled(False)
        self.continuousButton.hide()
        self.stopButton.show()
        self.maxRateSpinBox.show()
        self.noMaxButton.show()
        self.fpsLabel.show()
        self.fpsLabel.setText('? fps')

    def exit_continuous_mode(self):
        self.snapButton.setEnabled(True)
        self.attributesButton.setEnabled(True)
        self.continuousButton.show()
        self.maxRateSpinBox.hide()
        self.noMaxButton.hide()
        self.stopButton.hide()
        self.fpsLabel.hide()

    def set_colormap(self, colormap):
        self.image.ui.histogram.gradient.restoreState(colormap)

    def set_max_fps(self, rate):
        self.maxRateSpinBox.setValue(rate)
