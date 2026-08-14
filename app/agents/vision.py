"""Vision agent: screenshots, scanned pages, PPT/PDF images via local Ollama vision."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx

from app.agents.base import Blackboard
from app.config import settings
from app.llm import ping_ollama


PROMPT = (
    "Extract every readable requirement, test step, table cell, ID, and expected result from this image. "
    "Write plain text. If it is a screenshot of a spec or test sheet, transcribe it faithfully."
)


def _describe(path: Path) -> str:
    data = path.read_bytes()
    if len(data) > 8_000_000:
        return f"[image too large to send to local vision model: {path.name}]"
    b64 = base64.b64encode(data).decode("ascii")
    url = settings.ollama_host.rstrip("/") + "/api/chat"
    payload = {
        "model": settings.ollama_vision_model,
        "stream": False,
        "messages": [{"role": "user", "content": PROMPT, "images": [b64]}],
    }
    with httpx.Client(timeout=180.0) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        body = resp.json()
    return str((body.get("message") or {}).get("content") or "").strip()


class VisionAgent:
    name = "vision_agent"
    role = "Read images, scans, and screenshots with a local vision model"

    def run(self, board: Blackboard) -> None:
        status = ping_ollama()
        vision_ok = bool(status.get("ok") and status.get("vision_present"))
        seen: set[str] = set()
        n = 0
        skipped = 0
        for lane, docs in (("req", board.req_docs), ("test", board.test_docs)):
            for doc in docs:
                if doc.modality not in {"vision", "mixed"} and not doc.images:
                    continue
                chunks: list[str] = []
                for img in doc.images:
                    key = str(img)
                    if key in seen:
                        continue
                    seen.add(key)
                    if not vision_ok:
                        chunks.append(f"[vision skipped — pull {settings.ollama_vision_model}: {img.name}]")
                        skipped += 1
                        continue
                    try:
                        board.log(self.name, self.role, "image", f"reading {img.name}")
                        chunks.append(f"## {img.name}\n{_describe(img)}")
                        n += 1
                    except Exception as exc:
                        chunks.append(f"[vision error {img.name}: {exc}]")
                        skipped += 1
                if chunks:
                    board.vision_text[f"{lane}:{doc.source_name}"] = "\n\n".join(chunks)
        board.log(
            self.name,
            self.role,
            "images_read",
            f"{n} images described with {settings.ollama_vision_model}; {skipped} skipped",
        )
