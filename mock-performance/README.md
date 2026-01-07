# mock-performance

A lightweight mock backend that provides the same API shape as `frontend/app.py` for:

- `POST /auto-step/`
- `POST /performance-evaluation/`

By default, the mock payload comes from `mock-performance/perf_eval_real_min.json` (the last captured real backend response).

You can also use an inline JSON blob in `mock_backend.py` for quick edits.

## Run

```bash
# from repo root
python mock-performance/mock_backend.py

# or choose a different port
MOCK_PORT=5001 python mock-performance/mock_backend.py

# prefer inline MOCK_DATA_JSON instead of perf_eval_real_min.json
MOCK_PREFER_INLINE_JSON=1 MOCK_PORT=5001 python mock-performance/mock_backend.py
```

## Edit mock payloads

Default: edit `mock-performance/perf_eval_real_min.json`.

Or, if you run with `MOCK_PREFER_INLINE_JSON=1`, edit `mock-performance/mock_backend.py` and update `MOCK_DATA_JSON`.
