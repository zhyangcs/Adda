// Define these to print extra informational output and warnings.
#define MLPACK_PRINT_INFO
#define MLPACK_PRINT_WARN
#include <mlpack.hpp>
#include <boost/archive/text_oarchive.hpp>
#include <boost/archive/text_iarchive.hpp>
#include <cereal/archives/binary.hpp>
#include <sstream>
#include <iostream>
#include <fstream>
using namespace arma;
using namespace mlpack;
using namespace mlpack::tree;
using namespace std;

std::stringstream ss;

#include <mlpack/core.hpp>
#include <mlpack/core/cv/metrics/roc_auc_score.hpp>

float try_aoc()
{
  // 示例数据：真实标签和预测概率得分数组
  float predictions[] = {0, 1, 0.6, 0.1, 0.9}; // 预测概率得分数组
  float truths[] = {1, 0, 1, 0, 1}; // 真实标签数组
  size_t arrlen = 5; // 数组长度

  
  arma::Row<double> predVec(arrlen);
  arma::Row<size_t> truthVec(arrlen);
  for (size_t i = 0; i < arrlen; ++i) {
      predVec(i) = predictions[i];
      truthVec(i) = (size_t)truths[i];
  }

  // 计算 ROC-AUC
  double rocAuc = mlpack::ROCAUCScore<1>::Evaluate(truthVec, predVec);

  // 输出结果
  std::cout << "ROC-AUC: " << rocAuc << std::endl;

  return 0;
}


int main()
{
  mlpack::math::RandomSeed(42);
  // Load the datasets.
  mat dataset;
  Row<size_t> labels;
  if (!data::Load("covertype-small.data.csv", dataset))
    throw std::runtime_error("Could not read covertype-small.data.csv!");
  if (!data::Load("covertype-small.labels.csv", labels))
    throw std::runtime_error("Could not read covertype-small.labels.csv!");

  // Labels are 1-7, but we want 0-6 (we are 0-indexed in C++).
  labels -= 1;

  // Now split the dataset into a training set and test set, using 30% of the
  // dataset for the test set.
  mat trainDataset, testDataset;
  Row<size_t> trainLabels, testLabels;
  data::Split(dataset, labels, trainDataset, testDataset, trainLabels,
      testLabels, 0.3);

  // Create the RandomForest object and train it on the training data.
  RandomForest<> r(trainDataset,
                   trainLabels,
                   7 /* number of classes */,
                   10 /* number of trees */,
                   1 /* minimum leaf size */);

  // data::Save("model.xml", "rf_model", r);

  RandomForest<> nr;
  // data::Load("model.xml", "rf_model", nr);
  // cereal::BinaryOutputArchive archive(ss);
  // archive(r);

  // cereal::BinaryInputArchive archive2(ss);
  // archive2(nr);
  {
    std::ofstream ofs("datafile.dat", std::ios::binary);
    cereal::BinaryOutputArchive archive(ofs);
    archive(r);
  }

  {
    std::ifstream ifs("datafile.dat", std::ios::binary);
    cereal::BinaryInputArchive archive(ifs);
    archive(nr);
  }

  // Compute and print the training error.
  Row<size_t> trainPredictions;
  nr.Classify(trainDataset, trainPredictions);
  const double trainError =
      arma::accu(trainPredictions != trainLabels) * 100.0 / trainLabels.n_elem;
  cout << "Training error: " << trainError << "%." << endl;

  // Now compute predictions on the test points.
  Row<size_t> testPredictions;
  nr.Classify(testDataset, testPredictions);
  const double testError =
      arma::accu(testPredictions != testLabels) * 100.0 / testLabels.n_elem;
  cout << "Test error: " << testError << "%." << endl;

  try_aoc();
}