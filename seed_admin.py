"""
Run once to create the initial admin account.

Usage:
    python seed_admin.py --username admin --password yourpassword
"""
import argparse

from app.db.database import SessionLocal
from app.models.admin_model import Admin
from app.utils.security import hash_password


def seed(username: str, password: str):
    db = SessionLocal()
    try:
        existing = db.query(Admin).filter(Admin.username == username).first()
        if existing:
            print(f"Admin '{username}' already exists.")
            return
        admin = Admin(username=username, password_hash=hash_password(password))
        db.add(admin)
        db.commit()
        print(f"Admin '{username}' created successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()
    seed(args.username, args.password)
