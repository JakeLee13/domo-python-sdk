"""
AI text generation client for Domo SDK.
"""

import json
import time
from typing import Any, List, Callable, Union
from concurrent.futures import ThreadPoolExecutor, as_completed

from ..core import _get_domo_client, _config
from .. import templates
from .. import usage


class LLM:
    """AI text generation client with template support and parallel processing."""
    
    def prompt(self, message: str, *args, template: str = None, 
               conversation: List[dict] = None, response_format: dict = None,
               **kwargs) -> Union[str, dict]:
        """
        Send a message to the AI model with optional formatting and conversation history.
        
        Args:
            message: The message text (supports .format() with *args and **kwargs)
            *args: Positional arguments for message.format()
            template: Optional template name for expert scaffolding
            conversation: Optional conversation history 
                         [{"role": "USER"/"ASSISTANT", "text": "..."}]
            response_format: Optional JSON Schema for structured output
                           e.g., {"properties": {"city": {"type": "string"}}, 
                                  "required": ["city"], "type": "object"}
            **kwargs: Keyword arguments for message.format()
            
        Returns:
            str: Generated text from the AI model (when response_format is None)
            dict: Parsed JSON object (when response_format is provided)
        """
        if args or kwargs:
            formatted_message = message.format(*args, **kwargs)
        else:
            formatted_message = message
        
        if template:
            scaffold = templates.get_scaffold(template)
            formatted_message = scaffold.format(formatted_message)
        
        return self._call_api(formatted_message, conversation, response_format)
    
    def _call_api(self, message: str, conversation: List[dict] = None,
                  response_format: dict = None) -> Union[str, dict]:
        """
        Execute API call to Domo's AI messages service.

        API Details:
        - Endpoint: {hostname}/api/ai/v1/messages/chat
        - Method: POST
        - Expects: Message array with role/content structure
        - Returns: Response with content array and metadata

        Args:
            message: The formatted message to send
            conversation: Optional conversation history
            response_format: Optional JSON Schema for structured output

        Returns:
            str: Text response (default behavior)
            dict: Parsed JSON object (when response_format is provided)
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/ai/v1/messages/chat"
        messages = []

        if conversation:
            for msg in conversation:
                messages.append({
                    "role": msg["role"],
                    "content": [{"type": "TEXT", "text": msg["text"]}]
                })

        messages.append({
            "role": "USER",
            "content": [{"type": "TEXT", "text": message}]
        })
        payload = {
            "input": messages,
            "model": _config['llm_settings']['model'],
            "temperature": _config['llm_settings']['temperature'],
            "maxTokens": _config['llm_settings']['max_tokens']
        }

        # Add system prompt if configured
        if _config['llm_settings']['system']:
            payload["system"] = [{"type": "TEXT", "text": _config['llm_settings']['system']}]
        # Add structured output format if provided
        if response_format:
            payload["responseFormat"] = {
                "type": "JSON",
                "schema": response_format
            }
        call_started = time.time()
        response = domo_client._post(url, payload).json()
        elapsed = time.time() - call_started

        # Record usage. modelProviderUsage may be null on rare error responses,
        # and reasoningTokens is explicitly null on non-reasoning models — so
        # `.get(..., 0) or 0` is needed (`.get(k, 0)` returns None when value is None).
        provider_usage = response.get("modelProviderUsage") or {}
        usage.record_call(
            surface="chat",
            model_id=response.get("modelId"),
            input_tokens=provider_usage.get("inputTokens") or 0,
            output_tokens=provider_usage.get("outputTokens") or 0,
            reasoning_tokens=provider_usage.get("reasoningTokens") or 0,
            elapsed_seconds=elapsed,
        )

        # Return structured output if schema was provided
        if response_format:
            return json.loads(response["content"][0]["text"])

        # Return text output (default behavior)
        return response["content"][0]["text"]
    
    
    def parallel(self, items: List[Any], prompt_func: Callable[[Any], str], 
                max_workers: int = 4, show_progress: bool = True) -> List[Union[str, dict]]:
        """
        Process multiple items in parallel using AI generation.
        
        Args:
            items: List of items to process
            prompt_func: Function that takes an item and returns a result
                        (should call self.prompt() internally)
            max_workers: Number of parallel threads
            show_progress: Whether to print progress updates
            
        Returns:
            List of results (strings or dicts depending on prompt_func behavior)
        """
        if not items:
            return []

        results = [None] * len(items)

        if show_progress:
            print(f"Processing {len(items)} items with {max_workers} workers...")
            start_time = time.time()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Let prompt_func handle the entire prompt call
            future_to_index = {
                executor.submit(prompt_func, item): idx 
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