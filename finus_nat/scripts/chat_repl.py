# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Multi-turn REPL for NAT /v1/chat/completions (stdin must be the TTY — not a shell heredoc).

With streaming (default), NAT emits ``intermediate_data:`` SSE events (LLM/tool steps) — shown
as chain-of-thought style traces on stderr. Set FINUS_CHAT_STREAM=0 to disable streaming.
Set FINUS_CHAT_COT=0 to hide intermediate steps only.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASE = os.environ["FINUS_NAT_URL"].rstrip("/")
MODEL = (
    os.environ.get("FINUS_CHAT_MODEL")
    or os.environ.get("NAT_CHAT_MODEL")
    or os.environ.get("OPENAI_CHAT_MODEL")
    or ""
)
INITIAL = (os.environ.get("FINUS_CHAT_INITIAL") or "").strip()
USE_STREAM = os.environ.get("FINUS_CHAT_STREAM", "1").strip().lower() not in ("0", "false", "no")
SHOW_COT = os.environ.get("FINUS_CHAT_COT", "1").strip().lower() not in ("0", "false", "no")
_USE_COLOR = os.environ.get("FINUS_CHAT_COLOR", "1").strip().lower() not in ("0", "false", "no") and sys.stderr.isatty()

_TAG_RE = re.compile(r"<[^>]+>")


def _dim(s: str) -> str:
    if not _USE_COLOR:
        return s
    return f"\033[2m{s}\033[0m"


def _bold(s: str) -> str:
    if not _USE_COLOR:
        return s
    return f"\033[1m{s}\033[0m"


def _strip_markup(payload: str, *, max_len: int = 12000) -> str:
    t = html.unescape(payload or "")
    t = _TAG_RE.sub("", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if len(t) > max_len:
        t = t[: max_len - 3] + "..."
    return t


def _print_intermediate(obj: dict) -> None:
    name = obj.get("name") or "(step)"
    step_type = obj.get("type") or ""
    payload = _strip_markup(str(obj.get("payload") or ""))
    print(file=sys.stderr)
    print(_bold(f"━━ CoT · {name}") + (f"  [{step_type}]" if step_type else ""), file=sys.stderr)
    if payload:
        print(_dim(payload), file=sys.stderr)
    print(_dim("━━"), file=sys.stderr)


def _handle_sse_line(line: str, parts: list[str]) -> None:
    line = line.strip()
    if not line:
        return

    if line.startswith("intermediate_data:"):
        if not SHOW_COT:
            return
        raw = line[len("intermediate_data:") :].strip()
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            print(_dim(f"(unparsed intermediate: {raw[:200]}…)"), file=sys.stderr)
            return
        _print_intermediate(obj)
        return

    if line.startswith("data:"):
        raw = line[len("data:") :].strip()
        if raw == "[DONE]":
            return
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            return
        if isinstance(obj, dict) and obj.get("code") and obj.get("message"):
            print(f"NAT error: {obj.get('message')}", file=sys.stderr)
            return
        for ch in obj.get("choices") or []:
            delta = ch.get("delta") or {}
            c = delta.get("content")
            if isinstance(c, str) and c:
                parts.append(c)
        return

    if line.startswith("{") and '"code"' in line and '"message"' in line:
        try:
            obj = json.loads(line)
            print(f"NAT error: {obj.get('message')}", file=sys.stderr)
        except json.JSONDecodeError:
            pass


def post_stream(messages: list[dict]) -> str:
    body: dict = {"messages": messages, "stream": True}
    if MODEL:
        body["model"] = MODEL
    req = urllib.request.Request(
        f"{BASE}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    parts: list[str] = []
    with urllib.request.urlopen(req, timeout=600) as resp:
        enc = resp.headers.get_content_charset() or "utf-8"
        buf = ""
        while True:
            chunk = resp.read(8192)
            if not chunk:
                break
            buf += chunk.decode(enc, errors="replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                _handle_sse_line(line, parts)
        if buf.strip():
            for piece in buf.split("\n"):
                _handle_sse_line(piece, parts)
    return "".join(parts)


def post_json(messages: list[dict]) -> dict:
    body: dict = {"messages": messages, "stream": False}
    if MODEL:
        body["model"] = MODEL
    req = urllib.request.Request(
        f"{BASE}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.load(resp)


def assistant_text(data: dict) -> str:
    ch = data.get("choices") or []
    if not ch:
        return json.dumps(data, ensure_ascii=False, indent=2)[:8000]
    msg = ch[0].get("message") or {}
    c = msg.get("content")
    if isinstance(c, str):
        return c
    return str(c)


def complete_turn(messages: list[dict]) -> str:
    if USE_STREAM:
        return post_stream(messages)
    return assistant_text(post_json(messages))


def main() -> None:
    mode = "streaming + CoT on stderr" if USE_STREAM else "non-streaming"
    if USE_STREAM and not SHOW_COT:
        mode = "streaming (CoT hidden; FINUS_CHAT_COT=0)"
    print(f"Connected to {BASE} ({mode}). Commands: /exit, /reset", file=sys.stderr)
    if USE_STREAM:
        print(_dim("Tip: FINUS_CHAT_COT=0 hides step traces; FINUS_CHAT_STREAM=0 uses one JSON response."), file=sys.stderr)

    messages: list[dict] = []
    if INITIAL:
        messages.append({"role": "user", "content": INITIAL})
        try:
            reply = complete_turn(messages)
        except urllib.error.HTTPError as e:
            print(e.code, e.read().decode(errors="replace")[:4000], file=sys.stderr)
            raise SystemExit(1) from e
        if not reply.strip() and USE_STREAM:
            print("(empty assistant reply; check NAT logs)", file=sys.stderr)
        print(reply)
        messages.append({"role": "assistant", "content": reply})

    while True:
        try:
            line = input("You> ").strip()
        except EOFError:
            print(file=sys.stderr)
            break
        if not line:
            continue
        low = line.lower()
        if low in ("/exit", "/quit", "exit", "quit"):
            break
        if low == "/reset":
            messages.clear()
            print("(conversation cleared)", file=sys.stderr)
            continue
        messages.append({"role": "user", "content": line})
        try:
            reply = complete_turn(messages)
        except urllib.error.HTTPError as e:
            err = e.read().decode(errors="replace")
            print(f"HTTP {e.code}: {err[:4000]}", file=sys.stderr)
            messages.pop()
            continue
        except Exception as exc:
            print(f"Request failed: {exc}", file=sys.stderr)
            messages.pop()
            continue
        if not reply.strip() and USE_STREAM:
            print("(empty assistant reply; check NAT logs)", file=sys.stderr)
        print(reply)
        messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
