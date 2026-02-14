import os
import re
import json
import qtutils.icons

from PyQt5 import uic, QtWidgets, QtGui, QtCore
from PyQt5.Qt import Qt, QStyledItemDelegate, QColor
from PyQt5.QtCore import pyqtSignal, QAbstractItemModel, QModelIndex, QSortFilterProxyModel
from PyQt5.QtWidgets import (QSpinBox, QPushButton, QComboBox, QDialog, QLineEdit, QWidget,
                             QHBoxLayout)

from ._genicam._feature_value_tuple import (FeatureValueTuple, FeatureType, FeatureAccessMode,
                                            FeatureVisibility)
from ._genicam._tree import OrderedTreeNode

from typing import Union


class FeatureTreeNode(OrderedTreeNode):
    _readable_access_modes = [FeatureAccessMode.RW, FeatureAccessMode.RO]
    _readable_nodes = [
            FeatureType.Boolean,
            FeatureType.Enumeration,
            FeatureType.Float,
            FeatureType.Integer,
            FeatureType.String,
            FeatureType.Register
            ]

    def __init__(self, name, parent_node=None, data: Union[FeatureValueTuple, None]=None, child_nodes=None):
        super().__init__(name, parent_node, data, child_nodes)

    def columnCount(self):
        return 2 if self.data else 1

    def value(self, column):
        data = self.data

        if not data:  # this is a catagory node
            if column == 0:
                return self.name
            else:
                return None

        if column == 0:
            value = self.name
        else:
            if data.type == FeatureType.Command:
                value = '[Click here]'
            else:
                if data.access_mode not in self._readable_access_modes:
                    value = '[Not accessible]'
                elif data.type not in self._readable_nodes:
                    value = '[Not readable]'
                else:
                    value = data.value

        return value

    def tooltip(self, column):
        return None  # I can't see this to be useful

    def background(self, column):
        if not self.data: # this is a catagory node
            return QColor("grey")
        else:
            return None

    def foreground(self, column):
        if not self.data: # this is a catagory node
            return QColor('white')
        else:
            return None

    def parent(self):
        return self.parent_node

    def row(self):
        if self.parent_node:
            return self.parent_node.child_nodes.index(self)

        return 0

    def child(self, row):
        return self.child_nodes[row]

    def childCount(self):
        return len(self.child_nodes)

    def dump_value_dict(self):
        value_tree = OrderedTreeNode.eval_tree(self, lambda data: data.value)
        return value_tree.dump_value_dict()


class FeatureTreeModel(QAbstractItemModel):
    _capable_roles = [
        Qt.DisplayRole, Qt.ToolTipRole, Qt.BackgroundColorRole,
        Qt.ForegroundRole
    ]

    _editables = [FeatureAccessMode.RW, FeatureAccessMode.WO]

    on_attribute_set = pyqtSignal(FeatureTreeNode)

    def __init__(self, parent, feat_value_dict):
        """
        REMARKS: QAbstractItemModel might impact the performance and could
        slow Harvester. As far as we've confirmed, QAbstractItemModel calls
        its index() method for every item already shown. Especially, such
        a call happens every time when (1) its view got/lost focus or (2)
        its view was scrolled. If such slow performance makes people
        irritating we should investigate how can we optimize it.
        """

        super().__init__()

        self.root_item = FeatureTreeNode('root', child_nodes=[])
        self.item_index_lookup = {}
        self.populate_tree_items(feat_value_dict, self.root_item)


    # ----- Methods required by Qt -----

    def columnCount(self, parent=None, *args, **kwargs):
        return 2

    def data(self, index, role=None):
        # index: QModelIndex
        if not index.isValid():
            return None

        if role not in self._capable_roles:
            return None

        item = index.internalPointer()  # FeatureValueTuple

        if role == Qt.DisplayRole:
            value = item.value(index.column())
        elif role == Qt.ToolTipRole:
            value = item.tooltip(index.column())
        elif role == Qt.BackgroundColorRole:
            value = item.background(index.column())
        else:
            value = item.foreground(index.column())

        return value

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags

        tree_item = index.internalPointer()
        feature = tree_item.data
        if feature is None:
            return Qt.ItemIsEnabled

        access_mode = feature.access_mode

        if access_mode in self._editables:
            ret = Qt.ItemIsEnabled | Qt.ItemIsEditable
        else:
            if index.column() == 1:
                ret = Qt.NoItemFlags
            else:
                ret = Qt.ItemIsEnabled
        return ret

    def headerData(self, p_int, Qt_Orientation, role=None):
        # p_int: section
        if Qt_Orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if p_int == 0:
                return "Feature name"
            elif p_int == 1:
                return "Value"
        return None

    def index(self, p_int, p_int_1, parent=None, *args, **kwargs):
        # p_int: row
        # p_int_1: column
        if not self.hasIndex(p_int, p_int_1, parent):
            return QModelIndex()

        if not parent or not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        child_item = parent_item.child(p_int)
        if child_item:
            index = self.createIndex(p_int, p_int_1, child_item)
            self.item_index_lookup[child_item] = index
            return index
        else:
            return QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return index

        child_item = index.internalPointer()
        parent_item = child_item.parent()

        if parent_item == self.root_item:
            return QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent, *args, **kwargs):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        return len(parent_item.child_nodes) if parent_item.child_nodes else 0

    def setData(self, index, value, role=Qt.EditRole):
        # index: QModelIndex
        if role == Qt.EditRole:
            # TODO: Check the type of the target and convert the given value.
            item = index.internalPointer()
            feat = item.data

            item.data = FeatureValueTuple(name=feat.name,
                                          value=value,
                                          type=feat.type,
                                          entries=feat.entries,
                                          access_mode=feat.access_mode,
                                          visibility=feat.visibility)

            self.dataChanged.emit(index, index)
            self.on_attribute_set.emit(item)

            return True
        return False

    # ----- My methods, not required by Qt -----

    @classmethod
    def populate_tree_items(cls, feature_dict, parent_node):
        for name, feature in feature_dict.items():
            if not isinstance(feature, dict):
                item = FeatureTreeNode(name, parent_node, feature, None)
            else:
                item = FeatureTreeNode(name, parent_node, None, [])
                cls.populate_tree_items(feature, item)

            parent_node.add_child(item)

    def update_attr_from_dict(self, attr_dict, parent_paths=[]):
        for k in attr_dict.keys():
            v = attr_dict[k]
            if isinstance(v, dict):
                attr_dict[k] = self.update_attr_from_dict(v, parent_paths + [k])
            else:
                node = self.root_item.access(parent_paths + [k])
                feat = node.data
                node.data = FeatureValueTuple(name=feat.name,
                                              value=v,
                                              type=feat.type,
                                              entries=feat.entries,
                                              access_mode=feat.access_mode,
                                              visibility=feat.visibility)

                #if node in self.item_index_lookup:
                assert node in self.item_index_lookup
                index = self.item_index_lookup[node]
                self.dataChanged.emit(index, index)


class FeatureEditDelegate(QStyledItemDelegate):
    def __init__(self, proxy, parent=None):
        super().__init__()

        self._proxy = proxy

    def createEditor(self, parent, QStyleOptionViewItem, proxy_index: QModelIndex):

        # Get the actual source.
        src_index = self._proxy.mapToSource(proxy_index)

        # If it's the column #0, then immediately return.
        if src_index.column() == 0:
            return None

        tree_item = src_index.internalPointer()
        feature = tree_item.data
        interface_type = feature.type

        if interface_type == FeatureType.Integer:
            w = QSpinBox(parent)
            w.setRange(feature.min, feature.max)
            w.setSingleStep(feature.inc)
            w.setValue(feature.value)
        elif interface_type == FeatureType.Command:
            w = QPushButton(parent)
            w.setText('Execute')
            w.clicked.connect(lambda: self.on_button_clicked(proxy_index))
        elif interface_type == FeatureType.Boolean:
            w = QComboBox(parent)
            boolean_ints = {'False': 0, 'True': 1}
            w.addItem('False')
            w.addItem('True')
            proxy_index = boolean_ints['True'] if feature.value else boolean_ints['False']
            w.setCurrentIndex(proxy_index)
        elif interface_type == FeatureType.Enumeration:
            w = QComboBox(parent)
            for item in feature.entries:
                w.addItem(item)
            w.setCurrentText(feature.value)
        elif interface_type == FeatureType.String:
            w = QLineEdit(parent)
            w.setText(feature.value)
        elif interface_type == FeatureType.Float:
            w = QLineEdit(parent)
            w.setText(str(feature.value))
        else:
            return None

        return w

    def setEditorData(self, editor: QWidget, proxy_index: QModelIndex):
        src_index = self._proxy.mapToSource(proxy_index)
        value = src_index.data(Qt.DisplayRole)
        tree_item = src_index.internalPointer()
        feature = tree_item.data
        interface_type = feature.type

        if interface_type == FeatureType.Integer:
            editor.setValue(int(value))
        elif interface_type == FeatureType.Boolean:
            editor.setCurrentIndex(1 if value else 0)
        elif interface_type == FeatureType.Enumeration:
            editor.setEditText(value)
        elif interface_type == FeatureType.String:
            editor.setText(value)
        elif interface_type == FeatureType.Float:
            editor.setText(str(value))

    def setModelData(self, editor: QWidget, model: QAbstractItemModel, proxy_index: QModelIndex):
        src_index = self._proxy.mapToSource(proxy_index)
        tree_item = src_index.internalPointer()
        feature = tree_item.data
        interface_type = feature.type

        if interface_type == FeatureType.Integer:
            data = editor.value()
            model.setData(proxy_index, data)
        elif interface_type == FeatureType.Boolean:
            data = editor.currentText()
            model.setData(proxy_index, data)
        elif interface_type == FeatureType.Enumeration:
            data = editor.currentText()
            model.setData(proxy_index, data)
        elif interface_type == FeatureType.String:
            data = editor.text()
            model.setData(proxy_index, data)
        elif interface_type == FeatureType.Float:
            data = editor.text()
            model.setData(proxy_index, data)

    def on_button_clicked(self, proxy_index: QModelIndex):
        src_index = self._proxy.mapToSource(proxy_index)
        tree_item = src_index.internalPointer()
        feature = tree_item.data
        interface_type = feature.type

        if interface_type == FeatureType.Command:
            proxy_index.model().setData(proxy_index, True)


class FilterProxyModel(QSortFilterProxyModel):
    def __init__(self, visibility=FeatureVisibility.Beginner):
        #
        super().__init__()

        #
        self._visibility = visibility
        self._keyword = ''

    def filterVisibility(self, visibility):
        beginner_items = {FeatureVisibility.Beginner}
        expert_items = beginner_items.union({FeatureVisibility.Expert})
        guru_items = expert_items.union({FeatureVisibility.Guru})
        all_items = guru_items.union({FeatureVisibility.Invisible})

        items_dict = {
            FeatureVisibility.Beginner: beginner_items,
            FeatureVisibility.Expert: expert_items,
            FeatureVisibility.Guru: guru_items,
            FeatureVisibility.Invisible: all_items
        }

        if visibility not in items_dict[self._visibility]:
            return False
        else:
            return True

    def filterPattern(self, name):
        if not re.search(self._keyword, name, re.IGNORECASE):
            print(name + ': refused')
            return False
        else:
            print(name + ': accepted')
            return True

    def setVisibility(self, visibility: FeatureVisibility):
        self._visibility = visibility
        self.invalidateFilter()

    def setKeyword(self, keyword: str):
        self._keyword = keyword
        self.invalidateFilter()

    def filterAcceptsRow(self, src_row, src_parent: QModelIndex):
        src_model = self.sourceModel()
        src_index = src_model.index(src_row, 0, parent=src_parent)

        tree_item = src_index.internalPointer()
        name = tree_item.name
        feature = tree_item.data
        visibility = feature.visibility if feature else FeatureVisibility.Beginner
        if tree_item.child_nodes and len(tree_item.child_nodes):
            for child in tree_item.child_nodes:
                if self.filterAcceptsRow(child.row(), src_index):
                    return True
            return False
        else:
            matches = re.search(self._keyword, name, re.IGNORECASE)

        if matches:
            result = self.filterVisibility(visibility)
        else:
            result = False
        return result


class GeniCamFeatureTreeDialog(QDialog):
    on_attr_change_requested = pyqtSignal(dict)

    def __init__(self, parent, device_name, attr_dict):
        super().__init__(parent)

        self.device_name = device_name

        ui_filepath = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), 'attributes_dialog.ui'
        )

        self.layout = QHBoxLayout()
        self.setLayout(self.layout)

        self.setWindowFlags(QtCore.Qt.Tool)
        self.setWindowTitle(f"GeniCam attributes: {self.device_name}")

        self.ui = uic.loadUi(ui_filepath)
        self.ui.setParent(self)

        self.layout.addWidget(self.ui)

        self.ui.copyButton.clicked.connect(self.on_copy_clicked)
        self.ui.visibilityComboBox.currentIndexChanged.connect(self.on_attr_visibility_level_changed)

        self.model = FeatureTreeModel(parent, attr_dict)
        self.proxy = FilterProxyModel()
        self.proxy.setSourceModel(self.model)
        self.delegate = FeatureEditDelegate(proxy=self.proxy)

        self.ui.attributeTreeView.setModel(self.proxy)
        self.ui.attributeTreeView.setItemDelegate(self.delegate)
        self.ui.attributeTreeView.setUniformRowHeights(True)
        self.ui.attributeTreeView.setColumnWidth(0, 260)

        self.ui.closeButton.clicked.connect(lambda: self.accept())

        self.model.on_attribute_set.connect(self.on_attribute_set)

    def on_attr_visibility_level_changed(self, value):
        self.proxy.setVisibility(FeatureVisibility(value))

    def on_attribute_set(self, node):
        feature = node.data
        path = node.get_path_to_node()
        value = feature.value

        _dict = value
        for p in reversed(path):
            _dict = {p: _dict}

        self.on_attr_change_requested.emit(_dict)

    def on_copy_clicked(self, button):
        _visibility = self.ui.visibilityComboBox.currentIndex()

        filtered_tree = FeatureTreeNode.filter_tree(self.model.root_item,
                lambda n: n if (n.visibility.value <= _visibility and n.access_mode == FeatureAccessMode.RW) else None
                )

        filtered_tree.print()

        if filtered_tree:
            text = json.dumps(filtered_tree.dump_value_dict(), indent=4)

            clipboard = QtGui.QApplication.instance().clipboard()
            clipboard.setText(text)

    def updte_attributes(self, attr_dict):
        return self.model.update_attr_from_dict(attr_dict)

