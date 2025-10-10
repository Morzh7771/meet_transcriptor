import asyncio
import json
from datetime import datetime
from uuid import uuid4
from src.backend.db.dbFacade import DBFacade
from src.backend.models.db_models import *
from sqlalchemy import text
from src.backend.db.tables import Base

async def drop_tables_with_fk_constraints(db):
    """Удаляет все таблицы с правильной обработкой внешних ключей"""
    async with db.async_engine.begin() as conn:
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    db.logger.info("Все таблицы удалены успешно!")

def parse_date(date_str):
    """Парсит дату из строки формата MM/DD/YYYY"""
    if not date_str:
        return None
    return datetime.strptime(date_str, "%m/%d/%Y")

def parse_hire_date(date_str):
    """Парсит дату найма из строки формата MM/DD/YYYY"""
    return datetime.strptime(date_str, "%m/%d/%Y")

def safe_string(value, default=""):
    """Безопасно конвертирует значение в строку, возвращая default если value равно None"""
    return str(value) if value is not None else default

async def create_person_fixed(db, person_data):
    """Исправленная версия создания Person с обработкой несоответствия полей"""
    async with db.AsyncSessionLocal() as session:
        from src.backend.db.tables import Person
        
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
        
        return personResponse(
            id=person.id,
            client_id=person.client_id,
            beneficiary_id=person.beneficiary_id,
            first_name=person.first_name,
            middle_name=person.middle_name,
            last_name=person.last_name,
            date_of_birth=person.date_of_birth,
            sex=person.sex,
            ssn_or_tin=person.ssn_or_tin,
            email=person.email,
            phone_number=person.phone_number,
            phone_alt=person.phone_alt
        )

async def process_profile(db, profile_data):
    """Обрабатывает один профиль и создает все связанные записи"""
    print(f"\n=== Обработка профиля {profile_data['user_id']} ===")
    
    personal_info = profile_data['personal_info']
    contact_info = profile_data['contact_info']
    employment_info = profile_data['employment_info']
    
    # 1. Создаем Client
    client_data = ClientCreate(
        citizenship=personal_info['citizenship'],
        marital_status=personal_info['marital_status'],
        id_number=personal_info['id_number'],
        id_type=personal_info['id_type'],
        country_of_issuance=personal_info['country_of_issuance'],
        id_issuance_date=parse_date(personal_info['id_issuance_date']),
        id_expiration_date=parse_date(personal_info['id_expiration_date'])
    )
    
    client = await db.create_client(client_data)
    print(f"Создан клиент: {client.id}")
    
    # 2. Создаем основных бенефициаров
    beneficiaries = {}
    
    for ben_data in profile_data['beneficiaries']:
        beneficiary_create = BeneficiaryCreate(
            client_id=client.id,
            beneficiary_type="primary",
            relation=ben_data['relationship'],
            share_percentage=float(ben_data['share_prc'])
        )
        
        beneficiary = await db.create_beneficiary(beneficiary_create)
        beneficiaries[ben_data['relationship']] = beneficiary
        print(f"Создан бенефициар {ben_data['relationship']}: {beneficiary.id}")
    
    # 3. Создаем резервных бенефициаров
    for cont_data in profile_data['contingent']:
        if cont_data.get('name') and cont_data.get('relationship'):
            contingent_create = BeneficiaryCreate(
                client_id=client.id,
                beneficiary_type="contingent",
                relation=cont_data['relationship'],
                share_percentage=float(cont_data['share_prc'] or 0)
            )
            
            contingent = await db.create_beneficiary(contingent_create)
            beneficiaries[f"contingent_{cont_data['relationship']}"] = contingent
            print(f"Создан резервный бенефициар {cont_data['relationship']}: {contingent.id}")
    
    # 4. Создаем основную персону (клиента)
    # Выбираем первого основного бенефициара для связи
    first_beneficiary = next(iter([b for b in beneficiaries.values() if hasattr(b, 'id')]))
    
    person_main_data = personCreate(
        client_id=client.id,
        beneficiary_id=first_beneficiary.id,
        first_name=safe_string(personal_info['first']),
        middle_name=safe_string(personal_info.get('middle')),
        last_name=safe_string(personal_info['last']),
        date_of_birth=parse_date(personal_info['dob']) or datetime.now(),
        sex=safe_string(personal_info['sex']),
        ssn_or_tin=safe_string(personal_info['ssn_or_tin']),
        email=safe_string(contact_info['email']),
        phone_number=safe_string(contact_info['phone_mobile']),
        phone_alt=safe_string(contact_info.get('phone_alt'))
    )
    
    person_main = await create_person_fixed(db, person_main_data)
    print(f"Создана основная персона: {person_main.id}")
    
    # 5. Создаем персон для всех бенефициаров
    persons = [person_main]
    
    for ben_data in profile_data['beneficiaries']:
        if ben_data.get('first'):  # Есть подробная информация
            person_ben_data = personCreate(
                client_id=client.id,
                beneficiary_id=beneficiaries[ben_data['relationship']].id,
                first_name=safe_string(ben_data['first']),
                middle_name=safe_string(ben_data.get('middle')),
                last_name=safe_string(ben_data['last']),
                date_of_birth=parse_date(ben_data.get('dob')) or datetime.now(),
                sex='Unknown',  # Не указан в данных
                ssn_or_tin=safe_string(ben_data.get('ssn_or_tin')),
                email=safe_string(ben_data.get('email')),
                phone_number=safe_string(ben_data.get('phone_mobile')),
                phone_alt=safe_string(ben_data.get('phone_alt'))
            )
            
            person_ben = await create_person_fixed(db, person_ben_data)
            persons.append(person_ben)
            print(f"Создана персона бенефициара {ben_data['relationship']}: {person_ben.id}")
    
    # 6. Создаем адреса
    main_address_data = PersonAddressCreate(
        person_id=person_main.id,
        address_type="primary",
        street=safe_string(contact_info['address']['street']),
        city=safe_string(contact_info['address']['city']),
        state=safe_string(contact_info['address']['state']),
        country="United States",
        zip_code=safe_string(contact_info['address']['zip_code'])
    )
    
    main_address = await db.create_person_address(main_address_data)
    print(f"Создан основной адрес: {main_address.id}")
    
    # 7. Создаем информацию о работе
    employment_data = ClientEmploymentCreate(
        client_id=client.id,
        company_name=safe_string(employment_info['company_name']),
        job_title=safe_string(employment_info['job_title']),
        job_description=f"Работник в должности {safe_string(employment_info['job_title'])}",
        hire_date=parse_hire_date(employment_info['hire_date']),
        pay_frequency=safe_string(employment_info['pay_frequency']),
        year_funds=float(employment_info.get('year_funds', 0)),
        add_funds=float(employment_info.get('add_funds', 0))
    )
    
    employment = await db.create_client_employment(employment_data)
    print(f"Создана информация о работе: {employment.id}")
    
    # 8. Создаем образование (пример)
    education_data = ClientEducationCreate(
        client_id=client.id,
        started_on=datetime(1990, 9, 1),  # Примерные даты
        ended_on=datetime(1994, 5, 15),
        field_of_study="Business Administration",
        degree="Bachelor's Degree",
        university_name="State University"
    )
    
    education = await db.create_client_education(education_data)
    print(f"Создано образование: {education.id}")
    
    # 9. Создаем планы
    for plan_info in profile_data['plans']:
        # Определяем значение roth_first_year
        roth_value = 0.0
        se_context = plan_info.get('se_context', {})
        
        if se_context.get('roth_first_year'):
            roth_first_year = se_context['roth_first_year']
            if isinstance(roth_first_year, (int, float)):
                roth_value = float(roth_first_year)
            elif isinstance(roth_first_year, str) and roth_first_year.replace('.', '').isdigit():
                roth_value = float(roth_first_year)
        
        # Используем данные из contribution_settings если доступны
        contrib_settings = profile_data.get('contribution_settings', {})
        if contrib_settings.get('roth'):
            roth_contrib = contrib_settings['roth']
            if isinstance(roth_contrib, (int, float)):
                roth_value = float(roth_contrib)
        
        plan_data = PlanCreate(
            client_id=client.id,
            plan_type=safe_string(plan_info['plan_type']),
            provider=safe_string(plan_info['provider']),
            plan_code=safe_string(plan_info['plan_id']),
            plan_name=safe_string(se_context.get('plan_name', f"{plan_info['plan_type']} Plan")),
            employer_tax_id=safe_string(se_context.get('employer_tax_id')),
            roth_first_year=roth_value
        )
        
        plan = await db.create_plan(plan_data)
        print(f"Создан план {plan_info['plan_type']}: {plan.id}")
    
    return client.id

async def populate_all_profiles():
    """Заполняет базу данных всеми профилями"""
    
    # Загружаем данные профилей
    import os
    
    # Получаем путь к текущему файлу скрипта
    script_dir = os.path.dirname(os.path.abspath(__file__))
    profile_path = os.path.join(script_dir, 'json', 'profile.json')
    
    try:
        with open(profile_path, 'r', encoding='utf-8') as f:
            profiles_data = json.load(f)
    except FileNotFoundError:
        # Fallback to current directory
        with open('profile.json', 'r', encoding='utf-8') as f:
            profiles_data = json.load(f)
    
    db = DBFacade()
    
    # Очищаем и создаем таблицы
    await drop_tables_with_fk_constraints(db)
    await db.create_tables()
    
    # Обрабатываем все профили
    profiles_to_process = profiles_data['users']
    
    processed_clients = []
    
    for profile in profiles_to_process:
        try:
            client_id = await process_profile(db, profile)
            processed_clients.append({
                'profile_id': profile['user_id'],
                'client_id': client_id,
                'name': profile['personal_info']['full_legal_name']
            })
        except Exception as e:
            print(f"ОШИБКА при обработке профиля {profile['user_id']}: {e}")
            import traceback
            print(traceback.format_exc())
            continue
    
    print(f"\n=== ЗАВЕРШЕНО ===")
    print(f"Успешно обработано профилей: {len(processed_clients)}")
    for client_info in processed_clients:
        print(f"- {client_info['profile_id']}: {client_info['name']} (ID: {client_info['client_id']})")

# Запуск
if __name__ == "__main__":
    asyncio.run(populate_all_profiles())