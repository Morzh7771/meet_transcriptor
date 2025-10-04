import time
from typing import Any, Dict, List
from src.backend.utils.configs import Config
from src.backend.core.baseFacade import BaseFacade
from src.backend.prompts.promptFacade import PromptFacade

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
from src.backend.parser.searcher import (
    SearchResult,
    FilterOutputLLM,
    FilterInputLLM,
    ValidatedResultsLLM,
)

import asyncio
from math import ceil

from src.backend.utils.logger import CustomLog

logger = CustomLog()  # Create an instance of CustomLog


class Filter(BaseFacade):
    config = Config.load_config()

    def __init__(self):
        super().__init__()

    def organize_results(self, response: SearchResult, results: SearchResult):
        """
        Organize the results based on the query and the results.
        """

        # Add the description and title to the results for each url that we had
        response_llm = response.model_dump()
        results_search = [result.model_dump() for result in results]
        for result in response_llm["results"]:
            for res in results_search:
                if res["url"] == result["url"]:
                    result["description"] = res["description"]
                    result["title"] = res["title"]
                    break

        organized_results = [
            SearchResult(**result) for result in response_llm["results"]
        ]
        return organized_results

    @retry(
        retry=retry_if_exception_type((Exception)), 
        wait=wait_exponential(
            multiplier=config.filter.exp_multiplier,
            max=config.filter.exp_max_wait_time,
        ),
        stop=stop_after_attempt(config.filter.exp_max_retries),
        before_sleep=lambda retry_state: logger.warning(
            f"Filtering failed. Retrying in {retry_state.next_action.sleep} seconds..."
        ),
    )
    async def filter_urls(self, filter_input: FilterInputLLM):
        """
        Validate the search results based on the query and the results.
        """
        # Filter the results in batches

        num_batches = ceil(len(filter_input.results) / self.configs.filter.batch_size)
        prompts = []
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.configs.filter.batch_size
            end_idx = min(
                start_idx + self.configs.filter.batch_size, len(filter_input.results)
            )

            batch_urls = filter_input.results[start_idx:end_idx]
            search_validation_prompt = eval(PromptFacade.get_prompt(
                "search_validation",
                QUERY=filter_input.query,
                SEARCH_RESULTS=batch_urls
            ))
            # Get the prompt
            # prompt = [
            #     {
            #         "role": "user",
            #         "content": self.prompt_facade.get_prompt(
            #             "search_validation",
            #             QUERY=filter_input.query,
            #             SEARCH_RESULTS=batch_urls,
            #         ),
            #     }
            # ]
            prompts.append(search_validation_prompt)

        time_start = time.time()
        responses = await asyncio.gather(
            *[
                self.client.chat.completions.create(
                    messages=prompt,
                    response_model=ValidatedResultsLLM,
                    model=self.configs.filter.model_name,
                    temperature=0.3,
                )
                for prompt in prompts
            ]
        )
        logger.info(f"Responses: {responses}")
        new_results = []
        for response in responses:
            new_results_url = self.organize_results(response, filter_input.results)
            new_results.extend(new_results_url)

        logger.info(f"New results: {new_results}")

        final_results = FilterOutputLLM(
            results=new_results, time_taken=time.time() - time_start
        )
        logger.info(f"Final results: {final_results}")
        return final_results

    async def filter_search_results_in_batches(
        self,
        queries: List[str],
        results: List[List[Dict[str, Any]]],
        batch_size: int = 10,
    ):
        """
        Validate search results in concurrent batches to improve processing efficiency.

        :param query: The user's search query
        :param results: The list of search results to validate
        :param batch_size: Number of results to process in each batch
        :return: A consolidated ValidatedResults object
        """
        validated_results = []
        total_items = len(queries)
        num_batches = ceil(total_items / batch_size)

        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_items)

            batch_queries = queries[start_idx:end_idx]
            batch_results = results[start_idx:end_idx]

            # Process this batch concurrently
            batch_tasks = [
                self.filter_urls(FilterInputLLM(query=query, results=res))
                for query, res in zip(batch_queries, batch_results)
            ]
            batch_validated_results = await asyncio.gather(*batch_tasks)
            validated_results.extend(batch_validated_results)

        return validated_results
