#include <string>
#include <vector>
#include <LightGBM/c_api.h>
#include <chrono>
extern "C" {
#include <postgres.h>
#include <catalog/pg_type.h>
#include <utils/rel.h>
#include <utils/builtins.h>
#include "executor/executor.h"  /* for GetAttributeByName() */
#include "fmgr.h"
#include "utils/geo_decls.h"
#include "funcapi.h"
#include <utils/lsyscache.h>
#include "catalog/pg_class.h"
#include "catalog/pg_type.h"
#include "access/htup_details.h"
#include "utils/typcache.h"
}

extern "C" {
PG_MODULE_MAGIC;

PG_FUNCTION_INFO_V1(udf_ctemplate);

int64* is_alone(int64* arr, int len) {
    int64* res = (int64*)palloc(sizeof(int64) * len);
    for (int i = 0; i < len; i++) {
        res[i] = 1;
    }
    for (int i = 0; i < len; i++) {
        res[i] = arr[i] == 0 ? 1 : 0;
    }
    return res;
}

Datum udf_ctemplate(PG_FUNCTION_ARGS){
    // convert the input data to the format that lightgbm can accept
    ArrayType *inputArray = PG_GETARG_ARRAYTYPE_P(0);
    int arrayLength;
    Datum *datums;
    bool *nulls;
    int16 elemWidth;
    bool elemTypeByVal, isNull, labelsElemTypeByVal;
    char elemAlignmentCode;
    Oid elemType = ARR_ELEMTYPE(inputArray);

    get_typlenbyvalalign(elemType, &elemWidth, &elemTypeByVal, &elemAlignmentCode);
    deconstruct_array(inputArray, elemType, elemWidth, elemTypeByVal, elemAlignmentCode, &datums, &nulls, &arrayLength);

    if (arrayLength == 0) {
        PG_RETURN_NULL();
    }

    HeapTupleHeader header = DatumGetHeapTupleHeader(datums[0]);
    TupleDesc td = lookup_rowtype_tupdesc(HeapTupleHeaderGetTypeId(header), HeapTupleHeaderGetTypMod(header));
    int num_of_attr = td->natts;
    DecrTupleDescRefCount(td);

    elog(INFO, "num_of_attr: %d", num_of_attr);

    int64 *cur_vals = (int64 *)palloc(sizeof(int64) * arrayLength);
    for (int i = 0; i < arrayLength; i++) {
        HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
        isNull = nulls[i];
        if (isNull) {
            cur_vals[i] = 0.0f;
        } else {
            cur_vals[i] = DatumGetInt64(GetAttributeByNum(header, 1, &isNull));
        }
    }

    // execute the outer function
    int64* new_vals = is_alone(cur_vals, arrayLength);
    for (int i = 0; i < arrayLength; i++) {
        elog(INFO, "new_vals[%d]: %ld", i, new_vals[i]);
    }
    
    // self construct the tupleDesc of the output type
    TupleDesc tupleDesc = NULL;
    Oid outputTypeId = 0;
    get_call_result_type(fcinfo, &outputTypeId, &tupleDesc);

    Oid outputBaseTypeId = get_base_element_type(outputTypeId);
    Oid outputBaseTypRelId = get_typ_typrelid(outputBaseTypeId);

    int16 typlen = 0;
    bool typbyval = false;
    char typalign;
    get_typlenbyvalalign(outputBaseTypeId, &typlen, &typbyval, &typalign);

    TupleDesc my_tupleDesc = CreateTemplateTupleDesc(num_of_attr + 1);
    for (int i = 1; i <= num_of_attr+1; ++i) {
        const char* attrName = get_attname(outputBaseTypRelId, i, false);
        const Oid attrTypeId = get_atttype(outputBaseTypRelId, i);
        TupleDescInitEntry(my_tupleDesc, i, attrName, attrTypeId, -1, 0);
    }
    
    my_tupleDesc = BlessTupleDesc(my_tupleDesc);
    
    Datum* values = (Datum*)palloc((num_of_attr+1) * sizeof(Datum));
    bool* outnulls = (bool*)palloc((num_of_attr+1) * sizeof(bool));
    Datum* outputDatums = static_cast<Datum*>(palloc(arrayLength * sizeof(Datum)));
    elog(INFO, "arrayLength: %d, start wrapper the return value", arrayLength);
    for (int i = 0; i < arrayLength; ++i) {
        HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
        for (int j = 0; j < num_of_attr; ++j) {
            values[j] = GetAttributeByNum(header, j+1, &isNull);
            outnulls[j] = isNull;
        }

        values[num_of_attr] = Int8GetDatum(new_vals[i]);
        outnulls[num_of_attr] = false;

        HeapTuple tuple = heap_form_tuple(my_tupleDesc, values, outnulls);
        outputDatums[i] = HeapTupleGetDatum(tuple);
    }
    pfree(values);
    pfree(outnulls);

    ArrayType* outputArray = construct_array(outputDatums, arrayLength, outputBaseTypeId, typlen, typbyval, typalign);
    pfree(outputDatums);
    PG_RETURN_ARRAYTYPE_P(outputArray);
}
}