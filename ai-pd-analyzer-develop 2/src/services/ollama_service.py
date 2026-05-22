from src.services.prompt_manager import PromptManager
from src.core.logger import setup_logger
from src.services.utils import execute_llm_chain
from typing import Dict, Any, Optional
from .config import load_config

from langchain_ollama import OllamaLLM

logger = setup_logger(__name__)

class OllamaService:
    def __init__(self, prompt_manager:PromptManager):
        self.prompt_manager = prompt_manager
        self.prompt_manager.load_all()

        self.llm_qwen = OllamaLLM(
            model=load_config().norms_model_qwen,
            base_url=load_config().ollama_url,
            timeout=1200,
            temperature=0.0,
            top_k=1,
            top_p=1.0,
            seed=42,
            mirostat=0,
            mirostat_tau=0,
            frequencyPenalty=0.0,
            presencePenalty=0.0,
            num_predict=2048
        )
        
    def get_tg_model_answer(self, prompt_name: str, payload: dict):
        chain = self.prompt_manager.get_template(prompt_name) | self.llm_qwen
        response = execute_llm_chain(chain, payload, stub={})
        return response
    
    def get_tg_model_answer_with_batch(
            self, 
            prompt_name: str,
            payload: list, 
            ):
        """Возвращает {"input": , "response": }"""
        result = []
        for p in payload:
            response = self.get_tg_model_answer(prompt_name, p)
            result.append({"input": p, "response": response})
        return result