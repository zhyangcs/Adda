#include <string>
#include <vector>
#include <unordered_map>
#include <LightGBM/c_api.h>
#include <chrono>
#include <unistd.h>
#include <thread>
#include <fstream>
#include <sstream>
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
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
}

// init an map to store the model incase of redeserialize
std::unordered_map<std::string, BoosterHandle> model_map;
// std::unordered_map<std::string, std::string> model_map;
int num = 0;

extern "C" {
PG_MODULE_MAGIC;

PG_FUNCTION_INFO_V1(lightgbm_regress);
PG_FUNCTION_INFO_V1(lightgbm_classify);
PG_FUNCTION_INFO_V1(lightgbm_predict_classification);
PG_FUNCTION_INFO_V1(lightgbm_predict_regression);
PG_FUNCTION_INFO_V1(lightgbm_predict_regression1);
/*
    This function do not need to considering the type of the input. 
    In this case, we only need to generate it once
    input: [id, feature1, feature2, ..., label]
    output: str of model
*/
Datum lightgbm_regress(PG_FUNCTION_ARGS){
    // convert the input data to the format that lightgbm can accept
    ArrayType *inputArray = PG_GETARG_ARRAYTYPE_P(0);
    int arrayLength;
    Datum *datums;
    bool *nulls;
    int16 elemWidth;
    bool elemTypeByVal, isNull;
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

    elog(WARNING, "Start reformat the data %d, %d", num_of_attr, arrayLength);
    
    auto t1 = std::chrono::high_resolution_clock::now();

    elog(WARNING, "malloc train_features");
    auto num_of_feature = num_of_attr - 2;
    float *train_features = (float *)palloc(sizeof(float)*(num_of_feature)*arrayLength);
    float *train_labels = (float *)palloc(sizeof(float)*arrayLength);

    for (int i = 0; i < arrayLength; ++i) {
        if(!nulls[i]){
            HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
            for (int j = 0; j < num_of_feature; ++j) {
                // elog(WARNING, "%d GetAttributeByNum %d %d", i, j+1, arrayLength);
                train_features[i*num_of_feature+j] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, j+2, &isNull)));
                // elog(WARNING, "%d GetAttributeByNum %d %d %f", i, j+1, arrayLength, train_features[i*num_of_attr+j]);
            }
            // elog(WARNING, "%d GetAttributeByNum %d", i, num_of_attr);
            train_labels[i] = DatumGetFloat8(GetAttributeByNum(header, num_of_attr, &isNull));
        }
    }
    elog(WARNING, "labels %f %f %f %f %f", train_labels[0], train_labels[1], train_labels[2], train_labels[3], train_labels[4]);

    elog(WARNING, "construct traindata");

    DatasetHandle train_data;

    int ret = LGBM_DatasetCreateFromMat(
        (void*)train_features, C_API_DTYPE_FLOAT32, arrayLength, num_of_feature, 1, 
        "", NULL, &train_data);

    if (ret != 0) {
        elog(WARNING, "Failed to create dataset.\n");
        return -1;
    }

    elog(WARNING, "set label");
    // 设置标签
    LGBM_DatasetSetField(train_data, "label", (void*)train_labels, arrayLength, C_API_DTYPE_FLOAT32);

    auto t2 = std::chrono::high_resolution_clock::now();

    // 创建 Booster
    BoosterHandle booster;
    const char* train_params = "application=regression";
    LGBM_BoosterCreate(train_data, train_params, &booster);

    elog(WARNING, "start training");

    // 进行训练
    int num_iterations = 25; // 训练迭代次数
    for (int i = 0; i < num_iterations; ++i) {
        // if(i%100 == 0)
        //     elog(WARNING, "Training for %d.\n", i);
        int is_finished = 0;
        LGBM_BoosterUpdateOneIter(booster, &is_finished);
        if (is_finished) {
            elog(WARNING, "Finished training for %d.\n", i);
            break;
        }
    }

    auto t3 = std::chrono::high_resolution_clock::now();

    elog(WARNING, "Total preprocess Time regression %f", std::chrono::duration<double>(t2-t1).count());
    elog(WARNING, "Total Training Time regression %f", std::chrono::duration<double>(t3-t2).count());

    // 保存模型到字符串
    int64_t buffer_len = 10 * 1024 * 1024;
    int64_t out_len = 0;
    char *model_str = (char*) palloc(buffer_len * sizeof(char));
    LGBM_BoosterSaveModelToString(booster, 0, -1, C_API_FEATURE_IMPORTANCE_SPLIT, buffer_len, &out_len, model_str);


    // // prediction
    // out_len = 0;
    // double *result = (double *)palloc(sizeof(double)*arrayLength);
    // float *predict_feature = (float *)palloc(sizeof(float)*num_of_feature*1);
    // for(int i = 0; i < num_of_feature; ++i){
    //     predict_feature[i] = train_features[i+1];
    // }
    // ret = LGBM_BoosterPredictForMat(booster, (void*)predict_feature, C_API_DTYPE_FLOAT32, 1, num_of_feature, 1, C_API_PREDICT_NORMAL, 0, -1, "", &out_len, result);
    // elog(WARNING, "ret result %d", ret);
    // if(ret){
    //     elog(WARNING, "Error: LGBM_BoosterPredictForMat()\n");
    //     PG_RETURN_NULL();
    // } else {
    //     for (int i = 0; i < out_len; ++i) {
    //         elog(WARNING, "predict %d : %f", num_of_feature, result[i]);
    //     }
    // }

    // elog(WARNING, "model string %d %s", out_len, model_str);

    text *model_str_c = cstring_to_text(model_str);


    pfree(train_features);
    pfree(train_labels);

    PG_RETURN_TEXT_P(model_str_c);
    // PG_RETURN_INT32(1);
}

Datum lightgbm_classify(PG_FUNCTION_ARGS){
    // convert the input data to the format that lightgbm can accept
    ArrayType *inputArray = PG_GETARG_ARRAYTYPE_P(0);
    int arrayLength;
    Datum *datums;
    bool *nulls;
    int16 elemWidth;
    bool elemTypeByVal, isNull;
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

    elog(WARNING, "Start reformat the data %d, %d", num_of_attr, arrayLength);
    
    auto t1 = std::chrono::high_resolution_clock::now();

    auto num_of_feature = num_of_attr - 2;
    float *train_features = (float *)palloc(sizeof(float)*(num_of_feature)*arrayLength);
    float *train_labels = (float *)palloc(sizeof(float)*arrayLength);

    for (int i = 0; i < arrayLength; ++i) {
        if(!nulls[i]){
            HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
            
            train_labels[i] = DatumGetFloat8(GetAttributeByNum(header, num_of_attr, &isNull));
            // elog(WARNING, "%d GetAttributeByNum %d %f", i, 1, train_labels[i]);
            for (int j = 0; j < num_of_feature; ++j) {
                // elog(WARNING, "%d GetAttributeByNum %d %d", i, j+1, arrayLength);
                train_features[i*num_of_feature+j] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, j+2, &isNull)));
                // elog(WARNING, "%d GetAttributeByNum %d %d %f", i, j+1, arrayLength, train_features[i*(num_of_attr-1)+j-1]);
            }
            
        }
    }

    elog(WARNING, "construct traindata");

    DatasetHandle train_data;

    int ret = LGBM_DatasetCreateFromMat(
        (void*)train_features, C_API_DTYPE_FLOAT32, arrayLength, num_of_feature, 1, 
        "", NULL, &train_data);

    if (ret != 0) {
        elog(WARNING, "Failed to create dataset.\n");
        return -1;
    }

    elog(WARNING, "set label");
    // 设置标签
    LGBM_DatasetSetField(train_data, "label", (void*)train_labels, arrayLength, C_API_DTYPE_FLOAT32);

    auto t2 = std::chrono::high_resolution_clock::now();

    // 创建 Booster
    int32 num_class = PG_GETARG_INT32(1);
    BoosterHandle booster;
    // const char* train_params = ;
    // set the num_class into the train_params
    char *train_params = (char*) palloc(100 * sizeof(char));
    if(num_class == 2)
        sprintf(train_params, "objective=binary");
    else if(num_class > 2)
        sprintf(train_params, "objective=multiclass num_class=%d", num_class);

    elog(WARNING, "start create booster %s %d", train_params, num_class);
    LGBM_BoosterCreate(train_data, train_params, &booster);

    elog(WARNING, "start training");

    // 进行训练
    int num_iterations = 22; // 训练迭代次数
    for (int i = 0; i < num_iterations; ++i) {
        // if(i%100 == 0)
            
        int is_finished = 0;
        auto tt1 = std::chrono::high_resolution_clock::now();
        LGBM_BoosterUpdateOneIter(booster, &is_finished);
        auto tt2 = std::chrono::high_resolution_clock::now();
        elog(WARNING, "Training for %d.%f\n", i, std::chrono::duration<double>(tt2-tt1).count());
        if (is_finished) {
            elog(WARNING, "Finished training for %d.\n", i);
            break;
        }
    }

    auto t3 = std::chrono::high_resolution_clock::now();

    elog(WARNING, "Total preprocess Time classify %f", std::chrono::duration<double>(t2-t1).count());
    elog(WARNING, "Total Training Time classify %f", std::chrono::duration<double>(t3-t2).count());
    
    PG_RETURN_NULL();
}

// input: array[id, xxxx(other features)]
// output: array[id, result]
Datum lightgbm_predict_classification(PG_FUNCTION_ARGS){
    // convert the input data to the format that lightgbm can accept
    ArrayType *inputArray = PG_GETARG_ARRAYTYPE_P(0);
    int arrayLength;
    Datum *datums;
    bool *nulls;
    int16 elemWidth;
    bool elemTypeByVal, isNull;
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

    elog(WARNING, "Start reformat the data %d, %d", num_of_attr, arrayLength);
    
    auto t1 = std::chrono::high_resolution_clock::now();

    // reserve the first column for the id
    auto num_of_feature = num_of_attr - 1;
    float *train_features = (float *)palloc(sizeof(float)*num_of_feature*arrayLength);
    float *train_id = (float *)palloc(sizeof(float)*arrayLength);

    for (int i = 0; i < arrayLength; ++i) {
        if(!nulls[i]){
            HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
            train_id[i] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, 1, &isNull)));
            for (int j = 0; j < num_of_feature; ++j) {
                // elog(WARNING, "%d GetAttributeByNum %d %d", i, j+1, arrayLength);
                train_features[i * num_of_feature + j] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, j + 2, &isNull)));
                // elog(WARNING, "%d GetAttributeByNum %d %d %f", i, j+1, arrayLength, train_features[i*num_of_feature+j]);
            }
        }
    }

    double *result = (double *)palloc(sizeof(double)*arrayLength);
    text *model_name_str = PG_GETARG_TEXT_P(1);
    char *model_name_str_c = text_to_cstring(model_name_str);

    BoosterHandle booster;
    // get the booster if it is already in the map
    if(model_map.find(model_name_str_c) != model_map.end()){
        booster = model_map[model_name_str_c];
    } else {
        text *model_str = PG_GETARG_TEXT_P(2);
        char *model_str_c = text_to_cstring(model_str);
        int iter_num;
        auto ret = LGBM_BoosterLoadModelFromString(model_str_c, &iter_num, &booster);
        if(ret){
            elog(WARNING, "Error: LGBM_BoosterLoadModelFromString()\n");
            PG_RETURN_NULL();
        } 
        model_map[model_name_str_c] = booster;
    }

    int64_t out_len = 0;
    auto ret = LGBM_BoosterPredictForMat(booster, (void*)train_features, C_API_DTYPE_FLOAT32, arrayLength, num_of_feature, 1, C_API_PREDICT_NORMAL, 0, -1, "", &out_len, result);
    elog(WARNING, "ret result %d", ret);
    if(ret){
        elog(WARNING, "Error: LGBM_BoosterPredictForMat()\n");
        PG_RETURN_NULL();
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

    TupleDesc my_tupleDesc = CreateTemplateTupleDesc(2);
    for (int i = 1; i <= 2; ++i) {
        const char* attrName = get_attname(outputBaseTypRelId, i, false);
        const Oid attrTypeId = get_atttype(outputBaseTypRelId, i);
        TupleDescInitEntry(my_tupleDesc, i, attrName, attrTypeId, -1, 0);
    }
    
    my_tupleDesc = BlessTupleDesc(my_tupleDesc);
    
    Datum* values = (Datum*)palloc(2 * sizeof(Datum));
    bool* outnulls = (bool*)palloc(2 * sizeof(bool));
    Datum* outputDatums = static_cast<Datum*>(palloc(arrayLength * sizeof(Datum)));
    for (int i = 0; i < arrayLength; ++i) {
        // 填充数值字段
        values[0] = Int8GetDatum((int)train_id[i]); // id
        int binary = result[i] > 0.5 ? 1 : 0;
        values[1] = Int8GetDatum(binary);       // result

        // 对于非数值字段，设置 nulls 数组相应位置为 false
        for (int j = 0; j < 2; ++j) {
            outnulls[j] = false;
        }

        HeapTuple tuple = heap_form_tuple(my_tupleDesc, values, outnulls);
        outputDatums[i] = HeapTupleGetDatum(tuple);
    }
    pfree(values);
    pfree(outnulls);

    ArrayType* outputArray = construct_array(outputDatums, arrayLength, outputBaseTypeId, typlen, typbyval, typalign);
    pfree(outputDatums);
    PG_RETURN_ARRAYTYPE_P(outputArray);
}

// input: array[id, xxxx(other features)]
// output: array[id, result]
Datum lightgbm_predict_regression(PG_FUNCTION_ARGS){
    // convert the input data to the format that lightgbm can accept
    ArrayType *inputArray = PG_GETARG_ARRAYTYPE_P(0);
    int arrayLength;
    Datum *datums;
    bool *nulls;
    int16 elemWidth;
    bool elemTypeByVal, isNull;
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

    // elog(WARNING, "Start reformat the data %d, %d", num_of_attr, arrayLength);
    
    auto t1 = std::chrono::high_resolution_clock::now();

    // reserve the first column for the id
    auto num_of_feature = num_of_attr - 1;
    float *train_features = (float *)palloc(sizeof(float)*num_of_feature*arrayLength);
    float *train_id = (float *)palloc(sizeof(float)*arrayLength);

    for (int i = 0; i < arrayLength; ++i) {
        if(!nulls[i]){
            HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
            train_id[i] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, 1, &isNull)));
            for (int j = 0; j < num_of_feature; ++j) {
                // elog(WARNING, "%d GetAttributeByNum %d %d", i, j+1, arrayLength);
                train_features[i * num_of_feature + j] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, j + 2, &isNull)));
                // elog(WARNING, "%d GetAttributeByNum %d %d %f", i, j+1, arrayLength, train_features[i*num_of_feature+j]);
            }
        }
    }

    double *result = (double *)palloc(sizeof(double)*arrayLength);
    text *model_name_str = PG_GETARG_TEXT_P(1);
    char *model_name_str_c = text_to_cstring(model_name_str);

    BoosterHandle booster;
    // elog(WARNING, "get model from map %s", model_name_str_c)
    // get the booster if it is already in the map
    if(model_map.find(model_name_str_c) != model_map.end()){
        booster = model_map[model_name_str_c];
        num++;
        // elog(WARNING, "get model from map %d %d", num, getpid());
    } else {
        text *model_str = PG_GETARG_TEXT_P(2);
        char *model_str_c = text_to_cstring(model_str);
        int iter_num;
        auto ret = LGBM_BoosterLoadModelFromString(model_str_c, &iter_num, &booster);
        if(ret){
            elog(WARNING, "Error: LGBM_BoosterLoadModelFromString()\n");
            PG_RETURN_NULL();
        } 
        model_map[model_name_str_c] = booster;
    }
    auto t2 = std::chrono::high_resolution_clock::now();
    // elog(WARNING, "load model %f", std::chrono::duration<double>(t2-t1).count());

    int64_t out_len = 0;
    auto ret = LGBM_BoosterPredictForMat(booster, (void*)train_features, C_API_DTYPE_FLOAT32, arrayLength, num_of_feature, 1, C_API_PREDICT_NORMAL, 0, -1, "", &out_len, result);
    // elog(WARNING, "ret result %d", ret);
    if(ret){
        elog(WARNING, "Error: LGBM_BoosterPredictForMat()\n");
        PG_RETURN_NULL();
    }
    auto t3 = std::chrono::high_resolution_clock::now();
    // elog(WARNING, "predict %f", std::chrono::duration<double>(t3-t2).count());

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

    TupleDesc my_tupleDesc = CreateTemplateTupleDesc(2);
    for (int i = 1; i <= 2; ++i) {
        const char* attrName = get_attname(outputBaseTypRelId, i, false);
        const Oid attrTypeId = get_atttype(outputBaseTypRelId, i);
        TupleDescInitEntry(my_tupleDesc, i, attrName, attrTypeId, -1, 0);
    }
    
    my_tupleDesc = BlessTupleDesc(my_tupleDesc);
    
    Datum* values = (Datum*)palloc(2 * sizeof(Datum));
    bool* outnulls = (bool*)palloc(2 * sizeof(bool));
    Datum* outputDatums = static_cast<Datum*>(palloc(arrayLength * sizeof(Datum)));
    for (int i = 0; i < arrayLength; ++i) {
        // 填充数值字段
        values[0] = Float8GetDatum(train_id[i]); // id
        values[1] = Float8GetDatum(result[i]);       // result

        // 对于非数值字段，设置 nulls 数组相应位置为 false
        for (int j = 0; j < 2; ++j) {
            outnulls[j] = false;
        }

        HeapTuple tuple = heap_form_tuple(my_tupleDesc, values, outnulls);
        outputDatums[i] = HeapTupleGetDatum(tuple);
    }
    auto t4 = std::chrono::high_resolution_clock::now();
    // elog(WARNING, "end %f", std::chrono::duration<double>(t4-t3).count());
    pfree(values);
    pfree(outnulls);

    ArrayType* outputArray = construct_array(outputDatums, arrayLength, outputBaseTypeId, typlen, typbyval, typalign);
    pfree(outputDatums);
    PG_RETURN_ARRAYTYPE_P(outputArray);
}

Datum lightgbm_predict_regression1(PG_FUNCTION_ARGS){
    // convert the input data to the format that lightgbm can accept
    ArrayType *inputArray = PG_GETARG_ARRAYTYPE_P(0);
    int arrayLength;
    Datum *datums;
    bool *nulls;
    int16 elemWidth;
    bool elemTypeByVal, isNull;
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

    // elog(WARNING, "Start reformat the data %d, %d", num_of_attr, arrayLength);
    
    auto t1 = std::chrono::high_resolution_clock::now();

    // reserve the first column for the id
    auto num_of_feature = num_of_attr - 1;
    float *train_features = (float *)palloc(sizeof(float)*num_of_feature*arrayLength);
    float *train_id = (float *)palloc(sizeof(float)*arrayLength);

    for (int i = 0; i < arrayLength; ++i) {
        if(!nulls[i]){
            HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
            train_id[i] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, 1, &isNull)));
            for (int j = 0; j < num_of_feature; ++j) {
                // elog(WARNING, "%d GetAttributeByNum %d %d", i, j+1, arrayLength);
                train_features[i * num_of_feature + j] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, j + 2, &isNull)));
                // elog(WARNING, "%d GetAttributeByNum %d %d %f", i, j+1, arrayLength, train_features[i*num_of_feature+j]);
            }
        }
    }

    double *result = (double *)palloc(sizeof(double)*arrayLength);
    // text *model_name_str = PG_GETARG_TEXT_P(1);
    // char *model_name_str_c = text_to_cstring(model_name_str);

    BoosterHandle booster;
    // // elog(WARNING, "get model from map %s", model_name_str_c)
    // // get the booster if it is already in the map
    // if(model_map.find(model_name_str_c) != model_map.end()){
    //     booster = model_map[model_name_str_c];
    //     elog(WARNING, "get model from map");
    // } else {
    text *model_str = PG_GETARG_TEXT_P(2);
    char *model_str_c = text_to_cstring(model_str);
    int iter_num;
    auto ret = LGBM_BoosterLoadModelFromString(model_str_c, &iter_num, &booster);
    if(ret){
        elog(WARNING, "Error: LGBM_BoosterLoadModelFromString()\n");
        PG_RETURN_NULL();
    } 
    //     model_map[model_name_str_c] = booster;
    // }
    auto t2 = std::chrono::high_resolution_clock::now();
    elog(WARNING, "load model %f", std::chrono::duration<double>(t2-t1).count());

    int64_t out_len = 0;
    ret = LGBM_BoosterPredictForMat(booster, (void*)train_features, C_API_DTYPE_FLOAT32, arrayLength, num_of_feature, 1, C_API_PREDICT_NORMAL, 0, -1, "", &out_len, result);
    // elog(WARNING, "ret result %d", ret);
    if(ret){
        elog(WARNING, "Error: LGBM_BoosterPredictForMat()\n");
        PG_RETURN_NULL();
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

    TupleDesc my_tupleDesc = CreateTemplateTupleDesc(2);
    for (int i = 1; i <= 2; ++i) {
        const char* attrName = get_attname(outputBaseTypRelId, i, false);
        const Oid attrTypeId = get_atttype(outputBaseTypRelId, i);
        TupleDescInitEntry(my_tupleDesc, i, attrName, attrTypeId, -1, 0);
    }
    
    my_tupleDesc = BlessTupleDesc(my_tupleDesc);
    
    Datum* values = (Datum*)palloc(2 * sizeof(Datum));
    bool* outnulls = (bool*)palloc(2 * sizeof(bool));
    Datum* outputDatums = static_cast<Datum*>(palloc(arrayLength * sizeof(Datum)));
    for (int i = 0; i < arrayLength; ++i) {
        // 填充数值字段
        values[0] = Float8GetDatum(train_id[i]); // id
        values[1] = Float8GetDatum(result[i]);       // result

        // 对于非数值字段，设置 nulls 数组相应位置为 false
        for (int j = 0; j < 2; ++j) {
            outnulls[j] = false;
        }

        HeapTuple tuple = heap_form_tuple(my_tupleDesc, values, outnulls);
        outputDatums[i] = HeapTupleGetDatum(tuple);
    }
    auto t3 = std::chrono::high_resolution_clock::now();
    elog(WARNING, "predict %f", std::chrono::duration<double>(t3-t2).count());
    pfree(values);
    pfree(outnulls);

    ArrayType* outputArray = construct_array(outputDatums, arrayLength, outputBaseTypeId, typlen, typbyval, typalign);
    pfree(outputDatums);
    PG_RETURN_ARRAYTYPE_P(outputArray);
}


PG_FUNCTION_INFO_V1(lightgbm_multi);
PG_FUNCTION_INFO_V1(lightgbm_multi1);
void load_and_predict(char *model_str_c, int arrayLength, int num_of_feature, float *train_features, int tid){
    double *result = (double *)palloc(sizeof(double)*arrayLength);
    // text *model_name_str = PG_GETARG_TEXT_P(1);
    // char *model_name_str_c = text_to_cstring(model_name_str);

    auto startt = std::chrono::high_resolution_clock::now();
    BoosterHandle booster;
    
    if(model_map.find(model_str_c) != model_map.end()){
        booster = model_map[model_str_c];
    } else {
        int iter_num;
        auto ret = LGBM_BoosterLoadModelFromString(model_str_c, &iter_num, &booster);
        // elog(WARNING, "[%d] start load model %d", tid, &booster);
        if(ret){
            elog(WARNING, "Error: LGBM_BoosterLoadModelFromString()\n");
        } 
        model_map[model_str_c] = booster;
    }
    // // LGBM_BoosterCreate(NULL, "application=regression", &booster); 
    // int iter_num;
    // auto ret = LGBM_BoosterLoadModelFromString(model_str_c, &iter_num, &booster);
    // // elog(WARNING, "[%d] start load model %d", tid, &booster);
    // if(ret){
    //     elog(WARNING, "Error: LGBM_BoosterLoadModelFromString()\n");
    // } 

    int num = 0;
    auto t1 = std::chrono::high_resolution_clock::now();
    while(num < 1){
        // elog(WARNING, "[%d] start predict0", tid);
        auto midt = std::chrono::high_resolution_clock::now();
        // elog(WARNING, "[%d] start predict1", tid);
        int64_t out_len = 0;
        // elog(WARNING, "[%d] start predict2", tid);
        auto ret = LGBM_BoosterPredictForMat(booster, (void*)train_features, C_API_DTYPE_FLOAT32, arrayLength, num_of_feature, 1, C_API_PREDICT_NORMAL, 0, -1, "", &out_len, result);
        // elog(WARNING, "[%d] ret result %f %d", tid, result[0], ret);
        // if(out_len>0){
        //     elog(WARNING, "[%d] ret result %f %d", tid, result[0], ret);
        // }
        if(ret){
            elog(WARNING, "Error: LGBM_BoosterPredictForMat()\n");
        }
        auto endt = std::chrono::high_resolution_clock::now();
        // elog(WARNING, "[%d] predict %f %d", tid, std::chrono::duration<double>(endt-midt).count());
        num++;
        // elog(WARNING, "[%d] predict %d", tid, num);
    }
    auto t2 = std::chrono::high_resolution_clock::now();
    elog(WARNING, "[%d] predict %f", tid, std::chrono::duration<double>(t2-t1).count()/50);
    pfree(result);
    
    // return result;
}

Datum lightgbm_multi(PG_FUNCTION_ARGS){
    // convert the input data to the format that lightgbm can accept
    ArrayType *inputArray = PG_GETARG_ARRAYTYPE_P(0);
    int arrayLength;
    Datum *datums;
    bool *nulls;
    int16 elemWidth;
    bool elemTypeByVal, isNull;
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

    // elog(WARNING, "Start reformat the data %d, %d", num_of_attr, arrayLength);
    
    auto t1 = std::chrono::high_resolution_clock::now();

    // reserve the first column for the id
    auto num_of_feature = num_of_attr - 1;
    float *train_features = (float *)palloc(sizeof(float)*num_of_feature*arrayLength);
    float *train_id = (float *)palloc(sizeof(float)*arrayLength);

    for (int i = 0; i < arrayLength; ++i) {
        if(!nulls[i]){
            HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
            train_id[i] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, 1, &isNull)));
            for (int j = 0; j < num_of_feature; ++j) {
                // elog(WARNING, "%d GetAttributeByNum %d %d", i, j+1, arrayLength);
                train_features[i * num_of_feature + j] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, j + 2, &isNull)));
                // elog(WARNING, "%d GetAttributeByNum %d %d %f", i, j+1, arrayLength, train_features[i*num_of_feature+j]);
            }
        }
    }

    // start multi-thread doing the same prediction
    double *result = (double *)palloc(sizeof(double)*arrayLength);
    text *model_str = PG_GETARG_TEXT_P(2);
    char *model_str_c = text_to_cstring(model_str);
    auto tt1 = std::chrono::high_resolution_clock::now();
    std::thread thread1(load_and_predict, model_str_c, arrayLength, num_of_feature, train_features, 1);
    // std::thread thread2(load_and_predict, model_str_c, arrayLength, num_of_feature, train_features, 2);

    
    load_and_predict(model_str_c, arrayLength, num_of_feature, train_features, getpid());
    thread1.join();
    // thread2.join();
    auto tt2 = std::chrono::high_resolution_clock::now();
    elog(WARNING, "Total predict %f", std::chrono::duration<double>(tt2-tt1).count());
     

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

    TupleDesc my_tupleDesc = CreateTemplateTupleDesc(2);
    for (int i = 1; i <= 2; ++i) {
        const char* attrName = get_attname(outputBaseTypRelId, i, false);
        const Oid attrTypeId = get_atttype(outputBaseTypRelId, i);
        TupleDescInitEntry(my_tupleDesc, i, attrName, attrTypeId, -1, 0);
    }
    
    my_tupleDesc = BlessTupleDesc(my_tupleDesc);
    
    Datum* values = (Datum*)palloc(2 * sizeof(Datum));
    bool* outnulls = (bool*)palloc(2 * sizeof(bool));
    Datum* outputDatums = static_cast<Datum*>(palloc(arrayLength * sizeof(Datum)));
    for (int i = 0; i < arrayLength; ++i) {
        // 填充数值字段
        values[0] = Float8GetDatum(train_id[i]); // id
        values[1] = Float8GetDatum(result[i]);       // result

        // 对于非数值字段，设置 nulls 数组相应位置为 false
        for (int j = 0; j < 2; ++j) {
            outnulls[j] = false;
        }

        HeapTuple tuple = heap_form_tuple(my_tupleDesc, values, outnulls);
        outputDatums[i] = HeapTupleGetDatum(tuple);
    }
    auto t3 = std::chrono::high_resolution_clock::now();
    // elog(WARNING, "predict %f", std::chrono::duration<double>(t3-t2).count());
    pfree(values);
    pfree(outnulls);

    ArrayType* outputArray = construct_array(outputDatums, arrayLength, outputBaseTypeId, typlen, typbyval, typalign);
    pfree(outputDatums);
    PG_RETURN_ARRAYTYPE_P(outputArray);
}

Datum lightgbm_multi1(PG_FUNCTION_ARGS){
    pid_t pid = fork();
    std::stringstream ss;
    std::string path = ss.str();
    std::ofstream outfile(path);
    // convert the input data to the format that lightgbm can accept
    ArrayType *inputArray = PG_GETARG_ARRAYTYPE_P(0);
    int arrayLength;
    Datum *datums;
    bool *nulls;
    int16 elemWidth;
    bool elemTypeByVal, isNull;
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

    // elog(WARNING, "Start reformat the data %d, %d", num_of_attr, arrayLength);
    
    auto t1 = std::chrono::high_resolution_clock::now();

    // reserve the first column for the id
    auto num_of_feature = num_of_attr - 1;
    float *train_features = (float *)palloc(sizeof(float)*num_of_feature*arrayLength);
    float *train_id = (float *)palloc(sizeof(float)*arrayLength);

    for (int i = 0; i < arrayLength; ++i) {
        if(!nulls[i]){
            HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
            train_id[i] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, 1, &isNull)));
            for (int j = 0; j < num_of_feature; ++j) {
                // elog(WARNING, "%d GetAttributeByNum %d %d", i, j+1, arrayLength);
                train_features[i * num_of_feature + j] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, j + 2, &isNull)));
                // elog(WARNING, "%d GetAttributeByNum %d %d %f", i, j+1, arrayLength, train_features[i*num_of_feature+j]);
            }
        }
    }

    // start multi-thread doing the same prediction
    double *result = (double *)palloc(sizeof(double)*arrayLength);
    text *model_str = PG_GETARG_TEXT_P(2);
    char *model_str_c = text_to_cstring(model_str);
    auto tt1 = std::chrono::high_resolution_clock::now();
    // std::thread thread1(load_and_predict, model_str_c, arrayLength, num_of_feature, train_features, 1);
    // std::thread thread2(load_and_predict, model_str_c, arrayLength, num_of_feature, train_features, 2);

    
    load_and_predict(model_str_c, arrayLength, num_of_feature, train_features, 3);
    // thread1.join();
    // thread2.join();
    auto tt2 = std::chrono::high_resolution_clock::now();
    outfile<<std::chrono::duration<double>(tt2-tt1).count()<<std::endl;
    outfile.close();
    // elog(WARNING, "Total predict %f", std::chrono::duration<double>(tt2-tt1).count());


    if(pid == 0){
        // child process
        elog(WARNING, "child process");
        exit(0);
    } else {
        // parent process
        elog(WARNING, "parent process");
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

    TupleDesc my_tupleDesc = CreateTemplateTupleDesc(2);
    for (int i = 1; i <= 2; ++i) {
        const char* attrName = get_attname(outputBaseTypRelId, i, false);
        const Oid attrTypeId = get_atttype(outputBaseTypRelId, i);
        TupleDescInitEntry(my_tupleDesc, i, attrName, attrTypeId, -1, 0);
    }
    
    my_tupleDesc = BlessTupleDesc(my_tupleDesc);
    
    Datum* values = (Datum*)palloc(2 * sizeof(Datum));
    bool* outnulls = (bool*)palloc(2 * sizeof(bool));
    Datum* outputDatums = static_cast<Datum*>(palloc(arrayLength * sizeof(Datum)));
    for (int i = 0; i < arrayLength; ++i) {
        // 填充数值字段
        values[0] = Float8GetDatum(train_id[i]); // id
        values[1] = Float8GetDatum(result[i]);       // result

        // 对于非数值字段，设置 nulls 数组相应位置为 false
        for (int j = 0; j < 2; ++j) {
            outnulls[j] = false;
        }

        HeapTuple tuple = heap_form_tuple(my_tupleDesc, values, outnulls);
        outputDatums[i] = HeapTupleGetDatum(tuple);
    }
    auto t3 = std::chrono::high_resolution_clock::now();
    // elog(WARNING, "predict %f", std::chrono::duration<double>(t3-t2).count());
    pfree(values);
    pfree(outnulls);

    ArrayType* outputArray = construct_array(outputDatums, arrayLength, outputBaseTypeId, typlen, typbyval, typalign);
    pfree(outputDatums);
    PG_RETURN_ARRAYTYPE_P(outputArray);
}
}
