from src.pg.op_type import *
from src.llm.utils.llm_util import *


REFLECTION_RULE = """
you should construct the pipeline according to the following rules:
1. You should not use for loop iteration and if operator except for function used in the pandas.apply()
2. for each pipeline operator, you should only use the function given between the ```python and ``` to represent your pipeline
3. for each function used in the pipeline, you should explictly clarify the parameter of columns if the function has the parameter of columns.
4. Instead of using one operator to replace the original column to the result of function, you should store the result of each function in a new column then drop the original column (if needed to) in the following drop operator
5. Do not use any other functions of pandas (such as pandas.DataFrame.map, pandas.DataFrame.groupby,  etc.) except for the pandas operator symbols provided above
6. For the use of the pandas. apply function, it is not expressed in the form of lambda, but is called through the function name after being defined externally
7. Ensure that each attribute of the final output dataframe is of data type int, bool, or float to ensure that the model can be trained
8. If using the sklearn, scipy, or other library, you should import the relevant function first
9. If you need to select some column with certain dtype, you should use the dataframe.select_dtypes() function
"""
# NEXT_STEP_FORMAT = """{operator_description} From now on, we have executed such code operations:
# ```python
# {executed_ops}
# ```
# Please return the next operation you want to execute from the following list, and give a very brief reason:
# Output format: {{operation name}}: {{reason for choosing this operation}}
# Unary operation: apply a function to each element in the choosen attribute.
# Binary operation: use +,-,*,/,&,|,!,>>,<< and some arithmetic operator to transform several input dataframe to one final new feature.
# Get_dummies operation: convert categorical variable into dummy/indicator variables.
# Normalization operation: create shifted and scaled versions of statistics.
# Discretize operation: transfer continuous functions, models, variables, and equations into discrete counterparts.
# Fillna operation: fill the 'nan' value in the dataset with other calculated value.
# Drop operation: drop some attributes in the input dataframe, which is not needed in the following pipeline.
# Numerization operation: transfer non numeric discrete value columns to numeric discrete value columns.
# Output example for other tasks:/*
# {output_examples}
# """
NEXT_STEP_FORMAT = """{data_desc} 
In this task, you should generate a meaningful new feature for predicting Outcome using open-world knowledge and the attribute set.
The downstream {model_type} machine learning model will be trained on the new feature you generate.
You can try to prioritize attributes that are less frequently used, if you have multiple choices at the same time.
you should execute one of the following operations to generate a new feature:
an Multiple-Elements operation: use +,-,*,/,&,|,!,>>,<< and some arithmetic operator to transform **several input features** to **one new feature**. you should generate the feature which is meaningful to the real world instead of randomly arithmetic combination of several features.
an Unary-Elements operation: use discretization or apply a custom function to transform **one input feature** to **one new feature**. 

{memory_info}
Output format:
'new_feature': the name of the new feature.
'detailed description': a description of the new feature.
'brief description': a brief description of the new feature.
'relevant': a list of relevant columns used to extract the feature (excluding attribute {y_attr}).
except the four lines above, do not generate other useless msg, including the operation type.
notice: do not generate the same feature we have generated before !!!
Moreover, do not use the target_col({y_attr}) to be the relevant column for generating the new feature.
"""

NEXT_STEP_FORMAT_SHRINK = """{data_desc} 
In this task, you should generate a meaningful new feature for predicting Outcome using open-world knowledge and the attribute set.
The downstream {model_type} machine learning model will be trained on the new feature you generate.
You can try to prioritize attributes that are less frequently used, if you have multiple choices at the same time.
you should execute one of the following operations to generate a new feature:
an Multiple-Elements operation: use +,-,*,/,&,|,!,>>,<< and some arithmetic operator to transform **several input features** to **one new feature**. you should generate the feature which is meaningful to the real world instead of randomly arithmetic combination of several features.

{memory_info}
Output format:
'new_feature': the name of the new feature.
'detailed description': a description of the new feature.
'brief description': a brief description of the new feature.
'relevant': a list of relevant columns used to extract the feature (excluding attribute {y_attr}).
except the four lines above, do not generate other useless msg, including the operation type.
notice: do not generate the same feature we have generated before !!!
"""

NEXT_STEP_FREE_OLD = """{data_desc} 
In this task, you should generate a meaningful new feature for predicting Outcome using open-world knowledge and the attribute set.
The downstream {model_type} machine learning model will be trained on the new feature you generate.
Think what High-order statistics feature could be generated in the field of current task using the given attributes.
You could use operator like add, subtract, multiply, divide, and, or, not, shift, etc, or some popular data processing method as bucketization, normalization, numerization, or apply some function to the attribute to generate the new feature.
Moreover, you could use some condition description to generate the feature more accurate, such as 'male', who drink alcohol more than 3, who do not have the diabetes, etc.

High-order Feature Example in other domain which you should generate the feature with similar complexity: we compute the cvhi by compute the standard normalized value of diabp, double of the mean of bmi who do not have the diabetes but using blood pressure medication, 
the half value of the mean value of person's systolic blood pressure whose glucose level is bigger than 13, the mean value of the sysbp, and the mean value of the summation of totchol and age.
then we sum all of the variable mentioned above with the factor of 0.5, 2, 0.5, 1, and 1 respectively, and finally divide by the bmi to be named as the parameter of tmp1.
we then compute the average value of the bmi of male who smoking 2~5 cigarettes each day, and divide by the logarithm of the summation of ones's diastolic blood pressure who do not had stroke, and multiply the result to the tmp1 as final result.

{memory_info}
Output format:
'new_feature': the name of the new feature.
'detailed description': a description of the new feature.
'brief description': a brief description of the new feature.
'relevant': a list of relevant columns used to extract the feature (excluding attribute {y_attr}).
except the four lines above, do not generate other useless msg, including the operation type or ```json wrapped.
notice: do not generate the same feature we have generated before !!!
"""


NEXT_STEP_FREE = """{data_desc} 
In this task, you should generate a meaningful new feature for predicting Outcome using open-world knowledge and the attribute set.
The downstream {model_type} machine learning model will be trained on the new feature you generate.
Think what High-order statistics feature could be generated in the field of current task using the given attributes.
You could use operator like add, subtract, multiply, divide, and, or, not, shift, etc, or some popular data processing method as bucketization, normalization, numerization, or apply some function to the attribute to generate the new feature.
Moreover, you could use some condition description to generate the feature more accurate, such as 'male', who drink alcohol more than 3, who do not have the diabetes, etc.

Here is one High-order Feature Example in other domain: we compute the cvhi by compute the standard normalized value of diabp, double of the mean of bmi who do not have the diabetes but using blood pressure medication, 
the half value of the mean value of person's systolic blood pressure whose glucose level is bigger than 13, the mean value of the sysbp, and the mean value of the summation of totchol and age.
then we sum all of the variable mentioned above with the factor of 0.5, 2, 0.5, 1, and 1 respectively, and finally divide by the bmi to be named as the parameter of tmp1.
we then compute the average value of the bmi of male who smoking 2~5 cigarettes each day, and divide by the logarithm of the summation of ones's diastolic blood pressure who do not had stroke, and multiply the result to the tmp1 as final result.

{memory_info}
Output format:
'new_feature': the name of the new feature.
'detailed description': a description of the new feature.
'brief description': a brief description of the new feature.
'relevant': a list of relevant columns used to extract the feature (excluding attribute {y_attr}).
except the four lines above, do not generate other useless msg, including the operation type or ```json wrapped.
notice: do not generate the same feature we have generated before !!!
"""



OPERATOR_FORMAT = """{operator_description}
Output format:
task description: {{task_desc}}. output attributes: {{output_attrs}}. input attributes: {{input_attrs}}.
Output example for other tasks:/*
{output_examples}
*/"""

FUNCTION_FORMAT = """{operator_description}
Output example for other tasks:/*
{output_examples}
*/"""

# List all possible appropriate operators, and your confidence levels (certain/high/medium/low).
# Return answers with low confidence level for less beneficial transformations compared to the original input feature. Use "certain" and "high" very cautiously.
NORMALIZATION_FORMAT = """Considering the normalization operation to some attribute in the input dataframe and generate the same number of new feature. Normalization refers to the creation of shifted and scaled versions of statistics, \
where the intention is that these normalized values allow the comparison of corresponding normalized values for different datasets in a way that eliminates the effects of certain gross influences. 
"""

BUCKETIZATION_FORMAT = """Considering the discretize operation to one attribute in the input dataframe and generate one new feature. Discretization refers to the process of transferring continuous functions, models, variables, and equations into discrete counterparts.
"""

GET_DUMMIES_FORMAT = """Considering the get_dummies operation to one attribute in the input dataframe and generate several new features. \
Get_dummies refers to the process of converting categorical variable into dummy/indicator variables, or means transferring a discretized feature to numerical variables.
"""

UNARY_FORMAT = """Consider the unary operation to one attribute in the input dataframe and generate one new feature. \
Unary operation refers to the process of applying a function to each element in the choosen attribute. you should describe the procedure of function in natural language as detailed as possible.
"""

BINARY_FORMAT = """Consider the multi-element operation to several attribute in the input dataframe and finally generate one new feature. \
Multi-element operation refers to the use +,-,*,/,&,|,!,>>,<< and some arithmetic operator to transform several input dataframe to one final new feature. 
you should describe the procedure of caculation for these operator in natural language as detailed as possible.
"""

FILLNA_FORMAT = """Considering the fillna operation to one attribute in the input dataframe and generate one new feature. \
Fillna refers to fill the 'nan' value in the dataset with other calculated value, such as the mean, median, mode, constant value of other nonnan attribute or itself. 
"""

DROP_FORMAT = """Considering the drop operation to some attributes in the input dataframe. \
Drop refers to drop some attributes in the input dataframe, which is not needed in the following pipeline. \
One could specify the attributes to be dropped in natural language by column name or column type.
"""

DIMENSION_REDUCTION_FORMAT = """Considering the dimension reduction operation to some attributes in the input dataframe and generate one new feature. \
Dimension reduction refers to the transformation of data from a high-dimensional space into a low-dimensional space \
so that the low-dimensional representation retains some meaningful properties of the original data, ideally close to its intrinsic dimension. \
"""

NUMERIZATION_FORMAT = """Considering the numerization operation to some attributes in the input dataframe and generate one new feature. \
Numerization refers to the process of transferring non numeric discrete value columns to numeric discrete value columns.
"""

CONVERT_FUNCTION_PROMPT = """Generate the most appropriate piece of python code to obtain new feature (output) in dataframe named `df` using old features (input).
Prioritize using Pandas's own functions. If you cannot find a suitable function that meets the requirements, then use external libraries
New feature description: {op_desc}.
New feature {output_attrs}.
Old features {input_attrs}.
Old feature descriptions: {input_desc}.
Please closely follow the provided column descriptions, considering data types and ranges.
Consider the following situiations:
(0) Check column type the guarantee the code generated could be executed
(1) If you can staightly provide the Python code, please do so. If an external function is required, include the import library before the function(pandas, numpy...). 
(2) Try do not use any extra function similar to check the type of unnecessary checking utility, just give the core operation code
(3) Better use the simple arithmetic operation to generate the new feature if could instead of pandas function.
(4) generate the code as concise as possible, and try to straightly give the column name if could instead of using function or variables
(5) **do not use** for, if and other iteration or judgement statement in the code, if you need to use the iteration or judgement statement or some function like(map, reduce), please use the pandas.apply() function
Code format:
```python
# Import necessary libraries:
import xxx
# core code definition
xxxx
```
"""

EXAMPLE_FORMAT = """task description: {task_desc}. output attribute: {output_attrs}. input attribute: {input_attrs}."""

# record the type-prompt matching template
TYPE_TO_PROMPT = {
    OpTypeEnum.UNARY: UNARY_FORMAT,
    OpTypeEnum.BINARY: BINARY_FORMAT,
    OpTypeEnum.GET_DUMMIES: GET_DUMMIES_FORMAT,
    OpTypeEnum.NORMALIZE: NORMALIZATION_FORMAT,
    OpTypeEnum.DISCRETIZE: BUCKETIZATION_FORMAT,
    OpTypeEnum.FILLNA: FILLNA_FORMAT,
    OpTypeEnum.DROP: DROP_FORMAT,
    OpTypeEnum.APPLY: UNARY_FORMAT
}

ROLE_PROMPT = """You are an expert datascientist assistant solving Kaggle problems. You answer following question only by generating natural language describing the attribute process procedure. Answer as concisely as possible."""

# Label encoding: the old feature is categorical, and we need to transform it to numerical feature
GENERATE_FIX_FEATURE_PROMPT = """{df_desc}
Do you think some preprocessing is needed for this feature? \
please return the next operation you want to execute from the following list, and give the relevant column
No need to preprocess: the old feature is good enough
Fill NaN: the old feature has too much NaN value, and we need to fill it
Normalization: the range of old feature is too large, or too skewed, and we need to normalize it
'operation_type': the type of the operation you choose
'relevant column': one relevant columns to be processed (excluding the output attr: [{output_attr}])
Output format:
'operation_type1': 'relevant column1', 'operation_type2': 'relevant column2', ...
for the format above, please give the operation_type and relevant column straightly instead of rewrite 'operation_type': Fill NaN.
Moreover, if two columns need to execute the same procedure, we should split it to two pair. for example: instead of {{}}
"""

APPLY_PYTHON2C_PROMPT = """you should convert the following python function to c++ function which use palloc to allocate the memory for the created variable.
Each Python function takes an array as input and outputs an array. The simpler the output content, the better.
python code: ```python
{python_code}
```
input feature: {input_feature}
output feature: {output_feature}

Output Format:
```c++
int64* function_name(int64* arr, int len){{
    int64* res = (int64*)palloc(len * sizeof(int64));
    // core operation for code
    return res;
}}
```
where arr is the input array and len is the length of the input array.
Output Examples:
```c++
int64* is_alone(int64* arr, int len) {{
    int64* res = (int64*)palloc(sizeof(int64) * len);
    for (int i = 0; i < len; i++) {{
        res[i] = 1;
    }}
    for (int i = 0; i < len; i++) {{
        res[i] = arr[i] == 0 ? 1 : 0;
    }}
    return res;
}}
```
```c++
int64* add_two(int64* arr, int len) {{
    int64* res = (int64*)palloc(sizeof(int64) * len);
    for (int i = 0; i < len; i++) {{
        res[i] = arr[i] + 2;
    }}
    return res;
}}
```"""

CODE_COMBINE_PROMPT = """you should combine the following code snippets into one code snippet. each snippet contains the generation of one attributes in pandas dataframe.
Considering the following rules:
1. you should guarantee the generate code should has the same effect as executing all of the original code snippets.
2. you should generate the new code with higher efficiency by eliminating the redundant code, the unneed attribute generation, and the repeated operation, and other situations.
3. you should guarantee the generated code could be executed without any error.
4. you should priority use the library instead of self defining the function
5. you should consider some attributes would be dropped finally, which you can not generate them for accelerating
here is the code snippets:
```python
{code_snippets}
```
"""
# Moreover, we also need **one** final description(Final_Combine_Step) for how combining the variables from intermediate steps to the final output variable.
# Final_Combine_Step | {{final input variables}} | {{final output variable}} | combine description
SPLIT_PROMPT = """Here is the description of operation procedure which generate new feature to a pandas dataframe.
The dataframe has some original attributes: {input_features} 
please split the whole description into several step descriptions(Intermediate_Step_i) which each step accept corresponding to some input variables and some output variables.
**Each Step could be separately executed without the knowledge of the original description, so try using the concrete number and do not assume one step acknowledge the factor or computing procedure of other steps.**
Operation procedure description: {procedure_desc}
Final Variable we need to generate: {output_feature}
each step description_i should modify the origin description as small as possible.
each step description_i and combine description should be as detailed as possible which describe how each intermediate variable in the output variable was generated.
Output format:
Intermediate_Step_i | {{input variables_i}} | {{output variables_i}} | intermediate description_i <END_INTER_STEP>"""

# Final feature description[for reference]: {final_op_desc}.
SPLIT_CONVERT_FUNCTION_PROMPT = """Generate the most appropriate piece of python code to obtain new intermidate feature (output) in dataframe named as `df[{output_attrs}]` using old features (input){input_attrs}.
The output is one of steps for generating the final feature, which the operation description would be given for enhancing the understanding of intermediate feature generation.
Prioritize using Pandas's own functions. If you cannot find a suitable function that meets the requirements, then use external libraries.

New feature description[for code generation]: {op_desc}.
New feature {output_attrs}.
Old features {input_attrs}.
Old feature descriptions: {input_desc}.
Please closely follow the provided column descriptions, considering data types and ranges.
Consider the following situiations:
(0) Check column type the guarantee the code generated could be executed
(1) If you can staightly provide the Python code, please do so. If an external function is required, include the import library before the function. 
(2) Better use the simple arithmetic operation to generate the new feature if could instead of pandas function.
(3) Otherwise, respond with 'Cannot find the function.' 
(4) generate the code as concise as possible, and try to straightly give the column name if could instead of using function or variables
(5) **do not use** for, if and other iteration or judgement statement in the code, if you need to use the iteration or judgement statement or some function like(map, reduce), please use the pandas.apply() function
Code format:
```python
# Import necessary libraries:
import xxx
# core code definition
xxxx
```
"""

extractor_function_prompt = '''Generate the most appropriate piece of python code to generate new feature based from the original features.
The output is one of steps for generating the final feature, which the operation description would be given for enhancing the understanding of intermediate feature generation.
Final feature description[for reference]: {final_op_desc}.
New feature description[for code generation]: {op_desc}.
New feature {output_attrs}.
Old features {input_attrs}.
Old feature descriptions: {input_desc}.
Please closely follow the provided column descriptions, considering data types and ranges.
Consider the following situiations:
(1) provide the Python code for the function. The data set is already stored in a map named as `cur_data` which is a dictionary of (name, [data in the list])
Output Code format:
```python
# operation to data    
xxx
```end
(2) try do not use any external library including(numpy, pandas), you should use the basic operation and keywords in orginal Python to generate the new feature
'''
# (2) Better use the if and else instead of using the logical operation in the `[]` of dataframe such as `<, >, ==, |, &, !, ... `.


SINGLE_EXAMPLE = """By Add Feature `{new_feature}` into original dataframe with attributes {original_feature}, the prediction performance of model {performance_result}."""

RAW_PROMPT = """/* Data description: {data_desc} */
In this task, you should generate one or more meaningful new features for predicting Outcome using open-world knowledge and the attribute set.
You can try to prioritize attributes that are less frequently used, if you have multiple choices at the same time.
you should execute some following operations or self-defining operator to generate one or more new feature:
Do not use the predict column to do the feature generation.
an Multiple-Elements operation: use +,-,*,/,&,|,!,>>,<< and some arithmetic operator to transform **several input features** to **some new feature**. 
and Think what High-order statistics feature could be generated in the field of current task using the given attributes.
You should generate the feature which is meaningful to the real world instead of randomly arithmetic combination of several features.

you should output the python code for procedure the original feature to generate the new feature set, with a description of each newly generated feature
"""

if __name__ == "__main__":
    task_name = ["bank", "adult", "titanic", "bar_pass", "diabetes", "bike", "abalone", "boston_house", "airfoil", "house_sale", "labor", "hepatitis", "medical"]

    