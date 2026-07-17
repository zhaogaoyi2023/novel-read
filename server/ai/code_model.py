"""
Code Model

This module handles AI code generation and error fixing.
It uses LLM models to generate scraping scripts and fix errors.
"""

from typing import Optional, Dict, Any, List
from loguru import logger
import httpx
from openai import AsyncOpenAI


class CodeModel:
    """AI code generation and error fixing model."""
    
    def __init__(self, endpoint: str = None, model: str = "gpt-4", api_key: str = None):
        self.endpoint = endpoint or "https://api.openai.com/v1"
        self.model = model
        self.api_key = api_key
        
        if self.api_key:
            self.client = AsyncOpenAI(
                base_url=self.endpoint,
                api_key=self.api_key
            )
        else:
            self.client = None
            logger.warning("CodeModel initialized without API key")
    
    async def generate_scraping_script(self, url: str, html_sample: str, requirements: str) -> str:
        """
        Generate a web scraping script for a given website.
        
        Args:
            url: Target website URL
            html_sample: Sample HTML from the website
            requirements: Specific requirements for what to extract
            
        Returns:
            Generated Python scraping script
        """
        logger.info(f"Generating scraping script for {url}")
        
        if not self.client:
            return self._generate_fallback_script(url, requirements)
        
        prompt = f"""
Create a Python web scraping script to extract novel content from the following website.

Target URL: {url}

Requirements:
{requirements}

Sample HTML structure:
{html_sample[:5000]}  # Limit HTML length

The script should:
1. Use asyncio and httpx for async HTTP requests
2. Use BeautifulSoup for HTML parsing
3. Handle errors gracefully
4. Return structured data (title, content, chapters, etc.)
5. Include proper logging

Provide only the Python code, no explanations.
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert Python developer specializing in web scraping."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,
                temperature=0.3
            )
            
            script = response.choices[0].message.content.strip()
            logger.info("Successfully generated scraping script")
            return script
            
        except Exception as e:
            logger.error(f"Failed to generate script: {e}")
            return self._generate_fallback_script(url, requirements)
    
    async def fix_script_error(self, script: str, error_message: str, context: str = "") -> str:
        """
        Fix errors in a scraping script.
        
        Args:
            script: The original script
            error_message: Error message encountered
            context: Additional context about the issue
            
        Returns:
            Fixed script
        """
        logger.info(f"Fixing script error: {error_message[:100]}")
        
        if not self.client:
            return script
        
        prompt = f"""
Fix the following Python script that has encountered an error.

Original Script:
{script}

Error Message:
{error_message}

Additional Context:
{context}

Provide the corrected complete script. Only output the fixed code, no explanations.
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert Python debugger."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,
                temperature=0.3
            )
            
            fixed_script = response.choices[0].message.content.strip()
            logger.info("Successfully fixed script error")
            return fixed_script
            
        except Exception as e:
            logger.error(f"Failed to fix script: {e}")
            return script
    
    async def generate_site_rules(self, url: str, html_sample: str) -> Dict[str, Any]:
        """
        Generate scraping rules for a new website.
        
        Args:
            url: Website URL
            html_sample: Sample HTML
            
        Returns:
            Dictionary containing scraping rules
        """
        logger.info(f"Generating site rules for {url}")
        
        if not self.client:
            return self._generate_fallback_rules(url)
        
        prompt = f"""
Analyze the following website HTML and generate scraping rules in JSON format.

URL: {url}

HTML Sample:
{html_sample[:5000]}

Generate rules for extracting:
- Novel title
- Author name
- Chapter list
- Chapter content
- Cover image

Output ONLY valid JSON, no explanations.
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing website structures."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.3
            )
            
            import json
            rules_text = response.choices[0].message.content.strip()
            rules = json.loads(rules_text)
            logger.info("Successfully generated site rules")
            return rules
            
        except Exception as e:
            logger.error(f"Failed to generate rules: {e}")
            return self._generate_fallback_rules(url)
    
    def _generate_fallback_script(self, url: str, requirements: str) -> str:
        """Generate a basic fallback scraping script."""
        return f'''
# Fallback scraping script for {url}
# This is a basic template - please customize for your needs

import httpx
from bs4 import BeautifulSoup
from loguru import logger

async def scrape(url: str) -> dict:
    """Basic scraping function."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # TODO: Customize selectors based on actual website structure
            result = {{
                "title": soup.find('h1').text if soup.find('h1') else "",
                "content": soup.find('div', class_='content').text if soup.find('div', class_='content') else "",
            }}
            
            return result
    except Exception as e:
        logger.error(f"Scraping failed: {{e}}")
        return None
'''
    
    def _generate_fallback_rules(self, url: str) -> Dict[str, Any]:
        """Generate basic fallback rules."""
        return {
            "url": url,
            "selectors": {
                "title": "h1",
                "content": ".content",
                "chapters": ".chapter-list a",
                "author": ".author"
            },
            "note": "These are fallback rules - please customize for actual website structure"
        }
