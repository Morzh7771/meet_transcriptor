from src.backend.models.llm_models import SlmResponse,llmResponse
from src.backend.core.baseFacade import BaseFacade
from src.backend.prompts.promptFacade import PromptFacade
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

    def __init__(self, slm_model="gpt-4o-mini", llm_model="gpt-5-2025-08-07"):
        super().__init__()
        self.slm_model = slm_model  # Small model for quick checks
        self.llm_model = llm_model  # Large model for detailed analysis

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
            self.logger.info(f"SLM Response: {slm_response}")
            self.logger.info(f"SLM has_violation type: {type(slm_response.has_violation)}")
            self.logger.info(f"SLM has_violation value: {slm_response.has_violation}")
            
            # If violation detected - pass to large model
            if slm_response.has_violation:
                self.logger.info("Violation detected, calling LLM for detailed analysis...")
                detailed_analysis = await self._analyze_with_llm(transcription_text, slm_response)
                self.logger.info(f"LLM Response type: {type(detailed_analysis)}")
                self.logger.info(f"LLM Response: {detailed_analysis}")
                
                result = {
                    "has_violation": True,
                    "detailed_analysis": detailed_analysis
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
            slm_prompt_template = eval(PromptFacade.get_prompt("slm_teamplate", transcription_text=transcription_text))
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

    async def _analyze_with_llm(self, transcription_text: str, slm_response: SlmResponse):
        """
        Detailed analysis with large model when violation is detected.
        """
        try:
            self.logger.info("=== _analyze_with_llm started ===")
            self.logger.info(f"SLM Response chunk: {slm_response.chunk}")
            self.logger.info(f"SLM Response law_desc: {slm_response.law_desc}")
            
            llm_prompt_template = eval(PromptFacade.get_prompt(
                "llm_template", 
                transcription_text=transcription_text,
                chunk=slm_response.chunk,
                law_desc=slm_response.law_desc
            ))
            
            self.logger.info(f"LLM prompt prepared, calling API...")
            
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

    async def __call__(self, transcription_text: str):
        """
        Main method for calling the agent.
        Backward compatibility with previous version.
        """
        return await self.analyze_transcription(transcription_text)