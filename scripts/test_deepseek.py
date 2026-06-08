import os
import sys
import time

# Allow running as a script without installing the package
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from energy_system.config.config_loader import load_app_config


def _pick_api_key() -> str | None:
    # Optional: load local .env for demo convenience (ignored by git).
    def _read_text_with_fallback(p: str) -> str:
        try:
            data = open(p, "rb").read()
        except Exception:
            return ""
        for enc in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "utf-16-be"):
            try:
                return data.decode(enc)
            except Exception:
                continue
        return ""

    def _load_env_file(p: str) -> None:
        text = _read_text_with_fallback(p)
        if not text:
            return
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("//") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip().lstrip("\ufeff")
            v = v.strip().strip('"').strip("'")
            if k and v and k not in os.environ:
                os.environ[k] = v

    try:
        _load_env_file(os.path.join(ROOT, ".env"))
        _load_env_file(os.path.join(ROOT, "ai_workspace", "von.env"))
    except Exception:
        pass

    return (
        os.getenv("DEEPSEEK_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("AI_API_KEY", "").strip()
        or None
    )


def _key_source() -> str | None:
    if os.getenv("DEEPSEEK_API_KEY", "").strip():
        return "deepseek"
    if os.getenv("OPENAI_API_KEY", "").strip() or os.getenv("AI_API_KEY", "").strip():
        return "openai"
    return None


def main() -> int:
    api_key = _pick_api_key()
    if not api_key:
        print("Missing API key. Set one of: DEEPSEEK_API_KEY / OPENAI_API_KEY / AI_API_KEY")
        return 2

    cfg, warnings = load_app_config()
    for w in warnings:
        print(f"[config-warning] {w}")

    model = (cfg.ai.model or "").strip()
    base_url = (cfg.ai.api_base or "").strip()

    src = _key_source()
    # Minimal flow: if user provided a DeepSeek key but didn't change params.yaml,
    # do the sensible defaults for DeepSeek.
    if src == "deepseek":
        if (not base_url) or ("openai.com" in base_url):
            base_url = "https://api.deepseek.com/v1"
        if (not model) or model.startswith("gpt-"):
            model = "deepseek-chat"
    else:
        base_url = base_url or "https://api.openai.com/v1"
        model = model or "gpt-4o-mini"

    try:
        import openai  # type: ignore
    except Exception as e:
        print(f"openai package not available: {e}")
        print("Install it in your venv: pip install openai")
        return 3

    client = openai.OpenAI(api_key=api_key, base_url=base_url, timeout=20.0)

    t0 = time.monotonic()
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise assistant."},
                {
                    "role": "user",
                    "content": "Reply with exactly: OK (and nothing else).",
                },
            ],
            temperature=0.0,
            max_tokens=16,
        )
    except Exception as e:
        dt = (time.monotonic() - t0) * 1000
        print(f"CALL FAILED in {dt:.0f} ms")
        print(f"base_url={base_url}")
        print(f"model={model}")
        print(f"error={e}")
        return 1

    dt = (time.monotonic() - t0) * 1000
    content = (resp.choices[0].message.content or "").strip()

    print(f"CALL OK in {dt:.0f} ms")
    print(f"base_url={base_url}")
    print(f"model={model}")
    print(f"reply={content!r}")

    if content == "OK":
        return 0
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
