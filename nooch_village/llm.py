from __future__ import annotations
import logging
import os


def reason(prompt: str) -> str | None:
    """Optionele LLM-redenering. Probeert Anthropic, dan Gemini. Geen key -> None
    (dan valt de Field Note terug op deterministische logica)."""
    ak = os.getenv("ANTHROPIC_API_KEY")
    if ak:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ak, timeout=30.0)
            msg = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=700,
                messages=[{"role": "user", "content": prompt}])
            return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
        except Exception as exc:
            logging.warning("LLM Anthropic faalde: %s", exc)
    gk = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gk:
        try:
            from google import genai
            from google.genai import types as genai_types
            client = genai.Client(api_key=gk)
            resp = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=genai_types.GenerateContentConfig(
                    http_options=genai_types.HttpOptions(timeout=30)
                ),
            )
            return (resp.text or "").strip()
        except Exception as exc:
            logging.warning("LLM Gemini faalde: %s", exc)
    return None
