#!/bin/bash
set -e

# Ensure required directories exist with proper permissions
mkdir -p /adda/src/clib/lib /adda/src/clib/models
chmod 777 /adda/src/clib/models

# Copy pre-compiled UDF .so files to the shared volume on first start
if [ ! -f /adda/src/clib/lib/udf_rf.so ] && [ ! -f /adda/src/clib/lib/udf_xgboost.so ]; then
    echo "Initializing shared UDF library volume..."
    cp /adda/src/clib/lib-built/*.so /adda/src/clib/lib/ 2>/dev/null || true
    echo "UDF libraries copied to shared volume."
fi

exec docker-entrypoint.sh "$@"
