#include <string>
#include <vector>
#include <unordered_map>
#include <chrono>
#include <unistd.h>
#include <thread>
#include <fstream>
#include <sstream>
#include <iostream>
#include <mlpack.hpp>
#include <cereal/archives/binary.hpp>
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

#define MLPACK_PRINT_INFO
#define MLPACK_PRINT_WARN

using namespace mlpack;
using namespace mlpack::tree;
// using namespace arma;

int num = 0;

extern "C" {
PG_MODULE_MAGIC;

PG_FUNCTION_INFO_V1(rf_classify);

Datum rf_classify(PG_FUNCTION_ARGS){
    // convert the input data to the format that lightgbm can accept
    ArrayType *inputArray = PG_GETARG_ARRAYTYPE_P(0);
    int arrayLength;
    Datum *datums;
    bool *nulls;
    int16 elemWidth;
    bool elemTypeByVal, isNull;
    char elemAlignmentCode;
    Oid elemType = ARR_ELEMTYPE(inputArray);
    int32 class_num = PG_GETARG_INT32(1);

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
    double *train_features = (double *)palloc(sizeof(double)*(num_of_feature)*arrayLength);
    size_t *train_labels = (size_t *)palloc(sizeof(size_t)*arrayLength);

    for (int i = 0; i < arrayLength; ++i) {
        if(!nulls[i]){
            HeapTupleHeader header = DatumGetHeapTupleHeader(datums[i]);
            for (int j = 0; j < num_of_feature; ++j) {
                // elog(WARNING, "%d GetAttributeByNum %d %d", i, j+1, arrayLength);
                train_features[i*num_of_feature+j] = static_cast<float>(DatumGetFloat8(GetAttributeByNum(header, j+2, &isNull)));
                elog(WARNING, "%d GetAttributeByNum %d %d %f", i, j+1, arrayLength, train_features[i*num_of_feature+j]);
            }
            
            train_labels[i] = DatumGetUInt8(GetAttributeByNum(header, num_of_attr, &isNull));
            // elog(WARNING, "%d GetAttributeByNum %d %ld", i, num_of_attr, train_labels[i]);
        }
    }
    elog(WARNING, "labels %ld %ld %ld %ld %ld", train_labels[0], train_labels[1], train_labels[2], train_labels[3], train_labels[4]);

    elog(WARNING, "construct traindata");

    arma::mat train_data = arma::mat(train_features, num_of_feature, arrayLength);
    arma::Row<size_t> train_labels_data = arma::Row<size_t>(train_labels, arrayLength);
    
    RandomForest<> rf(train_data, train_labels_data, class_num, 100, 1);

    //create the name of new model "rf_{num}"
    std::string model_name = "rf_" + std::to_string(num);
    {
        std::ofstream ofs(model_name, std::ios::binary);
        cereal::BinaryOutputArchive archive(ofs);
        archive(rf);
    }

    RandomForest<> nrf;
    {
        std::ifstream ifs(model_name, std::ios::binary);
        cereal::BinaryInputArchive archive(ifs);
        archive(nrf);
    }
    
    // do predict for try
    arma::Row<size_t> train_predictions;
    nrf.Classify(train_data, train_predictions);
    const double trainError = arma::accu(train_predictions != train_labels_data) * 100.0 / train_labels_data.n_elem;
    elog(WARNING, "Training error: %f%%.", trainError);

    pfree(train_features);
    pfree(train_labels);

    PG_RETURN_TEXT_P(cstring_to_text(model_name.c_str()));
}

}