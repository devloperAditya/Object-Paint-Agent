# Operations

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | 7860 | HTTP server port |
| `MAX_IMAGE_PIXELS` | 1024 | Max image dimension (0 = no resize) |
| `DATA_DIR` | ./data | Export directory for painted images and metadata |
| `MODEL_CACHE_DIR` | ./models | Directory for optional model weights |
| `LITE_MODE` | (unset) | Set to `true` to prefer GrabCut and skip heavy model load |

## Logging

- Application logs go to stdout/stderr. In Docker, use the default JSON or text driver; with ECS/App Runner, send stdout to CloudWatch Logs.
- No PII is logged in the base implementation; avoid logging uploaded file contents or user-provided paths.

## Metrics (suggestion)

- **Health**: Use `GET /health` for liveness and readiness (returns 200 when the app is up).
- Optional: instrument request duration and error count (e.g. Prometheus client or CloudWatch metrics) in the FastAPI app.
- Optional: track pipeline step timings (segment, recolor) in metadata and aggregate in your monitoring.

## Restarts and deployment

- Graceful shutdown: uvicorn handles SIGTERM; allow a short drain period in the load balancer (e.g. 30 s) before terminating tasks.
- No in-memory session store; restart-safe. For persistence of exports, use a volume or object store (see AWS_DEPLOYMENT.md).
