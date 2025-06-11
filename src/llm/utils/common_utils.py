import networkx as nx
import dataclasses
from src.pg.op_type import *
from sklearn.linear_model import LogisticRegression
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, plot_tree
from xgboost import XGBClassifier, XGBRegressor
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor


# this part originally for multipipe, but current abandoned
@dataclasses.dataclass
class PIPE():
    hash2resAttr: dict = dataclasses.field(default_factory=dict)
    hash2inAttr: dict = dataclasses.field(default_factory=dict)
    resAttr2isStore: dict = dataclasses.field(default_factory=dict)
    resAttr2Ti: dict = dataclasses.field(default_factory=dict)
    reusemap: dict = dataclasses.field(default_factory=dict)
    attr2OpTypeEnum: dict = dataclasses.field(default_factory=dict)
    code_path: str = ""
    pipe_id: int = -1
    
    def intersect(self, other):
        """
        intersection of two PIPEDAGNODE
        # Q: how to check whether two candidate feature is equal?
        # A: we prehash the op_tree to str_seq, and compare two seqs
        """
        return len(set(self.hash2inAttr.values()) & set(other.hash2resAttr.values()))
    
    def get_pipe_str(self) -> str:
        """
        print the store and reuse information for the pipe
        """
        pipe_str = str(self.resAttr2isStore) + "\n" + str(self.reusemap) + "\n" + str(self.code_path)

        return pipe_str

    
class PIPEDAGNODE():
    node_id: int
    
def get_model(model_type, task_type):
    # if model_type == "LR":
    #     return "LogisticRegression", LogisticRegression()
    # elif model_type == "LDA":
    #     return "LinearDiscriminantAnalysis", LinearDiscriminantAnalysis()
    # elif model_type == "KNN":
    #     return "KNeighborsClassifier", KNeighborsClassifier()
    # elif model_type == "CART":
    #     return "DecisionTreeClassifier", DecisionTreeClassifier(random_state=42)
    # elif model_type == "NB":
    #     return "GaussianNB", GaussianNB()
    # elif model_type == "SVM":
    #     return "SVC", SVC(random_state=42)
    # elif model_type == "RF":
    #     return "RandomForestClassifier", RandomForestClassifier(random_state=42)
    # elif model_type == "ET":
    #     return "ExtraTreesClassifier", ExtraTreesClassifier(random_state=42)
    # elif model_type == "XGB":
    #     return "XGBClassifier", XGBClassifier(random_state=42)
    # elif model_type == "LGBM":
    #     return "LGBMClassifier", LGBMClassifier(random_state=42)    
    
    assert model_type in ["CART", "RF", "ET", "XGB", "LGBM", "all"]
    assert task_type in ["classify", "regression"]
    if task_type == "classify":
        if model_type == "CART":
            return "DecisionTreeClassifier", DecisionTreeClassifier(random_state=42)
        elif model_type == "RF":
            return "RandomForestClassifier", RandomForestClassifier(random_state=42)
        elif model_type == "ET":
            return "ExtraTreesClassifier", ExtraTreesClassifier(random_state=42)
        elif model_type == "XGB":
            return "XGBClassifier", XGBClassifier(random_state=42)
        elif model_type == "LGBM":
            return "LGBMClassifier", LGBMClassifier(random_state=42)
        elif model_type == "all":
            return "", [DecisionTreeClassifier(random_state=42), RandomForestClassifier(random_state=42), ExtraTreesClassifier(random_state=42), XGBClassifier(random_state=42), LGBMClassifier(random_state=42)]
    elif task_type == "regression":
        if model_type == "CART":
            return "DecisionTreeRegressor", DecisionTreeRegressor(random_state=42)
        elif model_type == "RF":
            return "RandomForestRegressor", RandomForestRegressor(random_state=42)
        elif model_type == "ET":
            return "ExtraTreesRegressor", ExtraTreesRegressor(random_state=42)
        elif model_type == "XGB":
            return "XGBRegressor", XGBRegressor(random_state=42)
        elif model_type == "LGBM":
            return "LGBMRegressor", LGBMRegressor(random_state=42)
        elif model_type == "all":
            return "", [DecisionTreeRegressor(random_state=42), RandomForestRegressor(random_state=42), ExtraTreesRegressor(random_state=42), XGBRegressor(random_state=42), LGBMRegressor(random_state=42)]
        
def modeltype2importcode(model_type:str, task_type:str):
    if task_type == "classify":
        if model_type == "CART":
            return "from sklearn.tree import DecisionTreeClassifier"
        elif model_type == "RF":
            return "from sklearn.ensemble import RandomForestClassifier"
        elif model_type == "ET":
            return "from sklearn.ensemble import ExtraTreesClassifier"
        elif model_type == "XGB":
            return "from xgboost import XGBClassifier"
        elif model_type == "LGBM":
            return "from lightgbm import LGBMClassifier"
    else:
        if model_type == "CART":
            return "from sklearn.tree import DecisionTreeRegressor"
        elif model_type == "RF":
            return "from sklearn.ensemble import RandomForestRegressor"
        elif model_type == "ET":
            return "from sklearn.ensemble import ExtraTreesRegressor"
        elif model_type == "XGB":
            return "from xgboost import XGBRegressor"
        elif model_type == "LGBM":
            return "from lightgbm import LGBMRegressor"

def modeltype2class(model_type:str, task_type:str):
    if task_type == "classify":
        if model_type == "CART":
            return "DecisionTreeClassifier"
        elif model_type == "RF":
            return "RandomForestClassifier"
        elif model_type == "ET":
            return "ExtraTreesClassifier"
        elif model_type == "XGB":
            return "XGBClassifier"
        elif model_type == "LGBM":
            return "LGBMClassifier"
    else:
        if model_type == "CART":
            return "DecisionTreeRegressor"
        elif model_type == "RF":
            return "RandomForestRegressor"
        elif model_type == "ET":
            return "ExtraTreesRegressor"
        elif model_type == "XGB":
            return "XGBRegressor"
        elif model_type == "LGBM":
            return "LGBMRegressor"
    
        