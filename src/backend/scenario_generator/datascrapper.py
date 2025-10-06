import sys
import os
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict, field
from src.backend.utils.logger import CustomLog

# Ensure project root on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.backend.db.dbFacade import DBFacade
from src.backend.models.db_models import *  # personResponse, ClientResponse, etc.

from src.backend.vector_db.qdrant_Facade import VectorDBFacade
from src.backend.core.baseFacade import BaseFacade

# -------- Data container -------------------------------------------------------

@dataclass
class FullClientData:
    person: Optional[personResponse] = None
    client: Optional[ClientResponse] = None
    addresses: List[PersonAddressResponse] = field(default_factory=list)
    educations: List[ClientEducationResponse] = field(default_factory=list)
    employments: List[ClientEmploymentResponse] = field(default_factory=list)
    beneficiaries: List[BeneficiaryResponse] = field(default_factory=list)
    plans: List[PlanResponse] = field(default_factory=list)
    meetings: List[MeetResponse] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# -------- Helper ---------------------------------------------------------------

def _group_by(items: List[Any], key):
    """
    Simple utility to group a list of objects by a key function or attribute name.
    key: Callable or string attribute name
    """
    kf = (lambda x: getattr(x, key)) if isinstance(key, str) else key
    out: Dict[Any, List[Any]] = {}
    for it in items or []:
        out.setdefault(kf(it), []).append(it)
    return out


# -------- Core reader ----------------------------------------------------------

class ClientDataReader(BaseFacade):
    def __init__(self):
        self.db = DBFacade()
        vector_db = VectorDBFacade()
        self.logger = CustomLog()
        self.vector_similarity = vector_db.client_profiles
 

    # ---------- Single client --------------------------------------------------

    async def get_client_by_email(self, email: str) -> Optional[FullClientData]:
        """
        Fetch a single client's full data by a person's email.
        """
        try:
            person = await self.db.get_person_by_email(email)
            if not person:
                self.logger.error(f"Client with email '{email}' not found")
                return None

            client = await self.db.get_client_by_id(person.client_id) if person.client_id else None
            data = FullClientData(person=person, client=client)

            # Pull everything once and filter locally (keeps DBFacade unchanged)
            all_addresses = await self.db.get_all_person_addresses()
            all_educations = await self.db.get_all_client_educations()
            all_employments = await self.db.get_all_client_employments()
            all_beneficiaries = await self.db.get_all_beneficiaries()
            all_plans = await self.db.get_all_plans()
            all_meets = await self.db.get_all_meets()

            cid = person.client_id
            pid = person.id

            data.addresses = [a for a in all_addresses if a.person_id == pid]
            if cid:
                data.educations = [e for e in all_educations if e.client_id == cid]
                data.employments = [e for e in all_employments if e.client_id == cid]
                data.beneficiaries = [b for b in all_beneficiaries if b.client_id == cid]
                data.plans = [p for p in all_plans if p.client_id == cid]
                data.meetings = [m for m in all_meets if m.client_id == cid]

            return data

        except Exception as e:
            self.logger.error(f"Error fetching client '{email}': {e}")
            return None

    # ---------- All clients ----------------------------------------------------

    async def get_all_clients(self) -> List[FullClientData]:
        """
        Fetch all persons and stitch related client data efficiently.
        """
        try:
            persons = await self.db.get_all_persons()
            self.logger.info(f"Found {len(persons)} persons in the database")

            clients = await self.db.get_all_clients()
            addresses = await self.db.get_all_person_addresses()
            educations = await self.db.get_all_client_educations()
            employments = await self.db.get_all_client_employments()
            beneficiaries = await self.db.get_all_beneficiaries()
            plans = await self.db.get_all_plans()
            meetings = await self.db.get_all_meets()

            # Index for quick joins
            clients_by_id = {c.id: c for c in clients}
            addrs_by_person = _group_by(addresses, "person_id")
            edus_by_client = _group_by(educations, "client_id")
            emps_by_client = _group_by(employments, "client_id")
            bens_by_client = _group_by(beneficiaries, "client_id")
            plans_by_client = _group_by(plans, "client_id")
            meets_by_client = _group_by(meetings, "client_id")

            all_data: List[FullClientData] = []
            for p in persons:
                cid = p.client_id
                all_data.append(
                    FullClientData(
                        person=p,
                        client=clients_by_id.get(cid),
                        addresses=addrs_by_person.get(p.id, []),
                        educations=edus_by_client.get(cid, []) if cid else [],
                        employments=emps_by_client.get(cid, []) if cid else [],
                        beneficiaries=bens_by_client.get(cid, []) if cid else [],
                        plans=plans_by_client.get(cid, []) if cid else [],
                        meetings=meets_by_client.get(cid, []) if cid else [],
                    )
                )

            self.logger.info(f"Successfully assembled data for {len(all_data)} clients")
            return all_data

        except Exception as e:
            self.logger.error(f"Error fetching all clients: {e}")
            return []

    # ---------- Similar clients + context -------------------------------------

    async def get_similar_clients_for_target(
        self,
        target_email: str,
        similarity_count: int = 5,
        update_vector_db: bool = True,
    ) -> Dict[str, Any]:
        """
        Find similar clients to the target client using vector search.
        Returns: dict with target_client (FullClientData), list of similar_clients, and total_similar_found.
        """
        try:
            target_client = await self.get_client_by_email(target_email)
            if not target_client:
                return {"error": f"Target client with email '{target_email}' not found"}

            self.logger.info(f"Target client: {target_client.person.first_name} {target_client.person.last_name}")

            if update_vector_db:
                self.logger.info("Refreshing vector database...")
                all_clients = await self.get_all_clients()
                await self.vector_similarity.store_all_clients(all_clients)
                self.logger.info("Vector database updated")

            self.logger.info(f"Searching for top-{similarity_count} similar clients...")
            similar_infos = await self.vector_similarity.find_similar_clients(
                target_client, top_k=similarity_count
            )

            # Resolve similar persons once
            persons = await self.db.get_all_persons()
            persons_by_id = {str(p.id): p for p in persons}

            similar_full: List[Dict[str, Any]] = []
            for info in similar_infos:
                pid = str(info.get("client_id"))
                person = persons_by_id.get(pid)
                if person and getattr(person, "email", None):
                    full = await self.get_client_by_email(person.email)
                    if full:
                        similar_full.append(
                            {
                                "similarity_score": info.get("similarity_score", 0.0),
                                "client_data": full,
                                "profile_summary": info.get("metadata", {}).get("profile_text", ""),
                            }
                        )

            self.logger.info(f"Found {len(similar_full)} similar clients")
            return {
                "target_client": target_client,
                "similar_clients": similar_full,
                "total_similar_found": len(similar_full),
            }

        except Exception as e:
            self.logger.error(f"Error searching similar clients: {e}")
            return {"error": str(e)}

    async def prepare_scenario_context(self, target_email: str, similarity_count: int = 3) -> str:
        """
        Build an LLM-friendly text context with the target client and a few similar clients.
        """
        try:
            result = await self.get_similar_clients_for_target(
                target_email, similarity_count, update_vector_db=True
            )
            if "error" in result:
                return f"Error: {result['error']}"

            target = result["target_client"]
            similars = result["similar_clients"]

            lines: List[str] = []
            lines.append("=== CONTEXT FOR SCENARIO GENERATION ===\n")

            lines.append("TARGET CLIENT:\n")
            lines.append(self._format_client_for_context(target, is_target=True))
            lines.append("\n" + "=" * 50 + "\n")

            lines.append("SIMILAR CLIENTS (for reference):\n")
            for i, sc in enumerate(similars, 1):
                lines.append(f"SIMILAR CLIENT #{i} (similarity: {sc['similarity_score']:.3f}):")
                lines.append(f"Profile: {sc['profile_summary']}\n")
                lines.append("Details:")
                lines.append(self._format_client_for_context(sc["client_data"]))
                lines.append("\n" + "-" * 30 + "\n")

            lines.append("=== END OF CONTEXT ===\n")
            return "\n".join(lines)

        except Exception as e:
            return f"Error preparing context: {e}"

    def _format_client_for_context(self, client_data: FullClientData, is_target: bool = False) -> str:
        """
        Format a client's data for LLM context. Hides email for the target client.
        """
        p = client_data.person
        c = client_data.client
        out: List[str] = []

        def add(label: str, val):
            if val not in (None, "", []):
                out.append(f"{label}: {val}")

        # Person
        if p:
            add("Name", f"{p.first_name} {p.last_name}".strip())
            add("Birth date", p.birth_date)
            add("Phone", p.phone)
            if not is_target:
                add("Email", p.email)

        # Client
        if c:
            add("Income", c.income)
            add("Marital status", c.marital_status)
            add("Children count", c.children_count)
            add("Risk tolerance", c.risk_tolerance)
            add("Investment experience", c.investment_experience)
            add("Financial goals", c.financial_goals)

        # Addresses
        if client_data.addresses:
            out.append("Addresses:")
            for a in client_data.addresses:
                city = getattr(a, "city", None)
                addr = getattr(a, "address", None)
                if city or addr:
                    out.append(f"  - {', '.join([x for x in [city, addr] if x])}")

        # Education
        if client_data.educations:
            out.append("Education:")
            for e in client_data.educations:
                pieces = [
                    getattr(e, "institution", None),
                    f"({e.degree})" if getattr(e, "degree", None) else None,
                    f"- {e.field_of_study}" if getattr(e, "field_of_study", None) else None,
                    f"({e.graduation_year})" if getattr(e, "graduation_year", None) else None,
                ]
                text = "  - " + " ".join([p for p in pieces if p])
                out.append(text)

        # Employment
        if client_data.employments:
            out.append("Employment:")
            for emp in client_data.employments:
                pieces = [
                    getattr(emp, "company", None),
                    f"- {emp.position}" if getattr(emp, "position", None) else None,
                    f"({emp.industry})" if getattr(emp, "industry", None) else None,
                    f", salary: {emp.salary}" if getattr(emp, "salary", None) else None,
                ]
                text = "  - " + " ".join([p for p in pieces if p])
                out.append(text)

        # Plans
        if client_data.plans:
            out.append("Insurance plans:")
            for pl in client_data.plans:
                pieces = [
                    getattr(pl, "name", None),
                    f"({pl.type})" if getattr(pl, "type", None) else None,
                    f", premium: {pl.premium}" if getattr(pl, "premium", None) else None,
                    f", coverage: {pl.coverage_amount}" if getattr(pl, "coverage_amount", None) else None,
                ]
                text = "  - " + " ".join([p for p in pieces if p])
                out.append(text)

        # Beneficiaries
        if client_data.beneficiaries:
            out.append("Beneficiaries:")
            for b in client_data.beneficiaries:
                name = getattr(b, "name", None)
                rel = getattr(b, "relationship", None)
                if name or rel:
                    out.append(f"  - {name} ({rel})" if rel else f"  - {name}")

        # Meetings
        if client_data.meetings:
            if is_target:
                out.append("Recent meetings:")
                for m in client_data.meetings[-3:]:
                    date = getattr(m, "meeting_date", None)
                    purpose = getattr(m, "purpose", None) or "Not specified"
                    out.append(f"  - {date}: {purpose}")
            else:
                out.append(f"Meetings count: {len(client_data.meetings)}")

        return "\n".join(out)

    # ---------- Vector DB bootstrap -------------------------------------------

    async def initialize_vector_database(self) -> bool:
        """
        Initialize (or reinitialize) the vector DB with all clients.
        """
        try:
            self.logger.info("Initializing vector database...")
            await self.vector_similarity.initialize_collection()

            all_clients = await self.get_all_clients()
            if not all_clients:
                self.logger.error("No clients found to initialize")
                return False

            count = await self.vector_similarity.store_all_clients(all_clients)
            self.logger.info(f"Vector database initialized with {count} clients")
            return count > 0

        except Exception as e:
            self.logger.error(f"Error initializing vector database: {e}")
            return False


# -------- Public API -----------------------------------------------------------

async def get_scenario_context(target_email: str, similar_count: int = 3) -> str:
    """
    Produce the formatted context for LLM based on a target client and similar clients.
    """
    reader = ClientDataReader()
    return await reader.prepare_scenario_context(target_email, similar_count)


async def initialize_system() -> bool:
    """
    Initialize the vector similarity system (collection + embeddings).
    """
    reader = ClientDataReader()
    return await reader.initialize_vector_database()


async def demo_system(target_email: Optional[str] = None):
    """
    Demo run: pick the first available client if email is not provided, then print context.
    """
    reader = ClientDataReader()

    if not target_email:
        all_clients = await reader.get_all_clients()
        if all_clients and all_clients[0].person and all_clients[0].person.email:
            target_email = all_clients[0].person.email
        else:
            print("Could not find a client for demo")
            return

    print(f"Demo for client: {target_email}")
    print("=" * 60)
    context = await get_scenario_context(target_email, 2)
    print("GENERATED CONTEXT:")
    print(context)
    return context


# -------- CLI -----------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Similar clients search system")
    parser.add_argument("--email", "-e", type=str, help="Target client email")
    parser.add_argument("--init", "-i", action="store_true", help="Initialize vector DB")
    parser.add_argument("--demo", "-d", action="store_true", help="Run demo")
    parser.add_argument("--similar-count", "-s", type=int, default=3, help="Number of similar clients")
    args = parser.parse_args()

    if args.init:
        print("Initializing system...")
        ok = asyncio.run(initialize_system())
        print(f"Initialization {'succeeded' if ok else 'failed'}")

    elif args.demo:
        asyncio.run(demo_system(args.email))

    elif args.email:
        ctx = asyncio.run(get_scenario_context(args.email, args.similar_count))
        print(ctx)

    else:
        print("Use --help to see options")
