import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.base import Base
from app.models.user import User


async def create_user():
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine)

    async with session_maker() as session:
        user = User(email="admin@quantpilot.ai", hashed_password=get_password_hash("securepassword123"))
        session.add(user)
        try:
            await session.commit()
            print("User created successfully!")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(create_user())
