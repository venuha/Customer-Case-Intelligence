"""Optional read-only Plaid sandbox transaction feed; no payment capabilities."""

import os
import httpx


class BankUnavailable(RuntimeError):
    pass


class PlaidSandbox:
    def __init__(self, client=None):
        self.client = client or httpx.Client(timeout=20)

    def configured(self):
        return all(
            os.getenv(k)
            for k in ("PLAID_CLIENT_ID", "PLAID_SECRET", "PLAID_ACCESS_TOKEN")
        )

    def transactions(self, cursor=None):
        if not self.configured():
            raise BankUnavailable("Bank sandbox is not configured.")
        added = []
        modified = []
        removed = []
        for _ in range(100):
            payload = {
                k: os.environ[v]
                for k, v in [
                    ("client_id", "PLAID_CLIENT_ID"),
                    ("secret", "PLAID_SECRET"),
                    ("access_token", "PLAID_ACCESS_TOKEN"),
                ]
            }
            if cursor:
                payload["cursor"] = cursor
            try:
                response = self.client.post(
                    "https://sandbox.plaid.com/transactions/sync", json=payload
                )
                if response.status_code != 200:
                    raise BankUnavailable(
                        "Bank sandbox request failed; review provider dashboard privately."
                    )
                data = response.json()
                added.extend(data["added"])
                modified.extend(data["modified"])
                removed.extend(data["removed"])
                cursor = data["next_cursor"]
                if not data["has_more"]:
                    return {
                        "added": added,
                        "modified": modified,
                        "removed": removed,
                        "next_cursor": cursor,
                        "environment": "sandbox",
                        "proves_refund_acceptance": False,
                    }
            except (httpx.HTTPError, ValueError, KeyError):
                raise BankUnavailable(
                    "Bank sandbox returned an unusable response."
                ) from None
        raise BankUnavailable(
            "Pagination limit reached. Cursor was not committed; retry from the original checkpoint."
        )
