import json
import re
import httpx
from typing import Dict, Any, List
from backend.config import GROQ_API_KEY, OLLAMA_URL, OLLAMA_MODEL, DEFAULT_LLM_PROVIDER

def parse_llm_json(content: str) -> Dict[str, Any]:
    """
    Robust JSON parser for LLM responses.
    Attempts standard parsing, splits markdown blocks, and falls back to regex extraction if malformed.
    """
    content = content.strip()
    
    # 1. Try direct JSON parsing
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
        
    # 2. Try extracting from markdown code block ```json ... ```
    if "```json" in content:
        try:
            json_block = content.split("```json")[1].split("```")[0].strip()
            return json.loads(json_block)
        except Exception:
            pass
            
    # 3. Robust Regex Fallback
    # Extract the "answer" string
    # We look for "answer": "..." followed by "citations" or end of string
    answer = ""
    answer_match = re.search(r'"answer"\s*:\s*"(.*?)"\s*,\s*"citations"', content, re.DOTALL)
    if not answer_match:
        # Try matching "answer" to end of string
        answer_match = re.search(r'"answer"\s*:\s*"(.*?)"', content, re.DOTALL)
        
    if answer_match:
        answer = answer_match.group(1)
        # Unescape common JSON characters
        answer = answer.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
    else:
        # If no answer block could be extracted, treat the whole content as the answer
        answer = content
        
    # Extract the "citations" list
    citations = []
    citations_match = re.search(r'"citations"\s*:\s*(\[.*?\])', content, re.DOTALL)
    if citations_match:
        try:
            # Clean up trailing comma issues in JSON lists if present
            cleaned_list = re.sub(r',\s*\]', ']', citations_match.group(1))
            citations = json.loads(cleaned_list)
        except Exception:
            pass
            
    return {
        "answer": answer,
        "citations": citations
    }

class LLMClient:
    
    @classmethod
    def get_provider(cls) -> str:
        """
        Returns the active provider based on availability of Groq API Key.
        """
        if GROQ_API_KEY:
            return "groq"
        return "ollama"

    @classmethod
    def generate_completion(cls, messages: List[Dict[str, str]], provider: str = None) -> Dict[str, Any]:
        """
        Generates completion from Groq or local Ollama.
        """
        active_provider = provider or cls.get_provider()
        
        if active_provider == "groq":
            return cls._generate_groq(messages)
        else:
            return cls._generate_ollama(messages)

    @classmethod
    def _generate_groq(cls, messages: List[Dict[str, str]], force_text_mode: bool = False) -> Dict[str, Any]:
        """
        Call Groq API using HTTP POST.
        Supports retrying in text-mode if JSON-validation mode fails.
        """
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        model = "llama-3.1-8b-instant"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2048
        }
        
        # Only use strict json mode if not forced to text mode
        if not force_text_mode:
            payload["response_format"] = {"type": "json_object"}
            
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(url, headers=headers, json=payload)
                
                # Check for JSON validation failure (HTTP 400 with json_validate_failed code)
                if response.status_code == 400 and not force_text_mode:
                    res_json = response.json()
                    error_code = res_json.get("error", {}).get("code", "")
                    if "json" in error_code or "validate" in error_code:
                        print("Groq JSON validation failed. Retrying in text-mode...")
                        return cls._generate_groq(messages, force_text_mode=True)
                        
                response.raise_for_status()
                res_data = response.json()
                
                content = res_data["choices"][0]["message"]["content"]
                parsed_response = parse_llm_json(content)
                
                return {
                    "answer": parsed_response.get("answer", content),
                    "citations": parsed_response.get("citations", []),
                    "model": model
                }
        except Exception as e:
            # If JSON validation failed in httpx call but wasn't caught above, retry in text mode
            if not force_text_mode and ("json_validate_failed" in str(e) or "400" in str(e)):
                print("Encountered 400 error in Groq. Retrying in text-mode...")
                try:
                    return cls._generate_groq(messages, force_text_mode=True)
                except Exception as retry_err:
                    e = retry_err
            
            # If the user explicitly configured a Groq API Key, raise the error directly
            if GROQ_API_KEY:
                error_msg = str(e)
                if hasattr(e, "response") and e.response is not None:
                    try:
                        error_msg = f"{e.response.status_code} - {e.response.json()}"
                    except Exception:
                        error_msg = f"{e.response.status_code} - {e.response.text}"
                raise ConnectionError(f"Failed to communicate with Groq API. Error: {error_msg}")
            
            print(f"Groq API error: {e}. Falling back to local Ollama if available...")
            return cls._generate_ollama(messages)

    @classmethod
    def _generate_ollama(cls, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Call local Ollama instance.
        """
        url = f"{OLLAMA_URL}/api/chat"
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1
            }
        }
        
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                res_data = response.json()
                
                content = res_data["message"]["content"]
                parsed_response = parse_llm_json(content)
                
                return {
                    "answer": parsed_response.get("answer", content),
                    "citations": parsed_response.get("citations", []),
                    "model": f"ollama/{OLLAMA_MODEL}"
                }
        except Exception as e:
            raise ConnectionError(
                f"Failed to communicate with LLM provider. Groq is not configured or failed, "
                f"and Ollama at {OLLAMA_URL} is unreachable. Error: {e}"
            )
