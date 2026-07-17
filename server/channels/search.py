"""
Search Channel

This module handles multi-engine search for novel content when other sources fail.
It supports Baidu, Bing, 360 Search, and other search engines.
"""

from typing import List, Dict, Optional, Any
from loguru import logger
import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote_plus


class SearchChannel:
    """Multi-engine search channel for novel acquisition."""
    
    def __init__(self):
        self.name = "search"
        self.engines = {
            "baidu": self._search_baidu,
            "bing": self._search_bing,
            "so360": self._search_so360,
        }
    
    async def search(self, query: str, engines: List[str] = None) -> List[Dict[str, Any]]:
        """
        Search for novels across multiple engines.
        
        Args:
            query: Search query (novel title, author, etc.)
            engines: List of search engines to use
            
        Returns:
            List of search results
        """
        if engines is None:
            engines = list(self.engines.keys())
        
        logger.info(f"Searching for '{query}' using engines: {engines}")
        
        all_results = []
        
        for engine_name in engines:
            if engine_name in self.engines:
                try:
                    results = await self.engines[engine_name](query)
                    all_results.extend(results)
                    logger.info(f"Found {len(results)} results from {engine_name}")
                except Exception as e:
                    logger.error(f"Search failed on {engine_name}: {e}")
        
        # Remove duplicates and sort by relevance
        return self._deduplicate_and_sort(all_results)
    
    async def _search_baidu(self, query: str) -> List[Dict[str, Any]]:
        """Search using Baidu."""
        results = []
        encoded_query = quote_plus(query)
        url = f"https://www.baidu.com/s?wd={encoded_query}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Parse Baidu search results
                for item in soup.select('.c-container'):
                    title_elem = item.select_one('h3 a')
                    if title_elem:
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "url": title_elem.get('href', ''),
                            "snippet": item.select_one('.c-abstract').get_text(strip=True) if item.select_one('.c-abstract') else "",
                            "engine": "baidu"
                        })
        
        return results[:10]  # Limit to top 10 results
    
    async def _search_bing(self, query: str) -> List[Dict[str, Any]]:
        """Search using Bing."""
        results = []
        encoded_query = quote_plus(query)
        url = f"https://www.bing.com/search?q={encoded_query}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Parse Bing search results
                for item in soup.select('#b_results .b_algo'):
                    title_elem = item.select_one('h2 a')
                    if title_elem:
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "url": title_elem.get('href', ''),
                            "snippet": item.select_one('.b_caption p').get_text(strip=True) if item.select_one('.b_caption p') else "",
                            "engine": "bing"
                        })
        
        return results[:10]
    
    async def _search_so360(self, query: str) -> List[Dict[str, Any]]:
        """Search using 360 Search."""
        results = []
        encoded_query = quote_plus(query)
        url = f"https://www.so.com/s?q={encoded_query}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Parse 360 search results
                for item in soup.select('.res-list'):
                    title_elem = item.select_one('.f-title a')
                    if title_elem:
                        results.append({
                            "title": title_elem.get_text(strip=True),
                            "url": title_elem.get('href', ''),
                            "snippet": item.select_one('.f-desc').get_text(strip=True) if item.select_one('.f-desc') else "",
                            "engine": "so360"
                        })
        
        return results[:10]
    
    def _deduplicate_and_sort(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate URLs and sort by relevance."""
        seen_urls = set()
        unique_results = []
        
        for result in results:
            if result["url"] not in seen_urls:
                seen_urls.add(result["url"])
                unique_results.append(result)
        
        # Simple sorting - can be enhanced with more sophisticated ranking
        return unique_results
