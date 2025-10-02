import json
from datetime import datetime
from typing import Dict, Any
import asyncio
from src.backend.core.baseFacade import BaseFacade
from src.backend.prompts.promptFacade import PromptFacade
from src.backend.models.llm_models import SummarizerResponse


class AdvisorProcessor(BaseFacade):

    _instance = None
 
    async def process_advice(self, unified_data: Dict[str, Any]) -> SummarizerResponse:
      
        meeting_analysis, strategy_analysis = await asyncio.gather(
            self._analyze_meeting(unified_data),
            self._analyze_strategy(unified_data)
        )

     
        combined_summary = self._combine_reports(meeting_analysis, strategy_analysis)
      
        tags = await self._generate_tags(combined_summary)

        self.logger.info("Analysis completed successfully")
        
        return SummarizerResponse(
            summary=combined_summary,
            tags=tags
        )

    async def _analyze_meeting(self, unified_data: Dict[str, Any]) -> str:
        prompt_data = self._prepare_prompt_data(unified_data)
        messages = eval(PromptFacade.get_prompt("meet_analyzer_post", **prompt_data))
        
        result = await self.completion(
            "gpt-4.1",
            messages=messages,
            temperature=0.1,
            max_tokens=16000
        )
        
        self.logger.info("Meeting analysis completed")
        return result.choices[0].message.content

    async def _analyze_strategy(self, unified_data: Dict[str, Any]) -> str:
        prompt_data = self._prepare_prompt_data(unified_data)
        messages = eval(PromptFacade.get_prompt("strategy_planner_post", **prompt_data))
        
        result = await self.completion(
            "gpt-4.1",
            messages=messages,
            temperature=0.1,
            max_tokens=16000
        )
        
        self.logger.info("Strategy analysis completed")
        return result.choices[0].message.content

    async def _generate_tags(self, text: str) -> list[str]:
        messages = [
            {
                "role": "system",
                "content": "Extract 5-10 key topics from the financial report. Return ONLY comma-separated keywords in lowercase."
            },
            {
                "role": "user",
                "content": f"Extract tags:\n\n{text[:2000]}"
            }
        ]
        
        result = await self.completion(
            "gpt-4.1",
            messages=messages,
            temperature=0.1,
            max_tokens=100
        )
        
        tags_text = result.choices[0].message.content.strip()
        tags = [tag.strip() for tag in tags_text.split(',')]
        
        self.logger.info(f"Generated {len(tags)} tags")
        return tags[:10]

    def _combine_reports(self, meeting_analysis: str, strategy_analysis: str) -> str:
        current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return (
            "# COMPREHENSIVE FINANCIAL ADVISOR REPORT\n\n"
            "## MEETING ANALYSIS\n"
            f"{meeting_analysis}\n\n"
            "---\n\n"
            "## STRATEGY & PRODUCT ANALYSIS\n"
            f"{strategy_analysis}\n\n"
            "---\n\n"
            f"*Report generated: {current_datetime}*"
        )

    def _prepare_prompt_data(self, unified_data: Dict[str, Any]) -> Dict[str, str]:
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        return {
            "selected_profile": unified_data["selected_profile"],
            "products": unified_data["products"],
            "transcript": unified_data["transcript"],
            "current_date": current_date
        }