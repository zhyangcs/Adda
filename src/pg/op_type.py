import os
from enum import Enum
import copy

class OpTypeEnum(Enum):
    """
    The type of operation.
    """
    # Binary: the operation include more than one column
    BINARY = 0
    # Easy: straight convert by the pandas-to-sql (include Drop operation)
    UNARY = 1
    # Get_dummies: use encoding to convert some of the columns
    GET_DUMMIES = 2
    # nomalize: use the normalize to convert some of the columns
    NORMALIZE = 3
    # numerize: use the numerize to convert some of the columns
    NUMERIZE = 4
    # descretize: use the descretize to convert some of the columns
    DISCRETIZE = 5
    # UnSupport: the operation is not supported to convert to the sql, which could only use the c(so)/python udf to combine to the sql
    UNSUPPORT = 6
    # Train: the last operation of train the data which processed in the above
    TRAIN = 7
    # Start: the dummy node in the dag graph
    START = 8
    # Join: the join operation
    JOIN = 9
    # Fillna: the fillna operation
    FILLNA = 10
    # Predict: the last operation of predict the data which processed in the above
    PREDICT = 11
    # Apply: the apply operation (or we could say all of the unary operation)
    APPLY = 12
    # DROP: the drop operation
    DROP = 13
    # REUSE: reuse the result from the previous operation
    REUSE = 14
    # VALIDATE: validate the validate_data after the model trained on the train_data
    VALIDATE = 15
    # END
    END = 16

# record the type needed to be optimize in the 
UDF_OP_TYPE  = (OpTypeEnum.UNSUPPORT, OpTypeEnum.DISCRETIZE, OpTypeEnum.APPLY)    
# record the type would be straight convert by the pandas-to-sql
EASY_OF_TYPE = (OpTypeEnum.UNARY, OpTypeEnum.BINARY, OpTypeEnum.DROP)


class OpType:
    def __init__(self, op_type: OpTypeEnum, relevant_cols: list = [], label_cols: list = [], target_cols: list = [], parameters: dict = {}) -> None:
        """
        df["target_cols"] = encoder.fit(df["relevant_cols"], 3, ["low", "medium", "high"](which is the new_cols)))
        """
        self.op_type = op_type
        # record the operated columns
        self.relevant_cols = relevant_cols.copy()
        # record the labels of the labelEncoder
        self.label_cols = label_cols.copy()
        # record the target columns in the assignment
        self.target_cols = target_cols.copy()
        # record the parameters of the operation
        # 'fillna_type' record the na relevant msg
        self.parameters = parameters.copy()
        
    def assign_op(self, op_type: OpTypeEnum):
        self.op_type = op_type
    
    def append_relevant_cols(self, relevant_cols: list[str]):
        self.relevant_cols += relevant_cols
        
    def append_label_cols(self, label_cols: list[str]):
        self.label_cols += label_cols
    
    def append_target_cols(self, target_cols: list[str]):
        self.target_cols += target_cols
        
    def __str__(self) -> str:
        return str(self.op_type) + " " + str(self.parameters)
    
    def __copy__(self):
        return OpType(self.op_type, copy.deepcopy(self.relevant_cols), copy.deepcopy(self.label_cols), copy.deepcopy(self.target_cols), copy.deepcopy(self.parameters))

class FillnaTypeEnum(Enum):
    """
    The type of fillna operation.
    """
    # fillna with the mean of the column
    MEAN = 1
    # fillna with the median of the column
    MEDIAN = 2
    # fillna with the mode of the column
    MODE = 3
    # fillna with the constant
    CONSTANT = 4
    # fillna with the max of the column
    MAX = 5
    # fillna with the min of the column
    MIN = 6
    # Unsupport
    UNSUPPORT = 7

class FillnaType:
    def __init__(self, fill_type: FillnaTypeEnum) -> None:
        self.fill_type = fill_type
        self.constant = None
    
    def assign_constant(self, constant: str):
        self.constant = constant
    
    def assign_type(self, fill_type: FillnaTypeEnum):
        self.fill_type = fill_type
        
class NormTypeEnum(Enum):
    """
    The type of normalize operation.
    """
    # normalize with the minmax
    MINMAX = 1
    # normalize with the standard
    STANDARD = 2
    # normalize with the robust
    ROBUST = 3
    # Unsupport
    UNSUPPORT = 4

class DiscretizeTypeEnum(Enum):
    """
    The type of discretize operation.
    """
    # discretize with the qcut
    QCUT = 1
    # discretize with the cut
    CUT = 2
    # Unsupport
    UNSUPPORT = 3

class PipeTypeEnum(Enum):
    """
    the type of the whole pipeline execute
    """
    # None
    NOTHING = 1
    # Train
    TRAIN = 2
    # Predict
    PREDICT = 3
    # Validate
    VALIDATE = 4
    
    # str function
    def __str__(self):
        if self == PipeTypeEnum.NOTHING:
            return "nothing"
        elif self == PipeTypeEnum.TRAIN:
            return "train"
        elif self == PipeTypeEnum.PREDICT:
            return "predict"
        elif self == PipeTypeEnum.VALIDATE:
            return "validate"

if __name__ == "__main__":
    op1 = OpType(OpTypeEnum.EASY)
    op2 = OpType(OpTypeEnum.EASY)
    op2.append_relevant_cols(['a', 'b'])
    op2.append_target_cols(['c'])
    op3 = copy.copy(op2)
    op4 = OpType(OpTypeEnum.EASY)