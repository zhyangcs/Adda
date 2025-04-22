# Adda
In this repo, we introduce Adda, an automated feature engineering tool support by agent's collaboration

<div style="text-align: center;">
<img src="./img/overview.png" alt="本地图片" width="70%">
</div>


## Prerequisites

### 1. install the python library
```sh
pip install -r requirements.txt
```
and you should install the suitable `torch` version considering you GPU.

### 2. install c++ library
you should install the `armadillo` and `postgres database` to the server


### 3. config the environment variable
in `src/env.py` you could set the project configurable variables, especially `openai_api_key` and `rag_model_id_or_path`


## Code execution example

### 1. download the necessary data
you could download the data from the https://drive.google.com/file/d/1qTUpAEn25_-9CUEnk1IgCsvQMkn62R-Z/view?usp=sharing, and unzip to the ./data directory of the project

### 2. do the feature generation
include import the raw csv to the postgres, then do the feature engineering.
You could assign the task_name and the model_type
```python
python src/llm/tests/test_util.py --task_name heart --model_type RF
```

### 3. do the In-DB computation part
```python
python src/run_multimodel_type.py --task_name heart --model_type RF
```
with this you could see the prediction score in terminal

## TODO:
- [ ] Support more convenient training and prediction pipeline
- [ ] Support more C++ version downstream algorithm(currently lightgbm)


## Notice
* To add new dataset, you should follow the format of train_new.csv, data_agenda.txt and desc.txt and update ./src/llm/tests/config.yaml

* The pd2sql modify on the base of another repo https://github.com/AmirPupko/pandas-to-sql
