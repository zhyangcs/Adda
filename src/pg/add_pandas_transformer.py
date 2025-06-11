import ast
import copy

class AddPandasTransformer(ast.NodeTransformer):
    """
    find all the attributes of pandas appear in the code
    """
    def __init__(self, df_name:str):
        self.df_name = df_name
        self.attrs = set()

    def visit_Subscript(self, node):
        """
        for code like df['a'], df[['a', 'b']]
        for the first, the ast would like
            Subscript(
                value=Name(id='df', ctx=Load()),
                slice=Constant(value='a'),
                ctx=Load()
            )
        for the second, the ast would like
            Subscript(
                value=Name(id='df', ctx=Load()),
                slice=List(
                    elts=[
                        Constant(value='a'),
                        Constant(value='b')
                    ],
                    ctx=Load()
                ),
                ctx=Load()
            )
        """
        if isinstance(node.value, ast.Name):
            if hasattr(node.slice, 'value'):
                # print(node.value.id, node.slice.value)
                if node.value.id == self.df_name:
                    self.attrs.add(node.slice.value)
            elif hasattr(node.slice, 'elts'):
                # print(node.slice.elts)
                for item in node.slice.elts:
                    if node.value.id == self.df_name:
                        self.attrs.add(item.value)
        self.generic_visit(node)

    def visit_Attribute(self, node):
        
        self.generic_visit(node)

    def get_attrs(self) -> list:
        return list(self.attrs)