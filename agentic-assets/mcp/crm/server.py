"""Mock CRM MCP server (stdio).
 
A single-file, in-memory CRM with basic CRUD for contacts, companies and
deals. No network calls, no file I/O — all state lives in process memory and
is reset every time the server starts. Comes pre-seeded with a little sample
data so the tools return something useful immediately.
 
Every function decorated with ``@mcp.tool`` becomes a tool the agent can call;
the docstring is what it reads to decide when to call it.
"""
 
from __future__ import annotations
 
from datetime import datetime, timezone
from typing import Any, Optional
 
from fastmcp import FastMCP
 
mcp = FastMCP("crm")
 
# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------
 
_DB: dict[str, dict[int, dict[str, Any]]] = {
    "contacts": {},
    "companies": {},
    "deals": {},
}
_NEXT_ID: dict[str, int] = {"contacts": 1, "companies": 1, "deals": 1}
 
CONTACT_FIELDS = {"name", "email", "phone", "title", "company_id", "notes", "tags"}
COMPANY_FIELDS = {"name", "domain", "industry", "size", "notes"}
DEAL_FIELDS = {"title", "value", "stage", "contact_id", "company_id", "notes"}
DEAL_STAGES = ["lead", "qualified", "proposal", "negotiation", "won", "lost"]
 
 
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
 
 
def _create(kind: str, allowed: set[str], data: dict[str, Any]) -> dict[str, Any]:
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Unknown {kind[:-1]} field(s): {sorted(unknown)}")
    rid = _NEXT_ID[kind]
    _NEXT_ID[kind] += 1
    ts = _now()
    record = {"id": rid, **data, "created_at": ts, "updated_at": ts}
    _DB[kind][rid] = record
    return record
 
 
def _get(kind: str, rid: int) -> dict[str, Any]:
    record = _DB[kind].get(rid)
    if record is None:
        raise ValueError(f"{kind[:-1].capitalize()} {rid} not found")
    return record
 
 
def _update(kind: str, allowed: set[str], rid: int, data: dict[str, Any]) -> dict[str, Any]:
    record = _get(kind, rid)
    changes = {k: v for k, v in data.items() if v is not None}
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError(f"Unknown {kind[:-1]} field(s): {sorted(unknown)}")
    record.update(changes)
    record["updated_at"] = _now()
    return record
 
 
def _delete(kind: str, rid: int) -> dict[str, Any]:
    record = _get(kind, rid)
    del _DB[kind][rid]
    return {"deleted": True, kind[:-1]: record}
 
 
def _list(kind: str, query: Optional[str], limit: int) -> list[dict[str, Any]]:
    rows = list(_DB[kind].values())
    if query:
        q = query.lower()
        rows = [r for r in rows if q in " ".join(str(v) for v in r.values()).lower()]
    return rows[: max(1, limit)]
 
 
def _require_exists(kind: str, rid: Optional[int]) -> None:
    if rid is not None:
        _get(kind, rid)
 
 
# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------
 
 
@mcp.tool
def create_contact(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    title: Optional[str] = None,
    company_id: Optional[int] = None,
    notes: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """Create a new contact. ``company_id`` must reference an existing company if given."""
    _require_exists("companies", company_id)
    return _create(
        "contacts",
        CONTACT_FIELDS,
        {
            "name": name,
            "email": email,
            "phone": phone,
            "title": title,
            "company_id": company_id,
            "notes": notes,
            "tags": tags or [],
        },
    )
 
 
@mcp.tool
def get_contact(contact_id: int) -> dict:
    """Fetch a single contact by id."""
    return _get("contacts", contact_id)
 
 
@mcp.tool
def list_contacts(query: Optional[str] = None, limit: int = 50) -> list[dict]:
    """List contacts. ``query`` does a case-insensitive substring match across all fields."""
    return _list("contacts", query, limit)
 
 
@mcp.tool
def update_contact(
    contact_id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    title: Optional[str] = None,
    company_id: Optional[int] = None,
    notes: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    """Update fields on an existing contact. Only provided (non-null) fields are changed."""
    _require_exists("companies", company_id)
    return _update(
        "contacts",
        CONTACT_FIELDS,
        contact_id,
        {
            "name": name,
            "email": email,
            "phone": phone,
            "title": title,
            "company_id": company_id,
            "notes": notes,
            "tags": tags,
        },
    )
 
 
@mcp.tool
def delete_contact(contact_id: int) -> dict:
    """Delete a contact by id. Deals referencing it keep their ``contact_id`` (dangling)."""
    return _delete("contacts", contact_id)
 
 
# ---------------------------------------------------------------------------
# Companies
# ---------------------------------------------------------------------------
 
 
@mcp.tool
def create_company(
    name: str,
    domain: Optional[str] = None,
    industry: Optional[str] = None,
    size: Optional[int] = None,
    notes: Optional[str] = None,
) -> dict:
    """Create a new company (account)."""
    return _create(
        "companies",
        COMPANY_FIELDS,
        {"name": name, "domain": domain, "industry": industry, "size": size, "notes": notes},
    )
 
 
@mcp.tool
def get_company(company_id: int) -> dict:
    """Fetch a single company by id, including its contacts and deals."""
    company = dict(_get("companies", company_id))
    company["contacts"] = [c for c in _DB["contacts"].values() if c.get("company_id") == company_id]
    company["deals"] = [d for d in _DB["deals"].values() if d.get("company_id") == company_id]
    return company
 
 
@mcp.tool
def list_companies(query: Optional[str] = None, limit: int = 50) -> list[dict]:
    """List companies. ``query`` does a case-insensitive substring match across all fields."""
    return _list("companies", query, limit)
 
 
@mcp.tool
def update_company(
    company_id: int,
    name: Optional[str] = None,
    domain: Optional[str] = None,
    industry: Optional[str] = None,
    size: Optional[int] = None,
    notes: Optional[str] = None,
) -> dict:
    """Update fields on an existing company. Only provided (non-null) fields are changed."""
    return _update(
        "companies",
        COMPANY_FIELDS,
        company_id,
        {"name": name, "domain": domain, "industry": industry, "size": size, "notes": notes},
    )
 
 
@mcp.tool
def delete_company(company_id: int) -> dict:
    """Delete a company by id. Contacts and deals that pointed at it keep a dangling ``company_id``."""
    return _delete("companies", company_id)
 
 
# ---------------------------------------------------------------------------
# Deals
# ---------------------------------------------------------------------------
 
 
@mcp.tool
def create_deal(
    title: str,
    value: float = 0.0,
    stage: str = "lead",
    contact_id: Optional[int] = None,
    company_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> dict:
    """Create a new deal. ``stage`` must be one of: lead, qualified, proposal, negotiation, won, lost."""
    if stage not in DEAL_STAGES:
        raise ValueError(f"Invalid stage {stage!r}; must be one of {DEAL_STAGES}")
    _require_exists("contacts", contact_id)
    _require_exists("companies", company_id)
    return _create(
        "deals",
        DEAL_FIELDS,
        {
            "title": title,
            "value": value,
            "stage": stage,
            "contact_id": contact_id,
            "company_id": company_id,
            "notes": notes,
        },
    )
 
 
@mcp.tool
def get_deal(deal_id: int) -> dict:
    """Fetch a single deal by id."""
    return _get("deals", deal_id)
 
 
@mcp.tool
def list_deals(
    query: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """List deals, optionally filtered by ``stage`` and/or a substring ``query``."""
    rows = _list("deals", query, 10_000)
    if stage:
        rows = [d for d in rows if d.get("stage") == stage]
    return rows[: max(1, limit)]
 
 
@mcp.tool
def update_deal(
    deal_id: int,
    title: Optional[str] = None,
    value: Optional[float] = None,
    stage: Optional[str] = None,
    contact_id: Optional[int] = None,
    company_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> dict:
    """Update fields on an existing deal (e.g. move it to a new stage). Only non-null fields change."""
    if stage is not None and stage not in DEAL_STAGES:
        raise ValueError(f"Invalid stage {stage!r}; must be one of {DEAL_STAGES}")
    _require_exists("contacts", contact_id)
    _require_exists("companies", company_id)
    return _update(
        "deals",
        DEAL_FIELDS,
        deal_id,
        {
            "title": title,
            "value": value,
            "stage": stage,
            "contact_id": contact_id,
            "company_id": company_id,
            "notes": notes,
        },
    )
 
 
@mcp.tool
def delete_deal(deal_id: int) -> dict:
    """Delete a deal by id."""
    return _delete("deals", deal_id)
 
 
# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
 
 
@mcp.tool
def pipeline_summary() -> dict:
    """Summarise the deal pipeline: count and total value per stage, plus overall totals."""
    by_stage = {s: {"count": 0, "value": 0.0} for s in DEAL_STAGES}
    for d in _DB["deals"].values():
        bucket = by_stage.setdefault(d["stage"], {"count": 0, "value": 0.0})
        bucket["count"] += 1
        bucket["value"] += float(d.get("value") or 0)
    open_stages = [s for s in DEAL_STAGES if s not in ("won", "lost")]
    return {
        "by_stage": by_stage,
        "open_count": sum(by_stage[s]["count"] for s in open_stages),
        "open_value": sum(by_stage[s]["value"] for s in open_stages),
        "won_value": by_stage["won"]["value"],
        "totals": {k: len(v) for k, v in _DB.items()},
    }
 
 
@mcp.tool
def reset_crm(seed: bool = True) -> dict:
    """Wipe all in-memory data. If ``seed`` is true, reload the sample dataset afterwards."""
    for kind in _DB:
        _DB[kind].clear()
        _NEXT_ID[kind] = 1
    if seed:
        _seed()
    return {"reset": True, "seeded": seed, "totals": {k: len(v) for k, v in _DB.items()}}
 
 
# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------
 
 
def _seed() -> None:
    acme = _create("companies", COMPANY_FIELDS, {"name": "Acme Corp", "domain": "acme.com", "industry": "Manufacturing", "size": 250, "notes": None})
    globex = _create("companies", COMPANY_FIELDS, {"name": "Globex", "domain": "globex.io", "industry": "Software", "size": 40, "notes": None})
 
    dana = _create("contacts", CONTACT_FIELDS, {"name": "Dana Levi", "email": "dana@acme.com", "phone": "+1-555-0101", "title": "VP Operations", "company_id": acme["id"], "notes": None, "tags": ["decision-maker"]})
    omer = _create("contacts", CONTACT_FIELDS, {"name": "Omer Katz", "email": "omer@globex.io", "phone": "+1-555-0102", "title": "CTO", "company_id": globex["id"], "notes": "Met at conference", "tags": ["technical"]})
    _create("contacts", CONTACT_FIELDS, {"name": "Maya Cohen", "email": "maya@example.com", "phone": None, "title": "Freelance consultant", "company_id": None, "notes": None, "tags": []})
 
    _create("deals", DEAL_FIELDS, {"title": "Acme annual license", "value": 48000, "stage": "proposal", "contact_id": dana["id"], "company_id": acme["id"], "notes": None})
    _create("deals", DEAL_FIELDS, {"title": "Globex pilot", "value": 12000, "stage": "qualified", "contact_id": omer["id"], "company_id": globex["id"], "notes": "3-month pilot"})
    _create("deals", DEAL_FIELDS, {"title": "Globex expansion", "value": 90000, "stage": "lead", "contact_id": omer["id"], "company_id": globex["id"], "notes": None})
 
 
_seed()