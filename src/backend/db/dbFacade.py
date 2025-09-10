from typing import List, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text, select


from semantic_chunkers import StatisticalChunker
from semantic_router.encoders import OpenAIEncoder


from src.backend.db.tables import *
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

    async def drop_all_tables(self):
        async with self.async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        self.logger.info("All tables dropped successfully!")

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

    # ============ USER OPERATIONS ============

    async def create_user(self, user_data: "UserCreate") -> "UserResponse":
        """CREATE - Insert new user"""
        async with self.AsyncSessionLocal() as session:
            user = User(
                email=user_data.email,
                company_id=user_data.company_id,
                username=user_data.username,
                password=user_data.password,
                role=user_data.role,
                gender=user_data.gender,
                language=user_data.language
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return UserResponse.model_validate(user)

    async def get_user_by_id(self, user_id: str) -> Optional["UserResponse"]:
        """READ - Get user by ID"""
        async with self.AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            return UserResponse.model_validate(user) if user else None

    async def get_user_by_email(self, email: str) -> Optional["UserResponse"]:
        """READ - Get user by email"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(User).where(User.email == email)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            return UserResponse.model_validate(user) if user else None

    async def get_all_users(self) -> List["UserResponse"]:
        """READ - Get all users"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(User)
            result = await session.execute(stmt)
            users = result.scalars().all()
            return [UserResponse.model_validate(user) for user in users]

    async def update_user(self, user_id: str, user_update: "UserUpdate") -> Optional["UserResponse"]:
        """UPDATE - Update user fields"""
        async with self.AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                return None

            update_data = user_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(user, field, value)

            await session.commit()
            await session.refresh(user)
            return UserResponse.model_validate(user)

    async def delete_user(self, user_id: str) -> bool:
        """DELETE - Remove user from database"""
        async with self.AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if not user:
                return False

            await session.delete(user)
            await session.commit()
            return True

    async def user_exists(self, user_id: str) -> bool:
        """Check if user exists"""
        user = await self.get_user_by_id(user_id)
        return True if user else False

    # ============ MEET OPERATIONS ============

    async def create_meet(self, meet_data: "MeetCreate") -> "MeetResponse":
        """CREATE - Insert new meet"""
        async with self.AsyncSessionLocal() as session:
            meet = Meet(
                user_id=meet_data.user_id,
                title=meet_data.title,
                summary=meet_data.summary,
                date=meet_data.date,
                duration=meet_data.duration,
                meet_code=meet_data.meet_code,
                participants=meet_data.participants,
                overview=meet_data.overview,
                notes=meet_data.notes,
                action_items=meet_data.action_items,
                transcript=meet_data.transcript,
                language=meet_data.language,
                tags=meet_data.tags
            )
            session.add(meet)
            await session.commit()
            await session.refresh(meet)
            return meet.id

    async def get_meet_by_id(self, meet_id: str) -> Optional["MeetResponse"]:
        """READ - Get meet by ID"""
        async with self.AsyncSessionLocal() as session:
            meet = await session.get(Meet, meet_id)
            return MeetResponse.model_validate(meet) if meet else None

    async def get_all_meets(self) -> List["MeetResponse"]:
        """READ - Get all meets"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Meet)
            result = await session.execute(stmt)
            meets = result.scalars().all()
            return [MeetResponse.model_validate(meet) for meet in meets]

    async def get_meets_by_user_id(self, user_id: str) -> List["MeetResponse"]:
        """READ - Get all meets for a specific user"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Meet).where(Meet.user_id == user_id)
            result = await session.execute(stmt)
            meets = result.scalars().all()
            return [MeetResponse.model_validate(meet) for meet in meets]

    async def update_meet(self, meet_id: str, meet_update: "MeetUpdate") -> Optional["MeetResponse"]:
        """UPDATE - Update meet fields"""
        async with self.AsyncSessionLocal() as session:
            meet = await session.get(Meet, meet_id)
            if not meet:
                return None

            update_data = meet_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(meet, field, value)

            await session.commit()
            await session.refresh(meet)
            return MeetResponse.model_validate(meet)

    async def delete_meet(self, meet_id: str) -> bool:
        """DELETE - Remove meet from database"""
        async with self.AsyncSessionLocal() as session:
            meet = await session.get(Meet, meet_id)
            if not meet:
                return False

            await session.delete(meet)
            await session.commit()
            return True

    async def meet_exists(self, meet_id: str) -> bool:
        """Check if meet exists"""
        meet = await self.get_meet_by_id(meet_id)
        return True if meet else False

    # ============ MEETING MESSAGE OPERATIONS ============

    async def create_meeting_message(self, message_data: "MeetingMessageCreate") -> "MeetingMessageResponse":
        """CREATE - Insert new meeting message"""
        async with self.AsyncSessionLocal() as session:
            message = MeetingMessage(
                meet_id=message_data.meet_id,
                time=message_data.time,
                email=message_data.email,
                content=message_data.content
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            return MeetingMessageResponse.model_validate(message)

    async def get_meeting_message_by_id(self, message_id: str) -> Optional["MeetingMessageResponse"]:
        """READ - Get meeting message by ID"""
        async with self.AsyncSessionLocal() as session:
            message = await session.get(MeetingMessage, message_id)
            return MeetingMessageResponse.model_validate(message) if message else None

    async def get_all_meeting_messages(self) -> List["MeetingMessageResponse"]:
        """READ - Get all meeting messages"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(MeetingMessage)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [MeetingMessageResponse.model_validate(msg) for msg in messages]

    async def get_messages_by_meet_id(self, meet_id: str) -> List["MeetingMessageResponse"]:
        """READ - Get all messages for a specific meet"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(MeetingMessage).where(MeetingMessage.meet_id == meet_id)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [MeetingMessageResponse.model_validate(msg) for msg in messages]

    async def update_meeting_message(self, message_id: str, message_update: "MeetingMessageUpdate") -> Optional["MeetingMessageResponse"]:
        """UPDATE - Update meeting message fields"""
        async with self.AsyncSessionLocal() as session:
            message = await session.get(MeetingMessage, message_id)
            if not message:
                return None

            update_data = message_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(message, field, value)

            await session.commit()
            await session.refresh(message)
            return MeetingMessageResponse.model_validate(message)

    async def delete_meeting_message(self, message_id: str) -> bool:
        """DELETE - Remove meeting message from database"""
        async with self.AsyncSessionLocal() as session:
            message = await session.get(MeetingMessage, message_id)
            if not message:
                return False

            await session.delete(message)
            await session.commit()
            return True

    async def meeting_message_exists(self, message_id: str) -> bool:
        """Check if meeting message exists"""
        message = await self.get_meeting_message_by_id(message_id)
        return True if message else False

    # ============ MEETING CHAT MESSAGE OPERATIONS ============

    async def create_meeting_chat_message(self, chat_data: "MeetingChatMessageCreate") -> "MeetingChatMessageResponse":
        """CREATE - Insert new meeting chat message"""
        async with self.AsyncSessionLocal() as session:
            chat_message = MeetingChatMessage(
                meet_id=chat_data.meet_id,
                time=chat_data.time,
                role=chat_data.role,
                content=chat_data.content
            )
            session.add(chat_message)
            await session.commit()
            await session.refresh(chat_message)
            return MeetingChatMessageResponse.model_validate(chat_message)

    async def get_meeting_chat_message_by_id(self, chat_id: str) -> Optional["MeetingChatMessageResponse"]:
        """READ - Get meeting chat message by ID"""
        async with self.AsyncSessionLocal() as session:
            chat_message = await session.get(MeetingChatMessage, chat_id)
            return MeetingChatMessageResponse.model_validate(chat_message) if chat_message else None

    async def get_all_meeting_chat_messages(self) -> List["MeetingChatMessageResponse"]:
        """READ - Get all meeting chat messages"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(MeetingChatMessage)
            result = await session.execute(stmt)
            chat_messages = result.scalars().all()
            return [MeetingChatMessageResponse.model_validate(msg) for msg in chat_messages]

    async def get_chat_messages_by_meet_id(self, meet_id: str) -> List["MeetingChatMessageResponse"]:
        """READ - Get all chat messages for a specific meet"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(MeetingChatMessage).where(MeetingChatMessage.meet_id == meet_id).order_by(MeetingChatMessage.time)
            result = await session.execute(stmt)
            chat_messages = result.scalars().all()
            return [MeetingChatMessageResponse.model_validate(msg) for msg in chat_messages]

    async def update_meeting_chat_message(self, chat_id: str, chat_update: "MeetingChatMessageUpdate") -> Optional["MeetingChatMessageResponse"]:
        """UPDATE - Update meeting chat message fields"""
        async with self.AsyncSessionLocal() as session:
            chat_message = await session.get(MeetingChatMessage, chat_id)
            if not chat_message:
                return None

            update_data = chat_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(chat_message, field, value)

            await session.commit()
            await session.refresh(chat_message)
            return MeetingChatMessageResponse.model_validate(chat_message)

    async def delete_meeting_chat_message(self, chat_id: str) -> bool:
        """DELETE - Remove meeting chat message from database"""
        async with self.AsyncSessionLocal() as session:
            chat_message = await session.get(MeetingChatMessage, chat_id)
            if not chat_message:
                return False

            await session.delete(chat_message)
            await session.commit()
            return True

    async def meeting_chat_message_exists(self, chat_id: str) -> bool:
        """Check if meeting chat message exists"""
        chat_message = await self.get_meeting_chat_message_by_id(chat_id)
        return True if chat_message else False

    # ============ PARTICIPANT OPERATIONS ============

    async def create_participant(self, participant_data: "ParticipantCreate") -> "ParticipantResponse":
        """CREATE - Insert new participant"""
        async with self.AsyncSessionLocal() as session:
            participant = Participant(
                meet_id=participant_data.meet_id,
                time=participant_data.time,
                email=participant_data.email
            )
            session.add(participant)
            await session.commit()
            await session.refresh(participant)
            return ParticipantResponse.model_validate(participant)

    async def get_participant_by_id(self, participant_id: str) -> Optional["ParticipantResponse"]:
        """READ - Get participant by ID"""
        async with self.AsyncSessionLocal() as session:
            participant = await session.get(Participant, participant_id)
            return ParticipantResponse.model_validate(participant) if participant else None

    async def get_all_participants(self) -> List["ParticipantResponse"]:
        """READ - Get all participants"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Participant)
            result = await session.execute(stmt)
            participants = result.scalars().all()
            return [ParticipantResponse.model_validate(p) for p in participants]

    async def get_participants_by_meet_id(self, meet_id: str) -> List["ParticipantResponse"]:
        """READ - Get all participants for a specific meet"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Participant).where(Participant.meet_id == meet_id)
            result = await session.execute(stmt)
            participants = result.scalars().all()
            return [ParticipantResponse.model_validate(p) for p in participants]

    async def update_participant(self, participant_id: str, participant_update: "ParticipantUpdate") -> Optional["ParticipantResponse"]:
        """UPDATE - Update participant fields"""
        async with self.AsyncSessionLocal() as session:
            participant = await session.get(Participant, participant_id)
            if not participant:
                return None

            update_data = participant_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(participant, field, value)

            await session.commit()
            await session.refresh(participant)
            return ParticipantResponse.model_validate(participant)

    async def delete_participant(self, participant_id: str) -> bool:
        """DELETE - Remove participant from database"""
        async with self.AsyncSessionLocal() as session:
            participant = await session.get(Participant, participant_id)
            if not participant:
                return False

            await session.delete(participant)
            await session.commit()
            return True

    async def participant_exists(self, participant_id: str) -> bool:
        """Check if participant exists"""
        participant = await self.get_participant_by_id(participant_id)
        return True if participant else False
    
    # ============ Front End chat bot in meet list ============

    async def create_front_chat_massage(self, chat_data: "FrontMessageCreate") -> "FrontMessageCreate":
        """CREATE - Insert new meeting chat message"""
        async with self.AsyncSessionLocal() as session:
            chat_message = FrontMessageCreate(
                chat_id=chat_data.chat_id,
                meet_id=chat_data.meet_id,
                role=chat_data.role,
                content=chat_data.content
            )
            session.add(chat_message)
            await session.commit()
            await session.refresh(chat_message)
            return FrontMessageResponse.model_validate(chat_message)

    async def get_front_chat_message_by_id(self, chat_id: str) -> Optional["FrontMessageResponse"]:
        """READ - Get meeting chat message by ID"""
        async with self.AsyncSessionLocal() as session:
            chat_message = await session.get(FrontMessage, chat_id)
            return FrontMessageResponse.model_validate(chat_message) if chat_message else None

    async def get_all_front_chat_messages(self) -> List["FrontMessageResponse"]:
        """READ - Get all meeting chat messages"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(FrontMessage)
            result = await session.execute(stmt)
            chat_messages = result.scalars().all()
            return [FrontMessageResponse.model_validate(msg) for msg in chat_messages]

    async def get_front_chat_by_meet_id(self, meet_id: str) -> List["FrontMessageResponse"]:
        """READ - Get all chat messages for a specific meet"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(FrontMessage).where(FrontMessage.meet_id == meet_id).order_by(FrontMessage.time)
            result = await session.execute(stmt)
            chat_messages = result.scalars().all()
            return [FrontMessageResponse.model_validate(msg) for msg in chat_messages]

    async def update_front_chat_message(self, chat_id: str, chat_update: "FrontMessageUpdate") -> Optional["FrontMessageResponse"]:
        """UPDATE - Update meeting chat message fields"""
        async with self.AsyncSessionLocal() as session:
            chat_message = await session.get(FrontMessage, chat_id)
            if not chat_message:
                return None

            update_data = chat_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(chat_message, field, value)

            await session.commit()
            await session.refresh(chat_message)
            return FrontMessageResponse.model_validate(chat_message)

    async def delete_front_chat_message(self, chat_id: str) -> bool:
        """DELETE - Remove meeting chat message from database"""
        async with self.AsyncSessionLocal() as session:
            chat_message = await session.get(FrontMessage, chat_id)
            if not chat_message:
                return False

            await session.delete(chat_message)
            await session.commit()
            return True

    async def meeting_front_chat_exists(self, chat_id: str) -> bool:
        """Check if meeting chat message exists"""
        chat_message = await self.get_meeting_chat_message_by_id(chat_id)
        return True if chat_message else False