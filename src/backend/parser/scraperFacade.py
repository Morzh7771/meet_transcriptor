from pickle import FALSE
import re
import time
import asyncio
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Optional, Union
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from src.backend.utils.configs import Config
from src.backend.utils.logger import CustomLog
import tiktoken
from bs4 import BeautifulSoup

log = CustomLog()


class ErrorType(Enum):
    TIMEOUT = "timeout"
    NETWORK = "network" 
    UNREACHABLE = "unreachable"
    RATE_LIMIT = "rate_limit"
    OTHER = "other"


@dataclass
class ScrapingResult:
    url: str
    success: bool
    markdown: str = ""
    text: str = ""
    html: str = ""
    links: Dict[str, List] = None
    error_message: str = ""
    error_type: Optional[ErrorType] = None
    
    def __post_init__(self):
        if self.links is None:
            self.links = {"internal": [], "external": []}


class ErrorClassifier:
    """Centralized error classification logic."""
    
    ERROR_PATTERNS = {
        ErrorType.UNREACHABLE: [
            "net::err_name_not_resolved",
            "net::err_connection_refused", 
            "net::err_address_unreachable",
            "net::err_host_unreachable",
            "dns_error",
            "name_not_resolved",
            "host not found",
        ],
        ErrorType.TIMEOUT: [
            "timeout",
            "timed out", 
            "navigation timeout",
            "60000ms exceeded",
        ],
        ErrorType.NETWORK: [
            "network",
            "connection",
            "ssl",
            "tls",
            "certificate",
        ],
        ErrorType.RATE_LIMIT: [
            "rate limit",
            "too many requests",
            "429",
        ]
    }
    
    @classmethod
    def classify_error(cls, error: Exception) -> ErrorType:
        error_str = str(error).lower()
        
        for error_type, patterns in cls.ERROR_PATTERNS.items():
            if any(pattern in error_str for pattern in patterns):
                return error_type
                
        return ErrorType.OTHER
    
    @classmethod 
    def should_retry(cls, error_type: ErrorType) -> bool:
        """Determine if error type should be retried."""
        return error_type not in {ErrorType.UNREACHABLE}


class RetryStrategy:
    """Unified retry strategy with configurable behavior."""
    
    def __init__(self):
        self.config = Config.load_config()
        
    def get_retry_decorator(self, is_doi: bool = False, error_type: ErrorType = None):
        """Get appropriate retry decorator based on context."""
        base_delay = self.config.scraper.base_delay
        max_delay = self.config.scraper.max_delay
        max_retries = self.config.scraper.max_retries
        
        # Adjust for DOI URLs
        if is_doi:
            base_delay *= 2
            max_delay *= 1.5
            
        # Adjust for specific error types  
        if error_type == ErrorType.TIMEOUT:
            base_delay *= 3
            max_retries += self.config.scraper.timeout_extra_retries
            
        return retry(
            retry=retry_if_exception_type((Exception,)),
            wait=wait_exponential(multiplier=2, min=base_delay, max=max_delay),
            stop=stop_after_attempt(max_retries),
        )


class ScraperFacade:
    """Optimized scraper with advanced content filtering."""
    
    def __init__(self, enable_content_filtering=True):
        self.config = Config.load_config().scraper
        self.enable_filtering = enable_content_filtering
        self.excluded_tags = [
                    # Navigation and UI elements
                    '.navigation', '.nav', '.menu', '.sidebar', '.header', '.footer',
                    '.navbar', '.topbar', '.bottombar', '.main-nav', '.site-nav',
                    
                    # Advertisements and promotions
                    '.advertisement', '.ad', '.ads', '.promo', '.banner', '.sponsored',
                    '[class*="ad-"]', '[id*="ad-"]', '.google-ads', '.adsense',
                    
                    # Citation and reference metadata (keep content, remove UI)
                    '.citation-links', '.references-links', '.crossref-links',
                    '.citation-tools', '.reference-tools', '.doi-links',
                    
                    # Subscribe/login/paywall elements
                    '.login', '.subscribe', '.paywall', '.membership', '.signup',
                    '.register', '.signin', '.account', '.user-menu',
                    
                    # Social media and sharing
                    '.social', '.share', '.sharing-buttons', '.social-media',
                    '.twitter', '.facebook', '.linkedin', '.share-tools',
                    
                    # Breadcrumbs and pagination
                    '.breadcrumb', '.breadcrumbs', '.pagination', '.page-nav',
                    '.prev-next', '.page-numbers', '.pager',
                    
                    # Sidebars and metadata panels
                    '.author-info-sidebar', '.article-metadata-sidebar',
                    '.related-content', '.also-read', '.recommended',
                    
                    # Journal-specific selectors
                    'div[class*="sidebar"]', 'div[class*="navigation"]',
                    'div[class*="menu"]', 'section[class*="nav"]',
                    '.journal-header', '.journal-footer', '.journal-nav',
                    '.article-tools', '.article-nav', '.related-articles',
                    
                    # Comments and discussion
                    '.comments', '.discussion', '.comment-section',
                    
                    # Search and filters
                    '.search', '.filters', '.sort-options', '.search-box'
                ]
        
        # Basic browser configuration
        self.browser_config = BrowserConfig(headless=self.config.headless, verbose=False)
        
        # Advanced content filtering configuration
        if enable_content_filtering:
            self.run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                stream=False,
                remove_overlay_elements=True,
                process_iframes=True,
                
                # CONTENT FILTERING - Remove unwanted HTML elements
                excluded_tags=['nav', 'header', 'footer', 'aside', 'script', 'style', 'noscript'],
                
                excluded_selector=", ".join(self.excluded_tags),
                
                
                word_count_threshold=10,
                exclude_external_links=FALSE,
                exclude_social_media_links=True,
                
                # For academic sites, focus on main content
            )
        else:
            # Minimal filtering - only remove scripts and styles
            self.run_config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                stream=False,
                remove_overlay_elements=True,
                process_iframes=True,
                excluded_tags=['script', 'style', 'noscript'],
            )
        
        self.retry_strategy = RetryStrategy()
        self.error_classifier = ErrorClassifier()
        
        # Initialize tiktoken tokenizer
        self._tokenizer = tiktoken.get_encoding("cl100k_base")
        
    def _is_doi_url(self, url: str) -> bool:
        return "doi.org" in url.lower()
        
    def _create_failed_result(self, url: str, error: Exception) -> ScrapingResult:
        """Create a standardized failed result."""
        error_type = self.error_classifier.classify_error(error)
        return ScrapingResult(
            url=url,
            success=False,
            error_message=str(error),
            error_type=error_type
        )

    def _clean_scraped_content(self, content: str, url: str) -> str:
        """Post-process scraped content to remove unwanted elements."""
        if not content or not self.enable_filtering:
            return content
        
        lines = content.split('\n')
        cleaned_lines = []
        
        # Patterns to filter out
        unwanted_patterns = [
            # Navigation and UI
            r'^(Skip to|Navigate to|Go to|Jump to)',
            r'^(Menu|Navigation|Breadcrumb)',
            r'^(Sign in|Login|Register|Subscribe|Donate|Join)',
            r'^(Search|Advanced Search|Quick Search)',
            r'^\[Advertisement\]',
            r'^(Advertisement|Ad disclaimer)',
            
            # Citation and reference links (keep content, remove navigation)
            r'^\[Go to Citation\]',
            r'^\[Crossref\]',
            r'^\[PubMed\]',
            r'^\[Google Scholar\]',
            r'^Open in Viewer',
            r'^View all metrics',
            r'^Track Citations',
            r'^Add to favorites',
            
            # Social and sharing
            r'^(Share|Tweet|Facebook|LinkedIn|Email|Print)',
            r'^(Save|Export|Download|PDF)',
            
            # Journal-specific navigation
            r'^(Current Issue|Archive|Journal Information)',
            r'^(For Authors|For Reviewers|For Subscribers)',
            r'^(Submit|Publish|Information)',
            r'^(About|Contact|Help|Support)',
            
            # Metrics and metadata navigation
            r'^(Metrics|Citations|Show shopping cart)',
            r'^[0-9,]+\s*(Downloads?|Citations?|Views?)\s*$',
            
            # Generic link text and UI elements
            r'^\[\s*\]$',  # Empty links
            r'^[0-9,]+$',  # Just numbers (often metrics/navigation)
            r'^[\s\-•·]+$',  # Just punctuation/spaces
            r'^\.\.\.$',   # Ellipsis
        ]
        
        # Special handling for academic papers
        if any(domain in url.lower() for domain in ['doi.org', 'pubmed', 'arxiv', 'springer', 'wiley', 'elsevier', 'ahajournals']):
            unwanted_patterns.extend([
                r'^(Volume \d+|Number \d+|Issue \d+)',
                r'^(Originally Published|Published online|Received|Accepted)',
                r'^(PDF/EPUB|Full Text|Download|View PDF)',
                r'^(Author Info|Affiliations|Correspondence)',
                r'^\d{4}-\d{2}-\d{2}$',  # Dates
                r'^https?://doi\.org/',  # DOI links
                r'^doi:\s*10\.',  # DOI identifiers
                r'^PMID:\s*\d+',  # PubMed IDs
            ])
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Skip lines matching unwanted patterns
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in unwanted_patterns):
                continue
                
            # Skip very short lines that are likely navigation (but keep headings)
            if len(line) < 10 and not re.match(r'^[A-Z][a-z]+', line) and not line.isupper():
                continue
                
            # Skip lines that are mostly special characters or numbers
            alpha_chars = re.sub(r'[^a-zA-Z]', '', line)
            if len(alpha_chars) < len(line) * 0.3 and len(line) > 5:
                continue
                
            cleaned_lines.append(line)
        
        # Join lines and clean up extra whitespace
        cleaned_content = '\n'.join(cleaned_lines)
        
        # Remove excessive newlines
        cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
        
        return cleaned_content.strip()

    def _extract_main_content(self, html_content: str, url: str) -> str:
        """Extract main content using BeautifulSoup if available."""
            
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements completely
            for element in soup.find_all(['nav', 'header', 'footer', 'aside', 'script', 'style']):
                element.decompose()
            
            # Remove elements by class/id patterns
            unwanted_selectors = [
                '[class*="nav"]', '[class*="menu"]', '[class*="sidebar"]',
                '[class*="ad"]', '[class*="advertisement"]', '[class*="banner"]',
                '[id*="nav"]', '[id*="menu"]', '[id*="sidebar"]',
                '[class*="share"]', '[class*="social"]'
            ]
            
            for selector in unwanted_selectors:
                for element in soup.select(selector):
                    element.decompose()
            
            # Try to find main content area
            main_content = None
            content_selectors = [
                'main', 'article', '[role="main"]',
                '.main-content', '.content', '.article-content',
                '.paper-content', '.full-text', '.article-body',
                '.post-content', '.entry-content'
            ]
            
            for selector in content_selectors:
                main_content = soup.select_one(selector)
                if main_content:
                    break
            
            if main_content:
                return main_content.get_text(separator='\n', strip=True)
            else:
                # Fallback: use body content
                body = soup.find('body')
                if body:
                    return body.get_text(separator='\n', strip=True)
                return soup.get_text(separator='\n', strip=True)
                
        except Exception:
            # If BeautifulSoup fails, return original content
            return html_content
        
    async def _scrape_single_url(self, url: str) -> ScrapingResult:
        """Scrape a single URL with appropriate configuration."""
        try:
            log.info(f"Starting scrape for URL: {url}")
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result_raw = await crawler.arun(url=url, config=self.run_config)

                if not hasattr(result_raw, "_results") or not result_raw._results:
                    return ScrapingResult(
                        url=url,
                        success=False,
                        error_message="No results returned from crawler",
                        error_type=ErrorType.OTHER
                    )

                result = result_raw._results[0]

                if result.success:
                    # Clean the content
                    cleaned_markdown = self._clean_scraped_content(result.markdown, url)
                    cleaned_text = self._clean_scraped_content(self._extract_main_content(result.html, url), url)
                    
                    # Additional content extraction from HTML if markdown is poor
                    if len(cleaned_markdown) < 500 and result.html:
                        extracted_content = self._extract_main_content(result.html, url)
                        if len(extracted_content) > len(cleaned_markdown):
                            cleaned_markdown = self._clean_scraped_content(extracted_content, url)
                    
                    return ScrapingResult(
                        url=result.url,
                        success=True,
                        markdown=cleaned_markdown,
                        text=cleaned_text,
                        html=result.html, 
                        links=getattr(result, 'links', {"internal": [], "external": []}),
                    )
                else:

                    error_msg = getattr(result, 'error_message', None) or \
                           getattr(result, 'error', None) or \
                           'Scraping failed - no error message provided'
                
                    log.warning(f"Scraping failed for {url}: {error_msg}")

                    return ScrapingResult(
                        url=url,
                        success=False,
                        error_message=str(error_msg),
                        error_type=self.error_classifier.classify_error(Exception(error_msg))
                    )
                
        except Exception as e:
            log.error(f"Exception during scraping {url}: {type(e).__name__}: {str(e)}")
            return self._create_failed_result(url, e)
    
    async def _scrape_with_retry(self, url: str) -> ScrapingResult:
        """Scrape URL with intelligent retry logic."""
        is_doi = self._is_doi_url(url)
        
        # Try initial scrape
        result = await self._scrape_single_url(url)
        
        if result.success:
            return result
            
        # Check if we should retry
        if not self.error_classifier.should_retry(result.error_type):
            return result
            
        # Apply appropriate retry strategy
        retry_decorator = self.retry_strategy.get_retry_decorator(
            is_doi=is_doi, 
            error_type=result.error_type
        )
        
        try:
            return await retry_decorator(self._scrape_single_url)(url)
        except Exception as e:
            return self._create_failed_result(url, e)
    
    async def scrape_urls(self, urls: List[str], max_concurrent: int = 5) -> List[ScrapingResult]:
        if not urls:
            return []
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def scrape_with_semaphore(url: str) -> ScrapingResult:
            async with semaphore:
                # Small delay to be respectful to servers
                await asyncio.sleep(0.1)
                return await self._scrape_with_retry(url)
        
        print(f"Starting concurrent scraping of {len(urls)} URLs (max {max_concurrent} concurrent)")
        
        # Create tasks for all URLs
        tasks = [scrape_with_semaphore(url) for url in urls]
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Handle exceptions that escaped the inner error handling
                failed_result = self._create_failed_result(urls[i], result)
                processed_results.append(failed_result)
            else:
                processed_results.append(result)
        
        successful = sum(1 for r in processed_results if r.success)
        print(f"Completed: {successful}/{len(urls)} URLs scraped successfully")
        
        return processed_results
    
    def _calculate_token_count(self, text: str) -> int:
        """Calculate token count using tiktoken."""
        if not text:
            return 0
        try:
            return len(self._tokenizer.encode(text))
        except Exception:
            return len(text) // 4
    
    async def deep_scrape(self, urls: List[str], max_depth: int = 2, 
                         max_pages: int = 50, max_tokens: int = None) -> Dict:
        start_time = time.time()
        
        all_pages = []
        scraped_urls = set()
        current_urls = urls.copy()
        
        for depth in range(max_depth):
            if not current_urls or len(scraped_urls) >= max_pages:
                break
                
            # Limit batch size
            batch_size = min(len(current_urls), max_pages - len(scraped_urls))
            batch_urls = current_urls[:batch_size]
            
            print(f"Depth {depth + 1}/{max_depth}: Scraping {len(batch_urls)} URLs")

            results = await self.scrape_urls(batch_urls)
            
            # Process results and collect next level URLs
            next_urls = []
            for result in results:
                if result.url not in scraped_urls:
                    token_count = self._calculate_token_count(result.markdown)
                    
                    page_data = {
                        'url': result.url,
                        'content': result.markdown,
                        'token_count': token_count,
                        'depth': depth,
                        'success': result.success
                    }
                    
                    all_pages.append(page_data)
                    scraped_urls.add(result.url)
                    
                    # Extract links for next depth
                    if result.success and depth < max_depth - 1:
                        for link in result.links.get('internal', []):
                            if link not in scraped_urls:
                                next_urls.append(link)
            
            current_urls = list(set(next_urls))
        
        # Apply token optimization if needed
        if max_tokens:
            all_pages = self._optimize_pages_for_tokens(all_pages, max_tokens)
        
        # Prepare final output
        total_time = time.time() - start_time
        combined_content = '\n\n'.join(p['content'] for p in all_pages if p['success'])
        
        return {
            'pages': all_pages,
            'combined_content': combined_content,
            'total_time': total_time,
            'pages_scraped': len(all_pages)
        }
    
    def _optimize_pages_for_tokens(self, pages: List[Dict], max_tokens: int) -> List[Dict]:
        """Simple greedy optimization for token limits."""
        # Sort by value/token ratio (could be more sophisticated)
        valid_pages = [p for p in pages if p['success'] and p['token_count'] > 0]
        valid_pages.sort(key=lambda x: x['token_count'] / (x['depth'] + 1))
        
        selected = []
        total_tokens = 0
        
        for page in valid_pages:
            if total_tokens + page['token_count'] <= max_tokens:
                selected.append(page)
                total_tokens += page['token_count']
            else:
                break
                
        return selected


# Usage example:
async def main():
    scraper = ScraperFacade()
    
    # Test concurrent scraping
    urls = [
        "https://example.com", 
        "https://httpbin.org/delay/1",
        "https://httpbin.org/delay/2", 
        "https://doi.org/10.1000/example"
    ]
    
    start_time = time.time()
    results = await scraper.scrape_urls(urls, max_concurrent=3)
    end_time = time.time()
    
    print(f"\nResults in {end_time - start_time:.2f} seconds:")
    for result in results:
        if result.success:
            token_count = scraper._calculate_token_count(result.markdown)
            print(f"✓ {result.url}: {len(result.markdown)} chars, {token_count} tokens")
        else:
            print(f"✗ {result.url}: {result.error_type.value} - {result.error_message}")


if __name__ == "__main__":
    asyncio.run(main())

