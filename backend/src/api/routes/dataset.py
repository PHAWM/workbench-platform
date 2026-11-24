"""
Dataset routes - redirects to ml_pipeline for import functionality.

The dataset import endpoint is available at:
    POST /api/v1/pipeline/dataset/import/

This file is kept as a placeholder. The dataset router is still
registered in main.py but has no endpoints of its own.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/dataset", tags=["Dataset"])
