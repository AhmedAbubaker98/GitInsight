#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "Starting API Service..."

# Start Uvicorn server for FastAPI app in the background
echo "Starting Uvicorn..."
uvicorn api_service.main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!
echo "Uvicorn PID: $UVICORN_PID"

# Start RQ worker for the results queue in the background
# The worker needs to import api_service.tasks.result_consumer.process_analysis_result
# Ensure PYTHONPATH is set correctly or modules are importable.
# RQ worker command needs the python path to the task function.
# RQ will call the function `api_service.tasks.result_consumer.process_analysis_result`
echo "Starting RQ worker for results queue: ${RESULT_QUEUE:-gitinsight_results}..."
echo "Redis URL for worker: ${REDIS_URL}"

# Give a moment for Uvicorn to start and potentially log errors
sleep 2

# Using `python -m rq worker` is often more robust for module discovery
python -m rq worker -u "${REDIS_URL}" "${RESULT_QUEUE:-gitinsight_results}" &
RQ_WORKER_PID=$!
echo "RQ Worker PID: $RQ_WORKER_PID"

# Graceful shutdown trap
trap 'echo "Shutting down..."; kill $UVICORN_PID $RQ_WORKER_PID; wait $UVICORN_PID; wait $RQ_WORKER_PID; exit 0' SIGINT SIGTERM

# Wait for any process to exit
wait -n $UVICORN_PID $RQ_WORKER_PID

# If Uvicorn exits, stop the RQ worker
if ! kill -0 $UVICORN_PID 2>/dev/null; then
    echo "Uvicorn exited, stopping RQ worker..."
    kill $RQ_WORKER_PID
    wait $RQ_WORKER_PID
    exit 1 # Exit with error if Uvicorn died
fi

# If RQ worker exits, stop Uvicorn
if ! kill -0 $RQ_WORKER_PID 2>/dev/null; then
    echo "RQ worker exited, stopping Uvicorn..."
    kill $UVICORN_PID
    wait $UVICORN_PID
    exit 1 # Exit with error if RQ worker died
fi

exit 0