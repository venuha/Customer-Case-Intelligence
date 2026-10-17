"""Local administration; passwords are prompted, never passed in command arguments."""

import argparse, getpass, json, secrets, sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.security.auth import create_user
from app.config import data_dir, runtime_dir


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["create", "demo"])
    p.add_argument("--username")
    p.add_argument("--role", choices=["customer_service", "supervisor", "head"])
    p.add_argument("--cases", nargs="+")
    args = p.parse_args()
    cases = [c["id"] for c in json.loads((data_dir() / "cases.json").read_text())]
    if args.action == "demo":
        users = []
        for name, role, assigned in [
            ("service", "customer_service", cases[:4]),
            ("supervisor", "supervisor", cases),
            ("head", "head", cases),
        ]:
            password = secrets.token_urlsafe(18)
            create_user(name, password, role, assigned)
            users.append({"username": name, "password": password, "role": role})
        path = runtime_dir() / "demo-access.json"
        path.write_text(json.dumps(users, indent=2))
        os.chmod(path, 0o600)
        print(
            "Created three local demo accounts. Their generated passwords are in the ignored runtime file work/demo-access.json. They are not included in reports, ZIP files, or Git."
        )
    else:
        if not args.username or not args.role:
            p.error("--username and --role are required")
        assigned = args.cases or cases
        if not set(assigned) <= set(cases):
            p.error("Unknown case ID")
        create_user(
            args.username,
            getpass.getpass("Password (12+ characters): "),
            args.role,
            assigned,
        )
        print("User created.")


if __name__ == "__main__":
    main()
