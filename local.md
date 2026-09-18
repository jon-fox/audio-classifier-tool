# Local Testing

Process a single episode without the SQS worker loop: in `src/main.py`, comment out the `main()` call, uncomment one of the example payloads at the bottom, and pass it to `process_payload(payload)`. Requires AWS credentials (config comes from SSM; results go to DynamoDB/S3) and `ffmpeg`.

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export BASE_PATH=. PYTHONPATH=$PWD
mkdir -p downloads output

python3 src/main.py
```

GPU is optional — the Whisper `tiny` model runs on CPU, just slower.
