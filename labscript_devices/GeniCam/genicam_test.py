from harvesters.core import Harvester
import numpy as np

from genicam.genapi import NodeMap
from genicam.genapi import EInterfaceType, EAccessMode, EVisibility

import textwrap

class TreeItem(object):
    _readable_nodes = [
        EInterfaceType.intfIBoolean,
        EInterfaceType.intfIEnumeration,
        EInterfaceType.intfIFloat,
        EInterfaceType.intfIInteger,
        EInterfaceType.intfIString,
        EInterfaceType.intfIRegister,
    ]

    _readable_access_modes = [EAccessMode.RW, EAccessMode.RO]

    def __init__(self, data=None, parent_item=None):
        #
        super().__init__()

        #
        self._parent_item = parent_item
        self._own_data = data
        self._child_items = []

    def print(self, indent=0):
        feature, name, interface_type, access_mode, value, entries = self.data()

        if interface_type == -1 or access_mode == -1:
            print(textwrap.indent(f"[----] {name}, {value}", '    '*indent))
        elif entries:
            print(textwrap.indent(f"[{str(EAccessMode(access_mode))} {str(EInterfaceType(interface_type))}] {name}, {value} ({entries})", '    '*indent))
        else:
            print(textwrap.indent(f"[{str(EAccessMode(access_mode))} {str(EInterfaceType(interface_type))}] {name}, {value}", '    '*indent))

        for child in self._child_items:
            child.print(indent+1)

    def dump_tree(self):
        _dict = {}

        feature, name, interface_type, access_mode, value, entries = self.data()

        if self._child_items:
            for child in self._child_items:
                _name, feat = child.dump_tree()
                _dict[_name] = feat
        else:
            return name, feature

        return name, _dict

    @property
    def parent_item(self):
        return self._parent_item

    @property
    def own_data(self):
        return self._own_data

    @property
    def child_items(self):
        return self._child_items

    def appendChild(self, item):
        self.child_items.append(item)

    def child(self, row):
        return self.child_items[row]

    def childCount(self):
        return len(self.child_items)

    def columnCount(self):
        try:
            ret = len(self.own_data)
        except TypeError:
            ret = 1
        return ret

    def data(self):
        if isinstance(self.own_data[0], str):
            return None, self.own_data[0], -1, -1, self.own_data[1], []

        feature = self.own_data[0]
        name = feature.node.display_name

        value = ''

        interface_type = feature.node.principal_interface_type

        access_mode = feature.node.get_access_mode()

        entries = []

        if interface_type != EInterfaceType.intfICategory:
            if interface_type == EInterfaceType.intfICommand:
                value = '[Click here]'
            else:
                if feature.node.get_access_mode() not in \
                        self._readable_access_modes:
                    value = '[Not accessible]'
                elif interface_type not in self._readable_nodes:
                    value = '[Not readable]'
                else:
                    try:
                        value = str(feature.value)
                    except AttributeError:
                        try:
                            value = feature.to_string()
                        except AttributeError:
                            pass

            if interface_type == EInterfaceType.intfIEnumeration:
                entries = [ item.symbolic for item in feature.entries ]

        return feature, name, interface_type, access_mode, value, entries

    def parent(self):
        return self._parent_item

    def row(self):
        if self._parent_item:
            return self._parent_item.child_items.index(self)

        return 0


def populateTreeItems(features, parent_item):
    for feature in features:
        interface_type = feature.node.principal_interface_type
        item = TreeItem([feature, feature], parent_item)
        parent_item.appendChild(item)
        if interface_type == EInterfaceType.intfICategory:
            populateTreeItems(feature.features, item)

def populateTreeItemsDict(features):
    _dict = {}

    for feature in features:
        interface_type = feature.node.principal_interface_type
        name = feature.node.display_name

        _dict[name] = feature

        if interface_type == EInterfaceType.intfICategory:
            _dict[name] = populateTreeItems(feature.features, item)

    return _dict


if __name__ == "__main__":
    h = Harvester()
    h.add_file('/home/gengyd/Downloads/Vimba_6_0/VimbaGigETL/CTI/x86_64bit/VimbaGigETL.cti')
    h.update()

    assert len(h.device_info_list) == 1

    print(h.device_info_list)

    ia = h.create(0)

    root = TreeItem(('Feature Name', 'Value'))

    ia.remote_device.node_map.ImageFormat.PixelFormat = "Mono10"

    # populateTreeItems(ia.remote_device.node_map.Root.features, root)
    print(populateTreeItemsDict(ia.remote_device.node_map.Root.features))


    #root.print()
    #feat_dict = root.dump_tree()[1]

    #print(feat_dict["ImageFormat"]["PixelFormat"].value)
    #feat_dict["ImageFormat"]["PixelFormat"].value = "Mono10"
    #print(feat_dict["ImageFormat"]["PixelFormat"].value)


