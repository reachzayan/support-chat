from __future__ import annotations

ERROR_MESSAGES = {
    "browser_crash": "The browser could not open this page.",
    "browser": "The browser could not open this page.",
    "timeout": "This page took too long to open.",
    "empty": "This page had no usable answers.",
    "ssrf": "This page could not be opened from our servers.",
    "http": "This page could not be opened.",
    "fetch": "This page could not be opened.",
    "extract": "This page could not be read.",
    "llm_extract": "This page could not be turned into answers.",
    "embed": "The answers could not be prepared for search.",
    "persist": "This page could not be saved.",
    "oversize": "This page was too large to save.",
    "numeric_fact_preservation": (
        "This page's numbers did not match the saved answers, so those answers were skipped."
    ),
    "no_truncation": "One answer was cut off, so it was skipped.",
    "schema": "One answer was incomplete, so it was skipped.",
    "dedupe": "Duplicate answers were skipped.",
    "size_cap": "One answer was too long, so it was skipped.",
    "smoke_assertions": "Required phrases were missing from the saved answers.",
    "validation": "This page's answers did not pass review, so they were skipped.",
    "page_failures": "Some pages could not be processed.",
}

STAGE_RUNNING = {
    "fetch": "Opening this page.",
    "extract": "Reading this page.",
    "llm_extract": "Turning this page into answers.",
    "embed": "Preparing answers for search.",
    "persist": "Saving this page.",
}

STAGE_DONE = {
    "fetch": "Opened this page.",
    "extract": "Read this page.",
    "llm_extract": "Turned this page into answers.",
    "embed": "Prepared answers for search.",
    "persist": "Saved this page.",
}


def describe_progress_event(
    *,
    stage: str,
    state: str,
    error_code: str | None = None,
) -> str:
    if error_code:
        base = ERROR_MESSAGES.get(error_code, "This page could not be finished.")
        if state == "transient_failed":
            return f"{base} Trying again."
        return base
    if state == "unchanged":
        return "This page had not changed, so the live answers were kept."
    if state == "running":
        return STAGE_RUNNING.get(stage, "Working on this page.")
    if state == "done":
        return STAGE_DONE.get(stage, "Finished this page.")
    if state == "dead_letter":
        return "This page could not be finished."
    return "Working on this page."
