"""
Vision Model

This module handles AI vision-based image recognition.
It uses multimodal LLM models to analyze images and convert them to text descriptions.
"""

from typing import Optional, Dict, Any, List
from loguru import logger
import base64
import httpx
from openai import AsyncOpenAI


class VisionModel:
    """AI vision model for image recognition."""
    
    def __init__(self, endpoint: str = None, model: str = "gpt-4-vision-preview", api_key: str = None):
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
            logger.warning("VisionModel initialized without API key")
    
    async def analyze_image(self, image_data: bytes, prompt: str = "Describe this image in detail.") -> str:
        """
        Analyze an image and return a text description.
        
        Args:
            image_data: Raw image bytes
            prompt: Custom prompt for analysis
            
        Returns:
            Text description of the image
        """
        logger.info("Analyzing image")
        
        if not self.client:
            return self._fallback_analysis(image_data)
        
        # Convert image to base64
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            description = response.choices[0].message.content.strip()
            logger.info(f"Image analysis complete: {description[:100]}...")
            return description
            
        except Exception as e:
            logger.error(f"Failed to analyze image: {e}")
            return self._fallback_analysis(image_data)
    
    async def recognize_captcha(self, image_data: bytes, captcha_type: str = "text") -> str:
        """
        Recognize captcha from an image.
        
        Args:
            image_data: Captcha image bytes
            captcha_type: Type of captcha (text, slider, click, etc.)
            
        Returns:
            Captcha solution
        """
        logger.info(f"Recognizing {captcha_type} captcha")
        
        prompt = f"""
This is a {captcha_type} captcha. Please analyze the image and provide the solution.

For text captchas: Output only the text shown in the image.
For slider captchas: Output the pixel offset needed to slide.
For click captchas: Output the coordinates of objects to click.

Respond with ONLY the solution, no explanations.
"""
        
        return await self.analyze_image(image_data, prompt)
    
    async def extract_text_from_image(self, image_data: bytes) -> str:
        """
        Extract text from an image (OCR-like functionality).
        
        Args:
            image_data: Image bytes
            
        Returns:
            Extracted text
        """
        logger.info("Extracting text from image")
        
        prompt = """
Extract all text visible in this image. Preserve the original formatting and order.
Output only the extracted text, no explanations.
"""
        
        return await self.analyze_image(image_data, prompt)
    
    async def identify_ui_elements(self, image_data: bytes) -> Dict[str, Any]:
        """
        Identify UI elements in a screenshot.
        
        Args:
            image_data: Screenshot image bytes
            
        Returns:
            Dictionary of identified UI elements with their positions
        """
        logger.info("Identifying UI elements")
        
        if not self.client:
            return {"elements": []}
        
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        prompt = """
Analyze this UI screenshot and identify all interactive elements such as:
- Buttons
- Input fields
- Links
- Checkboxes
- Dropdown menus

For each element, provide:
- Type of element
- Label/text on the element
- Approximate position (x, y coordinates)

Output as JSON format only, no explanations.
"""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000
            )
            
            import json
            result_text = response.choices[0].message.content.strip()
            result = json.loads(result_text)
            logger.info(f"Identified {len(result.get('elements', []))} UI elements")
            return result
            
        except Exception as e:
            logger.error(f"Failed to identify UI elements: {e}")
            return {"elements": []}
    
    def _fallback_analysis(self, image_data: bytes) -> str:
        """Fallback analysis when AI is not available."""
        return f"Image analysis unavailable. Image size: {len(image_data)} bytes"
