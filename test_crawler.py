import asyncio
import os

from dotenv import load_dotenv

load_dotenv()


def _crawl4ai_llm_config(api_key: str | None = None):
    from crawl4ai import LLMConfig

    key = api_key or os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("OPENAI_BASE_URL", "")
    raw_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if base_url:
        os.environ["OPENAI_API_BASE"] = base_url

    provider = raw_model if raw_model.startswith("openai/") else f"openai/{raw_model}"

    return LLMConfig(provider=provider, api_token=key)


async def test_crawl4ai():
    import requests
    from crawl4ai import (
        AsyncWebCrawler,
        BrowserConfig,
        CacheMode,
        CrawlerRunConfig,
        LLMExtractionStrategy,
    )

    url = "https://www.eventbrite.com/d/online/technology/"

    print("Testing Crawl4AI on URL:", url)

    source_url = url
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if resp.ok and resp.text.strip():
            print("Successfully requested URL natively. Length:", len(resp.text))
            source_url = f"raw://{resp.text}"
    except Exception as e:
        print("native request failed", e)
        pass

    llm_strategy = LLMExtractionStrategy(
        llm_config=_crawl4ai_llm_config(),
        instruction="Extract the event name, date, and city of the primary overarching technological event. Return pure valid JSON dictionary ONLY.",
        extraction_type="block",
    )
    config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, extraction_strategy=llm_strategy)
    browser_config = BrowserConfig(headless=True)

    async with AsyncWebCrawler(config=browser_config) as crawler:
        res = await crawler.arun(url=source_url, config=config)
        if not res.success:
            print("Crawl4AI failed:", res.error_message)
            return

        print("Success!")
        print("Extracted content:")
        print(res.extracted_content)


if __name__ == "__main__":
    asyncio.run(test_crawl4ai())
