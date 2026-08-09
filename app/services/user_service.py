from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.schemas.user import UserCreate

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

async def get_user_by_google_subject(db: AsyncSession, google_subject: str) -> User | None:
    result = await db.execute(select(User).where(User.google_subject == google_subject))
    return result.scalar_one_or_none()

async def create_google_user(db: AsyncSession, email: str, google_subject: str) -> User:
    user = User(email=email, hashed_password=None, google_subject=google_subject)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def create_user(db: AsyncSession, user_create: UserCreate) -> User:
    from app.core.security import get_password_hash

    hashed_password = get_password_hash(user_create.password)
    user = User(email=user_create.email, hashed_password=hashed_password)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
