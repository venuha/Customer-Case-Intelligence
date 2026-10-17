import httpx, pytest
from app.integrations.banking import PlaidSandbox, BankUnavailable


def test_read_only_sandbox_pagination(monkeypatch):
    for k in ("PLAID_CLIENT_ID", "PLAID_SECRET", "PLAID_ACCESS_TOKEN"):
        monkeypatch.setenv(k, "unit-test-placeholder")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "added": [{"transaction_id": str(len(calls))}],
                "modified": [],
                "removed": [],
                "next_cursor": str(len(calls)),
                "has_more": len(calls) < 2,
            },
        )

    result = PlaidSandbox(
        httpx.Client(transport=httpx.MockTransport(handler))
    ).transactions()
    assert len(result["added"]) == 2 and not result["proves_refund_acceptance"]
    assert all(
        str(r.url) == "https://sandbox.plaid.com/transactions/sync" for r in calls
    )


def test_provider_error_does_not_leak_credentials(monkeypatch):
    for k in ("PLAID_CLIENT_ID", "PLAID_SECRET", "PLAID_ACCESS_TOKEN"):
        monkeypatch.setenv(k, "private-test-value")
    bank = PlaidSandbox(
        httpx.Client(
            transport=httpx.MockTransport(
                lambda r: httpx.Response(400, json={"secret": "private-test-value"})
            )
        )
    )
    with pytest.raises(BankUnavailable) as error:
        bank.transactions()
    assert "private-test-value" not in str(error.value)
