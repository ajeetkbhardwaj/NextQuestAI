import os
import logging
import abc
from typing import List, Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass
from enum import Enum

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

DEFAULT_LLM_TIMEOUT = 60.0
DEFAULT_MAX_TOKENS = 4000

class LLMProvider(Enum):
    GEMINI = "gemini"
    HUGGINGFACE = "huggingface"
    NVIDIA = "nvidia"
    OPENROUTER = "openrouter"


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
        return ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]


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


class NvidiaLLM(BaseLLM):
    def __init__(
        self,
        model: str = "mistralai/mistral-nemotron",
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
        return [
            "mistralai/mistral-nemotron",
            "meta/llama-4-maverick-17b-128e-instruct",
            "google/gemma-3-27b-it",
            "nvidia/nemotron-3-super-120b-a12b",
            "google/gemma-3n-e4b-it",
            "deepseek-ai/deepseek-v4-flash",
            "meta/llama-3.1-405b-instruct",
        ]


class OpenRouterLLM(BaseLLM):
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "google/gemini-2.0-flash-001",
        timeout: float = DEFAULT_LLM_TIMEOUT,
    ):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            # Don't raise error here, allow it to fail during generate to prevent app crash on model probe
            pass
            
        self.model = model
        self.timeout = timeout
        self.base_url = "https://openrouter.ai/api/v1"
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "sk-dummy",
            timeout=httpx.Timeout(timeout),
            default_headers={
                "HTTP-Referer": "https://github.com/ajeetkbhardwaj/NextQuestAI",
                "X-Title": "NextQuestAI",
            },
        )

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        stream: bool = False,
    ) -> LLMResponse:
        if not self.api_key or self.api_key == "sk-dummy":
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouter provider")
            
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
        if not self.api_key or self.api_key == "sk-dummy":
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouter provider")

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
        return ["google/gemini-2.0-flash-001", "anthropic/claude-3.5-sonnet", "deepseek/deepseek-r1", "meta-llama/llama-3.3-70b-instruct"]


class LLMFactory:
    @staticmethod
    def create(
        provider: str = "nvidia",
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_LLM_TIMEOUT,
    ) -> BaseLLM:
        if provider == "gemini":
            return GeminiLLM(api_key=api_key, model=model or "gemini-2.0-flash", timeout=timeout)
        elif provider == "huggingface":
            return HuggingFaceLLM(
                api_key=api_key, base_url=base_url, model=model or "meta-llama/Llama-3.2-3B-Instruct", timeout=timeout
            )
        elif provider == "nvidia":
            return NvidiaLLM(
                model=model or "mistralai/mistral-nemotron",
                api_key=api_key,
                timeout=timeout,
            )
        elif provider == "openrouter":
            return OpenRouterLLM(
                api_key=api_key,
                model=model or "google/gemini-2.0-flash-001",
                timeout=timeout,
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    @staticmethod
    async def get_models(provider: str, api_key: Optional[str] = None, base_url: Optional[str] = None) -> List[str]:
        if provider == "gemini":
            return await GeminiLLM.fetch_available_models(api_key, base_url)
        elif provider == "huggingface":
            return await HuggingFaceLLM.fetch_available_models(api_key, base_url)
        elif provider == "nvidia":
            return await NvidiaLLM.fetch_available_models(api_key, base_url)
        elif provider == "openrouter":
            return await OpenRouterLLM.fetch_available_models(api_key, base_url)
        return []


llm_factory = LLMFactory()