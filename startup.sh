#!/bin/bash

# Initialize PYTHONPATH with any existing value, defaulting to empty if not set
export PYTHONPATH="${PYTHONPATH:-}"

# Check if /app/ directory exists and append it to PYTHONPATH
if [ -d "/app/" ]; then
    export PYTHONPATH="$PYTHONPATH:/app/"
fi

# Activate the virtual environment
# source venv/bin/activate

# Set environment variables using the Python script
eval $(python3 set_env_vars.py)

cleanup() {
    echo "Cleaning up..."
    if [ -n "$PID" ]; then
        kill $PID 2>/dev/null
    fi
}

# Trap the EXIT signal to run the cleanup function
trap cleanup EXIT

# Run the application in the background
python3 src/api/stream_mp3.py &

# Get the process ID of the last background command
PID=$!

if ps -p $PID > /dev/null
then
   echo "Process started successfully, PID=$PID"
else
   echo "Failed to start process"
fi

# Wait for the background process to finish
wait $PID