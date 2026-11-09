"""Creates two LOCAL TEST accounts so you can try the Pro and Admin parts before payments exist.
Run from the backend folder:  python -m app.seed
Do not run this on any public server."""
from datetime import timedelta

from .db import Base, SessionLocal, engine
from .models import User, utcnow
from .security import hash_password

TEST_PASSWORD = "genesis-demo-123"
ACCOUNTS = [("pro@genesis.test", "pro"), ("admin@genesis.test", "admin")]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for email, role in ACCOUNTS:
            user = db.query(User).filter(User.email == email).first()
            if user is None:
                user = User(email=email, password_hash=hash_password(TEST_PASSWORD), role=role)
                db.add(user)
            user.role = role
            user.pro_expires_at = utcnow() + timedelta(days=365)
            print(f"{role:5} account ready: {email} / {TEST_PASSWORD}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
