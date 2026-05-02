#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT}"

FE_PKG="finus_nat"

FE_PKG_ABS="${ROOT}/${FE_PKG}"
_nat_sh="${FE_PKG_ABS}/.venv/bin/nat"
if [[ -f "${_nat_sh}" ]]; then
  _py_line="$(head -1 "${_nat_sh}" || true)"
  _py="${_py_line/#\#!/}"
  if [[ -n "${_py}" && ! -x "${_py}" ]]; then
    echo "Removing stale ${FE_PKG}/.venv (nat launcher pointed at missing Python)." >&2
    rm -rf "${FE_PKG_ABS}/.venv"
  fi
fi

_default_uv_cache="${HOME}/.cache/uv"
if [[ -z "${UV_CACHE_DIR:-}" ]] && [[ -e "${_default_uv_cache}" ]] && [[ ! -w "${_default_uv_cache}" ]]; then
  export UV_CACHE_DIR="${HOME}/.cache/uv-${USER}"
fi

# Optional local secrets (fin-us/backend/.env is used by the Fin-Us backend stack)
for _env in "${ROOT}/backend/.env" "${ROOT}/.env"; do
  if [[ -f "${_env}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${_env}"
    set +a
  fi
done

# common.yml reads OPENAI_API_BASE_URL; backend .env often sets OPENAI_BASE_URL (OpenRouter, etc.)
if [[ -z "${OPENAI_API_BASE_URL:-}" && -n "${OPENAI_BASE_URL:-}" ]]; then
  export OPENAI_API_BASE_URL="${OPENAI_BASE_URL}"
fi

# Mem0 등 NAT 전용 비밀: finus_nat/.env 를 마지막에 로드해 fin-us/.env 보다 우선한다.
if [[ -f "${FE_PKG_ABS}/.env" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${FE_PKG_ABS}/.env"
  set +a
fi

# Self-hosted Mem0 compatibility for local `run.sh` execution:
# mem0 OSS endpoints may not implement cloud `/v1/ping` validation.
if [[ -n "${FINUS_MEM0_HOST:-}" || -n "${MEM0_API_KEY:-}" ]]; then
  uv run --project "${FE_PKG}" python - <<'PY'
from pathlib import Path

target = Path("finus_nat/.venv/lib/python3.12/site-packages/nat/plugins/mem0ai/memory.py")
if not target.exists():
    raise SystemExit(0)

text = target.read_text()
old = """    mem0_api_key = os.environ.get("MEM0_API_KEY")\n\n    if mem0_api_key is None:\n        raise RuntimeError("Mem0 API key is not set. Please specify it in the environment variable 'MEM0_API_KEY'.")\n\n    mem0_client = AsyncMemoryClient(api_key=mem0_api_key,\n                                    host=config.host,\n                                    org_id=config.org_id,\n                                    project_id=config.project_id)\n"""
new = """    mem0_api_key = os.environ.get("MEM0_API_KEY")\n\n    if mem0_api_key is None:\n        if config.host:\n            mem0_api_key = "selfhost-mem0-static-key"\n        else:\n            raise RuntimeError("Mem0 API key is not set. Please specify it in the environment variable 'MEM0_API_KEY'.")\n\n    if config.host:\n        original_validate = AsyncMemoryClient._validate_api_key\n\n        def _skip_validate(self):\n            return "selfhost-user"\n\n        AsyncMemoryClient._validate_api_key = _skip_validate\n        try:\n            mem0_client = AsyncMemoryClient(api_key=mem0_api_key,\n                                            host=config.host,\n                                            org_id=config.org_id,\n                                            project_id=config.project_id)\n        finally:\n            AsyncMemoryClient._validate_api_key = original_validate\n    else:\n        mem0_client = AsyncMemoryClient(api_key=mem0_api_key,\n                                        host=config.host,\n                                        org_id=config.org_id,\n                                        project_id=config.project_id)\n"""

if old in text and new not in text:
    target.write_text(text.replace(old, new, 1))

client_target = Path("finus_nat/.venv/lib/python3.12/site-packages/mem0/client/main.py")
if client_target.exists():
    client_text = client_target.read_text()
    client_old = """        response = await self.async_client.post("/v1/memories/", json=payload)\n"""
    client_new = """        endpoint = "/memories" if self.host and "api.mem0.ai" not in self.host else "/v1/memories/"\n        response = await self.async_client.post(endpoint, json=payload)\n"""
    if client_old in client_text and client_new not in client_text:
        client_text = client_text.replace(client_old, client_new, 1)

    client_old = """        response = await self.async_client.post(f"/{version}/memories/search/", json=payload)\n"""
    client_new = """        endpoint = "/search" if self.host and "api.mem0.ai" not in self.host else f"/{version}/memories/search/"\n        response = await self.async_client.post(endpoint, json=payload)\n"""
    if client_old in client_text and client_new not in client_text:
        client_text = client_text.replace(client_old, client_new, 1)

    client_target.write_text(client_text)

editor_target = Path("finus_nat/.venv/lib/python3.12/site-packages/nat/plugins/mem0ai/mem0_editor.py")
if editor_target.exists():
    editor_text = editor_target.read_text()
    editor_old = """        user_id = kwargs.pop("user_id")  # Ensure user ID is in keyword arguments\n\n        search_result = await self._client.search(query, user_id=user_id, top_k=top_k, output_format="v1.1", **kwargs)\n"""
    editor_new = """        user_id = kwargs.pop("user_id")  # Ensure user ID is in keyword arguments\n        search_kwargs = dict(kwargs)\n\n        host = getattr(self._client, "host", "") or ""\n        if "api.mem0.ai" in host:\n            search_kwargs["user_id"] = user_id\n        else:\n            search_kwargs["filters"] = {"user_id": user_id}\n\n        search_result = await self._client.search(query, top_k=top_k, output_format="v1.1", **search_kwargs)\n"""
    if editor_old in editor_text and editor_new not in editor_text:
        editor_text = editor_text.replace(editor_old, editor_new, 1)
        editor_target.write_text(editor_text)

agent_target = Path("finus_nat/.venv/lib/python3.12/site-packages/nat/plugins/langchain/agent/auto_memory_wrapper/agent.py")
if agent_target.exists():
    agent_text = agent_target.read_text()
    agent_old = """        user_manager = self._context.user_manager\n"""
    agent_new = """        user_manager = getattr(self._context, "user_manager", None)\n"""
    if agent_old in agent_text and agent_new not in agent_text:
        agent_text = agent_text.replace(agent_old, agent_new, 1)

    agent_old = """        if self._context.metadata and self._context.metadata.headers:\n            user_id = self._context.metadata.headers.get("x-user-id")\n"""
    agent_new = """        metadata = getattr(self._context, "metadata", None)\n        headers = getattr(metadata, "headers", None)\n        if headers:\n            user_id = headers.get("x-user-id")\n"""
    if agent_old in agent_text and agent_new not in agent_text:
        agent_text = agent_text.replace(agent_old, agent_new, 1)

    agent_target.write_text(agent_text)
PY
fi

uv run --project "${FE_PKG}" nat run --config_file "${FE_PKG}/configs/router.yml" --input "${1:-Hello}"
