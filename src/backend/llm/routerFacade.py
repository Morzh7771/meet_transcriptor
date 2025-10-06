from src.backend.models.llm_models import SlmResponse,llmResponse,RouterResponse
from src.backend.core.baseFacade import BaseFacade
from src.backend.prompts.promptFacade import PromptFacade
from src.backend.scenario_generator.scenarioFacade import ScenarioFacade
from src.backend.db.dbFacade import DBFacade
from typing import Dict, Any
from src.backend.rag_law.ragLawFacade import LawRAGFacade

class RouterAgent(BaseFacade):
    """
    Router agent for analyzing conversation transcriptions.
    Uses SLM for quick violation checks,
    triggers LLM for detailed analysis when violations are detected.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(RouterAgent, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, slm_model="gpt-4o-mini", llm_model="gpt-4.1"):
        super().__init__()
        self.slm_model = slm_model  # Small model for quick checks
        self.llm_model = llm_model  # Large model for detailed analysis
        self.scenario_facade = ScenarioFacade()
        self.law_rag_facade = LawRAGFacade()
        self.db = DBFacade()

    async def analyze_transcription(self, transcription_text: str):
        """
        Analyzes a 10-second transcription fragment.
        
        Args:
            transcription_text: Conversation transcription text
            
        Returns:
            dict with analysis results and violation flag
        """
        try:
            self.logger.info("=== Starting analyze_transcription ===")
            self.logger.info(f"Input text length: {len(transcription_text)}")
            
            # Check with small model
            self.logger.info("Calling SLM...")
            slm_response = await self._check_with_slm(transcription_text)
            
            self.logger.info(f"SLM Response type: {type(slm_response)}")
            #self.logger.info(f"SLM Response: {slm_response}")
            self.logger.info(f"SLM has_violation type: {type(slm_response.has_violation)}")
            self.logger.info(f"SLM has_violation value: {slm_response.has_violation}")
            
            # If violation detected - pass to large model
            if slm_response.has_violation:
           
                # Law RAG search
                law_rag_response_chunk = await self._rag_search(slm_response.chunk, limits=1)
                law_rag_response_disk = await self._rag_search(slm_response.law_disk, limits=1)
                law_rag_response = "\n".join([law_rag_response_chunk, law_rag_response_disk])
                self.logger.info(f'LAW RAG RESPONSE: {law_rag_response}')
                self.logger.info("Violation detected, calling LLM for detailed analysis...")
                detailed_analysis = await self._analyze_with_llm(transcription_text, slm_response, law_rag_response)
                self.logger.info(f"LLM Response type: {type(detailed_analysis)}")
                self.logger.info(f"LLM Response: {detailed_analysis}")
                
                result = {
                    "has_violation": detailed_analysis.has_violation,
                    "detailed_analysis": detailed_analysis.response
                }
                self.logger.info(f"Returning result with violation: {result}")
                return result
            
            # No violation detected
            result = {
                "has_violation": False
            }
            self.logger.info(f"No violation detected, returning: {result}")
            return result
            
        except Exception as e:
            self.logger.error(f"Error in analyze_transcription: {e}", exc_info=True)
            # Return safe default
            return {
                "has_violation": False,
                "error": str(e)
            }

    async def _check_with_slm(self, transcription_text: str) -> SlmResponse:
        """
        Quick check with small model for violations.
        """
        try:
            self.logger.info("=== _check_with_slm started ===")
            slm_prompt_template = eval(PromptFacade.get_prompt("slm_template", transcription_text=transcription_text))
            self.logger.info(f"SLM prompt prepared, calling API...")
            
            response = await self.client.chat.completions.create(
                model=self.slm_model,
                messages=slm_prompt_template,
                response_model=SlmResponse
            )
            
            self.logger.info(f"SLM API response received: {response}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error in _check_with_slm: {e}", exc_info=True)
            raise

    async def _rag_search(self, query: str, limits: int) -> str:
        """
        Perform a RAG search to retrieve relevant legal information.
        """
        try:
            self.logger.info("=== _rag_search started ===")
            self.logger.info(f"RAG query: {query}")
            
            documents = self.law_rag_facade.search_laws(query, limits)
            self.logger.info(f"RAG result type: {type(documents)}")
            self.logger.info(f"RAG result keys: {documents.keys()}")
             
            combined_docs = "\n\n".join(item["text"] for item in documents["results"] if "text" in item)
            self.logger.info(f"RAG search returned {len(documents)} documents. {documents}")
            self.logger.info(f"RAG search returned documents - {combined_docs}")
            return combined_docs
            
        except Exception as e:
            self.logger.error(f"Error in _rag_search: {e}", exc_info=True)
            return ""

    async def _analyze_with_llm(self, transcription_text: str, slm_response: SlmResponse, law_rag_response: str) -> llmResponse:
        """
        Detailed analysis with large model when violation is detected.
        """
        try:
            self.logger.info("=== _analyze_with_llm started ===")
            self.logger.info(f"SLM Response chunk: {slm_response.chunk}")
            self.logger.info(f"SLM Response law_desc: {slm_response.law_disk}")
            
            llm_prompt_template = eval(PromptFacade.get_prompt(
                "llm_template", 
                transcription_text=transcription_text,
                chunk=slm_response.chunk,
                law_desc=slm_response.law_disk,
                law_rag=law_rag_response
            ))
            
            self.logger.info(f"LLM prompt prepared, calling API...")
            self.logger.info(f"ALL DATA FOR LLM: {llm_prompt_template}")
            response = await self.client.chat.completions.create(
                model=self.llm_model,
                messages=llm_prompt_template,
                response_model=llmResponse
            )
            
            self.logger.info(f"LLM API response received: {response}")

            return response
            
        except Exception as e:
            self.logger.error(f"Error in _analyze_with_llm: {e}", exc_info=True)
            raise

    async def validate_chunk(self, chunk_text: str, scenario: str) -> Dict[str, Any]:
        try:
            
            result = await self.scenario_facade.validate_chunk_against_scenario(
                scenario=scenario,
                chunk_text=chunk_text
            )
            
            if hasattr(result, 'choices'):
                result_text = result.choices[0].message.content
            elif hasattr(result, 'content'):
                result_text = result.content
            else:
                result_text = str(result)
            
            has_deviation = bool(result_text and result_text.strip())
            
            return {
                "has_deviation": has_deviation,
                "deviation_details": result_text if has_deviation else None,
            }
            
        except Exception as e:
            self.logger.error(f"Scenario validation error for meeting: {e}", exc_info=True)
            return {
                "has_deviation": False,
                "error": str(e),
            }

    async def __call__(self, transcription_text: str):
        """
        Main method for calling the agent.
        Backward compatibility with previous version.
        """
        return await self.analyze_transcription(transcription_text)
    
    async def front_chat(self, chat_history, model="gpt-4.1"):

        response = await self.client.chat.completions.create(
            model = model,
            messages = chat_history,
            response_model=RouterResponse
        )

        return response
