"""Conservative language for negative event claims; original source excerpts stay intact."""

import re


def qualify_missing_event(text):
    if re.search(
        r"\b(evidenc\w*|records?|document\w*|unknown|unconfirmed|not established)\b",
        text,
        re.I,
    ):
        return text
    negative = re.search(r"\b(no|never|not|hasn't|haven't|didn't)\b", text, re.I)
    events = []
    for pattern, label in [
        (r"warehouse|intake|device.*receiv", "warehouse intake or device acceptance"),
        (r"approv", "refund approval"),
        (r"submi|processor", "processor submission"),
        (r"post|credit|bank", "posted bank credit"),
    ]:
        if re.search(pattern, text, re.I):
            events.append(label)
    if negative and events:
        return (
            "The available records do not establish "
            + ", ".join(events)
            + ". This does not prove the event never occurred."
        )
    return text
