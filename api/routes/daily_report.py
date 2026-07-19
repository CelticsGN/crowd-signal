"""Daily report routes for morning catalyst summary."""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request

from engine.scanner.catalyst_scanner import get_todays_report, run_daily_scan

router = APIRouter()


@router.get("/daily-report")
async def daily_report() -> dict[str, Any]:
    report = get_todays_report()
    if report is None:
        return {
            "status": "generating",
            "message": "Report not ready yet",
            "us_entries": [],
            "in_entries": [],
        }

    payload = dict(report)
    payload["status"] = "ready"
    return payload


@router.post("/daily-report/trigger")
async def trigger_daily_report(
    request: Request,
    x_admin_key: str | None = Header(default=None),
    upstash_signature: str | None = Header(default=None, alias="Upstash-Signature"),
) -> dict[str, Any]:
    from api.routes.admin import verify_admin_or_qstash
    await verify_admin_or_qstash(request, x_admin_key, upstash_signature)

    summary = await run_daily_scan("ALL")
    return {
        "tickers_scanned": int(summary.get("tickers_scanned", 0)),
        "catalysts_found": int(summary.get("catalysts_found", 0)),
        "simulations_run": int(summary.get("simulations_run", 0)),
        "report_date": str(summary.get("report_date", "")),
        "errors": list(summary.get("errors", [])),
        "skipped_tickers": list(summary.get("skipped_tickers", [])),
    }
