import requests
import json
import re
from typing import Optional, Dict, List
from loguru import logger
from config import Config

class AIService:
    """Service for AI-powered message composition."""
    
    def compose_message(
        self,
        topic: str,
        tone: str = "friendly",
        placeholders: Optional[Dict] = None,
        provider: str = "openrouter"
    ) -> Dict:
        """
        Compose a message using AI.
        
        Args:
            topic: The topic or purpose of the message
            tone: The tone of the message (friendly, formal, casual, urgent)
            placeholders: Dictionary of placeholders to include in the message
            provider: AI provider to use (openrouter or ollama)
        
        Returns:
            Dictionary with composed message or error
        """
        if provider == "openrouter":
            return self._compose_with_openrouter(topic, tone, placeholders)
        elif provider == "ollama":
            return self._compose_with_ollama(topic, tone, placeholders)
        else:
            return {
                "success": False,
                "error": f"Unknown AI provider: {provider}"
            }
    
    def _compose_with_openrouter(self, topic: str, tone: str, placeholders: Optional[Dict]) -> Dict:
        """Compose message using OpenRouter API."""
        
        if not Config.OPENROUTER_API_KEY:
            return {
                "success": False,
                "error": "OpenRouter API key not configured"
            }
        
        try:
            # Build the prompt
            prompt = self._build_prompt(topic, tone, placeholders)
            
            # OpenRouter API endpoint
            url = "https://openrouter.ai/api/v1/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/zapi-whatsapp",
                "X-Title": "Z-API WhatsApp Sender"
            }
            
            payload = {
                "model": "openai/gpt-3.5-turbo",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that creates short, WhatsApp-compatible messages. Keep messages concise, friendly, and under 500 characters. Avoid using links or excessive emojis."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 150,
                "temperature": 0.7
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                message = data["choices"][0]["message"]["content"]
                
                # Sanitize the message
                message = self._sanitize_message(message)
                
                return {
                    "success": True,
                    "message": message
                }
            else:
                logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"OpenRouter API error: {response.status_code}"
                }
                
        except Exception as e:
            logger.exception("Error composing message with OpenRouter")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _compose_with_ollama(self, topic: str, tone: str, placeholders: Optional[Dict]) -> Dict:
        """Compose message using Ollama local API."""
        
        try:
            # Build the prompt
            prompt = self._build_prompt(topic, tone, placeholders)
            
            # Ollama API endpoint
            url = f"{Config.OLLAMA_HOST}/api/generate"
            
            payload = {
                "model": "llama2",  # You can change this to any model you have installed
                "prompt": f"Create a short WhatsApp message (under 500 characters) that is {tone} in tone. {prompt}",
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "max_tokens": 150
                }
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                message = data.get("response", "")
                
                # Sanitize the message
                message = self._sanitize_message(message)
                
                return {
                    "success": True,
                    "message": message
                }
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Ollama API error: {response.status_code}"
                }
                
        except requests.ConnectionError:
            return {
                "success": False,
                "error": "Cannot connect to Ollama. Make sure Ollama is running locally."
            }
        except Exception as e:
            logger.exception("Error composing message with Ollama")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _build_prompt(self, topic: str, tone: str, placeholders: Optional[Dict]) -> str:
        """Build the prompt for AI message composition."""
        prompt = f"Create a message about: {topic}. "
        
        if placeholders:
            placeholder_str = ", ".join([f"{k}: {v}" for k, v in placeholders.items()])
            prompt += f"Include these details: {placeholder_str}. "
        
        prompt += f"The tone should be {tone}."
        
        return prompt
    
    def _sanitize_message(self, message: str) -> str:
        """Sanitize AI-generated message for WhatsApp."""
        # Remove excessive line breaks
        message = re.sub(r'\n{3,}', '\n\n', message)
        
        # Remove potential harmful links
        message = re.sub(r'https?://[^\s]+', '[link removed]', message)
        
        # Trim to reasonable length
        if len(message) > 1000:
            message = message[:997] + "..."
        
        # Remove leading/trailing whitespace
        message = message.strip()
        
        return message

# Singleton instance
_ai_service = None

def get_ai_service():
    """Get or create the AI service singleton."""
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service