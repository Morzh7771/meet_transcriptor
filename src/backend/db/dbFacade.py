import asyncio
from typing import List, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text, select


from sqlalchemy.dialects.postgresql import UUID
from semantic_chunkers import StatisticalChunker
from semantic_router.encoders import OpenAIEncoder
from datetime import datetime
import uuid


from src.backend.db.tabels import *
from src.backend.models.db_models import *
from src.backend.core.baseFacade import BaseFacade


class DBFacade(BaseFacade):

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        super().__init__()
        encoder = OpenAIEncoder(
            name="text-embedding-3-small", 
            openai_api_key=self.configs.openai.API_KEY.get_secret_value(),
        )

        self.chunker = StatisticalChunker(
            encoder=encoder, 
            max_split_tokens=1000,
            min_split_tokens=500,
            window_size=3
        )

        self.db_url = (
            f"mysql+aiomysql://{self.configs.db.USER}:{self.configs.db.PASSWORD.get_secret_value()}"
            f"@{self.configs.db.HOST}:{self.configs.db.PORT}"
            f"/{self.configs.db.NAME}?charset=utf8mb4"
        )
        self._get_engines()




    def _get_engines(self):
        self.async_engine: AsyncEngine = create_async_engine(
            self.db_url,
            pool_size=10,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=False 
        )

        self.AsyncSessionLocal = async_sessionmaker(
            self.async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )



    async def create_tables(self):
        """Create all tables in the database"""
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            self.logger.info("Tables created successfully!")

    async def delete_table(self, table_name: str):
        async with self.async_engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
            self.logger.info(f"Table {table_name} dropped successfully!")



    async def chunk_text(self, text):
        
        chunks = await self.chunker.acall(docs=[text])

        return [" ".join(chunk.splits) for chunk in chunks[0]]


    # ============ COMPANY OPERATIONS ============
    
    async def create_company(self, company_data: CompanyCreate) -> CompanyResponse:
        """CREATE - Insert new company"""
        async with self.AsyncSessionLocal() as session:
            company = Company(
                title=company_data.title,
                email_domen=company_data.email_domen,
                subscription=company_data.subscription,
                subscription_term=company_data.subscription_term,
                registration_date=company_data.registration_date
            )
            session.add(company)
            await session.commit()
            await session.refresh(company)
            return CompanyResponse.model_validate(company)

    async def get_company_by_id(self, company_id: str) -> Optional[CompanyResponse]:
        """READ - Get company by ID"""
        async with self.AsyncSessionLocal() as session:
            company = await session.get(Company, company_id)
            return CompanyResponse.model_validate(company) if company else None

    async def get_company_by_title(self, title: str) -> Optional[CompanyResponse]:
        """READ - Get company by title"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Company).where(Company.title == title)
            result = await session.execute(stmt)
            company = result.scalar_one_or_none()
            return CompanyResponse.model_validate(company) if company else None

    async def get_all_companies(self) -> List[CompanyResponse]:
        """READ - Get all companies"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Company)
            result = await session.execute(stmt)
            companies = result.scalars().all()
            return [CompanyResponse.model_validate(company) for company in companies]

    async def update_company(self, company_id: str, company_update: CompanyUpdate) -> Optional[CompanyResponse]:
        """UPDATE - Update company fields"""
        async with self.AsyncSessionLocal() as session:
            company = await session.get(Company, company_id)
            if not company:
                return None
            
            # Update only provided fields (exclude unset fields)
            update_data = company_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(company, field, value)
            
            await session.commit()
            await session.refresh(company)
            return CompanyResponse.model_validate(company)

    async def delete_company(self, company_id: str) -> bool:
        """DELETE - Remove company from database"""
        async with self.AsyncSessionLocal() as session:
            company = await session.get(Company, company_id)
            if not company:
                return False
            
            await session.delete(company)
            await session.commit()
            return True

    async def company_exists(self, company_id: str) -> bool:
        """Check if company exists"""
        company = await self.get_company_by_id(company_id)
        return True if company else False 