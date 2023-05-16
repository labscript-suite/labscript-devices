from genicam.genapi import NodeMap
from genicam.genapi import EInterfaceType, EAccessMode, EVisibility

from ._feature_value_tuple import (FeatureValueTuple, FeatureType,
                                   FeatureAccessMode, FeatureVisibility)

from ._tree import TreeNode

_readable_nodes = [
    EInterfaceType.intfIBoolean,
    EInterfaceType.intfIEnumeration,
    EInterfaceType.intfIFloat,
    EInterfaceType.intfIInteger,
    EInterfaceType.intfIString,
    EInterfaceType.intfIRegister,
]

_readable_access_modes = [EAccessMode.RW, EAccessMode.RO]


def populate_feature_value_tuple(feature):
    interface_type = feature.node.principal_interface_type
    value = None
    if interface_type in [EInterfaceType.intfIBoolean,
                          EInterfaceType.intfIFloat,
                          EInterfaceType.intfIInteger]:
        value = feature.value
    else:
        try:
            value = str(feature.value)
        except AttributeError:
            try:
                value = feature.to_string()
            except AttributeError:
                return None

    visibility = feature.node.visibility
    access_mode = feature.node.get_access_mode()
    entries = None
    if interface_type == EInterfaceType.intfIEnumeration:
        entries = [ item.symbolic for item in feature.entries ]

    return FeatureValueTuple(
            name=feature.node.display_name,
            value=value,
            type=FeatureType(int(interface_type)),
            entries=entries,
            access_mode=FeatureAccessMode(int(access_mode)),
            visibility=FeatureVisibility(int(visibility))
            )


class GeniCamFeatureTreeNode(TreeNode):
    def __init__(self, name, parent_node=None, data=None, child_nodes=None):
        super().__init__(name, parent_node, data, child_nodes)

    @property
    def feature(self):
        return self.data

    @classmethod
    def get_tree_from_genicam_root_node(cls, root_node):
        root = cls("Root", child_nodes={})
        features = root_node.features

        cls.populate_feature_tree(features, root)

        return root

    @classmethod
    def populate_feature_tree(cls, features, parent_item):
        for feature in features:
            interface_type = feature.node.principal_interface_type

            if interface_type == EInterfaceType.intfICategory:
                item = cls(feature.node.display_name, parent_node=parent_item, child_nodes={})
                cls.populate_feature_tree(feature.features, item)
            else:
                item = cls(feature.node.display_name, parent_node=parent_item, data=feature)

            parent_item.add_child(item)

    @staticmethod
    def _eval_feature(feature):
        value_tuple = populate_feature_value_tuple(feature)

        return value_tuple

    def __getitem__(self, k):
        if self.child_nodes:
            return self.child_nodes[k]
        else:
            raise KeyError(f"Node `{self.name}` is a data node that has no children.")

    def set_attributes(self, attr_dict, set_if_changed=False):
        return self._set_attributes(attr_dict, [], set_if_changed)

    def _set_attributes(self, attr_dict, parent_paths, set_if_changed=False):
        for k in attr_dict.keys():
            v = attr_dict[k]
            if isinstance(v, dict):
                attr_dict[k] = self._set_attributes(v, parent_paths + [k])
            else:
                feature = self.access(parent_paths + [k]).data

                interface_type = feature.node.principal_interface_type

                try:
                    if interface_type == EInterfaceType.intfICommand:
                        if v:
                            feature.execute()
                    elif interface_type == EInterfaceType.intfIBoolean:
                        _v = True if v.lower() == 'true' else False
                        if not set_if_changed or feature.value != _v:  # what's the point of doing this? should I cache?
                            feature.value = _v
                    elif interface_type == EInterfaceType.intfIFloat:
                        _v = float(v)
                        if not set_if_changed or feature.value != _v:
                            feature.value = _v
                    else:
                        if not set_if_changed or feature.value != v:
                            feature.value = v

                except Exception:
                    pass

                if interface_type == EInterfaceType.intfICommand:
                    attr_dict[k] = False
                else:
                    attr_dict[k] = feature.value

        return attr_dict

    def filter_tree_with_visibility(self, visibility=None, must_writable=False):
        visibility = EVisibility.Guru if visibility is None else visibility

        if isinstance(visibility, str):
            _visibility = {
                    "beginner": EVisibility.Beginner,
                    "expert": EVisibility.Expert,
                    "guru": EVisibility.Guru
                    }[visibility.lower()]
        else:
            _visibility = visibility

        filtered_tree = GeniCamFeatureTreeNode.filter_tree(
                self,
                lambda n: n if (int(n.node.visibility) <= int(_visibility) and ((n.node.get_access_mode() == EAccessMode.RW) \
                        if must_writable else (n.node.get_access_mode() in [EAccessMode.RO, EAccessMode.RW]))) else None
                )

        return filtered_tree

    def dump_value_dict(self, visibility=None, writable=False):
        filtered_tree = self.filter_tree_with_visibility(visibility, writable)

        if filtered_tree:
            value_tree = TreeNode.eval_tree(filtered_tree,
                                                          lambda node: self._eval_feature(node).value)
            return value_tree.dump_value_dict()
        else:
            return {}

    def dump_value_tuple_dict(self, visibility=None, writable=False):
        filtered_tree = self.filter_tree_with_visibility(visibility, writable)

        if filtered_tree:
            value_tree = TreeNode.eval_tree(filtered_tree, self._eval_feature)
            return value_tree.dump_value_dict()
        else:
            return {}
