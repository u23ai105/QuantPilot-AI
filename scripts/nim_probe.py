"""Probe NVIDIA's hosted chat models; requires only openai and NVIDIA_API_KEY."""

import json
import logging
import os
import re
import sys
import time

from openai import APIStatusError, OpenAI

BASE_URL = "https://integrate.api.nvidia.com/v1"
REQUEST_INTERVAL_SECONDS = 1.6
CANDIDATES = (
    ("GLM", r"(?:^|/)glm[-\d]"),
    ("DeepSeek V4 Flash", r"(?:^|/)deepseek[-_]v4[-_]flash(?:[-_]|$)"),
    ("Nemotron 3 Ultra", r"(?:^|/)nemotron[-_]3[-_]ultra(?:[-_]|$)"),
    ("Kimi K3", r"(?:^|/)kimi[-_]k3(?:[-_]|$)"),
    ("MiniMax M3", r"(?:^|/)minimax[-_]m3(?:[-_]|$)"),
    ("Llama 3.3 70B", r"(?:^|/)llama[-_]3\.3[-_]70b(?:[-_]|$)"),
    ("Qwen", r"(?:^|/)qwen[-\d]"),
)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_integers",
            "description": "Add two integers.",
            "parameters": {
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
        },
    }
]


def select_candidates(model_ids: list[str]) -> list[tuple[str, str | None]]:
    selected = []
    for label, pattern in CANDIDATES:
        matches = [
            model_id
            for model_id in model_ids
            if re.search(pattern, model_id, re.IGNORECASE) and not re.search(r"embed|rerank|guard|(?:^|-)vl(?:-|$)", model_id, re.IGNORECASE)
        ]
        matches.sort(key=lambda value: [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", value)])
        selected.append((label, matches[-1] if matches else None))
    return selected


def error_status(exc: Exception) -> str:
    if isinstance(exc, APIStatusError):
        return f"FAIL HTTP {exc.status_code}"
    return f"FAIL {type(exc).__name__}"


def probe_model(client: OpenAI, model: str) -> tuple[str, str, str]:
    results = []
    for mode in ("plain", "tool", "stream"):
        time.sleep(REQUEST_INTERVAL_SECONDS)
        try:
            if mode == "tool":
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Call add_integers with a=2 and b=3. Do not calculate it yourself."}],
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0,
                    max_tokens=4096,
                )
                calls = response.choices[0].message.tool_calls if response.choices else None
                passed = bool(
                    calls
                    and len(calls) == 1
                    and calls[0].id
                    and calls[0].function.name == "add_integers"
                    and json.loads(calls[0].function.arguments) == {"a": 2, "b": 3}
                )
                results.append("PASS" if passed else "FAIL tool call")
            elif mode == "stream":
                with client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Reply with only NIM_OK. No explanation or tool use."}],
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0,
                    max_tokens=4096,
                    stream=True,
                ) as stream:
                    text = "".join(chunk.choices[0].delta.content or "" for chunk in stream if chunk.choices)
                results.append("PASS" if text.strip() else "FAIL empty text")
            else:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Reply with only NIM_OK. No explanation."}],
                    temperature=0,
                    max_tokens=4096,
                )
                text = response.choices[0].message.content if response.choices else None
                results.append("PASS" if text and text.strip() else "FAIL empty text")
        except Exception as exc:
            results.append(error_status(exc))
    return tuple(results)


def print_table(rows: list[tuple[str, str, str, str, str]]) -> None:
    headers = ("Candidate", "Model ID", "Plain", "Tool", "Stream")
    widths = [max(len(row[i]) for row in [headers, *rows]) for i in range(len(headers))]
    for row in [headers, tuple("-" * width for width in widths), *rows]:
        print("  ".join(value.ljust(width) for value, width in zip(row, widths)), flush=True)


def main() -> int:
    logging.getLogger("openai").setLevel(logging.CRITICAL)
    logging.getLogger("httpx").setLevel(logging.CRITICAL)
    api_key = os.environ.get("NVIDIA_API_KEY", "").strip()
    if not api_key:
        print("NVIDIA_API_KEY is not set. Export it in the environment; do not put it in this script.", file=sys.stderr)
        return 2

    rows = []
    with OpenAI(api_key=api_key, base_url=BASE_URL, timeout=60, max_retries=0) as client:
        try:
            model_ids = sorted(model.id for model in client.models.list().data)
        except Exception as exc:
            print(f"GET /v1/models: {error_status(exc)}", file=sys.stderr)
            return 2
        print(f"GET /v1/models: {len(model_ids)} models", flush=True)
        for model_id in model_ids:
            print(f"  {model_id}", flush=True)
        print("\nGLM/Qwen: choose the highest natural-sort matching chat ID; do not substitute other requested versions.", flush=True)
        for label, model_id in select_candidates(model_ids):
            if model_id is None:
                rows.append((label, "NOT LISTED", "SKIP", "SKIP", "SKIP"))
                continue
            print(f"Probing {label}: {model_id}", flush=True)
            rows.append((label, model_id, *probe_model(client, model_id)))

    print("\nNVIDIA NIM probe results", flush=True)
    print_table(rows)
    passed = [row[1] for row in rows if row[2:] == ("PASS", "PASS", "PASS")]
    print("\nPassed all three checks: " + (", ".join(passed) if passed else "none"), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
