# Local Testing

Process a single episode without the SQS worker loop: in `src/main.py`, comment out the `main()` call, uncomment one of the example payloads at the bottom, and pass it to `process_payload(payload)`. Requires AWS credentials (config comes from SSM; results go to DynamoDB/S3) and `ffmpeg`.

```bash
uv sync
export BASE_PATH=. PYTHONPATH=$PWD
mkdir -p downloads output

uv run python src/main.py
```

GPU is optional — the Whisper `tiny` model runs on CPU, just slower.

## Building the Image

```bash
docker build -t jusskipit-app .
docker run --gpus all jusskipit-app
```

Drop `--gpus all` to run on CPU.