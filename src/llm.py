import os
import logging
import abc
from typing import List, Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

import httpx
from openai import AsyncOpenAI
import anthropic

logger = logging.getLogger(__name__)

DEFAULT_LLM_TIMEOUT = 60.0
DEFAULT_MAX_TOKENS = 4000

class LLMProvider(Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


@dataclass
class LLMResponse:
    content: str
    usage: Dict[str, int]
    model: str


class BaseLLM(abc.ABC):
    timeout: float = DEFAULT_LLM_TIMEOUT

    @abc.abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stream: bool = False,
    ) -> LLMResponse:
        pass

    @abc.abstractmethod
    async def stream_generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> AsyncGenerator[str, None]:
        pass

    @classmethod
    async def fetch_available_models(cls, api_key: Optional[str] = None, base_url: Optional[str] = None) -> List[str]:
        pass


class OpenAILLM(BaseLLM):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o", timeout: float = DEFAULT_LLM_TIMEOUT):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        self.model = model
        self.timeout = timeout
        self.client = AsyncOpenAI(api_key=self.api_key, timeout=httpx.Timeout(timeout))

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stream: bool = False,
    ) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )

        return LLMResponse(
            content=response.choices[0].message.content or "",
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            },
            model=response.model,
        )

    async def stream_generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> AsyncGenerator[str, None]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @classmethod
    async def fetch_available_models(cls, api_key: Optional[str] = None, base_url: Optional[str] = None) -> List[str]:
        if not api_key:
            return ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]
        try:
            client = AsyncOpenAI(api_key=api_key, timeout=httpx.Timeout(5.0))
            models = await client.models.list()
            return sorted([m.id for m in models.data if m.id.startswith("gpt") or m.id.startswith("o1") or m.id.startswith("o3")])
        except Exception as e:
            logger.error(f"OpenAI model fetch error: {e}")
            return ["gpt-4o", "gpt-4o-mini"]

class AnthropicLLM(BaseLLM):
    def __init__(
        self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022", timeout: float = DEFAULT_LLM_TIMEOUT
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider")
        self.model = model
        self.timeout = timeout
        self.client = anthropic.AsyncAnthropic(api_key=self.api_key, timeout=httpx.Timeout(timeout))

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stream: bool = False,
    ) -> LLMResponse:
        system = None
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
                break

        filtered_messages = [msg for msg in messages if msg["role"] != "system"]

        response = await self.client.messages.create(
            model=self.model,
            system=system,
            messages=filtered_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )

        return LLMResponse(
            content=response.content[0].text,
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
            },
            model=response.model,
        )

    async def stream_generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> AsyncGenerator[str, None]:
        system = None
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
                break

        filtered_messages = [msg for msg in messages if msg["role"] != "system"]

        async with self.client.messages.stream(
            model=self.model,
            system=system,
            messages=filtered_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    @classmethod
    async def fetch_available_models(cls, api_key: Optional[str] = None, base_url: Optional[str] = None) -> List[str]:
        return ["claude-3-7-sonnet-20250219", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229"]


class GeminiLLM(BaseLLM):
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash", timeout: float = DEFAULT_LLM_TIMEOUT):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini provider")
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        self.timeout = timeout
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key, timeout=httpx.Timeout(timeout))

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stream: bool = False,
    ) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )

        return LLMResponse(
            content=response.choices[0].message.content or "",
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            model=response.model,
        )

    async def stream_generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> AsyncGenerator[str, None]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @classmethod
    async def fetch_available_models(cls, api_key: Optional[str] = None, base_url: Optional[str] = None) -> List[str]:
        return ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]


class HuggingFaceLLM(BaseLLM):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "meta-llama/Llama-3.2-3B-Instruct",
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_LLM_TIMEOUT,
    ):
        self.api_key = api_key or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_KEY")
        if not self.api_key:
            raise ValueError("HF_TOKEN or HUGGINGFACE_API_KEY is required for HuggingFace provider")
        self.model = model
        self.base_url = base_url or "https://api-inference.huggingface.co/v1/"
        self.timeout = timeout
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key, timeout=httpx.Timeout(timeout))

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stream: bool = False,
    ) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )

        return LLMResponse(
            content=response.choices[0].message.content or "",
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            model=response.model,
        )

    async def stream_generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> AsyncGenerator[str, None]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @classmethod
    async def fetch_available_models(cls, api_key: Optional[str] = None, base_url: Optional[str] = None) -> List[str]:
        return ["meta-llama/Llama-3.2-3B-Instruct", "meta-llama/Llama-3.1-8B-Instruct", "Qwen/Qwen2-7B-Instruct"]


class OllamaLLM(BaseLLM):
    def __init__(
        self,
        model: str = "gemma4:e2b",
        base_url: str = "http://localhost:11434/v1",
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_LLM_TIMEOUT,
    ):
        self.model = model
        self.base_url = base_url
        self.api_key = api_key or os.getenv("OLLAMA_API_KEY", "ollama")
        self.timeout = timeout
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key, timeout=httpx.Timeout(timeout))

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stream: bool = False,
    ) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )

        return LLMResponse(
            content=response.choices[0].message.content or "",
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            model=response.model,
        )

    async def stream_generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> AsyncGenerator[str, None]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @classmethod
    async def fetch_available_models(cls, api_key: Optional[str] = None, base_url: Optional[str] = None) -> List[str]:
        url = base_url or "http://localhost:11434/v1"
        target = url.replace("/v1", "/api/tags")
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(target, timeout=5.0)
                resp.raise_for_status()
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception as e:
            logger.error(f"Ollama model fetch error: {e}")
            return ["gemma4:e2b", "llama3.2"]


class NvidiaLLM(BaseLLM):
    def __init__(
        self,
        model: str = "deepseek-ai/deepseek-v3.2",
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_LLM_TIMEOUT,
    ):
        self.model = model
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is required for Nvidia provider")
        self.timeout = timeout
        self.base_url = "https://integrate.api.nvidia.com/v1"
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key, timeout=httpx.Timeout(timeout))

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stream: bool = False,
    ) -> LLMResponse:
        extra_body = {}
        if "deepseek" in self.model.lower():
            extra_body["chat_template_kwargs"] = {"thinking": True}
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            top_p=0.95,
            max_tokens=max_tokens,
            stream=stream,
            extra_body=extra_body if extra_body else None,
        )

        return LLMResponse(
            content=response.choices[0].message.content or "",
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            model=response.model,
        )

    async def stream_generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> AsyncGenerator[str, None]:
        extra_body = {}
        if "deepseek" in self.model.lower():
            extra_body["chat_template_kwargs"] = {"thinking": True}
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            top_p=0.95,
            max_tokens=max_tokens,
            stream=True,
            extra_body=extra_body if extra_body else None,
        )

        async for chunk in response:
            reasoning = getattr(chunk.choices[0].delta, "reasoning", None) or getattr(
                chunk.choices[0].delta, "reasoning_content", None
            )
            if reasoning:
                yield f"[REASONING]{reasoning}[/REASONING]"
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @classmethod
    async def fetch_available_models(cls, api_key: Optional[str] = None, base_url: Optional[str] = None) -> List[str]:
        return ["deepseek-ai/deepseek-v3.2", "meta/llama-3.1-70b-instruct", "google/gemma-3n-e4b-it"]


class CustomOpenAILLM(BaseLLM):
    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_LLM_TIMEOUT,
    ):
        self.model = model
        self.api_key = api_key or os.getenv("CUSTOM_API_KEY")
        if not self.api_key:
            raise ValueError("CUSTOM_API_KEY is required for custom provider")
        self.base_url = base_url or os.getenv("CUSTOM_BASE_URL")
        if not self.base_url:
            raise ValueError("base_url or CUSTOM_BASE_URL is required for custom provider")
        self.timeout = timeout
        self.client = AsyncOpenAI(base_url=self.base_url, api_key=self.api_key, timeout=httpx.Timeout(timeout))

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stream: bool = False,
    ) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
        )
        return LLMResponse(
            content=response.choices[0].message.content or "",
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
            model=response.model,
        )

    async def stream_generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> AsyncGenerator[str, None]:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @classmethod
    async def fetch_available_models(cls, api_key: Optional[str] = None, base_url: Optional[str] = None) -> List[str]:
        return ["custom-model"]


class LLMFactory:
    @staticmethod
    def create(
        provider: str = "ollama",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_LLM_TIMEOUT,
    ) -> BaseLLM:
        if provider == "openai":
            return OpenAILLM(api_key=api_key, model=model or "gpt-4o", timeout=timeout)
        elif provider == "anthropic":
            return AnthropicLLM(
                api_key=api_key, model=model or "claude-3-5-sonnet-20241022", timeout=timeout
            )
        elif provider == "gemini":
            return GeminiLLM(api_key=api_key, model=model or "gemini-2.0-flash", timeout=timeout)
        elif provider == "huggingface":
            return HuggingFaceLLM(
                api_key=api_key, base_url=base_url, model=model or "meta-llama/Llama-3.2-3B-Instruct", timeout=timeout
            )
        elif provider == "ollama":
            return OllamaLLM(
                model=model or "gemma4:e2b",
                base_url=base_url or "http://localhost:11434/v1",
                api_key="ollama",
                timeout=timeout,
            )
        elif provider == "nvidia":
            return NvidiaLLM(
                model=model or "deepseek-ai/deepseek-v3.2",
                api_key=api_key,
                timeout=timeout,
            )
        elif provider == "custom":
            return CustomOpenAILLM(
                model=model or "custom-model",
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")


llm_factory = LLMFactory()