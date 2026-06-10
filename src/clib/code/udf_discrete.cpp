#include <string>
#include <vector>
#include <LightGBM/c_api.h>
#include <chrono>
#include <algorithm>
#include <iostream>
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

PG_FUNCTION_INFO_V1(discrete_cut);

Datum discrete_cut(PG_FUNCTION_ARGS){
    auto t4 = std::chrono::high_resolution_clock::now();
    // convert the input data to the format that lightgbm can accept
    ArrayType *inputArray = PG_GETARG_ARRAYTYPE_P(0);
    ArrayType *labelsArray = PG_GETARG_ARRAYTYPE_P(1);
    int arrayLength, labelsLength;
    Datum *datums, *labels;
    bool *nulls, *labelsNulls;
    int16 elemWidth, labelsElemWidth;
    bool elemTypeByVal, isNull, labelsElemTypeByVal;
    char elemAlignmentCode;
    Oid elemType = ARR_ELEMTYPE(inputArray);
    Oid labelsElemType = ARR_ELEMTYPE(labelsArray);

    get_typlenbyvalalign(elemType, &elemWidth, &elemTypeByVal, &elemAlignmentCode);
    deconstruct_array(inputArray, elemType, elemWidth, elemTypeByVal, elemAlignmentCode, &datums, &nulls, &arrayLength);

    get_typlenbyvalalign(labelsElemType, &labelsElemWidth, &labelsElemTypeByVal, &elemAlignmentCode);
    deconstruct_array(labelsArray, labelsElemType, labelsElemWidth, labelsElemTypeByVal, elemAlignmentCode, &labels, &labelsNulls, &labelsLength);

    if (arrayLength == 0) {
        PG_RETURN_NULL();
    }

    HeapTupleHeader header = DatumGetHeapTupleHeader(datums[0]);
    TupleDesc td = lookup_rowtype_tupdesc(HeapTupleHeaderGetTypeId(header), HeapTupleHeaderGetTypMod(header));
    int num_of_attr = td->natts;
    // try for print info of attrname
    // for (int i = 1; i <= num_of_attr; ++i) {
    //     Form_pg_attribute attr = TupleDescAttr(td, i-1);
    //     elog(INFO, "Attribute %d: Name=%s, Type=%u", i+1, NameStr(attr->attname), attr->atttypid);
    // }
    DecrTupleDescRefCount(td);

    elog(INFO, "num_of_attr: %d", num_of_attr);
    auto st = std::chrono::high_resolution_clock::now();
    float *cur_vals = (float *)palloc(sizeof(float) * arrayLength);
    float max_val = -0x3f3f3f3f, min_val = 0x3f3f3f3f;
    // for (int i=0;i<10;i++){
    //     HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
    //     isNull = nulls[i];
    //     for (int j = 1; j <= num_of_attr; ++j) {
    //         cur_vals[i] = DatumGetFloat8(GetAttributeByNum(header, j, &isNull));
    //         elog(INFO, "cur_vals[%d, %d]: %f", i, j, cur_vals[i]);
    //     }
    // }
    for (int i = 0; i < arrayLength; i++) {
        HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
        isNull = nulls[i];
        if (isNull) {
            cur_vals[i] = 0.0f;
        } else {
            cur_vals[i] = DatumGetFloat8(GetAttributeByNum(header, num_of_attr, &isNull));
            if (cur_vals[i] > max_val) {
                max_val = cur_vals[i];
            }
            if (cur_vals[i] < min_val) {
                min_val = cur_vals[i];
            }
        }
        if(arrayLength%100==0) elog(INFO, "cur_vals[%d]: %f", i, cur_vals[i]);
    }

    auto ft = std::chrono::high_resolution_clock::now();
    auto duration2 = std::chrono::duration_cast<std::chrono::milliseconds>(ft - st);
    elog(INFO, "duration2: %d", duration2.count());

    elog(INFO, "max_val: %f, min_val: %f", max_val, min_val);

    auto t1 = std::chrono::high_resolution_clock::now();
    // split the bins
    int num_bins = labelsLength;
    float* bin_edges = (float*)palloc(sizeof(float) * num_bins);
    float delta = (max_val - min_val) / num_bins;
    for (int i = 0; i < num_bins; i++) {
        bin_edges[i] = min_val + delta * i;
    }
    for (int i = 0; i < num_bins; i++) {
        elog(INFO, "%d: %f", i, bin_edges[i]);
    }
    Datum* new_vals = (Datum *)palloc(sizeof(Datum) * arrayLength);
    // use binary search to find the first bin edge that the value is larger than
    for (int i = 0; i < arrayLength; i++) {
        int l = 0, r = num_bins - 1;
        while (l <= r) {
            int mid = (l + r) >> 1;
            if (cur_vals[i] >= bin_edges[mid]) {
                l = mid + 1;
            } else {
                r = mid - 1;
            }
        }
        new_vals[i] = labels[r];
    }
    auto t2 = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(t2 - t1);
    elog(INFO, "duration: %d", duration.count());
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
        // elog(INFO, "attrName: %s, attrTypeId: %d", attrName, attrTypeId);
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

        values[num_of_attr] = new_vals[i];
        outnulls[num_of_attr] = false;

        HeapTuple tuple = heap_form_tuple(my_tupleDesc, values, outnulls);
        outputDatums[i] = HeapTupleGetDatum(tuple);
    }
    pfree(values);
    pfree(outnulls);

    ArrayType* outputArray = construct_array(outputDatums, arrayLength, outputBaseTypeId, typlen, typbyval, typalign);
    pfree(outputDatums);
    auto t3 = std::chrono::high_resolution_clock::now();
    auto duration1 = std::chrono::duration_cast<std::chrono::milliseconds>(t3 - t4);
    elog(INFO, "duration1: %d", duration1.count());
    PG_RETURN_ARRAYTYPE_P(outputArray);

}

PG_FUNCTION_INFO_V1(discrete_qcut);
Datum discrete_qcut(PG_FUNCTION_ARGS){
    auto t1 = std::chrono::high_resolution_clock::now();
    // convert the input data to the format that lightgbm can accept
    ArrayType *inputArray = PG_GETARG_ARRAYTYPE_P(0);
    ArrayType *labelsArray = PG_GETARG_ARRAYTYPE_P(1);
    int arrayLength, labelsLength;
    Datum *datums, *labels;
    bool *nulls, *labelsNulls;
    int16 elemWidth, labelsElemWidth;
    bool elemTypeByVal, isNull, labelsElemTypeByVal;
    char elemAlignmentCode;
    Oid elemType = ARR_ELEMTYPE(inputArray);
    Oid labelsElemType = ARR_ELEMTYPE(labelsArray);

    get_typlenbyvalalign(elemType, &elemWidth, &elemTypeByVal, &elemAlignmentCode);
    deconstruct_array(inputArray, elemType, elemWidth, elemTypeByVal, elemAlignmentCode, &datums, &nulls, &arrayLength);

    get_typlenbyvalalign(labelsElemType, &labelsElemWidth, &labelsElemTypeByVal, &elemAlignmentCode);
    deconstruct_array(labelsArray, labelsElemType, labelsElemWidth, labelsElemTypeByVal, elemAlignmentCode, &labels, &labelsNulls, &labelsLength);

    if (arrayLength == 0) {
        PG_RETURN_NULL();
    }

    HeapTupleHeader header = DatumGetHeapTupleHeader(datums[0]);
    TupleDesc td = lookup_rowtype_tupdesc(HeapTupleHeaderGetTypeId(header), HeapTupleHeaderGetTypMod(header));
    int num_of_attr = td->natts;
    DecrTupleDescRefCount(td);

    elog(INFO, "num_of_attr: %d", num_of_attr);

    float *cur_vals = (float *)palloc(sizeof(float) * arrayLength);
    // vector<float> (arrayLength);
    for (int i = 0; i < arrayLength; i++) {
        HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
        isNull = nulls[i];
        if (isNull) {
            cur_vals[i] = 0.0f;
        } else {
            cur_vals[i] = DatumGetFloat8(GetAttributeByNum(header, num_of_attr, &isNull));
        }
    }

    auto t3 = std::chrono::high_resolution_clock::now();
    auto duration2 = std::chrono::duration_cast<std::chrono::milliseconds>(t3 - t1);
    elog(INFO, "duration2: %d", duration2.count());

    // split the bins by the value of the quantile
    int num_bins = labelsLength;
    float* bin_edges = (float*)palloc(sizeof(float) * num_bins);
    std::sort(cur_vals, cur_vals + arrayLength);
    for (int i = 0; i < num_bins; i++) {
        bin_edges[i] = cur_vals[(int)(arrayLength * i / num_bins)];
    }

    for (int i = 0; i < num_bins; i++) {
        elog(INFO, "%d: %f", i, bin_edges[i]);
    }
    Datum* new_vals = (Datum *)palloc(sizeof(Datum) * arrayLength);
    // use binary search to find the first bin edge that the value is larger than
    for (int i = 0; i < arrayLength; i++) {
        int l = 0, r = num_bins - 1;
        while (l <= r) {
            int mid = (l + r) >> 1;
            if (cur_vals[i] >= bin_edges[mid]) {
                l = mid + 1;
            } else {
                r = mid - 1;
            }
        }
        new_vals[i] = labels[r];
    }

    auto t4 = std::chrono::high_resolution_clock::now();
    auto duration1 = std::chrono::duration_cast<std::chrono::milliseconds>(t4 - t3);
    elog(INFO, "duration1: %d", duration1.count());
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
    auto t5 = std::chrono::high_resolution_clock::now();
    for (int i = 0; i < arrayLength; ++i) {
        HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
        for (int j = 0; j < num_of_attr; ++j) {
            values[j] = GetAttributeByNum(header, j+1, &isNull);
            outnulls[j] = isNull;
        }

        values[num_of_attr] = new_vals[i];
        outnulls[num_of_attr] = false;

        HeapTuple tuple = heap_form_tuple(my_tupleDesc, values, outnulls);
        outputDatums[i] = HeapTupleGetDatum(tuple);
    }
    pfree(values);
    pfree(outnulls);

    ArrayType* outputArray = construct_array(outputDatums, arrayLength, outputBaseTypeId, typlen, typbyval, typalign);
    pfree(outputDatums);
    auto duration3 = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::high_resolution_clock::now() - t5);
    elog(INFO, "duration3: %d", duration3.count());

    auto t2 = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(t2 - t1);
    elog(INFO, "duration: %d", duration.count());
    PG_RETURN_ARRAYTYPE_P(outputArray);
}



}