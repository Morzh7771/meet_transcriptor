from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, HttpUrl, field_validator


class SearchResult(BaseModel):
    title: str = Field(..., description="Title of the search result")
    url: str = Field(..., description="URL of the search result")
    description: str = Field(default="", description="Description/snippet of the search result")
    
    @field_validator('url')
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Example Article Title",
                "url": "https://example.com/article",
                "description": "This is a brief description of the article content..."
            }
        }


class FilterInputLLM(BaseModel):
    query: str = Field(..., description="The original search query")
    results: List[SearchResult] = Field(..., description="List of search results to filter")
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()
    
    @field_validator('results')
    @classmethod
    def validate_results(cls, v: List[SearchResult]) -> List[SearchResult]:
        if not v:
            raise ValueError("Results list cannot be empty")
        return v


class ValidatedResultsLLM(BaseModel):
    results: List[SearchResult] = Field(
        default_factory=list,
        description="List of validated search results"
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Optional reasoning for the filtering decisions"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "title": "Relevant Article",
                        "url": "https://example.com/relevant",
                        "description": "This article is relevant to the query..."
                    }
                ],
                "reasoning": "Filtered out 3 results that were not relevant to the search query."
            }
        }


class FilterOutputLLM(BaseModel):
    results: List[SearchResult] = Field(
        default_factory=list,
        description="List of filtered search results"
    )
    time_taken: float = Field(..., description="Time taken to filter results in seconds")
    
    @field_validator('time_taken')
    @classmethod
    def validate_time(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Time taken cannot be negative")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "results": [
                    {
                        "title": "Filtered Result",
                        "url": "https://example.com/result",
                        "description": "This result passed the filter..."
                    }
                ],
                "time_taken": 1.23
            }
        }


class SearchQuery(BaseModel):
    query: str = Field(..., description="The search query string")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results to return")
    time_range: str = Field(
        default="all",
        description="Time range for search results",
        pattern="^(all|hour|day|week|month|year)$"
    )
    
    @field_validator('query')
    @classmethod
    def validate_query(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


class SearchResponse(BaseModel):
    query: str = Field(..., description="The original search query")
    results: List[SearchResult] = Field(
        default_factory=list,
        description="List of search results"
    )
    engine: str = Field(..., description="Search engine used (e.g., 'google_api', 'google_scraper')")
    search_time: float = Field(..., description="Time taken for the search in seconds")
    filter_time: float = Field(default=0.0, description="Time taken for filtering in seconds")
    total_results: int = Field(..., description="Total number of results returned")
    
    @field_validator('search_time', 'filter_time')
    @classmethod
    def validate_time(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Time values cannot be negative")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "machine learning",
                "results": [
                    {
                        "title": "Introduction to ML",
                        "url": "https://example.com/ml",
                        "description": "A comprehensive guide to machine learning..."
                    }
                ],
                "engine": "google_api",
                "search_time": 0.85,
                "filter_time": 1.23,
                "total_results": 10
            }
        }


class ScrapingRequest(BaseModel):
    urls: List[str] = Field(..., description="List of URLs to scrape")
    max_concurrent: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of concurrent scraping operations"
    )
    enable_content_filtering: bool = Field(
        default=True,
        description="Whether to enable advanced content filtering"
    )
    
    @field_validator('urls')
    @classmethod
    def validate_urls(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("URLs list cannot be empty")
        
        cleaned_urls = []
        for url in v:
            url = url.strip()
            if not url:
                continue
            if not (url.startswith('http://') or url.startswith('https://')):
                raise ValueError(f"Invalid URL format: {url}")
            cleaned_urls.append(url)
        
        if not cleaned_urls:
            raise ValueError("No valid URLs provided")
        
        return cleaned_urls


class ScrapedContent(BaseModel):
    url: str = Field(..., description="The scraped URL")
    success: bool = Field(..., description="Whether scraping was successful")
    markdown: str = Field(default="", description="Markdown content")
    text: str = Field(default="", description="Plain text content")
    html: str = Field(default="", description="HTML content")
    error_message: Optional[str] = Field(default=None, description="Error message if scraping failed")
    error_type: Optional[str] = Field(default=None, description="Type of error encountered")
    token_count: int = Field(default=0, ge=0, description="Number of tokens in the content")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.com/article",
                "success": True,
                "markdown": "# Article Title\n\nArticle content...",
                "text": "Article Title\n\nArticle content...",
                "html": "<html>...</html>",
                "error_message": None,
                "error_type": None,
                "token_count": 1250
            }
        }


class DeepScrapeRequest(BaseModel):
    urls: List[str] = Field(..., description="List of starting URLs")
    max_depth: int = Field(default=2, ge=1, le=5, description="Maximum depth for recursive scraping")
    max_pages: int = Field(default=50, ge=1, le=500, description="Maximum number of pages to scrape")
    max_tokens: Optional[int] = Field(
        default=None,
        ge=1000,
        description="Maximum total tokens to collect"
    )
    max_concurrent: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of concurrent operations"
    )
    
    @field_validator('urls')
    @classmethod
    def validate_urls(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("URLs list cannot be empty")
        return [url.strip() for url in v if url.strip()]


class DeepScrapeResponse(BaseModel):
    pages: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of scraped pages with metadata"
    )
    combined_content: str = Field(default="", description="Combined content from all pages")
    total_time: float = Field(..., description="Total time taken for the operation")
    pages_scraped: int = Field(..., ge=0, description="Number of pages successfully scraped")
    total_tokens: int = Field(default=0, ge=0, description="Total tokens collected")
    
    @field_validator('total_time')
    @classmethod
    def validate_time(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Time cannot be negative")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "pages": [
                    {
                        "url": "https://example.com/page1",
                        "content": "Page content...",
                        "token_count": 500,
                        "depth": 0,
                        "success": True
                    }
                ],
                "combined_content": "Combined content from all pages...",
                "total_time": 15.67,
                "pages_scraped": 10,
                "total_tokens": 5000
            }
        }


class BatchFilterRequest(BaseModel):
    queries: List[str] = Field(..., description="List of queries")
    results: List[List[Dict[str, Any]]] = Field(..., description="List of result lists corresponding to queries")
    batch_size: int = Field(default=10, ge=1, le=50, description="Batch size for processing")
    
    @field_validator('queries', 'results')
    @classmethod
    def validate_not_empty(cls, v: List) -> List:
        if not v:
            raise ValueError("List cannot be empty")
        return v
    
    @field_validator('results')
    @classmethod
    def validate_results_match_queries(cls, v: List[List[Dict]], info) -> List[List[Dict]]:
        queries = info.data.get('queries', [])
        if len(v) != len(queries):
            raise ValueError("Results list must have the same length as queries list")
        return v