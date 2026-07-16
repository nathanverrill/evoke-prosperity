"""Add a stakeholder or playtester and print their magic auto-login link.

Bypasses Brightspace/LTI entirely -- creates a plain users row (no
evoke_identities), assigns them to a team by name (created if it doesn't
exist), and prints a ?login= link that logs them in as themselves on click,
no password, no manual account creation on their end.

Usage:
    python3 scripts/add_playtester.py "Hailey Smith" hailey@example.com "Stakeholders"
    python3 scripts/add_playtester.py "Jordan Lee" jordan@example.com "Playtesters"

Reads PUBLIC_WEB_URL from .env for the link's host; falls back to
http://localhost:8000 if unset (e.g. testing before ngrok is up).
"""
import sys
import os
import requests

WEB_URL = "http://localhost:8000"


def load_public_url():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("PUBLIC_WEB_URL="):
                    return line.strip().split("=", 1)[1]
    return None


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    display_name, email, team_name = sys.argv[1], sys.argv[2], sys.argv[3]

    resp = requests.post(
        f"{WEB_URL}/api/admin/playtest-user",
        data={"email": email, "display_name": display_name, "team_name": team_name},
    )
    resp.raise_for_status()
    data = resp.json()

    public_url = load_public_url() or WEB_URL
    link = f"{public_url}/?login={email}"

    print(f"{display_name} <{email}> -> team '{team_name}'")
    print(f"  user_id: {data['user_id']}")
    print(f"  link:    {link}")


if __name__ == "__main__":
    main()
