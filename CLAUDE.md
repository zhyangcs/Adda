# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
**Adda** is an automated feature engineering tool using LLM-driven agent collaboration and PostgreSQL with C++ UDFs for in-database ML computation.

## Core Commands

### Development Setup
```bash
# Install system dependencies
sudo apt-get install libarmadillo-dev postgresql-server-dev-all

# Install Python dependencies
pip install -r requirements.txt

# Start PostgreSQL
service postgresql start

# Install pl/python libraries
/usr/bin/python3 -m pip install pandas scikit-learn xgboost lightgbm
```

### Feature Engineering Pipeline
```bash
# Generate features for a dataset
python src/llm/tests/test_util.py --task_name heart --model_type RF

# Run multi-model training
python src/run_multimodel_type.py --task_name heart --model_type RF

# Run benchmark tests
python adda_benchmark_test.py --datasets heart diabetes --models RF XGB
```

### Web Interface
```bash
cd demo && python app.py  # Runs on localhost:5000
```

## Architecture
- **Agents**: AutoGen-based multi-agent system for feature engineering
- **Database**: PostgreSQL with C++ UDFs for ML models (RF, XGBoost, LightGBM)
- **Execution**: Python orchestration + SQL queries + C++ computation
- **DAG**: Directed Acyclic Graph for feature dependencies

## Key Directories
- `/src/llm/` - LLM agents and DAG utilities
- `/src/pg/` - PostgreSQL integration and SQL generation
- `/src/clib/` - C++ UDF implementations and models
- `/dataset/task/` - 14 benchmark datasets
- `/demo/` - Flask web interface

## Configuration
- **Database**: Update `src/env.py` with PostgreSQL credentials
- **API Keys**: Set OpenAI API key in `src/env.py`
- **Models**: Configure in `src/llm/tests/config.yaml`

## Testing
- **Unit**: Individual components in `/src/llm/tests/`
- **Integration**: End-to-end pipeline testing
- **Benchmark**: Multi-dataset evaluation with `adda_benchmark_test.py`

## Output Locations
- **SQL**: `/test/store/{dataset}_{model}_Full/pipe_*/*.sql`
- **Models**: `/src/clib/models/*.pkl`
- **Visualizations**: `/test/store/{dataset}_{model}_Full/graph/*.png`

- Frontend UI must not display Chinese text; use English-only user-facing strings.