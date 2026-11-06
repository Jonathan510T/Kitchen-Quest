import getpass

from sqlalchemy import select

from . import models
from .database import SessionLocal
from .security import hash_password


def main():
    username = input("Admin username: ").strip().lower()
    password = getpass.getpass("Password (min 8 characters): ")
    if len(password) < 8:
        raise SystemExit("Password too short")
    with SessionLocal() as db:
        if db.scalar(select(models.User).where(models.User.username == username)):
            raise SystemExit("That username already exists")
        db.add(
            models.User(
                username=username,
                password_hash=hash_password(password),
                role=models.Role.admin,
            )
        )
        db.commit()
    print(f"Admin '{username}' created")


if __name__ == "__main__":
    main()