"""
Captcha Solver

This module provides automated captcha solving using AI vision.
It integrates with the vision model to recognize and solve various types of captchas.
"""

from typing import Optional, Dict, Any, Tuple, List
from loguru import logger
import base64
from .vision_model import VisionModel


class CaptchaSolver:
    """Automated captcha solver using AI vision."""
    
    def __init__(self, vision_model: VisionModel = None):
        self.vision_model = vision_model or VisionModel()
        self.solved_count = 0
    
    async def solve(self, image_data: bytes, captcha_type: str = "text") -> Dict[str, Any]:
        """
        Solve a captcha from an image.
        
        Args:
            image_data: Captcha image bytes
            captcha_type: Type of captcha
            
        Returns:
            Solution dictionary with action instructions
        """
        logger.info(f"Solving {captcha_type} captcha")
        
        solution = {
            "success": False,
            "type": captcha_type,
            "action": None,
            "data": None
        }
        
        try:
            if captcha_type == "text":
                text = await self.vision_model.recognize_captcha(image_data, "text")
                solution["success"] = len(text) > 0
                solution["action"] = "input_text"
                solution["data"] = text
                
            elif captcha_type == "slider":
                offset = await self._solve_slider_captcha(image_data)
                solution["success"] = offset is not None
                solution["action"] = "slide"
                solution["data"] = {"offset": offset}
                
            elif captcha_type == "click":
                coordinates = await self._solve_click_captcha(image_data)
                solution["success"] = len(coordinates) > 0
                solution["action"] = "click"
                solution["data"] = {"coordinates": coordinates}
                
            elif captcha_type == "rotate":
                angle = await self._solve_rotate_captcha(image_data)
                solution["success"] = angle is not None
                solution["action"] = "rotate"
                solution["data"] = {"angle": angle}
            
            if solution["success"]:
                self.solved_count += 1
                logger.info(f"Captcha solved successfully (total solved: {self.solved_count})")
            else:
                logger.warning("Failed to solve captcha")
                
        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
            solution["error"] = str(e)
        
        return solution
    
    async def _solve_slider_captcha(self, image_data: bytes) -> Optional[int]:
        """Solve slider captcha by finding the gap position."""
        prompt = """
This is a slider captcha. Analyze the image and determine the pixel offset 
needed to slide the piece into the correct position to complete the puzzle.

Output ONLY a single integer representing the pixel offset (e.g., 150), no explanations.
"""
        
        response = await self.vision_model.analyze_image(image_data, prompt)
        
        try:
            # Extract number from response
            import re
            numbers = re.findall(r'\d+', response)
            if numbers:
                return int(numbers[0])
        except Exception as e:
            logger.error(f"Failed to parse slider offset: {e}")
        
        return None
    
    async def _solve_click_captcha(self, image_data: bytes) -> List[Tuple[int, int]]:
        """Solve click captcha by identifying objects to click."""
        ui_elements = await self.vision_model.identify_ui_elements(image_data)
        
        coordinates = []
        for element in ui_elements.get("elements", []):
            if element.get("type") in ["button", "object", "target"]:
                coords = element.get("position", {})
                if "x" in coords and "y" in coords:
                    coordinates.append((coords["x"], coords["y"]))
        
        return coordinates
    
    async def _solve_rotate_captcha(self, image_data: bytes) -> Optional[int]:
        """Solve rotate captcha by determining the correct rotation angle."""
        prompt = """
This is a rotation captcha. Analyze the image and determine the angle 
(in degrees) needed to rotate the object to its correct orientation.

Output ONLY a single integer representing the rotation angle (e.g., 90), no explanations.
Positive values indicate clockwise rotation, negative for counter-clockwise.
"""
        
        response = await self.vision_model.analyze_image(image_data, prompt)
        
        try:
            import re
            numbers = re.findall(r'-?\d+', response)
            if numbers:
                return int(numbers[0])
        except Exception as e:
            logger.error(f"Failed to parse rotation angle: {e}")
        
        return None
    
    async def execute_solution(self, solution: Dict[str, Any], driver=None):
        """
        Execute the captcha solution using a browser automation tool.
        
        Args:
            solution: Solution dictionary from solve()
            driver: Selenium/Playwright driver instance
        """
        if not solution.get("success"):
            logger.error("Cannot execute failed solution")
            return False
        
        action = solution.get("action")
        data = solution.get("data")
        
        if not driver:
            logger.warning("No driver provided, cannot execute solution")
            return False
        
        try:
            if action == "input_text":
                # Find input field and enter text
                input_field = driver.find_element_by_css_selector("input[type='text'], input[name='captcha']")
                input_field.send_keys(data)
                
            elif action == "slide":
                # Perform slider action
                from selenium.webdriver.common.action_chains import ActionChains
                slider = driver.find_element_by_css_selector(".slider-btn, .slider-knob")
                ActionChains(driver).click_and_hold(slider).move_by_offset(data["offset"], 0).release().perform()
                
            elif action == "click":
                # Click at specified coordinates
                from selenium.webdriver.common.action_chains import ActionChains
                actions = ActionChains(driver)
                for x, y in data["coordinates"]:
                    actions.move_to_element_with_offset(driver.find_element_by_tag_name("body"), x, y).click()
                actions.perform()
                
            elif action == "rotate":
                # Perform rotation (implementation depends on specific captcha)
                logger.info(f"Rotate by {data['angle']} degrees - manual implementation required")
            
            logger.info("Captcha solution executed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute solution: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get captcha solving statistics."""
        return {
            "total_solved": self.solved_count,
            "model_available": self.vision_model.client is not None
        }
