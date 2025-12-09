# main.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

BASE_URL = os.getenv("USASPENDING_BASE_URL", "https://api.usaspending.gov").rstrip("/")

mcp = FastMCP("USAspending Tools", mask_error_details=True)

# Reuse a single client for performance.
_http_client = httpx.AsyncClient(
    base_url=BASE_URL,
    timeout=httpx.Timeout(30.0),
    headers={"Accept": "application/json"},
)


async def _raise_for_usaspending(resp: httpx.Response) -> None:
    """Normalize HTTP errors into user-visible ToolError messages."""
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        # Try to include any server-provided JSON detail when safe.
        detail = ""
        try:
            payload = resp.json()
            detail = f" Response: {payload}" if payload else ""
        except Exception:
            # Fallback to text (truncated)
            txt = (resp.text or "").strip()
            if txt:
                detail = f" Response: {txt[:500]}"
        raise ToolError(f"USAspending API error {resp.status_code} for {resp.request.method} {resp.request.url}.{detail}") from e


@mcp.tool
async def recipient_autocomplete(
    search_text: str,
    limit: int = 10,
    recipient_levels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    POST /api/v2/autocomplete/recipient/

    Searches recipients by text across recipient_name, uei, and duns.
    """
    if not search_text or not search_text.strip():
        raise ToolError("search_text is required and cannot be empty.")
    if limit < 1:
        raise ToolError("limit must be >= 1.")
    if limit > 500:
        raise ToolError("limit must be <= 500.")

    body: Dict[str, Any] = {"search_text": search_text, "limit": limit}
    if recipient_levels is not None:
        body["recipient_levels"] = recipient_levels

    resp = await _http_client.post("/api/v2/autocomplete/recipient/", json=body)
    await _raise_for_usaspending(resp)
    return resp.json()


@mcp.tool
async def recipient_list(
    awarding_agency_id: Union[int, float],
    fiscal_year: Union[int, float],
    limit: Optional[int] = None,
    page: Optional[int] = None,
) -> Dict[str, Any]:
    """
    GET /api/v2/award_spending/recipient/

    Returns a list of recipients and their amounts for a given awarding_agency_id + fiscal_year.
    """
    params: Dict[str, Any] = {
        "awarding_agency_id": awarding_agency_id,
        "fiscal_year": fiscal_year,
    }
    if limit is not None:
        if limit < 1:
            raise ToolError("limit must be >= 1.")
        params["limit"] = limit
    if page is not None:
        if page < 1:
            raise ToolError("page must be >= 1.")
        params["page"] = page

    resp = await _http_client.get("/api/v2/award_spending/recipient/", params=params)
    await _raise_for_usaspending(resp)
    return resp.json()


@mcp.tool
async def spending_by_award(
    filters: Dict[str, Any],
    fields: List[str],
    limit: Optional[int] = None,
    order: str = "desc",
    page: Optional[int] = None,
    sort: Optional[str] = None,
    subawards: bool = False,
    last_record_unique_id: Optional[int] = None,
    last_record_sort_value: Optional[str] = None,
    spending_level: str = "awards",
) -> Dict[str, Any]:
    """
    POST /api/v2/search/spending_by_award/

    Takes award filters + requested fields and returns the fields of the filtered awards.
    """
    if not isinstance(filters, dict) or not filters:
        raise ToolError("filters must be a non-empty object.")
    if not isinstance(fields, list) or not fields:
        raise ToolError("fields must be a non-empty array of strings.")
    if order not in ("asc", "desc"):
        raise ToolError("order must be 'asc' or 'desc'.")
    if spending_level not in ("awards", "subawards"):
        raise ToolError("spending_level must be 'awards' or 'subawards'.")

    body: Dict[str, Any] = {
        "filters": filters,
        "fields": fields,
        "order": order,
        "subawards": subawards,
        "spending_level": spending_level,
    }
    if limit is not None:
        if limit < 1:
            raise ToolError("limit must be >= 1.")
        body["limit"] = limit
    if page is not None:
        if page < 1:
            raise ToolError("page must be >= 1.")
        body["page"] = page
    if sort is not None:
        body["sort"] = sort
    if last_record_unique_id is not None:
        body["last_record_unique_id"] = last_record_unique_id
    if last_record_sort_value is not None:
        body["last_record_sort_value"] = last_record_sort_value

    resp = await _http_client.post("/api/v2/search/spending_by_award/", json=body)
    await _raise_for_usaspending(resp)
    return resp.json()


@mcp.tool
async def recipient_children(
    duns_or_uei: str,
    year: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    GET /api/v2/recipient/children/{duns_or_uei}/

    Returns a list of child recipients for a parent DUNS or UEI.
    Optional year: fiscal year, or 'all', or 'latest'.
    """
    if not duns_or_uei or not duns_or_uei.strip():
        raise ToolError("duns_or_uei is required and cannot be empty.")

    params: Dict[str, Any] = {}
    if year is not None:
        params["year"] = year

    path = f"/api/v2/recipient/children/{duns_or_uei.strip()}/"
    resp = await _http_client.get(path, params=params)
    await _raise_for_usaspending(resp)
    return resp.json()


# Optional: expose the OpenAPI YAML as a resource for easy retrieval by clients
# (This is not required, but handy.)
@mcp.resource("usaspending://openapi/selected.yaml")
def selected_openapi_schema() -> str:
    """Return the OpenAPI schema (selected endpoints) as YAML."""
    # Keep it light: load from a file if you prefer, but embedding is fine too.
    # If you want to load from disk, replace with: return Path("openapi.yaml").read_text()
    return os.getenv("USASPENDING_SELECTED_OPENAPI_YAML", "").strip()


async def _close_client() -> None:
    await _http_client.aclose()


if __name__ == "__main__":
    try:
        # Run with streamable HTTP transport on localhost:8000
        mcp.run(transport="streamable-http", port=8000, host="localhost")
    finally:
        # Ensure we close the underlying HTTP client on shutdown
        try:
            import asyncio

            asyncio.run(_close_client())
        except Exception:
            pass
