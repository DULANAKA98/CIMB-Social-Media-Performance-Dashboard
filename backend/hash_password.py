"""
Create a DASHBOARD_USERS entry for a dashboard account.

    python backend/hash_password.py            # prompts for username and password
    python backend/hash_password.py --secret   # prints a new SESSION_SECRET

The password is read without echo and never stored; only its salted hash is printed.
Join several users' entries with commas in DASHBOARD_USERS.
"""
import getpass
import secrets
import sys

from auth import USERNAME_PATTERN, hash_password

if __name__ == "__main__":
    if "--secret" in sys.argv:
        print(f"SESSION_SECRET={secrets.token_urlsafe(48)}")
        sys.exit(0)
    username = input("Username: ").strip()
    if not USERNAME_PATTERN.match(username):
        sys.exit("Use 1-64 letters, numbers, dots, dashes, underscores or @.")
    password = getpass.getpass("Password (min 12 characters): ")
    if len(password) < 12:
        sys.exit("Use at least 12 characters.")
    if getpass.getpass("Repeat password: ") != password:
        sys.exit("Passwords do not match.")
    print(f"{username.lower()}:{hash_password(password)}")
