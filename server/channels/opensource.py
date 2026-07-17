"""
Open Source Channel

This module integrates with open source novel APIs and projects
to provide stable and authoritative novel data sources.
"""

from typing import List, Dict, Optional, Any
from loguru import logger
import httpx


class OpenSourceChannel:
    """Open source novel API integration channel."""
    
    def __init__(self):
        self.name = "opensource"
        self.sources = []  # List of configured open source APIs
    
    def add_source(self, name: str, base_url: str, api_key: Optional[str] = None):
        """Add an open source API endpoint."""
        self.sources.append({
            "name": name,
            "base_url": base_url,
            "api_key": api_key
        })
        logger.info(f"Added open source: {name} ({base_url})")
    
    async def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for novels across configured open sources.
        
        Args:
            query: Search query
            
        Returns:
            List of search results
        """
        logger.info(f"Searching open sources for '{query}'")
        
        all_results = []
        
        for source in self.sources:
            try:
                results = await self._query_source(source, query)
                all_results.extend(results)
            except Exception as e:
                logger.error(f"Failed to query {source['name']}: {e}")
        
        return all_results
    
    async def _query_source(self, source: Dict, query: str) -> List[Dict[str, Any]]:
        """Query a specific open source API."""
        results = []
        base_url = source["base_url"]
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {}
            if source.get("api_key"):
                headers["Authorization"] = f"Bearer {source['api_key']}"
            
            # Generic search endpoint - adjust based on actual API
            response = await client.get(
                f"{base_url}/search",
                params={"q": query},
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                # Parse based on API response format
                results = self._parse_response(source["name"], data)
        
        return results
    
    def _parse_response(self, source_name: str, data: Any) -> List[Dict[str, Any]]:
        """Parse API response into standardized format."""
        results = []
        
        # This is a generic parser - should be customized per source
        if isinstance(data, dict):
            if "results" in data:
                for item in data["results"]:
                    results.append({
                        "title": item.get("title", ""),
                        "author": item.get("author", ""),
                        "url": item.get("url", ""),
                        "source": source_name
                    })
        elif isinstance(data, list):
            for item in data:
                results.append({
                    "title": item.get("title", ""),
                    "author": item.get("author", ""),
                    "url": item.get("url", ""),
                    "source": source_name
                })
        
        return results
    
    async def fetch_chapter(self, chapter_url: str, source_name: str) -> Optional[str]:
        """
        Fetch chapter content from an open source.
        
        Args:
            chapter_url: URL to the chapter
            source_name: Name of the source
            
        Returns:
            Chapter content text or None
        """
        logger.info(f"Fetching chapter from {source_name}: {chapter_url}")
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(chapter_url)
                
                if response.status_code == 200:
                    # Parse and extract chapter content
                    return self._extract_content(source_name, response.text)
        except Exception as e:
            logger.error(f"Failed to fetch chapter: {e}")
        
        return None
    
    def _extract_content(self, source_name: str, html: str) -> str:
        """Extract chapter content from HTML."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'lxml')
        
        # Generic extraction - should be customized per source
        # Look for common content containers
        content_divs = [
            soup.select_one('.content'),
            soup.select_one('#content'),
            soup.select_one('.chapter-content'),
            soup.select_one('.text-content'),
        ]
        
        for div in content_divs:
            if div:
                return div.get_text(separator='\n', strip=True)
        
        # Fallback: return all text
        return soup.get_text(separator='\n', strip=True)[:10000]  # Limit length
