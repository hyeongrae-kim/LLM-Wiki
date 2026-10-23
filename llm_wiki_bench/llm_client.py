"""LLM client — thin wrapper around any OpenAI-compatible Chat Completions API.

Reads endpoint and credentials from environment variables, so the same code
works against OpenAI, Azure OpenAI, vLLM, Ollama, etc. without modification:

    OPENAI_API_KEY    — bearer token (use a dummy value for local servers)
    OPENAI_BASE_URL   — base URL, default https://api.openai.com/v1

Models are picked up from `bench_config` (see LLM_MODEL / LLM_PREMIUM_MODEL).

Reasoning-family models (OpenAI ``gpt-5*``, ``gpt-6*``, ``o1``/``o3``/``o4``...)
take ``max_completion_tokens`` instead of ``max_tokens`` and a
``reasoning_effort``; sampling parameters are dropped unless the effort is
``none``. Tool calls always use ``reasoning_effort="none"`` because GPT-6
Sol/Luna only support function calling in Chat Completions at that effort.

    LLM_REASONING_EFFORT  effort for text calls on reasoning models (default: low)
    LLM_ENABLE_THINKING   1 to forward ``chat_template_kwargs`` (vLLM GLM/Qwen)
"""

import json
import logging
import os
import re
import time
import requests

import bench_config as config

_llm_logger = logging.getLogger("ingest.llm")

_REASONING_MODEL_RE = re.compile(r"^(gpt-5|gpt-6|o\d)", re.IGNORECASE)


class LLMRequestError(RuntimeError):
    """A non-retryable client error (bad request, auth, unknown model...)."""


def _is_reasoning_model(model: str) -> bool:
    return bool(_REASONING_MODEL_RE.match(model or ""))


def _apply_model_params(payload: dict, model: str, temperature: float | None,
                        max_tokens: int, effort: str | None = None) -> None:
    """Fill sampling / length / reasoning fields appropriate for ``model``."""
    if _is_reasoning_model(model):
        effort = effort or os.environ.get("LLM_REASONING_EFFORT", "low")
        payload["reasoning_effort"] = effort
        # Reasoning tokens count against the completion budget; small budgets
        # written for non-reasoning models (e.g. 256) would leave no room for output.
        payload["max_completion_tokens"] = max_tokens if effort == "none" else max(max_tokens, 4096)
        if effort == "none" and temperature is not None:
            payload["temperature"] = temperature
    else:
        if temperature is not None:
            payload["temperature"] = temperature
        payload["max_tokens"] = max_tokens


def _raise_if_client_error(resp: requests.Response) -> None:
    """Fail fast on 4xx responses that retrying cannot fix."""
    if 400 <= resp.status_code < 500 and resp.status_code not in (408, 409, 429):
        raise LLMRequestError(
            f"LLM request rejected (status={resp.status_code}): {resp.text[:500]}"
        )


def _thinking_enabled() -> bool:
    return os.environ.get("LLM_ENABLE_THINKING", "0") == "1"


def _api_base() -> str:
    return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def _headers() -> dict:
    api_key = os.environ.get("OPENAI_API_KEY", "")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}" if api_key else "",
    }


def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
    expect_json: bool = False,
    timeout: int = 300,
    model: str | None = None,
    enable_thinking: bool = False,
    lang_directive: bool = True,
) -> str:
    """Call an OpenAI-compatible Chat Completions endpoint.

    `enable_thinking` is forwarded only when ``LLM_ENABLE_THINKING=1`` (e.g. local
    vLLM deployments of GLM/Qwen); OpenAI rejects the unknown field.

    When ``WIKI_LANG`` is not English, the output-language directive from
    ``bench_config.language_directive()`` is appended to the system prompt so
    that every wiki-writing prompt (ingest, lint repair, indexing) produces
    content in that language. Pass ``lang_directive=False`` to opt out.
    """
    directive = config.language_directive() if lang_directive else ""
    if directive:
        system_prompt = f"{system_prompt}\n\n{directive}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    use_model = model or config.LLM_MODEL
    url = f"{_api_base()}/chat/completions"

    payload: dict = {"model": use_model, "messages": messages}
    _apply_model_params(
        payload, use_model,
        temperature if temperature is not None else config.LLM_TEMPERATURE,
        max_tokens if max_tokens is not None else config.LLM_MAX_TOKENS,
    )
    if expect_json:
        payload["response_format"] = {"type": "json_object"}
    if enable_thinking and _thinking_enabled():
        # Pass-through fields for backends that support reasoning / thinking mode.
        payload["chat_template_kwargs"] = {"enable_thinking": True}

    _llm_logger.info(
        "LLM call | model=%s | sys=%d chars | user=%d chars | temp=%s | effort=%s",
        use_model, len(system_prompt), len(user_prompt),
        payload.get("temperature"), payload.get("reasoning_effort"),
    )

    MAX_RETRIES = 5
    t_start = time.time()
    last_resp = None

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, headers=_headers(), json=payload, timeout=timeout)
            last_resp = resp
            _raise_if_client_error(resp)
            resp.raise_for_status()

            if not resp.text or not resp.text.strip():
                raise RuntimeError(f"Empty response (status={resp.status_code})")

            data = resp.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            if isinstance(content, list):
                content = "".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )
            # Some providers (GLM, Qwen, DeepSeek) place the answer in
            # `reasoning_content` / `reasoning` when thinking mode is on.
            reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
            if not content.strip() and reasoning.strip():
                content = reasoning

            t_elapsed = time.time() - t_start
            usage = data.get("usage", {})
            _llm_logger.info(
                "LLM done | %.1fs | resp=%d chars | tokens=%s",
                t_elapsed, len(content), usage.get("total_tokens", "?"),
            )
            return content.strip()

        except LLMRequestError:
            raise
        except (requests.RequestException, KeyError, IndexError,
                json.JSONDecodeError, RuntimeError) as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                _llm_logger.warning(
                    "LLM call failed (attempt %d/%d): %s — retrying in %ds",
                    attempt + 1, MAX_RETRIES, e, wait,
                )
                time.sleep(wait)
                continue
            try:
                body = last_resp.text[:500] if last_resp is not None else "?"
                status = last_resp.status_code if last_resp is not None else "?"
                _llm_logger.error("LLM final failure: status=%s body=%s", status, body)
            except Exception:
                pass
            raise RuntimeError(f"LLM call failed after {MAX_RETRIES} retries: {e}") from e


def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float | None = None,
) -> dict:
    """Call the LLM and parse the result as a JSON object.

    Falls back to extracting the first balanced JSON object from the text if
    the provider does not honor `response_format=json_object`.
    """
    try:
        text = call_llm(system_prompt, user_prompt, expect_json=True, model=model, temperature=temperature)
    except RuntimeError:
        text = call_llm(system_prompt, user_prompt, expect_json=False, model=model, temperature=temperature)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    start, end = text.find('{'), text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    raise RuntimeError(f"Cannot parse LLM output as JSON:\n{text[:500]}")


def call_llm_with_tools(
    messages: list[dict],
    tools: list[dict],
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    timeout: int = 300,
) -> dict | None:
    """Call a Chat Completions endpoint with OpenAI-style tool calling.

    Returns the raw assistant message (a dict that may contain `tool_calls`),
    or `None` if all retries fail. Raises `LLMRequestError` on a non-retryable
    client error (e.g. bad API key or unsupported parameter).
    """
    use_model = model or config.LLM_MODEL
    url = f"{_api_base()}/chat/completions"

    payload: dict = {
        "model": use_model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
    }
    _apply_model_params(payload, use_model, temperature, max_tokens, effort="none")

    MAX_RETRIES = 5
    last_resp = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(url, headers=_headers(), json=payload, timeout=timeout)
            last_resp = resp
            _raise_if_client_error(resp)
            resp.raise_for_status()
            if not resp.text or not resp.text.strip():
                raise RuntimeError(f"Empty response (status={resp.status_code})")
            data = resp.json()
            return data["choices"][0]["message"]
        except LLMRequestError:
            raise
        except (requests.RequestException, KeyError, IndexError,
                json.JSONDecodeError, RuntimeError) as e:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** (attempt + 1)
                _llm_logger.warning(
                    "tool-call LLM failed (attempt %d/%d): %s — retrying in %ds",
                    attempt + 1, MAX_RETRIES, e, wait,
                )
                time.sleep(wait)
                continue
            try:
                body = last_resp.text[:500] if last_resp is not None else "?"
                status = last_resp.status_code if last_resp is not None else "?"
                _llm_logger.error("tool-call LLM final failure: status=%s body=%s", status, body)
            except Exception:
                pass
            return None
    return None
