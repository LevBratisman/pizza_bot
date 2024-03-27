import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database.models import Base

from app.common.texts_for_db import categories, description_for_info_pages
from app.database.orm_query import orm_add_banner_description, orm_create_category, orm_drop_cart, orm_drop_user


engine = create_async_engine(os.getenv('DATABASE_URL'), echo=True)
session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def create_db():
        
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with session_maker() as session:
        await orm_create_category(session, categories)
        await orm_add_banner_description(session, description_for_info_pages)
        
        
async def drop_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)