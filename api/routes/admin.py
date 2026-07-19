"""Admin endpoints triggered via QStash or Admin Key."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from engine.backtesting.scorer import score_pending_predictions

router = APIRouter()


async def verify_admin_or_qstash(
    request: Request,
    x_admin_key: str | None,
    upstash_signature: str | None,
) -> bool:
    """Verifies that the request comes from either an Admin or QStash."""
    admin_key = os.getenv("ADMIN_KEY")
    is_admin = bool(admin_key and x_admin_key == admin_key)

    is_qstash = False
    if upstash_signature:
        current_key = os.getenv("QSTASH_CURRENT_SIGNING_KEY")
        next_key = os.getenv("QSTASH_NEXT_SIGNING_KEY")
        if current_key and next_key:
            try:
                from qstash import Receiver
                receiver = Receiver(
                    current_signing_key=current_key,
                    next_signing_key=next_key,
                )
                body = await request.body()
                receiver.verify(
                    body=body.decode("utf-8"),
                    signature=upstash_signature,
                    url=None,  # Skip URL validation to avoid proxy issues on Render
                )
                is_qstash = True
            except Exception as e:
                raise HTTPException(status_code=403, detail=f"Invalid QStash signature: {e}")

    if not is_admin and not is_qstash:
        raise HTTPException(status_code=403, detail="Unauthorized")

    return True


@router.post("/admin/score-now")
async def trigger_score_now(
    request: Request,
    x_admin_key: str | None = Header(default=None),
    upstash_signature: str | None = Header(default=None, alias="Upstash-Signature"),
) -> dict[str, Any]:
    """Force run the pending predictions scorer."""
    await verify_admin_or_qstash(request, x_admin_key, upstash_signature)
    
    result = score_pending_predictions()
    return result
