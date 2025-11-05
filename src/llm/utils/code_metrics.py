import re
import ast
import numpy as np
from src.llm.utils.prompt import *
from src.pg.func_utils import *
"""
This class is for computing the evaluating metrics for the split of the NL description for higher code generation acc
"""
class CodeMetrics():
    def __init__(self, code, column_names):
        self.code = code
        self.column_names = column_names
        
    def get_metrics(self):
        return {
            # 'AST_DEPTH': self.get_ast_depth(),
            # 'SCHEMA_MATCHING_HARDNESS': self.get_schema_matching_hardness(),
            # 'HALSTEAD_COMPLEXITY': self.get_halstead_complexity(),
            'CLYCOMATIC_COMPLEXITY': self.get_cyclomatic_complexity(),
        }
        
    def get_ast_depth(self):
        class ASTDepthVisitor(ast.NodeVisitor):
            def __init__(self):
                self.cur_depth = 0
                self.max_depth = 0
                
            def visit(self, node):
                self.cur_depth += 1
                self.max_depth = max(self.max_depth, self.cur_depth)
                super().visit(node)
                self.cur_depth -= 1
                
        ast_tree = ast.parse(self.code)
        depth_visitor = ASTDepthVisitor()
        depth_visitor.visit(ast_tree)
        return depth_visitor.max_depth
    
    def get_schema_matching_hardness(self):
        """
        return (attr appear in code, total schema attr)
        """
        appear_attr = 0
        for col in self.column_names:
            pattern = fr"(\"{col}\")|(\'{col}\')"
            if re.search(pattern, self.code):
                appear_attr += 1

        return (appear_attr, len(self.column_names))
    
    def get_halstead_complexity(self):
        """
        Halstead complexity metrics
        """
        class HalsteadVisitor(ast.NodeVisitor):
            def __init__(self):
                self.operators_num = 0
                self.operands_num = 0
                self.unique_operators = set()
                self.unique_operands = set()
                
            def visit_Name(self, node):
                if node.id != "df":
                    self.operands_num += 1
                    self.unique_operands.add(node.id)
                # super().visit(node)
                self.generic_visit(node)
                
            def visit_Constant(self, node: ast.Constant):
                self.operands_num += 1
                self.unique_operands.add(node.value)
                # super().visit(node)
                self.generic_visit(node)
                
            def visit_Call(self, node: ast.Call):
                self.operators_num += 1
                self.unique_operators.add(node.func.attr)
                # super().visit(node)
                self.generic_visit(node)

            def visit(self, node):
                if isinstance(node, ast.BinOp):
                    self.operators_num += 1
                    self.unique_operators.add(type(node.op))
                super().visit(node)
                
        halstead_visitor = HalsteadVisitor()
        halstead_visitor.visit(ast.parse(self.code))
        n1 = len(halstead_visitor.unique_operators)
        n2 = len(halstead_visitor.unique_operands)
        N1 = halstead_visitor.operators_num
        N2 = halstead_visitor.operands_num
        
        D = (n1 / 2) * (N2 / n2)   
        V = (N1 + N2) * np.log2(n1 + n2)
        # V = 1
        # print(termcolor.colored(f"uni op: {n1}, uni var: {n2}, op: {N1}, var: {N2}, D: {D}, V: {V}", "red"))
        return D * V
    
    def get_cyclomatic_complexity(self):
        """
        Compute the Cyclomatic complexity of the code:
        Except for the forloop and branch statement, we also consider the hidden complexity in the function or subscription of pandas
        """
        if not self.code or not self.code.strip():
            return 1  # Empty or whitespace-only code has minimal complexity

        try:
            class CyclomaticVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.complexity = 1
                    self.subscript_num = 0

                def visit(self, node):
                    name = node.__class__.__name__
                    if name in ('Try', 'TryExcept'):
                        self.complexity += len(node.handlers) + bool(node.orelse)
                    elif name == 'BoolOp':
                        self.complexity += len(node.values) - 1
                    elif name in ('If', 'IfExp'):
                        self.complexity += 1
                    elif name in ('For', 'While', 'AsyncFor'):
                        self.complexity += 1
                    elif name == 'comprehension':
                        self.complexity += len(node.ifs) + 1
                    super().visit(node)

                def visit_Call(self, node):
                    func_name = self.get_func_name(node.func)
                    # add the complexity for hidden for loop logical
                    if func_name in ('mean', 'sum', 'std', 'count', 'avg', 'groupby', 'between', 'max', 'min', 'value_count', 'transform', 'cut'):
                        self.complexity += 1
                    self.generic_visit(node)

                def visit_Subscript(self, node: ast.Subscript):
                    self.subscript_num += 1
                    self.generic_visit(node)
                    self.subscript_num -= 1

                def visit_Compare(self, node):
                    if self.subscript_num > 0:
                        self.complexity += len(node.ops)
                    self.generic_visit(node)

                def visit_UnaryOp(self, node: ast.UnaryOp):
                    if self.subscript_num > 0:
                        self.complexity += 1
                    self.generic_visit(node)

                def get_func_name(self, node):
                    if isinstance(node, ast.Name):
                        return node.id
                    if isinstance(node, ast.Attribute):
                        return node.attr
                    return ""

            cyclomatic_visitor = CyclomaticVisitor()
            cyclomatic_visitor.visit(ast.parse(self.code))
            return cyclomatic_visitor.complexity

        except (SyntaxError, ValueError, TypeError) as e:
            # If code cannot be parsed or has syntax errors, return a reasonable default
            print(f"Warning: Could not compute complexity for code due to {type(e).__name__}: {e}")
            return 5  # Return a moderate complexity for problematic code
        except Exception as e:
            # Handle any other unexpected errors
            print(f"Warning: Unexpected error computing complexity: {e}")
            return 1
    
    
def whether_code_complex(code, column_names):
    """
    Check the code whether too complex. If so, split the code for futher generation
    """
    metrics = CodeMetrics(code, column_names)
    metrics_dict = metrics.get_metrics()
    print(termcolor.colored(f"Metrics: {metrics_dict}", "red"))
    if metrics_dict['CLYCOMATIC_COMPLEXITY'] >= 10:
        return True
    return False

def get_code_complexity(code):
    """
    Get the code complexity
    """
    try:
        if not code or not code.strip():
            return 1

        metrics = CodeMetrics(code, [])
        metrics_dict = metrics.get_metrics()

        # Ensure we always get a numeric value
        complexity = metrics_dict.get('CLYCOMATIC_COMPLEXITY')
        if complexity is None or not isinstance(complexity, (int, float)):
            print(f"Warning: Invalid complexity value {complexity}, using default")
            return 1

        return int(complexity) if isinstance(complexity, bool) else complexity

    except Exception as e:
        print(f"Warning: Error computing code complexity: {e}")
        return 1  # Return minimal complexity as fallback

    
if __name__ == "__main__":
    # see code metrics of each snippets
    code = """# Import necessary libraries:
import pandas as pd

# core code definition
df['norm_diabp'] = (df['diabp'] - df['diabp'].mean()) / df['diabp'].std()
# Import necessary libraries:
import pandas as pd

# core code definition
df['mean_bmi_no_diabetes_bpmeds'] = 2 * df[(df['diabetes'] == 0) & (df['bpmeds'] == 1)]['bmi'].mean()
# Import necessary libraries:
import pandas as pd

# core code definition
df['mean_sysbp_glucose_above_13'] = df[df['glucose'] > 13].groupby('glucose')['sysbp'].mean() / 2
# Import necessary libraries:
import pandas as pd

# core code definition
df['mean_sysbp'] = df['sysbp'].mean()
# Import necessary libraries:
import pandas as pd

# core code definition
df['mean_sum_totchol_age'] = df[['age', 'totchol']].sum(axis=1).mean()
# Import necessary libraries:
import pandas as pd

# core code definition
df['tmp1'] = (df['norm_diabp'] + 2*df['mean_bmi_no_diabetes_bpmeds'] + 0.5*df['mean_sysbp_glucose_above_13'] + df['mean_sysbp'] + df['mean_sum_totchol_age']) / df['bmi']
# Import necessary libraries:
import numpy as np

# core code definition
df['avg_bmi_male_smoke_2_50'] = df[(df['gender'] == 'male') & (df['cigsperday'].between(2, 50))]['bmi'].mean()
# Import necessary libraries:
import numpy as np

# core code definition
df['log_sum_diabp_no_stroke'] = np.log(df[df['prevalentstroke'] == 0]['diabp'].sum())
# Import necessary libraries:
import pandas as pd

# core code definition
df['cvhi'] = (df['tmp1'] * df['avg_bmi_male_smoke_2_50']) / df['log_sum_diabp_no_stroke']"""
    
    code_list = code.split("# Import necessary libraries:")
    code_list_combine_2 = [code_list[i] + code_list[i+1] for i in range(len(code_list)-1)]
    for code in code_list_combine_2:
        if code.strip() == "":
            continue
        column_names = re.findall(r"'(\w+)'", code)
        metrics = CodeMetrics(code, column_names)
        print(termcolor.colored(f"{code}", "yellow"))
        print(metrics.get_metrics())
    
    
#     code = """# Import necessary libraries:
# import pandas as pd

# # core code definition
# df['CVHI'] = df['bmi'] * 2 + df['glucose'] * 3 + 2 + 3
# """

#     code2 = """# Import necessary libraries:
# import pandas as pd

# # Check if columns are numeric
# numeric_cols = ['MP', '3P', 'AST', 'FG', 'FT', 'TOV', 'DRB%', 'FGA', 'FTA', 'TRB', 'ORB', 'STL', 'BLK', 'PF', 'lg_FT', 'lg_PF', 'lg_AST', 'lg_FG', 'lg_FTA', 'lg_ORB', 'lg_FGA', 'lg_TO', 'lg_TRB', 'lg_PTS', 'team_AST', 'team_FG']
# if not all(df[col].dtype in (int, float) for col in numeric_cols):
#     raise ValueError("Columns must be numeric.")

# # Define constants
# factor = (2 / 3) - (0.5 * (df['lg_AST'] / df['lg_FG'])) / (2 * (df['lg_FG'] / df['lg_FT']))
# VOP = df['lg_PTS'] / (df['lg_FGA'] - df['lg_ORB'] + df['lg_TO'] + 0.44 * df['lg_FTA'])
# DRB_perc = (df['lg_TRB'] - df['lg_ORB']) / df['lg_TRB']

# # Calculate uPER
# df['uper'] = (1 / df['MP']) * (
#     3 * df['3P']
#     + (2 / 3) * df['AST']
#     + (2 - factor * (df['team_AST'] / df['team_FG'])) * df['FG']
#     + (df['FT'] * 0.5 * (1 + (1 - (df['team_AST'] / df['team_FG'])) + (2 / 3) * (df['team_AST'] / df['team_FG'])))
#     - VOP * df['TOV']
#     - VOP * DRB_perc * (df['FGA'] - df['FG'])
#     - VOP * 0.44 * (0.44 + (0.56 * DRB_perc)) * (df['FTA'] - df['FT'])
#     + VOP * (1 - DRB_perc) * (df['TRB'] - df['ORB'])
#     + VOP * DRB_perc * df['ORB']
#     + VOP * df['STL']
#     + VOP * DRB_perc * df['BLK']
#     - df['PF'] * ((df['lg_FT'] / df['lg_PF']) - 0.44 * (df['lg_FTA'] / df['lg_PF']) * VOP)
# )
#     """
#     column_names = ['bmi', 'glucose']
#     column_names2 = ['MP', '3P', 'AST', 'FG', 'FT', 'TOV', 'DRB%', 'FGA', 'FTA', 'TRB', 'ORB', 'STL', 'BLK', 'PF', 'lg_FT', 'lg_PF', 'lg_AST', 'lg_FG', 'lg_FTA', 'lg_ORB', 'lg_FGA', 'lg_TO', 'lg_TRB', 'lg_PTS', 'team_AST', 'team_FG']
#     metrics = CodeMetrics(code, column_names)
#     print(metrics.get_metrics())
    
#     metrics2 = CodeMetrics(code2, column_names2)
#     print(metrics2.get_metrics())
    
#     procedure = """{we compute the cvhi by compute the standard normalized value of diabp, double of the mean of bmi who do not have the diabetes but using blood pressure medication, 
# the half value of the mean value of person's systolic blood pressure whose glucose level is bigger than 13, the mean value of the sysbp, and the mean value of the summation of totchol and age.
# then we sum all of the variable mentioned above with the factor of 0.5, 2, 0.5, 1, and 1 respectively, and finally divide by the bmi to be named as the parameter of tmp1.
# we then compute the average value of the bmi of male who smoking 2~5 cigarettes each day, and divide by the logarithm of the summation of ones's diastolic blood pressure who do not had stroke, and multiply the result to the tmp1.}"""
#     input_features = """gender: male or female (Boolean, True-male),
# age: Age of the patient (Integer),
# education: the education level of the patient (Categorical-Integer),
# currentsmoker: whether or not the patient is a current smoker (Boolean),
# cigsperday: the number of cigarettes that the person smoked on average in one day(Integer),
# bpmeds: whether or not the patient was on blood pressure medication (Boolean),
# prevalentstroke: whether or not the patient had previously had a stroke (Boolean),
# prevalenthyp: whether or not the patient was hypertensive (Boolean),
# diabetes: whether or not the patient had diabetes (Boolean),
# totchol: total cholesterol level (RealNumber),
# sysbp: systolic blood pressure (RealNumber),
# diabp: diastolic blood pressure (RealNumber),
# bmi: Body Mass Index (RealNumber),
# heartrate: heart rate (RealNumber),
# glucose: glucose level (RealNumber),
# tenyearchd: 10 year risk of coronary heart disease CHD (binary: “1” means “Yes” “0” means “No”)"""
#     split_prompt = SPLIT_PROMPT.format(procedure_desc=procedure, input_features=input_features)
#     print(split_prompt)
    