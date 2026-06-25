import sys
sys.path.insert(0, "/app")

# mock account store — replace with real DB calls in production

MOCK_ACCOUNTS = {
    "user@example.com": {
        "name": "Jane Doe", "plan": "Pro", "status": "active",
        "usage": {"api_calls": 4200, "storage_gb": 12.4},
        "billing_cycle": "monthly", "next_billing": "2026-07-01",
    }
}


def get_account_info(email: str) -> dict:
    account = MOCK_ACCOUNTS.get(email)
    if not account:
        return {"found": False, "message": "Account not found."}
    return {"found": True, **account}


def get_usage(email: str) -> dict:
    account = MOCK_ACCOUNTS.get(email)
    if not account:
        return {"found": False}
    return {"found": True, "email": email, **account["usage"]}