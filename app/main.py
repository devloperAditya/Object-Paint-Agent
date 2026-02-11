"""Entrypoint: Gradio app with /health route, served via uvicorn."""

from __future__ import annotations

import argparse
import os

import gradio as gr
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.ui import build_ui


def health():
    return JSONResponse({"status": "ok", "service": "object-paint-agent"})


def get_app():
    """Return FastAPI app with Gradio mounted at / and /health."""
    fastapi_app = FastAPI(title="Object Paint Agent", docs_url=None, redoc_url=None)
    fastapi_app.add_api_route("/health", health, methods=["GET"])
    gradio_app = build_ui()
    gr.mount_gradio_app(fastapi_app, gradio_app, path="/")
    return fastapi_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "7860")))
    args = parser.parse_args()
    app = get_app()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
