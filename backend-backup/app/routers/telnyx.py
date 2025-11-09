# This file is DEPRECATED - use telnyx_webhooks.py instead
from fastapi import APIRouter
router = APIRouter(prefix="/telnyx", tags=["telnyx"])
# All webhook handlers moved to telnyx_webhooks.py
