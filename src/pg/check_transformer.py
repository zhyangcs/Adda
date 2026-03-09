import ast
import copy
from src.pg.op_type import *
import logging
from src.pg.func_utils import grab_attr_from_node

class CheckTransformer(ast.NodeTransformer):
    """
    check whether the code satisfy the rule of the pipeline
    """
    # check_fail = False
    def __init__(self, script_scope):
        """
        the script_scope should be the code circumstance before the execution of the current ast
        """
        self.script_scope = script_scope
        self.op_type = OpType(OpTypeEnum.BINARY)
        
    def split_on_bracket(self, node):
        """
        get the last function of the sequencial calling 
        example: a.groupby().agg().apply() --> a.groupby().agg().apply()
        """
        cnt = 0
        fidx = None
        fstr = ast.unparse(node)
        in_quote = False
        
        for index, char in enumerate(fstr):
            if char == "'":
                in_quote = not in_quote
            if not in_quote:
                if cnt == 0 and char == "(":
                    fidx = index
                    cnt += 1
                elif cnt != 0 and char == "(":
                    cnt += 1
                elif cnt != 0 and char == ")":
                    cnt -= 1

        return fstr[:fidx]
    
    # the visit of the child is from [leave to parent], so the calling seq is
    # df.groupby --> df.groupby.agg --> df.groupby.agg.apply
    def visit_Call(self, node):
        ast.NodeTransformer.generic_visit(self, node)
        func_string = self.split_on_bracket(copy.deepcopy(node))
        
        # print("func_string:" + func_string)
        # only make effect on the circumnstance of the function on the variable, which func has the ast.Attribute type
        if isinstance(node.func, ast.Attribute):
            try:
                module_info = eval("inspect.getmodule({})".format(func_string), self.script_scope)
            except Exception:
                module_info = None
            # print("func_string:" + func_string, module_info.__name__)
            # node.func.value.id is the name of the variable
            # node.func.attr is the name of the function
            
            if module_info is not None:
                # one should notice that declare the variable instead of call the func donot belong to the relevant category
                if module_info.__name__.startswith('sklearn.preprocessing._label') and node.func.attr == 'fit_transform':
                    self.assign_safe(OpTypeEnum.NUMERIZE)
                    self.op_type.append_relevant_cols(grab_attr_from_node(node.args[0].slice))
                    
                elif module_info.__name__.startswith('sklearn.base') and node.func.attr == 'fit_transform':
                    self.assign_safe(OpTypeEnum.NORMALIZE)
                    self.op_type.append_relevant_cols(grab_attr_from_node(node.args[0].slice))
                    scaler_module_info = eval("type({})".format(node.func.value.id), self.script_scope)
                    print("scaler_module_info:" + scaler_module_info.__name__)
                    if scaler_module_info.__name__ == 'MinMaxScaler':
                        self.op_type.parameters["scaler_type"] = NormTypeEnum.MINMAX
                    elif scaler_module_info.__name__ == 'StandardScaler':
                        self.op_type.parameters["scaler_type"] = NormTypeEnum.STANDARD
                    elif scaler_module_info.__name__ == 'RobustScaler':
                        self.op_type.parameters["scaler_type"] = NormTypeEnum.ROBUST
                    else:
                        print("Check Fail :", module_info.__name__, "variable name: " + str(node.func.value), "func name:" + node.func.attr)
                        self.op_type.assign_op(OpTypeEnum.UNSUPPORT)
                        
                elif module_info.__name__.startswith('pandas.core.reshape.encoding') and node.func.attr == 'get_dummies':
                    self.assign_safe(OpTypeEnum.GET_DUMMIES)
                    for kw in node.keywords:
                        if kw.arg == 'columns':
                            self.op_type.append_relevant_cols(grab_attr_from_node(kw.value))
                    # self.op_type.append_relevant_cols(grab_attr_from_node(node.keywords['columns']))
                    
                elif module_info.__name__.startswith('pandas.core.reshape.tile') and node.func.attr == 'qcut':
                    self.assign_safe(OpTypeEnum.DISCRETIZE)
                    self.op_type.append_relevant_cols(grab_attr_from_node(node.args[0].slice))
                    self.op_type.parameters["discretize_type"] = DiscretizeTypeEnum.QCUT
                    for kw in node.keywords:
                        if kw.arg == 'labels':
                            self.op_type.append_label_cols(grab_attr_from_node(kw.value))

                elif module_info.__name__.startswith('pandas.core.reshape.tile') and node.func.attr == 'cut':
                    # print(ast.dump(node, indent=4))
                    self.assign_safe(OpTypeEnum.DISCRETIZE)
                    self.op_type.append_relevant_cols(grab_attr_from_node(node.args[0].slice))
                    self.op_type.parameters["discretize_type"] = DiscretizeTypeEnum.CUT
                    if len(node.args) > 1:
                        self.op_type.parameters["discretize_bins"] = grab_attr_from_node(node.args[1].value)
                    for kw in node.keywords:
                        if kw.arg == 'labels':
                            self.op_type.append_label_cols(grab_attr_from_node(kw.value))
                        if kw.arg == 'bins':
                            self.op_type.parameters["discretize_bins"] = grab_attr_from_node(kw.value)
                            
                elif module_info.__name__.startswith('pandas.core.generic') and node.func.attr == 'fillna':
                    self.assign_safe(OpTypeEnum.FILLNA)
                    self.op_type.append_relevant_cols(grab_attr_from_node(node.func.value.slice))
                    
                    fillna_type = FillnaType(FillnaTypeEnum.UNSUPPORT)
                    if hasattr(node.args[0], 'func'):
                        if node.args[0].func.attr == 'median':
                            fillna_type.assign_type(FillnaTypeEnum.MEDIAN)
                        elif node.args[0].func.attr == 'mean':
                            fillna_type.assign_type(FillnaTypeEnum.MEAN)
                        elif node.args[0].func.attr == 'max':
                            fillna_type.assign_type(FillnaTypeEnum.MAX)
                        elif node.args[0].func.attr == 'min':
                            fillna_type.assign_type(FillnaTypeEnum.MIN)
                    elif hasattr(node.args[0], 'value'):
                        if hasattr(node.args[0].value, 'func'):
                            if node.args[0].value.func.attr == 'mode':
                                fillna_type.assign_type(FillnaTypeEnum.MODE)
                        else:
                            fillna_type.assign_type(FillnaTypeEnum.CONSTANT)
                            fillna_type.assign_constant(node.args[0].value)
                    else:
                        print("Check Fail :", module_info.__name__, "variable name: " + str(node.func.value), "func name:" + node.func.attr)
                        self.op_type.assign_op(OpTypeEnum.UNSUPPORT)
                        
                    self.op_type.parameters["fillna_type"] = fillna_type
                    
                elif module_info.__name__.startswith('pandas.core.series') and node.func.attr == 'apply':
                    self.assign_safe(OpTypeEnum.UNSUPPORT)
                    # self.op_type.append_relevant_cols(grab_attr_from_node(node.func.value.slice))
                    # self.op_type.parameters['apply_func_name'] = node.args[0].id
                    
                elif not module_info.__name__.startswith('pandas') or node.func.attr == 'apply':
                    print("Check Fail :", module_info.__name__, "variable name: " + str(node.func.value), "func name:" + node.func.attr)
                    self.op_type.assign_op(OpTypeEnum.UNSUPPORT)

                # get the target of the column
                parent_node = node.parent
                if type(parent_node) == ast.Assign and hasattr(parent_node.targets[0], 'slice'):
                    self.op_type.append_target_cols(grab_attr_from_node(parent_node.targets[0].slice))
                # elif type
            else:
                # contains the function the db not support, we register it by python/udf
                self.op_type.assign_op(OpTypeEnum.UNSUPPORT)
            
        return node
    
    def assign_safe(self, new_op_type: OpType):
        if self.op_type.op_type == OpTypeEnum.BINARY:
            self.op_type.assign_op(new_op_type)
        else:
            # two operation in one operator, so we log the error
            logging.critical("the comment of the pipeline maybe wrong for type [%s, %s]", self.op_type, new_op_type)