"""Create or update the first flipflop-admin staff account.

Usage:
    python scripts/seed_admin_user.py --email mac@theflipflop.shop --name "Mac" --password "..." --role owner

Run once per environment to bootstrap admin access. Safe to re-run: if the
email already exists, it updates the password/name/role instead of failing.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.admin_user import AdminUser
from app.services.auth_service import hash_password


async def seed_admin(email: str, name: str, password: str, role: str) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(AdminUser).where(AdminUser.email == email.lower()))
        admin = result.scalar_one_or_none()

        if admin:
            admin.name = name
            admin.password_hash = hash_password(password)
            admin.role = role
            admin.is_active = True
            print(f"Updated existing admin user: {email}")
        else:
            admin = AdminUser(
                email=email.lower(),
                name=name,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
            )
            db.add(admin)
            print(f"Created new admin user: {email}")

        await db.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--role", default="owner", choices=["owner", "staff"])
    args = parser.parse_args()

    if len(args.password) < 8:
        print("Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(seed_admin(args.email, args.name, args.password, args.role))
