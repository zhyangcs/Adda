import pandas as pd
import pandas
import operator

class DataFrameWrapper():
    def __init__(self, df:pd.DataFrame, read_set:set = set(), write_set:set = set()) -> None:
        self.df = df
        # print('-----------------start---------------------', read_set, write_set)
        self.read_set = read_set
        self.write_set = write_set
        # print(self.read_set, self.write_set)
        
    @staticmethod
    def get_attr_for_df_pandas_if_needed(obj):
        if isinstance(obj, DataFrameWrapper):
            return object.__getattribute__(obj, 'df'), object.__getattribute__(obj, 'read_set'), object.__getattribute__(obj, 'write_set')
        else:
            return obj, set(), set()
    @staticmethod
    def add_to_set(my_set:set, key):
        # print("--------------add to set--------------: ", key, my_set)
        if type(key) != list:
            my_set.add(key)
        else:
            my_set.update(key)
    
        
    def __getitem__(self, key):
        # print("--------------get item--------------: ", key)
        DataFrameWrapper.add_to_set(self.read_set, key)
        return DataFrameWrapper(self.df[key], self.read_set, self.write_set)
    
    def __setitem__(self, key, value):
        # print("--------------set item--------------: ", key, value)
        DataFrameWrapper.add_to_set(self.write_set, key)
        self.df[key], _, _ = DataFrameWrapper.get_attr_for_df_pandas_if_needed(value)
        
    def __delitem__(self, key):
        del self.df[key]
    
    def __getattr__(self, key):
        # print("--------------get attr--------------: ", key)
        if key == 'df':
            return super().__getattribute__(key)
        else:
            ans = getattr(self.df, key)
            
            if callable(ans):
                def hooked(*args, **kwargs):
                    # print(f"into the hook for {key}")
                    # print("kwargs", **kwargs)
                    
                    if key == "drop":
                        if 'columns' in kwargs:
                            print(f"function {key} called with columns {kwargs.get('columns')}")
                            DataFrameWrapper.add_to_set(self.read_set, kwargs.get('columns'))
                        # print("drop", self.read_se////t, self.write_set, kwargs)
                        result = DataFrameWrapper(ans(*args, **kwargs), self.read_set, self.write_set)
                    else:
                        result = ans(*args, **kwargs)
                    return result
                return hooked
            else:
                return ans
        
        # print("--------------get attr--------------: ", key)
        # df_attr = self.df.__getattribute__(key)
        # if key=='columns' and not hasattr(df_attr, '__call__'):
        #     return df_attr
        # if hasattr(df_attr, '__call__'):
        #     def _(*args, **kwargs):
        #         print("here", key, *args, **kwargs)
        #         def __dictionary_map_values(d, func):
        #             return {k: func(v) for k, v in d.items()}
                
        #         args_df = tuple(map(DataFrameWrapper.get_attr_for_df_pandas_if_needed, args))
        #         kwargs_df = __dictionary_map_values(kwargs, DataFrameWrapper.get_attr_for_df_pandas_if_needed)
                
        #         if 'columns' in kwargs_df:
        #             print(kwargs_df.get('columns'))
                
        #         a = df_attr(*args_df, **kwargs_df)
        #         return DataFrameWrapper(a)
        #     return _
    
    # def __setattr__(self, key, value):
    #     print("--------------set attr--------------: ", key)#, value)
    #     value_ = DataFrameWrapper.get_attr_for_df_pandas_if_needed(value)
    #     if key == 'df' or key == 'read_set' or key == 'write_set':
    #         super().__setattr__(key, value_)
    #     else:
    #         # print(value_)
    #         setattr(self.df, key, value_)
    
    def __delattr__(self, key):
        delattr(self.df, key)
        
    def apply(self, func, *args, **kwargs):
        print("parse the apply func to readset and writeset")
        print("func", func)
        print("args", args)
        print("kwargs", kwargs)
    
    @staticmethod
    def wrapper_run_operator(left, right, op):
        left_, left_rset, left_wset = DataFrameWrapper.get_attr_for_df_pandas_if_needed(left)
        right_, right_rset, right_wset = DataFrameWrapper.get_attr_for_df_pandas_if_needed(right)
        return DataFrameWrapper(op(left_, right_), left_rset.union(right_rset), left_wset.union(right_wset))
        
    def __add__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.add)

    def __sub__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.sub)
    
    def __mul__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.mul)
    
    def __rmul__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.mul)
    
    def __truediv__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.truediv)
    
    def __floordiv__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.floordiv)
    
    def __mod__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.mod)
    
    def __pow__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.pow)
    
    def __lshift__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.lshift)
    
    def __rshift__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.rshift)
    
    def __and__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.and_)
    
    def __xor__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.xor)
    
    def __or__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.or_)
    
    def __lt__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.lt)
    
    def __le__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.le)
    
    def __eq__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.eq)
    
    def __ne__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.ne)
    
    def __gt__(self, other):
        return DataFrameWrapper.wrapper_run_operator(self.df, other, operator.gt)
    
    def __ge__(self, other):
        return DataFrameWrapper(self.df >= other)
    
    def __neg__(self):
        return DataFrameWrapper(-self.df)
    
    def __pos__(self):
        return DataFrameWrapper(+self.df)
    
    def __abs__(self):
        return DataFrameWrapper(abs(self.df))
    
    def __invert__(self):
        return DataFrameWrapper(~self.df)
    
    def __round__(self, n=None):
        return DataFrameWrapper(round(self.df, n))
    
    def __floor__(self):
        return DataFrameWrapper(self.df.floor())
    
    def __ceil__(self):
        return DataFrameWrapper(self.df.ceil())
    
    def __trunc__(self):
        return DataFrameWrapper(self.df.trunc())
    
    def __len__(self):
        return len(self.df)
    
    def __call__(self, *args, **kwargs):
        print("--------------call--------------: ", args, kwargs)
        if 'columns' in kwargs:
            print(kwargs.get('columns'))
        return self.df(*args, **kwargs)
    