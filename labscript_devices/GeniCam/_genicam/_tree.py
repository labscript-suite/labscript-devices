import textwrap
from collections import OrderedDict


class TreeNode:
    def __init__(self, name, parent_node=None, data=None, child_nodes=None):
        self.parent_node = parent_node
        self.name = name
        self.data = data
        self.child_nodes = child_nodes  # is a dict

        assert (data is None or child_nodes is None), \
                "A tree node can't has both data and children."

    @classmethod
    def _get_new_child_container(cls):
        return {}

    def _get_child_nodes_iterable(self):
        return self.child_nodes.values()

    def __getitem__(self, k):
        if self.child_nodes:
            return self.child_nodes[k]
        else:
            raise KeyError(f"Node `{self.name}` is a data node that has no children.")

    def access(self, keys):
        node = self
        for key in keys:
            node = node[key]
        return node

    def get_path_to_node(self):
        if self.parent_node:
            return self.parent_node.get_path_to_node() + [self.name]
        else:
            return []

    def print(self, repr_func=None, indent=0):
        if self.data:
            if repr_func:
                print(textwrap.indent(f"[{self.name}]", '    '*indent), repr_func(self.data))
            else:
                print(textwrap.indent(f"[{self.name}]", '    '*indent), self.data)
        else:
            print(textwrap.indent(f"[{self.name}]", '    '*indent))
            for child in self._get_child_nodes_iterable():
                child.print(repr_func, indent+1)

    @classmethod
    def eval_tree(cls, tree, eval_func, parent_node=None):
        if tree.data:
            data = eval_func(tree.data)
            assert data is not None
            return cls(tree.name, parent_node, data=data)
        else:
            node = cls(tree.name, parent_node=parent_node, data=None, child_nodes=cls._get_new_child_container())
            for child in tree._get_child_nodes_iterable():
                node.add_child(cls.eval_tree(child, eval_func, node))

            return node

    @classmethod
    def filter_tree(cls, tree, filter_func, parent_node=None):
        if tree.data is not None:
            data = filter_func(tree.data)
            if data is not None:
                return TreeNode(tree.name, parent_node, data=filter_func(tree.data))
            else:
                return None
        else:
            node = cls(tree.name, parent_node=parent_node, data=None, child_nodes=cls._get_new_child_container())
            for child in tree._get_child_nodes_iterable():
                ret = cls.filter_tree(child, filter_func, node)
                if ret:
                    node.add_child(cls.filter_tree(child, filter_func, node))

            if len(node.child_nodes):
                return node
            else:
                return None

    def dump_value_dict(self, dump_func=None):
        if self.data is not None:
            if dump_func:
                return dump_func(self.data)
            else:
                return self.data
        else:
            child_nodes = {}
            if self.child_nodes:
                for child in self._get_child_nodes_iterable():
                    value = child.dump_value_dict(dump_func)
                    if value is not None:
                        child_nodes[child.name] = value

            return child_nodes

    def add_child(self, child):
        if self.data:
            raise KeyError(f"Node `{self.name}` is a data node.")

        self.child_nodes[child.name] = child


class OrderedTreeNode(TreeNode):

    @classmethod
    def _get_new_child_container(cls):
        return []

    def _get_child_nodes_iterable(self):
        return self.child_nodes

    def add_child(self, child):
        if self.data:
            raise KeyError(f"Node `{self.name}` is a data node.")

        self.child_nodes.append(child)

    def __getitem__(self, k):
        if self.child_nodes:
            ret = list(filter(lambda node: node.name == k, self.child_nodes))
            assert len(ret), f"Item `{k}` doesn't exist."
            assert len(ret) == 1, f"More than one item `{k}` was found."

            return ret[0]
        else:
            raise KeyError(f"Node `{self.name}` is a data node that has no children.")

    def print(self, repr_func=None, indent=0):
        if self.data:
            if repr_func:
                print(textwrap.indent(f"[{self.name}]", '    '*indent), repr_func(self.data))
            else:
                print(textwrap.indent(f"[{self.name}]", '    '*indent), self.data)
        else:
            print(textwrap.indent(f"[{self.name}]", '    '*indent))
            for child in self.child_nodes:
                child.print(repr_func, indent+1)
