import ast

class AddParentTransformer(ast.NodeTransformer):
    def __init__(self):
        self.current_parent = None

    def generic_visit(self, node):
        # old_parent = self.current_parent
        # self.current_parent = node

        for child in ast.iter_child_nodes(node):
            child.parent = node
            self.visit(child)

        # self.current_parent = old_parent
        return node