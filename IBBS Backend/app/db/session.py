from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.config import settings


DATABASE_URL = str(settings.DATABASE_URL)

# create async engine
engine = create_async_engine(DATABASE_URL, echo=settings.DEBUG, future=True)

# session factory
async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:  # to be used as dependency
    async with async_session() as session:
        yield session
