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
