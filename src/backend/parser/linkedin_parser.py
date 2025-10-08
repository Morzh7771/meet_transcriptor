import requests
from openai import OpenAI
from src.backend.utils.configs import Config
from src.backend.core.baseFacade import BaseFacade
from src.backend.parser.scraperFacade import ScraperFacade
from src.backend.parser.searcherFacade import SearcherFacade
from src.backend.prompts.promptFacade import PromptFacade
from src.backend.utils.logger import CustomLog
from typing import Dict, List
import asyncio



class LinkedInParser(BaseFacade):
    def __init__(self):
        self.logger = CustomLog()
        self.configs = Config.load_config()
        self.generect_url = "https://api.generect.com/api/linkedin/leads/by_link/"
        self.headers = {
            "Authorization": f"Token {self.configs.linkedinparser.API_KEY.get_secret_value()}",
            "Content-Type": "application/json"
        }
        self.client = OpenAI(api_key=self.configs.openai.API_KEY.get_secret_value())
        self.model = "gpt-4o-mini"

    def _fetch_user_data(self, user_link: str) -> dict:
        payload = {
            "comments": False,
            "inexact_company": False,
            "people_also_viewed": False,
            "posts": False,
            "url": user_link
        }

        try:
            response = requests.post(self.generect_url, headers=self.headers, json=payload, timeout=20)
            response.raise_for_status()
            data = response.json()
            lead = data.get("lead") or {}
            return lead
        except Exception as e:
            self.logger.error(f"Error fetching user data for {user_link}: {e}")
            return {}

    def _parse_companies(self, jobs: list) -> list:
        if not jobs or not isinstance(jobs, list):
            self.logger.warning("Jobs data is empty or invalid")
            return []
        
        companies = [job.get("company_name") for job in jobs if isinstance(job, dict) and job.get("company_name")]
        
        if not companies:
            self.logger.info("No valid company names found in jobs")
        
        return companies

    def _parse_educations(self, educations: list) -> list:
        if not isinstance(educations, list) or not educations:
            self.logger.warning("No education data found or invalid format")
            return []

        education_list = []
        for edu in educations:
            if not isinstance(edu, dict):
                continue

            started_on = edu.get("started_on") or {}
            ended_on = edu.get("ended_on") or {}

            education_list.append({
                "university": edu.get("university_name"),
                "degree": edu.get("degree"),
                "field": edu.get("fields_of_study"),
                "start": started_on.get("year"),
                "end": ended_on.get("year")
            })
        return education_list

    def normalize_openai_messages(self, messages: list) -> list:
        normalized = []
        for msg in messages:
            normalized_msg = {"role": msg["role"]}
            
            content = msg.get("content")
            
            if isinstance(content, dict):
                if "text" in content:
                    normalized_msg["content"] = content["text"]
                elif "type" in content and content["type"] == "text":
                    normalized_msg["content"] = content.get("text", "")
                else:
                    normalized_msg["content"] = str(content)
            else:
                normalized_msg["content"] = content
                
            normalized.append(normalized_msg)
        
        return normalized

    async def _get_info_about_company(self, company_name: str) -> Dict:
        query = f"Latest news about {company_name}"
        self.logger.info(f"Searching for: {query}")
        
        try:
            async with SearcherFacade(top_k=3, filter_results=False) as searcher:
                _, search_results, engine, search_time, _ = await searcher.search(query)
            
            self.logger.info(f"Found {len(search_results)} results in {search_time:.2f}s")
            
            if not search_results:
                self.logger.warning(f"No search results for {company_name}")
                return await self._describe_company(company_name)
            
            scraper = ScraperFacade(enable_content_filtering=True)
            urls = [result.url for result in search_results]
            scraping_results = await scraper.scrape_urls(urls, max_concurrent=3)
            
            scraped_content = []
            for i, scraping_result in enumerate(scraping_results):
                if scraping_result.success and scraping_result.text:
                    sentences = [s.strip() + '.' for s in scraping_result.text.split('.') if s.strip()]
                    summary = ' '.join(sentences[:2]) if len(sentences) >= 2 else scraping_result.text[:200]
                    
                    scraped_content.append({
                        'title': search_results[i].title,
                        'url': scraping_result.url,
                        'summary': summary,
                        'full_text': scraping_result.text[:1500]
                    })
            
            if not scraped_content:
                self.logger.warning(f"Failed to scrape content for {company_name}")
                return await self._describe_company(company_name)
                
            
            description = await self._describe_company_with_context(company_name, scraped_content)
            
            return description
            
            
        except Exception as e:
            self.logger.error(f"Error in _get_info_about_company for {company_name}: {str(e)}")
            return await self._describe_company(company_name)
            

    async def _describe_company_with_context(self, company_name: str, scraped_content: List[Dict]) -> str:
        context_parts = []
        for i, item in enumerate(scraped_content, 1):
            context_parts.append(f"Source {i} - {item['title']}:\n{item['summary']}")
        
        context = "\n\n".join(context_parts)

        company_with_context_description = eval(PromptFacade.get_prompt(
            "company_with_context_description",
            company_name=company_name,
            context=context
        ))

        company_with_context_description = self.normalize_openai_messages(company_with_context_description)
        def _call():
            return self.client.chat.completions.create(
                model=self.model,
                messages=company_with_context_description,
                max_tokens=700,
                temperature=0.2,
            )
        try:
            response = await asyncio.to_thread(_call)
            return response.choices[0].message.content.strip()

        except Exception as e:
            self.logger.error(f"OpenAI API error with context: {e}")
            return scraped_content[0]['summary'] if scraped_content else self._describe_company(company_name)

    async def _describe_company(self, company_name: str):
        if not company_name:
            return None

        company_description = eval(PromptFacade.get_prompt(
            "company_description",
            company_name=company_name
        ))

        company_description = self.normalize_openai_messages(company_description)
        def _call():
            return self.client.chat.completions.create(
                model=self.model,
                messages=company_description,
                max_tokens=400,
                temperature=0.2,
            )
        
        try:
            response = await asyncio.to_thread(_call)
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            return None

    async def parse_user(self, user_link: str) -> dict:
        lead = self._fetch_user_data(user_link)

        jobs = lead.get("jobs") or []
        educations = lead.get("educations") or []

        companies = self._parse_companies(jobs)
        educations = self._parse_educations(educations)

        company_data = []
        if companies:
            for company in companies:
                try:
                    description = await self._get_info_about_company(company)
                except Exception as e:
                    self.logger.error(f"Error getting info for {company}: {e}")
                    description = None
                company_data.append({
                    "name": company,
                    "description": description
                })
        else:
            self.logger.info(f"No companies to process for {user_link}")

        return {
            "companies": company_data,
            "educations": educations
        }