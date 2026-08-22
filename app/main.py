from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import credentials, health, lifecycle, messages, oauth, send, workflows

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

app = FastAPI(
    title="Nimba SMS pour monday.com",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Les vues de l'app tournent dans une iframe servie par un sous-domaine monday.
# Sans ce middleware, tous les appels du frontend vers ce backend sont bloques
# par le navigateur et la vue reste inerte.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://([a-z0-9-]+\.)*monday\.(com|app)",
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600,
)

@app.middleware("http")
async def security_headers(request, call_next):
    """En-tetes exiges par la revue securite du marketplace."""
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.include_router(health.router)
app.include_router(workflows.router)
app.include_router(credentials.router)
app.include_router(send.router)
app.include_router(messages.router)
app.include_router(oauth.router)
app.include_router(lifecycle.router)
