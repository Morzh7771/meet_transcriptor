from typing import List, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text, select, delete

# from semantic_chunkers import StatisticalChunker
# from semantic_router.encoders import OpenAIEncoder

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
        # encoder = OpenAIEncoder(
        #     name="text-embedding-3-small", 
        #     openai_api_key=self.configs.openai.API_KEY.get_secret_value(),
        # )

        # self.chunker = StatisticalChunker(
        #     encoder=encoder, 
        #     max_split_tokens=1000,
        #     min_split_tokens=500,
        #     window_size=3
        # )

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

    # ============ PLANS OPERATIONS ============
    
    async def create_plan(self, plan_data: PlanCreate) -> PlanResponse:
        """CREATE - Insert new plan"""
        async with self.AsyncSessionLocal() as session:
            plan = Plan(
                client_id=plan_data.client_id,
                plan_type=plan_data.plan_type,
                provider=plan_data.provider,
                plan_code=plan_data.plan_code,
                plan_name=plan_data.plan_name,
                employer_tax_id=plan_data.employer_tax_id,
                roth_first_year=plan_data.roth_first_year
            )
            session.add(plan)
            await session.commit()
            await session.refresh(plan)
            return PlanResponse.model_validate(plan)

    async def get_plan_by_id(self, plan_id: str) -> Optional[PlanResponse]:
        """READ - Get plan by ID"""
        async with self.AsyncSessionLocal() as session:
            plan = await session.get(Plan, plan_id)
            return PlanResponse.model_validate(plan) if plan else None

    async def get_plan_by_code(self, plan_code: str) -> Optional[PlanResponse]:
        """READ - Get plan by plan code"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Plan).where(Plan.plan_code == plan_code)
            result = await session.execute(stmt)
            plan = result.scalar_one_or_none()
            return PlanResponse.model_validate(plan) if plan else None

    async def get_all_plans(self) -> List[PlanResponse]:
        """READ - Get all plans"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Plan)
            result = await session.execute(stmt)
            plans = result.scalars().all()
            return [PlanResponse.model_validate(plan) for plan in plans]

    async def update_plan(self, plan_id: str, plan_update: PlanUpdate) -> Optional[PlanResponse]:
        """UPDATE - Update plan fields"""
        async with self.AsyncSessionLocal() as session:
            plan = await session.get(Plan, plan_id)
            if not plan:
                return None
            
            update_data = plan_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(plan, field, value)
            
            await session.commit()
            await session.refresh(plan)
            return PlanResponse.model_validate(plan)

    async def delete_plan(self, plan_id: str) -> bool:
        """DELETE - Remove plan from database"""
        async with self.AsyncSessionLocal() as session:
            plan = await session.get(Plan, plan_id)
            if not plan:
                return False
            
            await session.delete(plan)
            await session.commit()
            return True

    async def plan_exists(self, plan_id: str) -> bool:
        """Check if plan exists"""
        plan = await self.get_plan_by_id(plan_id)
        return True if plan else False 

    # ============ PERSON ADDRESS OPERATIONS ============

    async def create_person_address(self, address_data: PersonAddressCreate) -> PersonAddressResponse:
        """CREATE - Insert new person address"""
        async with self.AsyncSessionLocal() as session:
            address = PersonAddress(
                person_id=address_data.person_id,
                address_type=address_data.address_type,
                street=address_data.street,
                city=address_data.city,
                state=address_data.state,
                country=address_data.country,
                zip_code=address_data.zip_code
            )
            session.add(address)
            await session.commit()
            await session.refresh(address)
            return PersonAddressResponse.model_validate(address)

    async def get_person_address_by_id(self, address_id: str) -> Optional[PersonAddressResponse]:
        """READ - Get person address by ID"""
        async with self.AsyncSessionLocal() as session:
            address = await session.get(PersonAddress, address_id)
            return PersonAddressResponse.model_validate(address) if address else None

    async def get_all_person_addresses(self) -> List[PersonAddressResponse]:
        """READ - Get all person addresses"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(PersonAddress)
            result = await session.execute(stmt)
            addresses = result.scalars().all()
            return [PersonAddressResponse.model_validate(addr) for addr in addresses]

    async def update_person_address(self, address_id: str, address_update: PersonAddressUpdate) -> Optional[PersonAddressResponse]:
        """UPDATE - Update person address fields"""
        async with self.AsyncSessionLocal() as session:
            address = await session.get(PersonAddress, address_id)
            if not address:
                return None
            
            update_data = address_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(address, field, value)
            
            await session.commit()
            await session.refresh(address)
            return PersonAddressResponse.model_validate(address)

    async def delete_person_address(self, address_id: str) -> bool:
        """DELETE - Remove person address from database"""
        async with self.AsyncSessionLocal() as session:
            address = await session.get(PersonAddress, address_id)
            if not address:
                return False
            
            await session.delete(address)
            await session.commit()
            return True

    async def person_address_exists(self, address_id: str) -> bool:
        """Check if person address exists"""
        address = await self.get_person_address_by_id(address_id)
        return True if address else False

    # ============ PERSON OPERATIONS ============

    async def create_person(self, person_data: personCreate) -> personResponse:
        """CREATE - Insert new person"""
        async with self.AsyncSessionLocal() as session:
            person = Person(
                client_id=person_data.client_id,
                beneficiary_id=person_data.beneficiary_id,
                first_name=person_data.first_name,
                middle_name=person_data.middle_name,
                last_name=person_data.last_name,
                date_of_birth=person_data.date_of_birth,
                sex=person_data.sex,
                ssn_or_tin=person_data.ssn_or_tin,
                email=person_data.email,
                phone_number=person_data.phone_number,
                phone_alt=person_data.phone_alt or ""
            )
            session.add(person)
            await session.commit()
            await session.refresh(person)
            return personResponse.model_validate(person)

    async def get_person_by_id(self, person_id: str) -> Optional[personResponse]:
        """READ - Get person by ID"""
        async with self.AsyncSessionLocal() as session:
            person = await session.get(Person, person_id)
            return personResponse.model_validate(person) if person else None

    async def get_person_by_email(self, email: str) -> Optional[personResponse]:
        """READ - Get person by email"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Person).where(Person.email == email)
            result = await session.execute(stmt)
            person = result.scalar_one_or_none()
            return personResponse.model_validate(person) if person else None

    async def get_all_persons(self) -> List[personResponse]:
        """READ - Get all persons"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Person)
            result = await session.execute(stmt)
            persons = result.scalars().all()
            return [personResponse.model_validate(person) for person in persons]

    async def update_person(self, person_id: str, person_update: personUpdate) -> Optional[personResponse]:
        """UPDATE - Update person fields"""
        async with self.AsyncSessionLocal() as session:
            person = await session.get(Person, person_id)
            if not person:
                return None

            update_data = person_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if field == 'birth_date':
                    setattr(person, 'date_of_birth', value)
                else:
                    setattr(person, field, value)

            await session.commit()
            await session.refresh(person)
            return personResponse.model_validate(person)

    async def delete_person(self, person_id: str) -> bool:
        """DELETE - Remove person from database"""
        async with self.AsyncSessionLocal() as session:
            person = await session.get(Person, person_id)
            if not person:
                return False

            await session.delete(person)
            await session.commit()
            return True

    async def person_exists(self, person_id: str) -> bool:
        """Check if person exists"""
        person = await self.get_person_by_id(person_id)
        return True if person else False

    # ============ BENEFICIARIES OPERATIONS ============

    async def create_beneficiary(self, beneficiary_data: BeneficiaryCreate) -> BeneficiaryResponse:
        """CREATE - Insert new beneficiary"""
        async with self.AsyncSessionLocal() as session:
            beneficiary = Beneficiary(
                client_id=beneficiary_data.client_id,
                beneficiary_type=beneficiary_data.beneficiary_type,
                relation=beneficiary_data.relation,
                share_percentage=beneficiary_data.share_percentage
            )
            session.add(beneficiary)
            await session.commit()
            await session.refresh(beneficiary)
            return BeneficiaryResponse.model_validate(beneficiary)

    async def get_beneficiary_by_id(self, beneficiary_id: str) -> Optional[BeneficiaryResponse]:
        """READ - Get beneficiary by ID"""
        async with self.AsyncSessionLocal() as session:
            beneficiary = await session.get(Beneficiary, beneficiary_id)
            return BeneficiaryResponse.model_validate(beneficiary) if beneficiary else None

    async def get_all_beneficiaries(self) -> List[BeneficiaryResponse]:
        """READ - Get all beneficiaries"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Beneficiary)
            result = await session.execute(stmt)
            beneficiary = result.scalars().all()
            return [BeneficiaryResponse.model_validate(ben) for ben in beneficiary]

    async def update_beneficiary(self, beneficiary_id: str, beneficiary_update: BeneficiaryUpdate) -> Optional[BeneficiaryResponse]:
        """UPDATE - Update beneficiary fields"""
        async with self.AsyncSessionLocal() as session:
            beneficiary = await session.get(Beneficiary, beneficiary_id)
            if not beneficiary:
                return None

            update_data = beneficiary_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(beneficiary, field, value)

            await session.commit()
            await session.refresh(beneficiary)
            return BeneficiaryResponse.model_validate(beneficiary)

    async def delete_beneficiary(self, beneficiary_id: str) -> bool:
        """DELETE - Remove beneficiary from database"""
        async with self.AsyncSessionLocal() as session:
            beneficiary = await session.get(Beneficiary, beneficiary_id)
            if not beneficiary:
                return False

            await session.delete(beneficiary)
            await session.commit()
            return True

    async def beneficiary_exists(self, beneficiary_id: str) -> bool:
        """Check if beneficiary exists"""
        beneficiary = await self.get_beneficiary_by_id(beneficiary_id)
        return True if beneficiary else False

    # ============ CLIENT EMPLOYMENT OPERATIONS ============

    async def create_client_employment(self, employment_data: ClientEmploymentCreate) -> ClientEmploymentResponse:
        """CREATE - Insert new client employment"""
        async with self.AsyncSessionLocal() as session:
            employment = ClientEmployment(
                client_id=employment_data.client_id,
                company_name=employment_data.company_name,
                job_title=employment_data.job_title,
                job_description=employment_data.job_description,
                hire_date=employment_data.hire_date,
                pay_frequency=employment_data.pay_frequency,
                year_funds=employment_data.year_funds,
                add_funds=employment_data.add_funds
            )
            session.add(employment)
            await session.commit()
            await session.refresh(employment)
            return ClientEmploymentResponse.model_validate(employment)

    async def get_client_employment_by_id(self, employment_id: str) -> Optional[ClientEmploymentResponse]:
        """READ - Get client employment by ID"""
        async with self.AsyncSessionLocal() as session:
            employment = await session.get(ClientEmployment, employment_id)
            return ClientEmploymentResponse.model_validate(employment) if employment else None

    async def get_all_client_employments(self) -> List[ClientEmploymentResponse]:
        """READ - Get all client employments"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(ClientEmployment)
            result = await session.execute(stmt)
            employments = result.scalars().all()
            return [ClientEmploymentResponse.model_validate(emp) for emp in employments]

    async def update_client_employment(self, employment_id: str, employment_update: ClientEmploymentUpdate) -> Optional[ClientEmploymentResponse]:
        """UPDATE - Update client employment fields"""
        async with self.AsyncSessionLocal() as session:
            employment = await session.get(ClientEmployment, employment_id)
            if not employment:
                return None

            update_data = employment_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(employment, field, value)

            await session.commit()
            await session.refresh(employment)
            return ClientEmploymentResponse.model_validate(employment)

    async def delete_client_employment(self, employment_id: str) -> bool:
        """DELETE - Remove client employment from database"""
        async with self.AsyncSessionLocal() as session:
            employment = await session.get(ClientEmployment, employment_id)
            if not employment:
                return False

            await session.delete(employment)
            await session.commit()
            return True

    async def client_employment_exists(self, employment_id: str) -> bool:
        """Check if client employment exists"""
        employment = await self.get_client_employment_by_id(employment_id)
        return True if employment else False
    
    # ============ CLIENT EDUCATION OPERATIONS ============

    async def create_client_education(self, education_data: ClientEducationCreate) -> ClientEducationResponse:
        """CREATE - Insert new client education"""
        async with self.AsyncSessionLocal() as session:
            education = ClientEducation(
                client_id=education_data.client_id,
                started_on=education_data.started_on,
                ended_on=education_data.ended_on,
                field_of_study=education_data.field_of_study,
                degree=education_data.degree,
                university_name=education_data.university_name
            )
            session.add(education)
            await session.commit()
            await session.refresh(education)
            return ClientEducationResponse.model_validate(education)

    async def get_client_education_by_id(self, education_id: str) -> Optional[ClientEducationResponse]:
        """READ - Get client education by ID"""
        async with self.AsyncSessionLocal() as session:
            education = await session.get(ClientEducation, education_id)
            return ClientEducationResponse.model_validate(education) if education else None

    async def get_all_client_educations(self) -> List[ClientEducationResponse]:
        """READ - Get all client educations"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(ClientEducation)
            result = await session.execute(stmt)
            educations = result.scalars().all()
            return [ClientEducationResponse.model_validate(edu) for edu in educations]

    async def update_client_education(self, education_id: str, education_update: ClientEducationUpdate) -> Optional[ClientEducationResponse]:
        """UPDATE - Update client education fields"""
        async with self.AsyncSessionLocal() as session:
            education = await session.get(ClientEducation, education_id)
            if not education:
                return None

            update_data = education_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(education, field, value)

            await session.commit()
            await session.refresh(education)
            return ClientEducationResponse.model_validate(education)

    async def delete_client_education(self, education_id: str) -> bool:
        """DELETE - Remove client education from database"""
        async with self.AsyncSessionLocal() as session:
            education = await session.get(ClientEducation, education_id)
            if not education:
                return False

            await session.delete(education)
            await session.commit()
            return True

    async def client_education_exists(self, education_id: str) -> bool:
        """Check if client education exists"""
        education = await self.get_client_education_by_id(education_id)
        return True if education else False
    
    # ============ CLIENT OPERATIONS ============

    async def create_client(self, client_data: ClientCreate) -> ClientResponse:
        """CREATE - Insert new client"""
        async with self.AsyncSessionLocal() as session:
            client = Client(
                citizenship=client_data.citizenship,
                marital_status=client_data.marital_status,
                id_number=client_data.id_number,
                id_type=client_data.id_type,
                country_of_issuance=client_data.country_of_issuance,
                id_issuance_date=client_data.id_issuance_date,
                id_expiration_date=client_data.id_expiration_date
            )
            session.add(client)
            await session.commit()
            await session.refresh(client)
            return ClientResponse.model_validate(client)

    async def get_client_by_id(self, client_id: str) -> Optional[ClientResponse]:
        """READ - Get client by ID"""
        async with self.AsyncSessionLocal() as session:
            client = await session.get(Client, client_id)
            return ClientResponse.model_validate(client) if client else None

    async def get_all_clients(self) -> List[ClientResponse]:
        """READ - Get all clients"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Client)
            result = await session.execute(stmt)
            clients = result.scalars().all()
            return [ClientResponse.model_validate(client) for client in clients]

    async def update_client(self, client_id: str, client_update: ClientUpdate) -> Optional[ClientResponse]:
        """UPDATE - Update client fields"""
        async with self.AsyncSessionLocal() as session:
            client = await session.get(Client, client_id)
            if not client:
                return None

            update_data = client_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(client, field, value)

            await session.commit()
            await session.refresh(client)
            return ClientResponse.model_validate(client)

    async def delete_client(self, client_id: str) -> bool:
        """DELETE - Remove client from database"""
        async with self.AsyncSessionLocal() as session:
            client = await session.get(Client, client_id)
            if not client:
                return False

            await session.delete(client)
            await session.commit()
            return True

    async def client_exists(self, client_id: str) -> bool:
        """Check if client exists"""
        client = await self.get_client_by_id(client_id)
        return True if client else False

    # ============ PRODUCT OPERATIONS ============

    async def create_product(self, product_data: ProductCreate) -> ProductResponse:
        """CREATE - Insert new product"""
        async with self.AsyncSessionLocal() as session:
            product = Product(
                company_id=product_data.company_id,
                product_name=product_data.product_name,
                product_code=product_data.product_code,
                product_type=product_data.product_type,
                description=product_data.description
            )
            session.add(product)
            await session.commit()
            await session.refresh(product)
            return ProductResponse.model_validate(product)

    async def get_product_by_id(self, product_id: str) -> Optional[ProductResponse]:
        """READ - Get product by ID"""
        async with self.AsyncSessionLocal() as session:
            product = await session.get(Product, product_id)
            return ProductResponse.model_validate(product) if product else None

    async def get_product_by_code(self, product_code: str) -> Optional[ProductResponse]:
        """READ - Get product by product code"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Product).where(Product.product_code == product_code)
            result = await session.execute(stmt)
            product = result.scalar_one_or_none()
            return ProductResponse.model_validate(product) if product else None

    async def get_all_products(self) -> List[ProductResponse]:
        """READ - Get all products"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Product)
            result = await session.execute(stmt)
            products = result.scalars().all()
            return [ProductResponse.model_validate(product) for product in products]

    async def update_product(self, product_id: str, product_update: ProductUpdate) -> Optional[ProductResponse]:
        """UPDATE - Update product fields"""
        async with self.AsyncSessionLocal() as session:
            product = await session.get(Product, product_id)
            if not product:
                return None

            update_data = product_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(product, field, value)

            await session.commit()
            await session.refresh(product)
            return ProductResponse.model_validate(product)

    async def delete_product(self, product_id: str) -> bool:
        """DELETE - Remove product from database"""
        async with self.AsyncSessionLocal() as session:
            product = await session.get(Product, product_id)
            if not product:
                return False

            await session.delete(product)
            await session.commit()
            return True

    async def product_exists(self, product_id: str) -> bool:
        """Check if product exists"""
        product = await self.get_product_by_id(product_id)
        return True if product else False
    
    # ============ COMPANY OPERATIONS ============

    async def create_company(self, company_data: CompanyCreate) -> CompanyResponse:
        """CREATE - Insert new company"""
        async with self.AsyncSessionLocal() as session:
            company = Company(
                title=company_data.title,
                email_domen=company_data.email_domen,
                subscription=company_data.subscription,
                subscription_term=company_data.subscription_term,
                registration_date=company_data.registration_date,
            )
            session.add(company)
            await session.commit()
            await session.refresh(company)
            return CompanyResponse.model_validate(company)
        
    async def get_company_by_id(self, company_id: str) -> Optional[CompanyResponse]:
        """READ - Get company by ID with products"""
        async with self.AsyncSessionLocal() as session:
            company = await session.get(Company, company_id)
            return CompanyResponse.model_validate(company) if company else None

    async def get_company_by_email_domain(self, email_domain: str) -> Optional[CompanyResponse]:
        """READ - Get company by email domain"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Company).where(Company.email_domen == email_domain)
            result = await session.execute(stmt)
            company = result.scalar_one_or_none()
            
            if not company:
                return None
                
            return await self.get_company_by_id(company.id)

    async def get_company_by_title(self, title: str) -> Optional[CompanyResponse]:
        """READ - Get company by title"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Company).where(Company.title == title)
            result = await session.execute(stmt)
            company = result.scalar_one_or_none()
            
            if not company:
                return None
                
            return await self.get_company_by_id(company.id)

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
            return await self.get_company_by_id(company.id)

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

    # ============ CONSULTANT OPERATIONS ============

    async def create_consultant(self, consultant_data: ConsultantCreate) -> ConsultantResponse:
        """CREATE - Insert new consultant"""
        async with self.AsyncSessionLocal() as session:
            consultant = Consultant(
                company_id=consultant_data.company_id,
                email=consultant_data.email,
                username=consultant_data.username,
                password=consultant_data.password,
                role=consultant_data.role,
                gender=consultant_data.gender,
                language=consultant_data.language
            )
            session.add(consultant)
            await session.commit()
            await session.refresh(consultant)
            return ConsultantResponse.model_validate(consultant)

    async def get_consultant_by_id(self, consultant_id: str) -> Optional[ConsultantResponse]:
        """READ - Get consultant by ID"""
        async with self.AsyncSessionLocal() as session:
            consultant = await session.get(Consultant, consultant_id)
            return ConsultantResponse.model_validate(consultant) if consultant else None

    async def get_consultant_by_email(self, email: str) -> Optional[ConsultantResponse]:
        """READ - Get consultant by email"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Consultant).where(Consultant.email == email)
            result = await session.execute(stmt)
            consultant = result.scalar_one_or_none()
            return ConsultantResponse.model_validate(consultant) if consultant else None

    async def get_consultant_by_username(self, username: str) -> Optional[ConsultantResponse]:
        """READ - Get consultant by username"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Consultant).where(Consultant.username == username)
            result = await session.execute(stmt)
            consultant = result.scalar_one_or_none()
            return ConsultantResponse.model_validate(consultant) if consultant else None

    async def get_all_consultants(self) -> List[ConsultantResponse]:
        """READ - Get all consultants"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Consultant)
            result = await session.execute(stmt)
            consultants = result.scalars().all()
            return [ConsultantResponse.model_validate(consultant) for consultant in consultants]

    async def update_consultant(self, consultant_id: str, consultant_update: ConsultantUpdate) -> Optional[ConsultantResponse]:
        """UPDATE - Update consultant fields"""
        async with self.AsyncSessionLocal() as session:
            consultant = await session.get(Consultant, consultant_id)
            if not consultant:
                return None

            update_data = consultant_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(consultant, field, value)

            await session.commit()
            await session.refresh(consultant)
            return ConsultantResponse.model_validate(consultant)

    async def delete_consultant(self, consultant_id: str) -> bool:
        """DELETE - Remove consultant from database"""
        async with self.AsyncSessionLocal() as session:
            consultant = await session.get(Consultant, consultant_id)
            if not consultant:
                return False

            await session.delete(consultant)
            await session.commit()
            return True

    async def consultant_exists(self, consultant_id: str) -> bool:
        """Check if consultant exists"""
        consultant = await self.get_consultant_by_id(consultant_id)
        return True if consultant else False

    # ============ MEET OPERATIONS ============

    async def create_meet(self, meet_data: MeetCreate) -> MeetResponse:
        """CREATE - Insert new meeting"""
        async with self.AsyncSessionLocal() as session:
            meet = Meet(
                client_id=meet_data.client_id,
                consultant_id=meet_data.consultant_id,
                title=meet_data.title,
                summary=meet_data.summary,
                date=meet_data.date,
                duration=meet_data.duration,
                overview=meet_data.overview,
                notes=meet_data.notes,
                action_items=meet_data.action_items,
                trascription=meet_data.trascription,
                language=meet_data.language,
                tags=meet_data.tags,
                participants=meet_data.participants,
                next_meet_scenario=meet_data.next_meet_scenario
            )
            session.add(meet)
            await session.commit()
            await session.refresh(meet)
            return meet.id

    async def get_meet_by_id(self, meet_id: str) -> Optional[MeetResponse]:
        """READ - Get meeting by ID"""
        async with self.AsyncSessionLocal() as session:
            meet = await session.get(Meet, meet_id)
            return MeetResponse.model_validate(meet) if meet else None

    async def get_meets_by_client_id(self, client_id: str) -> List[MeetResponse]:
        """READ - Get all meetings for a specific client"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Meet).where(Meet.client_id == client_id)
            result = await session.execute(stmt)
            meets = result.scalars().all()
            return [MeetResponse.model_validate(meet) for meet in meets]

    async def get_meets_by_consultant_id(self, consultant_id: str) -> List[MeetResponse]:
        """READ - Get all meetings for a specific consultant"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Meet).where(Meet.consultant_id == consultant_id)
            result = await session.execute(stmt)
            meets = result.scalars().all()
            return [MeetResponse.model_validate(meet) for meet in meets]

    async def get_meets(
        self, client_id: Optional[str] = None, consultant_id: Optional[str] = None
        ) -> List[MeetResponse]:
        """READ - Get meetings filtered by client_id and/or consultant_id"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Meet)
            if client_id:
                stmt = stmt.where(Meet.client_id == client_id)
            if consultant_id:
                stmt = stmt.where(Meet.consultant_id == consultant_id)

            stmt = stmt.order_by(Meet.date.desc())

            result = await session.execute(stmt)
            meets = result.scalars().all()
            return [MeetResponse.model_validate(meet) for meet in meets]

    async def get_all_meets(self) -> List[MeetResponse]:
        """READ - Get all meetings"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(Meet)
            result = await session.execute(stmt)
            meets = result.scalars().all()
            return [MeetResponse.model_validate(meet) for meet in meets]

    async def update_meet(self, meet_id: str, meet_update: MeetUpdate) -> Optional[MeetResponse]:
        """UPDATE - Update meeting fields"""
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
        """DELETE - Remove meeting from database"""
        async with self.AsyncSessionLocal() as session:
            meet = await session.get(Meet, meet_id)
            if not meet:
                return False

            await session.delete(meet)
            await session.commit()
            return True

    async def meet_exists(self, meet_id: str) -> bool:
        """Check if meeting exists"""
        meet = await self.get_meet_by_id(meet_id)
        return True if meet else False

    # ============ REAL TIME MEETING MESSAGE OPERATIONS ============

    async def create_real_time_meeting_message(self, message_data: RealTimeMeetingMessageCreate) -> RealTimeMeetingMessageResponse:
        """CREATE - Insert new real-time meeting message"""
        async with self.AsyncSessionLocal() as session:
            message = RealTimeMeetingMessage(
                meet_id=message_data.meet_id,
                time=message_data.time,
                email=message_data.email,
                content=message_data.content
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            return RealTimeMeetingMessageResponse.model_validate(message)

    async def get_real_time_meeting_message_by_id(self, message_id: str) -> Optional[RealTimeMeetingMessageResponse]:
        """READ - Get real-time meeting message by ID"""
        async with self.AsyncSessionLocal() as session:
            message = await session.get(RealTimeMeetingMessage, message_id)
            return RealTimeMeetingMessageResponse.model_validate(message) if message else None

    async def get_real_time_meeting_messages_by_meet_id(self, meet_id: str) -> List[RealTimeMeetingMessageResponse]:
        """READ - Get all real-time messages for a specific meeting"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(RealTimeMeetingMessage).where(RealTimeMeetingMessage.meet_id == meet_id).order_by(RealTimeMeetingMessage.time)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [RealTimeMeetingMessageResponse.model_validate(msg) for msg in messages]

    async def get_real_time_meeting_messages_by_email(self, email: str) -> List[RealTimeMeetingMessageResponse]:
        """READ - Get all real-time messages by email"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(RealTimeMeetingMessage).where(RealTimeMeetingMessage.email == email).order_by(RealTimeMeetingMessage.time)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [RealTimeMeetingMessageResponse.model_validate(msg) for msg in messages]

    async def get_all_real_time_meeting_messages(self) -> List[RealTimeMeetingMessageResponse]:
        """READ - Get all real-time meeting messages"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(RealTimeMeetingMessage).order_by(RealTimeMeetingMessage.time)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [RealTimeMeetingMessageResponse.model_validate(msg) for msg in messages]

    async def update_real_time_meeting_message(self, message_id: str, message_update: RealTimeMeetingMessageUpdate) -> Optional[RealTimeMeetingMessageResponse]:
        """UPDATE - Update real-time meeting message fields"""
        async with self.AsyncSessionLocal() as session:
            message = await session.get(RealTimeMeetingMessage, message_id)
            if not message:
                return None

            update_data = message_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(message, field, value)

            await session.commit()
            await session.refresh(message)
            return RealTimeMeetingMessageResponse.model_validate(message)

    async def delete_real_time_meeting_message(self, message_id: str) -> bool:
        """DELETE - Remove real-time meeting message from database"""
        async with self.AsyncSessionLocal() as session:
            message = await session.get(RealTimeMeetingMessage, message_id)
            if not message:
                return False

            await session.delete(message)
            await session.commit()
            return True

    async def real_time_meeting_message_exists(self, message_id: str) -> bool:
        """Check if real-time meeting message exists"""
        message = await self.get_real_time_meeting_message_by_id(message_id)
        return True if message else False

    # ============ MEETING CHATBOT MESSAGE OPERATIONS ============

    async def create_meeting_chatbot_message(self, message_data: MeetingChatbotMessageCreate) -> MeetingChatbotMessageResponse:
        """CREATE - Insert new meeting chatbot message"""
        async with self.AsyncSessionLocal() as session:
            message = MeetingChatbotMessage(
                meet_id=message_data.meet_id,
                time=message_data.time,
                role=message_data.role,
                content=message_data.content
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            return MeetingChatbotMessageResponse.model_validate(message)

    async def get_meeting_chatbot_message_by_id(self, message_id: str) -> Optional[MeetingChatbotMessageResponse]:
        """READ - Get meeting chatbot message by ID"""
        async with self.AsyncSessionLocal() as session:
            message = await session.get(MeetingChatbotMessage, message_id)
            return MeetingChatbotMessageResponse.model_validate(message) if message else None

    async def get_meeting_chatbot_messages_by_meet_id(self, meet_id: str) -> List[MeetingChatbotMessageResponse]:
        """READ - Get all chatbot messages for a specific meeting"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(MeetingChatbotMessage).where(MeetingChatbotMessage.meet_id == meet_id).order_by(MeetingChatbotMessage.time)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [MeetingChatbotMessageResponse.model_validate(msg) for msg in messages]

    async def get_meeting_chatbot_messages_by_role(self, role: str) -> List[MeetingChatbotMessageResponse]:
        """READ - Get all chatbot messages by role"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(MeetingChatbotMessage).where(MeetingChatbotMessage.role == role).order_by(MeetingChatbotMessage.time)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [MeetingChatbotMessageResponse.model_validate(msg) for msg in messages]

    async def get_all_meeting_chatbot_messages(self) -> List[MeetingChatbotMessageResponse]:
        """READ - Get all meeting chatbot messages"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(MeetingChatbotMessage).order_by(MeetingChatbotMessage.time)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [MeetingChatbotMessageResponse.model_validate(msg) for msg in messages]

    async def update_meeting_chatbot_message(self, message_id: str, message_update: MeetingChatbotMessageUpdate) -> Optional[MeetingChatbotMessageResponse]:
        """UPDATE - Update meeting chatbot message fields"""
        async with self.AsyncSessionLocal() as session:
            message = await session.get(MeetingChatbotMessage, message_id)
            if not message:
                return None

            update_data = message_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(message, field, value)

            await session.commit()
            await session.refresh(message)
            return MeetingChatbotMessageResponse.model_validate(message)

    async def delete_meeting_chatbot_message(self, message_id: str) -> bool:
        """DELETE - Remove meeting chatbot message from database"""
        async with self.AsyncSessionLocal() as session:
            message = await session.get(MeetingChatbotMessage, message_id)
            if not message:
                return False

            await session.delete(message)
            await session.commit()
            return True

    async def meeting_chatbot_message_exists(self, message_id: str) -> bool:
        """Check if meeting chatbot message exists"""
        message = await self.get_meeting_chatbot_message_by_id(message_id)
        return True if message else False

    # ============ ALL CHATBOT MEETING MESSAGE OPERATIONS ============

    async def create_all_chatbot_meeting_message(self, message_data: AllChatbotMeetingMessageCreate) -> AllChatbotMeetingMessageResponse:
        """CREATE - Insert new all chatbot meeting message"""
        async with self.AsyncSessionLocal() as session:
            message = AllChatbotMeetingMessage(
                meet_id=message_data.meet_id,
                time=message_data.time,
                role=message_data.role,
                content=message_data.content
            )
            session.add(message)
            await session.commit()
            await session.refresh(message)
            return AllChatbotMeetingMessageResponse.model_validate(message)

    async def get_all_chatbot_meeting_message_by_id(self, message_id: str) -> Optional[AllChatbotMeetingMessageResponse]:
        """READ - Get all chatbot meeting message by ID"""
        async with self.AsyncSessionLocal() as session:
            message = await session.get(AllChatbotMeetingMessage, message_id)
            return AllChatbotMeetingMessageResponse.model_validate(message) if message else None

    async def get_all_chatbot_meeting_messages_by_meet_id(self, meet_id: str) -> List[AllChatbotMeetingMessageResponse]:
        """READ - Get all chatbot messages for a specific meeting"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(AllChatbotMeetingMessage).where(AllChatbotMeetingMessage.meet_id == meet_id).order_by(AllChatbotMeetingMessage.time)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [AllChatbotMeetingMessageResponse.model_validate(msg) for msg in messages]

    async def get_all_chatbot_meeting_messages_by_role(self, role: str) -> List[AllChatbotMeetingMessageResponse]:
        """READ - Get all chatbot messages by role"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(AllChatbotMeetingMessage).where(AllChatbotMeetingMessage.role == role).order_by(AllChatbotMeetingMessage.time)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [AllChatbotMeetingMessageResponse.model_validate(msg) for msg in messages]

    async def get_all_chatbot_meeting_messages(self) -> List[AllChatbotMeetingMessageResponse]:
        """READ - Get all chatbot meeting messages"""
        async with self.AsyncSessionLocal() as session:
            stmt = select(AllChatbotMeetingMessage).order_by(AllChatbotMeetingMessage.time)
            result = await session.execute(stmt)
            messages = result.scalars().all()
            return [AllChatbotMeetingMessageResponse.model_validate(msg) for msg in messages]

    async def update_all_chatbot_meeting_message(self, message_id: str, message_update: AllChatbotMeetingMessageUpdate) -> Optional[AllChatbotMeetingMessageResponse]:
        """UPDATE - Update all chatbot meeting message fields"""
        async with self.AsyncSessionLocal() as session:
            message = await session.get(AllChatbotMeetingMessage, message_id)
            if not message:
                return None

            update_data = message_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(message, field, value)

            await session.commit()
            await session.refresh(message)
            return AllChatbotMeetingMessageResponse.model_validate(message)

    async def delete_all_chatbot_meeting_message(self, message_id: str) -> bool:
        """DELETE - Remove all chatbot meeting message from database"""
        async with self.AsyncSessionLocal() as session:
            message = await session.get(AllChatbotMeetingMessage, message_id)
            if not message:
                return False

            await session.delete(message)
            await session.commit()
            return True

    async def all_chatbot_meeting_message_exists(self, message_id: str) -> bool:
        """Check if all chatbot meeting message exists"""
        message = await self.get_all_chatbot_meeting_message_by_id(message_id)
        return True if message else False