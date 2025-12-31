from typing import Optional, List, Dict, Any
import json
import re
import httpx

from app.config import settings


class LLMClient:
    """Async LLM Client for Ollama (via HTTP API).

    This keeps the same public interface as the previous OpenAI client
    (`chat`, `chat_json`, `clear_history`, `get_history_length`).
    """

    def __init__(self):
        self.http = httpx.AsyncClient(base_url=settings.llm_base_url, timeout=30.0)
        self.model = settings.llm_model
        self.conversation_history: List[Dict[str, str]] = []

    async def _call_ollama(self, prompt: str) -> str:
        endpoint = "/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens,
            "stream": False
        }

        try:
            resp = await self.http.post(endpoint, json=payload)
            resp.raise_for_status()
            # print("LLM Response:", resp.text)
            data = resp.json()
            # Try several possible response shapes for compatibility
            if isinstance(data, dict):
                if "generated" in data:
                    gen = data.get("generated")
                    if isinstance(gen, list) and gen:
                        first = gen[0]
                        if isinstance(first, dict):
                            return first.get("content") or first.get("text") or json.dumps(first)
                        if isinstance(first, str):
                            return first
                if "choices" in data:
                    choices = data.get("choices")
                    if isinstance(choices, list) and choices:
                        c = choices[0]
                        if isinstance(c, dict):
                            # Chat-like
                            msg = c.get("message") or c.get("content") or c.get("text")
                            if isinstance(msg, dict):
                                return msg.get("content") or msg.get("text") or json.dumps(msg)
                            if isinstance(msg, str):
                                return msg
                # Common fields
                for key in ("content", "text", "output"):
                    if key in data:
                        val = data.get(key)
                        if isinstance(val, str):
                            return val

            # Fallback: raw text
            return resp.text

        except Exception as e:
            raise Exception(f"LLM Error (Ollama): {e}")

    def _build_prompt(self, system_prompt: str, user_message: str, use_history: bool) -> str:
        parts = [f"System: {system_prompt}"]
        if use_history and self.conversation_history:
            for m in self.conversation_history:
                role = m.get("role", "user")
                content = m.get("content", "")
                parts.append(f"{role.capitalize()}: {content}")
        parts.append(f"User: {user_message}")
        parts.append("Assistant:")
        return "\n\n".join(parts)

    async def chat(
        self,
        system_prompt: str,
        user_message: str,
        use_history: bool = True,
    ) -> str:
        """Send a message to Ollama and get a response (text)."""
        prompt = self._build_prompt(system_prompt, user_message, use_history)
        assistant_message = await self._call_ollama(prompt)

        # Update history
        if use_history:
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            if len(self.conversation_history) > settings.max_history_length:
                self.conversation_history = self.conversation_history[-settings.max_history_length:]

        return assistant_message

    async def chat_json(self, system_prompt: str, user_message: str) -> Dict[str, Any]:
        """Send a message and parse the LLM response as JSON if possible."""
        response = await self.chat(system_prompt, user_message, use_history=settings.use_conversation_history)
        response=json.loads(response)["response"]
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            patterns = [r'```json\s*([\s\S]*?)\s*```', r'```\s*([\s\S]*?)\s*```', r'\{[\s\S]*\}']
            for pattern in patterns:
                match = re.search(pattern, response)
                if match:
                    json_str = match.group(1) if match.lastindex else match.group(0)
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        continue
            print("Failed to parse JSON from LLM response.")
            raise Exception("Failed to parse JSON from LLM response")

    def clear_history(self):
        self.conversation_history = []

    def get_history_length(self) -> int:
        return len(self.conversation_history)


# Singleton instance
llm_client = LLMClient()