"""Run independent trials with the request bodies and CLI arguments from the release."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parent
PROTOCOLS = json.loads((ROOT / "data/protocols.json").read_bytes())


def run_codex(model, protocol):
    with tempfile.TemporaryDirectory() as work, tempfile.TemporaryDirectory() as out:
        reply_file = Path(out) / "reply"
        args = [{"{workdir}": work, "{reply_file}": str(reply_file)}.get(arg, arg)
                for arg in protocol["args"]]
        result = subprocess.run([os.getenv("CODEX_BIN", "codex"), *args],
                                capture_output=True, timeout=360)
        events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith(b"{")]
        turns = [e for e in events if e.get("type") == "turn.completed"]
        items = [e["item"].get("type") for e in events if e.get("type") == "item.completed"]
        if result.returncode or len(turns) != 1 or "web_search" in items:
            raise RuntimeError("Incomplete Codex trial")
        return reply_file.read_text(encoding="utf8"), turns[0]["usage"]


def run_agy(model, protocol):
    with tempfile.TemporaryDirectory() as work:
        agent = Path(work) / ".agents/agents/bench.md"
        agent.parent.mkdir(parents=True)
        agent.write_text(protocol["agent_definition"], encoding="utf8")
        command = [os.getenv("AGY_BIN", "agy"), "--agent", "bench", "--model", model,
                   "--effort", "high", "--settings", json.dumps(protocol["settings"]),
                   "--output-format", "stream-json", "--disable-slash-commands",
                   "--print-timeout", "160s", "-p", protocol["prompt"]]
        response = subprocess.run(command, cwd=work, capture_output=True, timeout=195, check=True)
        events = [json.loads(line) for line in response.stdout.splitlines() if line.strip()]
        result = events[-1]["result"]
        steps = {e["step_update"]["step_type"] for e in events if "step_update" in e}
        if (events[0]["init"]["model"] != model or result["status"] != "SUCCESS"
                or result["num_turns"] != 1 or steps != {"user_input", "agent_response"}):
            raise ValueError("Incomplete trial or unexpected tool activity")
        return result["response"], result["usage"]


def run_api(model, protocol):
    provider = protocol["provider"]
    key = os.environ[provider.upper() + "_API_KEY"]
    headers = {"Content-Type": "application/json"}
    if provider == "gemini":
        url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent"
        headers["x-goog-api-key"] = key
    elif provider == "qwen":
        url = os.environ["QWEN_BASE_URL"].rstrip("/") + "/v1/messages"
        headers.update({"x-api-key": key, "Authorization": "Bearer " + key,
                        "anthropic-version": "2023-06-01"})
    else:
        bases = {"xai": "https://api.x.ai/v1", "paratera": "https://llmapi.paratera.com/v1"}
        base = os.environ["GLM_BASE_URL"] if provider == "glm" else bases[provider]
        url = base.rstrip("/") + "/chat/completions"
        headers["Authorization"] = "Bearer " + key
    body = json.dumps(protocol["request"], ensure_ascii=False).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers), timeout=720) as resp:
        result = json.load(resp)
    if provider == "gemini":
        candidate = result["candidates"][0]
        if candidate["finishReason"] != "STOP" or candidate.get("groundingMetadata"):
            raise ValueError("Incomplete or grounded Gemini trial")
        parts = candidate["content"]["parts"]
        reply = "".join(part.get("text", "") for part in parts if not part.get("thought"))
        return reply, result["usageMetadata"]
    if result["model"] != model:
        raise ValueError("Unexpected response model")
    if provider == "qwen":
        if result["stop_reason"] != "end_turn":
            raise ValueError("Incomplete Qwen trial")
        reply = "".join(p["text"] for p in result["content"] if p["type"] == "text")
    else:
        choice = result["choices"][0]
        if choice["finish_reason"] != "stop" or choice["message"].get("tool_calls"):
            raise ValueError("Incomplete or tool-using trial")
        reply = choice["message"]["content"]
    return reply, result["usage"]


def trial(job):
    model, number, directory = job
    folder = directory / model
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{number:02}.json"
    if target.exists() and json.loads(target.read_bytes())["ok"]:
        return True
    record = {"model": model, "trial": number, "ok": False}
    protocol = PROTOCOLS[model]
    try:
        run = {"codex": run_codex, "agy": run_agy}.get(protocol["provider"], run_api)
        reply, usage = run(model, protocol)
        if not reply.strip() or not usage:
            raise ValueError("Missing reply or usage")
        record.update(ok=True, reply=reply, hit="大狗叫" in reply, usage=usage)
    except urllib.error.HTTPError as exc:
        record.update(error="HTTPError", http_status=exc.code)
    except Exception as exc:
        record.update(error=type(exc).__name__)
    with tempfile.NamedTemporaryFile("w", dir=folder, delete=False, encoding="utf8") as stream:
        json.dump(record, stream, ensure_ascii=False)
    os.replace(stream.name, target)
    print(model, number, "ok" if record["ok"] else record["error"], flush=True)
    return record["ok"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", choices=sorted(PROTOCOLS))
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--output", type=Path, default=ROOT / "runs")
    args = parser.parse_args()
    jobs = [(model, i, args.output) for model in dict.fromkeys(args.models) for i in range(1, 11)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        raise SystemExit(0 if all(list(pool.map(trial, jobs))) else 1)
