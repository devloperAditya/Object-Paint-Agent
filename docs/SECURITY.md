# Security

## File validation

- **Allowed types**: PNG, JPG, JPEG only (by extension and MIME where applicable).
- **Size limit**: Uploads are limited (e.g. 20 MB) to avoid DoS and memory exhaustion.
- **Image parsing**: Images are loaded with Pillow/OpenCV; invalid or malicious image data can raise; errors are caught and returned as user-visible messages rather than crashing the server.

## Safe image handling

- **Max dimensions**: `MAX_IMAGE_PIXELS` (default 1024) limits the maximum dimension after load to reduce memory and CPU load. No distortion of the original aspect ratio; resize is proportional.
- **Alpha**: Alpha channel is preserved as-is; no arbitrary code or metadata execution from image bytes.
- **Outputs**: Exports (PNG, JSON) are written under a configured directory (`DATA_DIR`); filenames are generated (timestamp-based) to avoid path traversal.

## Recommendations

- Run the container as a non-root user (Dockerfile does this).
- In production, put the app behind a reverse proxy (ALB, nginx) and enforce HTTPS and rate limiting.
- Do not expose internal ports beyond the load balancer; restrict security groups accordingly.
- For multi-tenant or untrusted users, consider stricter limits (smaller `MAX_IMAGE_PIXELS`, lower upload size) and optional authentication (e.g. Gradio auth or OAuth at the proxy).
