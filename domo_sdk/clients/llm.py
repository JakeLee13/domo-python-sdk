"""
AI text generation client for Domo SDK.
"""

import time
from typing import Any, Dict, Optional, List, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from domojupyter.ai import PromptTemplate
from domojupyter.ai.models.TextGenerationRequest import TextGenerationRequest

from ..core import _get_domo_client, _config
from .. import templates


class LLM:
    """AI text generation client with expert prompt scaffolding."""
    
    def _call_api(self, prompt: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Execute API call to Domo's AI service."""
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/ai/v1/text/generation"
        
        request_json = TextGenerationRequest(
            input_str=prompt,
            prompt_template=PromptTemplate(prompt),
            parameters=params or {},
            model=_config['llm_settings']['model'],
            system=_config['llm_settings']['system'],
            model_configuration={
                "temperature": _config['llm_settings']['temperature'],
                "maxTokens": _config['llm_settings']['max_tokens']
            }
        ).to_json()
        
        response_json = domo_client._post(url, request_json).json()
        return response_json["output"]
    
    def prompt(self, prompt: str, *args, template=None, **kwargs) -> str:
        """
        Generate AI content with optional expert scaffold templating.
        
        Args:
            prompt: The prompt text to send to the AI
            *args: Positional arguments for prompt formatting
            template: Optional template name ('email', 'app') for expert scaffolding
            **kwargs: Keyword arguments for prompt formatting
            
        Returns:
            Generated text from the AI model
        """
        formatted_prompt = prompt.format(*args, **kwargs) if args or kwargs else prompt
        
        if template is not None:
            scaffold = templates.get_scaffold(template)
            formatted_prompt = scaffold.format(formatted_prompt)
        
        return self._call_api(formatted_prompt)
    
    def parallel(self, items: List[Any], prompt_func: Callable[[Any], str], 
                max_workers: int = 4, show_progress: bool = True) -> List[str]:
        """
        Process multiple items in parallel using AI generation.
        
        Args:
            items: List of items to process
            prompt_func: Function that takes an item and returns a prompt string
            max_workers: Number of parallel workers (default: 4)
            show_progress: Whether to show progress updates (default: True)
            
        Returns:
            List of generated responses in same order as input items
        """
        if not items:
            return []
        
        results = [None] * len(items)
        
        if show_progress:
            print(f"Processing {len(items)} items with {max_workers} workers...")
            start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(lambda item: self.prompt(prompt_func(item)), item): idx 
                for idx, item in enumerate(items)
            }
            
            completed = 0
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    results[idx] = future.result()
                    completed += 1
                    
                    if show_progress:
                        print(f"Completed {completed}/{len(items)} tasks")
                        
                except Exception as e:
                    print(f"Error processing item {idx}: {e}")
                    results[idx] = f"ERROR: {str(e)}"
        
        if show_progress:
            elapsed = time.time() - start_time
            print(f"Completed in {elapsed:.1f} seconds")
        
        return results