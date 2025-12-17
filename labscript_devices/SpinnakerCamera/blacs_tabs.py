#####################################################################
#                                                                   #
# /labscript_devices/SpinnakerCamera/blacs_tabs.py                  #
#                                                                   #
# Copyright 2019, Monash University and contributors                #
#                                                                   #
# This file is part of labscript_devices, in the labscript suite    #
# (see http://labscriptsuite.org), and is licensed under the        #
# Simplified BSD License. See the license.txt file in the root of   #
# the project for the full license.                                 #
#                                                                   #
#####################################################################

from labscript_devices.IMAQdxCamera.blacs_tabs import IMAQdxCameraTab
from qtpy import QtWidgets, QtGui


class SpinnakerCameraTab(IMAQdxCameraTab):

    # override worker class
    worker_class = 'labscript_devices.SpinnakerCamera.blacs_workers.SpinnakerCameraWorker'
    # def initialise_GUI(self):
    #     self.image_label = QtWidgets.QLabel(self)
    #     self.image_label.setFixedSize(640, 480)  # adjust to your camera
    #     self.layout().addWidget(self.image_label)
    
    # def new_image(self, img_array):
    #     # Convert NumPy array to QImage
    #     h, w = img_array.shape
    #     q_img = QtGui.QImage(img_array.data, w, h, w, QtGui.QImage.Format_Grayscale8)
    #     pixmap = QtGui.QPixmap.fromImage(q_img)
    #     self.image_label.setPixmap(pixmap)
    
    # def initialise_workers(self):
    #     # This is called after the worker is initialized
    #     # Connect the worker signal 'new_image' to the GUI update
    #     self.camera_worker.register_event('new_image', self.new_image)
