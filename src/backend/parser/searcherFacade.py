# Libraries for search engines
from googlesearch import search as search_google_scraper
from langchain_google_community import GoogleSearchAPIWrapper

# General libraries
import asyncio
import aiohttp
import time
from typing import List, Dict, Any, Optional, Literal

# Local imports
from src.backend.parser.FilterFacade import Filter
from src.backend.parser.searcher import *
from src.backend.core.baseFacade import BaseFacade
from src.backend.utils.logger import CustomLog

logger = CustomLog()  # Create an instance of CustomLog


class SearcherFacade(BaseFacade):
    def __new__(cls, *args, **kwargs):
        return super(BaseFacade, cls).__new__(cls)

    def __init__(
        self,
        top_k: int = 10,
        time_range: Literal["all", "hour", "day", "week", "month", "year"] = "all",
        filter_results: bool = False,
    ):
        super().__init__()
        self.session = None
        self.filter = Filter()
        self.top_k = top_k
        self.time_range = time_range
        self.filter_results = filter_results
        self.last_request_time = 0
        self.min_request_interval = 2  # Minimum seconds between requests
        self.max_retries = 3
        self.current_retry = 0

    async def __aenter__(self):
        logger.info("Creating aiohttp session")
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            logger.info("Closing aiohttp session")
            await self.session.close()
            self.session = None

    async def _wait_for_rate_limit(self):
        """Wait if necessary to respect rate limits"""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time
        if time_since_last_request < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last_request
            await asyncio.sleep(wait_time)
        self.last_request_time = time.time()

    async def google_scraper_search(
        self,
        query: str,
        top_k: int = 10,
        time_range: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        await self._wait_for_rate_limit()
        time_range = self.parse_time_range(time_range)
        if time_range:
            query = query + f" tbs=qdr:{time_range}"

        try:
            # Run the synchronous search function in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: search_google_scraper(query, num_results=top_k, advanced=True),
            )

            # Convert generator to list of dictionaries
            result_list = [
                {
                    "title": result.title,
                    "url": result.url,
                    "description": result.description,
                }
                for result in results
            ]
            self.current_retry = 0  # Reset retry counter on success
            return result_list
        except Exception as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                self.current_retry += 1
                if self.current_retry <= self.max_retries:
                    wait_time = self.min_request_interval * (
                        2**self.current_retry
                    )  # Exponential backoff
                    logger.warning(
                        f"Rate limit hit. Waiting {wait_time} seconds before retry {self.current_retry}/{self.max_retries}"
                    )
                    await asyncio.sleep(wait_time)
                    return await self.google_scraper_search(query, top_k, time_range)
            raise

    @staticmethod
    def parse_time_range(time_range):
        if time_range == "all":
            return None
        elif time_range == "hour":
            return "h"
        elif time_range == "day":
            return "d"
        elif time_range == "week":
            return "w"
        elif time_range == "month":
            return "m"
        elif time_range == "year":
            return "y"
        else:
            return None

    async def google_api_search(
        self,
        query: str,
    ) -> List[Dict[str, Any]]:
        time_range = self.parse_time_range(self.time_range)
        if time_range:
            query = query + f" tbs=qdr:{time_range}"
            logger.info(f"Modified query with date filter: '{query}'")

        search_google = GoogleSearchAPIWrapper(
            google_cse_id=self.configs.searcher.SEARCH_ENGINE_ID,
            google_api_key=self.configs.searcher.API_KEY.get_secret_value(),
        )

        logger.info(f"Running Google search with query: '{query}'")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: search_google.results(query, self.top_k)
        )
        return result

    # @retry(
    #     retry=retry_if_exception_type((Exception)),  # Retry on any exception
    #     wait=wait_exponential(
    #         multiplier=30,
    #         max=3600,
    #     ),
    #     stop=stop_after_attempt(10),
    #     before_sleep=lambda retry_state: logger.warning(
    #         f"Search failed with error: {retry_state.outcome.exception()}. Retrying in {retry_state.next_action.sleep} seconds..."
    #     ),
    # )
    async def search(self, query: str):
        # Get the start time
        start_time = time.time()
        results = []
        engine = "google_scraper"

        try:
            results = await self.google_api_search(query)
            engine = "google_api"
            elapsed_time = time.time() - start_time
            logger.info(f"Results: {results}")
            # organize results
            search_results = [
                SearchResult(
                    title=result.get("title", ""),
                    url=result.get("link", ""),
                    description=result.get("snippet", ""),
                )
                for result in results
                if isinstance(result, dict) and "Result" not in result
            ]
            logger.info(
                f"Retrieved {len(search_results)} results in {elapsed_time} seconds"
            )
        except Exception as e:
            logger.warning(f"Error getting results from google api: {str(e)}")
            raise

        if self.filter_results:
            logger.info("Filtering results")
            logger.info(f"Query: {query}")
            logger.info(f"Search results: {search_results}")
            filtered_response = await self.filter.filter_urls(
                FilterInputLLM(query=query, results=search_results)
            )
            filtered_results = filtered_response.results
            time_to_filter = filtered_response.time_taken
            logger.info(
                f"Filtered {len(filtered_results)} results in {time_to_filter} seconds"
            )
        else:
            filtered_results = search_results
            time_to_filter = 0

        return query, filtered_results, engine, elapsed_time, time_to_filter
