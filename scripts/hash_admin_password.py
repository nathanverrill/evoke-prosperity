"""Hash a password for EVOKE_ADMIN_PASSWORD_HASH (see evoke/auth_session.py).

The Evoke Admin login (POST /api/admin/login) is disabled entirely unless
this env var is set to a real bcrypt hash -- there's no default password,
and the app never sees or stores the plaintext.

Usage:
    python3 scripts/hash_admin_password.py
    (prompts for the password so it never lands in shell history)

Then set in .env:
    EVOKE_ADMIN_PASSWORD_HASH=<printed hash>
    EVOKE_ADMIN_USERNAME=admin   # or whatever you want the username to be
"""
import getpass
import bcrypt


def main():
    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm: ")
    if password != confirm:
        print("Passwords didn't match.")
        return
    if len(password) < 12:
        print("Use at least 12 characters -- this account can release/unrelease missions for a whole class.")
        return
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    print("\nEVOKE_ADMIN_PASSWORD_HASH=" + hashed)


if __name__ == "__main__":
    main()
