"""Render entrypoint.

Some deployments point uvicorn/gunicorn to `app:app`. To avoid ambiguity,
this module simply re-exports the FastAPI instance from main.py.
"""

from main import app  # noqa: F401
