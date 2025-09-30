import os
import asyncio
import json
from typing import List, Dict, Any, Optional
from dataclasses import asdict
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from openai import OpenAI
from src.backend.utils.configs import Config

class ClientVectorSimilarity:
    def __init__(self):
        self.configs = Config.load_config()
        self.qdrant_client = QdrantClient(
            # host=os.getenv("QDRANT_HOST", "localhost"),
            # port=int(os.getenv("QDRANT_PORT", 6333)),
            url=self.configs.vectordb.URL,
            api_key=self.configs.vectordb.API_KEY.get_secret_value(),
        )
        self.openai_client = OpenAI(api_key=self.configs.openai.API_KEY.get_secret_value())
        
        self.collection_name = "client_profiles"
        self.vector_size = 1536
        
    async def initialize_collection(self):
        """Creates collection in Qdrant if it doesn't exist"""
        try:
            collections = self.qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if self.collection_name not in collection_names:
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                print(f"Created collection {self.collection_name}")
            else:
                print(f"Collection {self.collection_name} already exists")
        except Exception as e:
            print(f"Error initializing collection: {e}")
            raise

    def _format_client_data(self, client_data) -> str:
        """Formats client data into text for vectorization"""
        person = client_data.person
        client = client_data.client
        
        profile_text = f"Client: {person.first_name} {person.last_name}"
        
        if hasattr(person, 'date_of_birth') and person.date_of_birth:
            profile_text += f", birth date: {person.date_of_birth}"
        if hasattr(person, 'phone_number') and person.phone_number:  
            profile_text += f", phone: {person.phone_number}"
        if hasattr(person, 'phone_alt') and person.phone_alt:
            profile_text += f", alt phone: {person.phone_alt}"
        if hasattr(person, 'email') and person.email:
            profile_text += f", email: {person.email}"
        if hasattr(person, 'sex') and person.sex:
            profile_text += f", sex: {person.sex}"
        if hasattr(person, 'ssn_or_tin') and person.ssn_or_tin:
            profile_text += f", SSN/TIN: {person.ssn_or_tin}"
        
        if client:
            if hasattr(client, 'citizenship') and client.citizenship:
                profile_text += f", citizenship: {client.citizenship}"
            if hasattr(client, 'marital_status') and client.marital_status:
                profile_text += f", marital status: {client.marital_status}"
            if hasattr(client, 'id_type') and client.id_type:
                profile_text += f", ID type: {client.id_type}"
            if hasattr(client, 'country_of_issuance') and client.country_of_issuance:
                profile_text += f", country of issuance: {client.country_of_issuance}"
        
        if hasattr(client_data, 'addresses') and client_data.addresses:
            addresses = []
            for addr in client_data.addresses:
                addr_parts = []
                if hasattr(addr, 'street') and addr.street:
                    addr_parts.append(addr.street)
                if hasattr(addr, 'city') and addr.city:
                    addr_parts.append(addr.city)
                if hasattr(addr, 'state') and addr.state:
                    addr_parts.append(addr.state)
                if hasattr(addr, 'country') and addr.country:
                    addr_parts.append(addr.country)
                if hasattr(addr, 'address_type') and addr.address_type:
                    addr_parts.append(f"({addr.address_type})")
                
                if addr_parts:
                    addresses.append(", ".join(addr_parts))
            
            if addresses:
                profile_text += f", addresses: {'; '.join(addresses)}"
        
        if hasattr(client_data, 'educations') and client_data.educations:
            educations = []
            for edu in client_data.educations:
                edu_parts = []
                if hasattr(edu, 'university_name') and edu.university_name:  
                    edu_parts.append(edu.university_name)
                if hasattr(edu, 'degree') and edu.degree:
                    edu_parts.append(f"({edu.degree})")
                if hasattr(edu, 'field_of_study') and edu.field_of_study:
                    edu_parts.append(f"- {edu.field_of_study}")
                
                if edu_parts:
                    educations.append(" ".join(edu_parts))
            
            if educations:
                profile_text += f", education: {'; '.join(educations)}"
        
        if hasattr(client_data, 'employments') and client_data.employments:
            employments = []
            for emp in client_data.employments:
                emp_parts = []
                if hasattr(emp, 'company_name') and emp.company_name:
                    emp_parts.append(emp.company_name)
                if hasattr(emp, 'job_title') and emp.job_title:
                    emp_parts.append(f"- {emp.job_title}")
                if hasattr(emp, 'job_description') and emp.job_description:
                    emp_parts.append(f"({emp.job_description})")
                if hasattr(emp, 'year_funds') and emp.year_funds:
                    emp_parts.append(f", annual funds: {emp.year_funds}")
                if hasattr(emp, 'pay_frequency') and emp.pay_frequency:
                    emp_parts.append(f", pay frequency: {emp.pay_frequency}")
                
                if emp_parts:
                    employments.append(" ".join(emp_parts))
            
            if employments:
                profile_text += f", employment: {'; '.join(employments)}"
        
        if hasattr(client_data, 'plans') and client_data.plans:
            plans = []
            for plan in client_data.plans:
                plan_parts = []
                if hasattr(plan, 'plan_name') and plan.plan_name:
                    plan_parts.append(plan.plan_name)
                if hasattr(plan, 'plan_type') and plan.plan_type:
                    plan_parts.append(f"({plan.plan_type})")
                if hasattr(plan, 'provider') and plan.provider:
                    plan_parts.append(f"provider: {plan.provider}")
                if hasattr(plan, 'plan_code') and plan.plan_code:
                    plan_parts.append(f"code: {plan.plan_code}")
                
                if plan_parts:
                    plans.append(", ".join(plan_parts))
            
            if plans:
                profile_text += f", plans: {'; '.join(plans)}"
        
        if hasattr(client_data, 'beneficiaries') and client_data.beneficiaries:
            beneficiaries = []
            for ben in client_data.beneficiaries:
                ben_parts = []
                if hasattr(ben, 'relation') and ben.relation:
                    ben_parts.append(f"relation: {ben.relation}")
                if hasattr(ben, 'beneficiary_type') and ben.beneficiary_type:
                    ben_parts.append(f"type: {ben.beneficiary_type}")
                if hasattr(ben, 'share_percentage') and ben.share_percentage:
                    ben_parts.append(f"share: {ben.share_percentage}%")
                
                if ben_parts:
                    beneficiaries.append(", ".join(ben_parts))
            
            if beneficiaries:
                profile_text += f", beneficiaries: {'; '.join(beneficiaries)}"
        
        if hasattr(client_data, 'meetings') and client_data.meetings:
            meetings_count = len(client_data.meetings)
            profile_text += f", meetings count: {meetings_count}"
            
            recent_meetings = []
            for meet in client_data.meetings[:3]:
                meet_parts = []
                if hasattr(meet, 'title') and meet.title:
                    meet_parts.append(meet.title)
                if hasattr(meet, 'date') and meet.date:
                    meet_parts.append(f"({meet.date})")
                
                if meet_parts:
                    recent_meetings.append(" ".join(meet_parts))
            
            if recent_meetings:
                profile_text += f", recent meetings: {'; '.join(recent_meetings)}"
        
        return profile_text

    async def _get_embedding(self, text: str) -> List[float]:
        """Gets vector representation of text through OpenAI API"""
        try:
            response = await asyncio.to_thread(
                self.openai_client.embeddings.create,
                input=text,
                model='text-embedding-3-small' #"text-embedding-ada-002"
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error getting embedding: {e}")
            raise

    async def store_client_vector(self, client_data, client_id: str) -> bool:
        """Stores client vector representation in Qdrant"""
        try:
            # Create client profile
            client_profile = self._format_client_data(client_data)
            
            # Get vector representation
            embedding = await self._get_embedding(client_profile)
            
            # Prepare metadata with safe attribute access
            person = client_data.person
            
            person_id = getattr(person, 'id', None) if person else None
            first_name = getattr(person, 'first_name', 'Unknown') if person else 'Unknown'
            last_name = getattr(person, 'last_name', '') if person else ''
            email = getattr(person, 'email', None) if person else None
            
            metadata = {
                "client_id": client_id,
                "person_id": person_id,
                "name": f"{first_name} {last_name}".strip(),
                "email": email,
                "profile_text": client_profile,
                "has_client_data": client_data.client is not None,
                "plans_count": len(getattr(client_data, 'plans', [])),
                "meetings_count": len(getattr(client_data, 'meetings', []))
            }
            
            # Store in Qdrant
            point = PointStruct(
                id=client_id,
                vector=embedding,
                payload=metadata
            )
            
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            print(f"Stored vector for client {metadata['name']} (ID: {client_id})")
            return True
            
        except Exception as e:
            print(f"Error storing vector for client {client_id}: {e}")
            return False

    async def store_all_clients(self, clients_data: List) -> int:
        """Stores all clients in vector database"""
        await self.initialize_collection()
        
        success_count = 0
        for i, client_data in enumerate(clients_data):
            client_id = str(client_data.person.id) if client_data.person and hasattr(client_data.person, 'id') else str(i)
            
            if await self.store_client_vector(client_data, client_id):
                success_count += 1
                
            await asyncio.sleep(0.1)
        
        print(f"Successfully stored {success_count} out of {len(clients_data)} clients")
        return success_count

    async def find_similar_clients(self, target_client_data, top_k: int = 5) -> List[Dict[str, Any]]:
        """Finds most similar clients for target client"""
        try:
            # Create target client profile
            target_profile = self._format_client_data(target_client_data)  # Fixed: was calling non-existent _summarize_client_profile
            
            # Get vector representation of target client
            target_embedding = await self._get_embedding(target_profile)
            
            # Search for similar vectors in Qdrant
            search_result = self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=target_embedding,
                limit=top_k + 1,  # +1 to exclude self if present in database
                with_payload=True,
                with_vectors=False
            )
            
            similar_clients = []
            target_client_id = str(target_client_data.person.id) if target_client_data.person else None
            
            for scored_point in search_result:
                # Skip the target client itself
                if target_client_id and scored_point.id == target_client_id:
                    continue
                    
                similar_clients.append({
                    "client_id": scored_point.id,
                    "similarity_score": scored_point.score,
                    "metadata": scored_point.payload
                })
                
                if len(similar_clients) >= top_k:
                    break
            
            print(f"Found {len(similar_clients)} similar clients for {target_client_data.person.first_name} {target_client_data.person.last_name}")
            
            # Display results
            for i, client in enumerate(similar_clients, 1):
                print(f"{i}. {client['metadata']['name']} (similarity: {client['similarity_score']:.3f})")
                print(f"   Profile: {client['metadata']['profile_text'][:100]}...")
                print()
            
            return similar_clients
            
        except Exception as e:
            print(f"Error finding similar clients: {e}")
            return []

    async def get_client_by_vector_id(self, vector_id: str) -> Optional[Dict[str, Any]]:
        """Gets client data from vector database by ID"""
        try:
            points = self.qdrant_client.retrieve(
                collection_name=self.collection_name,
                ids=[vector_id],
                with_payload=True
            )
            
            if points:
                return points[0].payload
            return None
            
        except Exception as e:
            print(f"Error retrieving client from vector database: {e}")
            return None

    def clear_collection(self):
        """Clears collection (for testing)"""
        try:
            self.qdrant_client.delete_collection(self.collection_name)
            print(f"Collection {self.collection_name} deleted")
        except Exception as e:
            print(f"Error deleting collection: {e}")

# Helper function for demonstration
async def demo_similarity_search():
    """Demonstration of similar client search system"""
    from datascrapper import ClientDataReader
    
    # Create class instances
    reader = ClientDataReader()
    similarity = ClientVectorSimilarity()
    
    # Get all clients
    print("Loading all clients...")
    all_clients = await reader.get_all_clients()
    
    if not all_clients:
        print("No clients found in database")
        return
    
    # Store all clients in vector database
    print("Storing clients in vector database...")
    await similarity.store_all_clients(all_clients)
    
    # Select target client (e.g., first one)
    target_client = all_clients[0]
    print(f"\nTarget client: {target_client.person.first_name} {target_client.person.last_name}")
    
    # Search for similar clients
    print("\nSearching for similar clients...")
    similar_clients = await similarity.find_similar_clients(target_client, top_k=3)
    
    return similar_clients

# if __name__ == "__main__":
#     asyncio.run(demo_similarity_search())