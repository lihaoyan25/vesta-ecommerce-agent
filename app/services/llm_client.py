"""DeepSeek LLM 客户端

封装 OpenAI 兼容的 /chat/completions 接口, 支持流式输出与 function calling
仅做协议层封装, 不含任何业务逻辑
"""
import json
from typing import AsyncIterator, List, Dict, Any, Optional
import httpx

from app.config import settings


class LLMError(Exception):
    """LLM 调用异常"""


class LLMClient:
    """DeepSeek 流式客户端(单例复用即可, 无状态)"""

    def __init__(self):
        self.base_url = settings.DEEPSEEK_BASE_URL.rstrip("/")
        self.api_key = settings.DEEPSEEK_API_KEY
        self.model = settings.DEEPSEEK_MODEL

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[dict]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """流式对话

        逐块 yield: 
          {"type": "delta", "content": "..."}                      # 文本增量
          {"type": "tool_calls", "tool_calls": [ {id,name,arguments} ]}  # 流结束时一次性给出
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": settings.DEEPSEEK_TEMPERATURE,
            "max_tokens": settings.DEEPSEEK_MAX_TOKENS,
            "top_p": settings.DEEPSEEK_TOP_P,
            "stream": True,
            # 思考模式显式开关(服务端默认 enabled, 不传会默认开启深度思考, 延迟与成本翻倍)
            "thinking": {"type": "enabled" if settings.DEEPSEEK_THINKING else "disabled"},
        }
        if tools:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(connect=30, read=180, write=30, pool=30)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", f"{self.base_url}/chat/completions", json=payload, headers=headers
                ) as resp:
                    if resp.status_code != 200:
                        body = (await resp.aread()).decode("utf-8", "ignore")
                        raise LLMError(f"LLM 接口返回 {resp.status_code}: {body[:200]}")

                    # 累积分片 tool_calls(按 index 聚合, id/name/arguments 分片到达)
                    tool_acc: Dict[int, Dict[str, str]] = {}

                    async for line in resp.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if not data or data == "[DONE]":
                            if data == "[DONE]":
                                break
                            continue

                        chunk = json.loads(data)
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}

                        if delta.get("content"):
                            yield {"type": "delta", "content": delta["content"]}

                        for tc in delta.get("tool_calls") or []:
                            idx = tc.get("index", 0)
                            acc = tool_acc.setdefault(idx, {"id": "", "name": "", "arguments": ""})
                            if tc.get("id"):
                                acc["id"] = tc["id"]
                            fn = tc.get("function") or {}
                            if fn.get("name"):
                                acc["name"] = fn["name"]
                            if fn.get("arguments"):
                                acc["arguments"] += fn["arguments"]

                    if tool_acc:
                        yield {
                            "type": "tool_calls",
                            "tool_calls": [tool_acc[i] for i in sorted(tool_acc)],
                        }
        except httpx.HTTPError as e:
            raise LLMError(f"LLM 连接失败: {e}") from e


# 模块级单例
llm_client = LLMClient()

# 复用的请求超时配置
_TIMEOUT = httpx.Timeout(connect=30, read=180, write=30, pool=30)


def chat_completion_sync(
    messages: List[Dict[str, Any]],
    *,
    temperature: float = 0.0,
    thinking: bool = False,
) -> str:
    """非流式对话(内部任务专用, 如 Text2SQL 生成) 

    与流式接口相互独立: 思考模式由参数显式指定, 不读全局开关 
    """
    payload = {
        "model": llm_client.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": settings.DEEPSEEK_MAX_TOKENS,
        "stream": False,
        "thinking": {"type": "enabled" if thinking else "disabled"},
    }
    headers = {
        "Authorization": f"Bearer {llm_client.api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(
                f"{llm_client.base_url}/chat/completions", json=payload, headers=headers
            )
    except httpx.HTTPError as e:
        raise LLMError(f"LLM 连接失败: {e}") from e

    if resp.status_code != 200:
        raise LLMError(f"LLM 接口返回 {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as e:
        raise LLMError(f"LLM 响应格式异常: {e}") from e
