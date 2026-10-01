"""Operator-reviewed data transfer controls; not a legal compliance certificate."""
import os


class DataTransferBlocked(RuntimeError):
    pass


def require_reviewed_transfer(provider: str) -> None:
    """Block production provider calls until their transfer inventory is reviewed.

    Approval is an operator decision backed by contracts and an inventory, never
    a substitute for a lawful processing basis or an end-user consent checkbox.
    """
    if os.getenv("APP_ENV", "").lower() != "production":
        return
    approved = {item.strip().lower() for item in os.getenv(
        "PRIVACY_REVIEWED_PROVIDERS", "").split(",") if item.strip()}
    if provider.lower() not in approved:
        raise DataTransferBlocked(f"Data transfer review required: {provider}")


def scrub_error_event(event, hint):
    """Remove payloads, identity, breadcrumbs and captured locals before export."""
    for key in ("user", "request", "breadcrumbs", "extra", "contexts"):
        event.pop(key, None)
    # Exception messages and locals can contain prompts, filenames or tokens.
    for item in event.get("exception", {}).get("values", []):
        item["value"] = "[redacted]"
        for frame in item.get("stacktrace", {}).get("frames", []):
            frame.pop("vars", None)
    event.pop("message", None)
    event.pop("logentry", None)
    event.pop("transaction", None)
    event.pop("tags", None)
    return event
