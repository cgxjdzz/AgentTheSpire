from __future__ import annotations


def build_stage_event(scope: str, stage: str, message: str, item_id: str | None = None) -> dict | None:
    clean = (message or "").strip()
    if not clean:
        return None

    payload = {
        "scope": scope,
        "stage": stage,
        "message": clean,
    }
    if item_id:
        payload["item_id"] = item_id
    return payload
