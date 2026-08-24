"""Thin client for a local Ollama server — used in place of a paid cloud LLM (e.g. Azure OpenAI)
for every AI feature in this framework (root cause analysis, test generation, NLP execution).
"""
import json

import requests

from config.config_reader import ConfigReader
from utils.logger import get_logger

logger = get_logger(__name__)


class OllamaClient:
    def __init__(self, host: str = None, model: str = None):
        self.host = host or ConfigReader.get("ollama_host", "http://localhost:11434")
        self.model = model or ConfigReader.get("ollama_model", "llama3.2")

    def generate(self, prompt: str, system: str = None, json_mode: bool = False, timeout: int = 60) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"

        logger.info(f"Ollama request -> model={self.model}")
        response = requests.post(f"{self.host}/api/generate", json=payload, timeout=timeout)
        response.raise_for_status()
        text = response.json().get("response", "")
        logger.info("Ollama response received")
        return text

    def generate_json(self, prompt: str, system: str = None, timeout: int = 60) -> dict:
        raw = self.generate(prompt, system=system, json_mode=True, timeout=timeout)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.error(f"Ollama did not return valid JSON: {raw}")
            return {}
