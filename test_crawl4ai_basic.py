import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from src.backend.parser.searcherFacade import SearcherFacade
from src.backend.parser.scraperFacade import ScraperFacade
from src.backend.parser.searcher import SearchQuery, ScrapedContent

async def test_crawl4ai_basic():
    """Test if crawl4ai works at all."""
    from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
    
    print("🧪 Testing basic crawl4ai functionality...")
    
    try:
        # Most minimal config possible
        print("\n1️⃣ Creating browser config...")
        browser_config = BrowserConfig(headless=True, verbose=True)
        print("✅ Browser config created")
        
        print("\n2️⃣ Creating crawler run config...")
        run_config = CrawlerRunConfig()
        print("✅ Run config created")
        
        print("\n3️⃣ Creating AsyncWebCrawler...")
        async with AsyncWebCrawler(config=browser_config) as crawler:
            print("✅ Crawler created successfully")
            
            print("\n4️⃣ Attempting to crawl example.com...")
            result = await crawler.arun(url="https://example.com", config=run_config)
            print("✅ Crawl completed!")
            
            print(f"\n5️⃣ Checking results...")
            if hasattr(result, '_results') and result._results:
                first_result = result._results[0]
                print(f"   Success: {first_result.success}")
                if first_result.success:
                    print(f"   Markdown length: {len(first_result.markdown)}")
                    print(f"   Preview: {first_result.markdown[:200]}")
                else:
                    print(f"   Error: {getattr(first_result, 'error_message', 'No error message')}")
            else:
                print("   ⚠️  No results in response")
                print(f"   Result object: {result}")
                
    except NotImplementedError as e:
        print(f"\n❌ NotImplementedError: {e}")
        print("\n💡 This usually means:")
        print("   1. Playwright browser not installed")
        print("   2. Run: playwright install chromium")
        import traceback
        print(f"\n📋 Traceback:\n{traceback.format_exc()}")
        
    except Exception as e:
        print(f"\n❌ Exception: {type(e).__name__}: {e}")
        import traceback
        print(f"\n📋 Traceback:\n{traceback.format_exc()}")


async def debug_single_scrape():
    """Debug single URL scraping with detailed output."""
    
    url = "https://profitview.net/blog/what-i-learned-when-building-an-ai-news-trading-bot"
    
    print(f"🔧 Debug scraping: {url}")
    print("=" * 80)
    
    scraper = ScraperFacade(enable_content_filtering=True)
    
    # Test direct scrape
    print("\n1️⃣ Testing direct _scrape_single_url...")
    try:
        result = await scraper._scrape_single_url(url)
        print(f"✅ Result received")
        print(f"   Success: {result.success}")
        print(f"   Error type: {result.error_type}")
        print(f"   Error message: '{result.error_message}'")
        print(f"   Markdown length: {len(result.markdown)}")
        print(f"   Text length: {len(result.text)}")
        
        if result.success:
            print(f"\n📄 Content preview (first 500 chars):")
            print(result.markdown)
        else:
            print(f"\n❌ Scraping failed")
            
    except Exception as e:
        print(f"💥 Exception caught: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Test with retry
    print("\n" + "=" * 80)
    print("2️⃣ Testing _scrape_with_retry...")
    try:
        result = await scraper._scrape_with_retry(url)
        print(f"✅ Result received")
        print(f"   Success: {result.success}")
        print(f"   Error type: {result.error_type}")
        print(f"   Error message: '{result.error_message}'")
        print(f"   Markdown length: {len(result.markdown)}")
        
    except Exception as e:
        print(f"💥 Exception caught: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
    
    # Test with scrape_urls (the public method)
    print("\n" + "=" * 80)
    print("3️⃣ Testing scrape_urls (public API)...")
    try:
        results = await scraper.scrape_urls([url], max_concurrent=1)
        result = results[0]
        print(f"✅ Result received")
        print(f"   Success: {result.success}")
        print(f"   Error type: {result.error_type}")
        print(f"   Error message: '{result.error_message}'")
        print(f"   Markdown length: {len(result.markdown)}")
        
        if result.success:
            print(f"\n📊 Token count: {scraper._calculate_token_count(result.markdown)}")
            print(f"\n📄 First 300 chars of content:")
            print(result.markdown)
            
    except Exception as e:
        print(f"💥 Exception caught: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 80)
    print("✨ Debug complete!")
# Run it
# asyncio.run(test_crawl4ai_basic())
asyncio.run(debug_single_scrape())