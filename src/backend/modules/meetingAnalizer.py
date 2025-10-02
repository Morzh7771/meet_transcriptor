import tiktoken
from src.backend.core.baseFacade import BaseFacade
from src.backend.prompts.promptFacade import PromptFacade
from src.backend.models.llm_models import NotesResponse, SummarizerResponse, OverviewResponse, ActionItemsResponse
from src.backend.db.dbFacade import DBFacade
from src.backend.modules.adviser_pipeline import AdvisorProcessor
db = DBFacade()
from src.backend.utils.logger import CustomLog  

class MeetingAnalizer(BaseFacade):
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(MeetingAnalizer, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        super().__init__()
        self.enc = tiktoken.encoding_for_model("gpt-4.1")
        self.CHUNK_SIZE = 20_000
        self.logger = CustomLog()
    async def summarize(self, full_transcript, meet_id):
        client_id = await db.get_client_id_by_meet_id(meet_id)
        consultant_id = await db.get_consultant_id_by_meet_id(meet_id)
        products = await db.get_company_products_by_consultant_id(consultant_id)
        profile = await db.get_client_full_info(client_id)
        unified_data = {
            "products": products,
            "transcript": full_transcript,
            "selected_profile": profile 
        }
        processor = AdvisorProcessor()
        result = await processor.process_advice(unified_data)
        return result

    async def generate_notes(self, full_transcript):

        messages = eval(PromptFacade.get_prompt("notes",
                                            meeting_transcript=full_transcript))
        
        result = await self.completion("gpt-4.1",
                                        messages=messages,
                                        max_tokens=16000,
                                        output_model=NotesResponse)

        return result

    async def generate_overview(self, full_transcript):

        messages = eval(PromptFacade.get_prompt("overview",
                                            meeting_transcript=full_transcript))
        
        result = await self.completion("gpt-4.1",
                                        messages=messages,
                                        max_tokens=16000,
                                        output_model=OverviewResponse)

        return result

    async def generate_action_items(self, summary, meet_id):
        consultant_id = await db.get_consultant_id_by_meet_id(meet_id)
        products = await db.get_company_products_by_consultant_id(consultant_id)
        product_names = [p.product_name for p in products if getattr(p, "product_name", None)]
        #self.logger.info(f"{summary}")
        #self.logger.info(f"{product_names}")
        #self.logger.info(f"{products}")
        #self.logger.info(f"{consultant_id}")

        messages = eval(PromptFacade.get_prompt(
                                                "action_items",    
                                                products=product_names,
                                                summary=summary,
                                                output_model=ActionItemsResponse
                                                ))

      
        result_raw = await self.completion(
            "gpt-4.1",
            messages=messages,
            max_tokens=256
        )
        #self.logger.info(f"Action items generated: {result_raw.choices[0].message.content.strip()}")
        result = result_raw.choices[0].message.content.strip()
        if result == "":
            result = "No action items identified."
        #self.logger.info(f"Action items generated: {result}")
        
        return result