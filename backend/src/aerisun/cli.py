from __future__ import annotations

import getpass
import sys

import bcrypt
from sqlalchemy.orm import Session

from aerisun.db import get_session_factory, init_db
from aerisun.models import AdminUser
from aerisun.settings import get_settings


def create_admin() -> None:
    """Create an admin user interactively."""
    settings = get_settings()
    settings.ensure_directories()
    init_db()

    username = input("Admin username: ").strip()
    if not username:
        print("Username cannot be empty.", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass("Admin password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    session_factory = get_session_factory()
    session: Session = session_factory()
    try:
        existing = session.query(AdminUser).filter(AdminUser.username == username).first()
        if existing:
            print(f"User '{username}' already exists.", file=sys.stderr)
            sys.exit(1)

        user = AdminUser(username=username, password_hash=hashed)
        session.add(user)
        session.commit()
        print(f"Admin user '{username}' created successfully.")
    finally:
        session.close()


if __name__ == "__main__":
    create_admin()
