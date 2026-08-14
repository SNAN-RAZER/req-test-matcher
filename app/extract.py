"""Turn document text into structured requirements and test cases using a local 8B model."""

from __future__ import annotations

import re
from langchain_core.messages import HumanMessage, SystemMessage

from app.ingest import ParsedDoc
from app.llm import chat_llm, parse_json_payload
from app.models import ExtractedItem

REQ_ID = re.compile(r"\b(REQ[-_ ]?\d{1,5}|FR[-_ ]?\d{1,5}|NFR[-_ ]?\d{1,5})\b", re.I)
TC_ID = re.compile(r"\b(TC[-_ ]?\d{1,5}|TEST[-_ ]?\d{1,5}|UT[-_ ]?\d{1,5})\b", re.I)


EXTRACT_SYS = """You extract software requirements or test cases from documents.
Return ONLY valid JSON. No markdown, no commentary.
Keep ids exactly as written when present. Invent a stable id only if none exists.
Never send data anywhere; you are a local assistant."""

REQ_PROMPT = """Extract every distinct requirement from this document.

Return JSON:
{{"items":[{{"id":"REQ-001","title":"short title","text":"full requirement text","priority":"must|should|may"}}]}}

Document name: {name}
Parent document: {parent}

TEXT:
{text}
"""

TC_PROMPT = """Extract every distinct test case from this document.

Return JSON:
{{"items":[{{"id":"TC-001","title":"short title","text":"preconditions, steps, expected result","linked_requirement_ids":["REQ-001"],"expected":"expected result"}}]}}

If a test clearly contradicts itself or has missing expected results, still extract it.

Document name: {name}
Parent document: {parent}

TEXT:
{text}
"""


def _chunk(text: str, max_chars: int = 8000) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        cut = text.rfind("\n", start, end)
        if cut <= start:
            cut = end
        chunks.append(text[start:cut])
        start = cut
    return chunks


def _heuristic_table_items(doc: ParsedDoc, kind: str) -> list[ExtractedItem]:
    items: list[ExtractedItem] = []
    lines = [ln for ln in doc.text.splitlines() if ln.strip()]
    header_idx = None
    for i, ln in enumerate(lines[:40]):
        low = ln.lower()
        if "|" in ln and ("id" in low or "req" in low or "test" in low):
            header_idx = i
            break
    if header_idx is None:
        # ID-prefixed paragraphs
        buf: list[str] = []
        current_id = None
        current_title = ""
        for ln in lines:
            m = (REQ_ID if kind == "requirement" else TC_ID).search(ln)
            if m and (ln.strip().startswith(m.group(0)) or ln.strip().split("|")[0].strip().upper().startswith(m.group(1)[:2].upper())):
                if current_id and buf:
                    items.append(
                        ExtractedItem(
                            id=current_id.upper().replace(" ", "-"),
                            title=current_title,
                            text=" ".join(buf).strip(),
                            source_file=doc.source_name,
                            parent_file=doc.parent_name,
                        )
                    )
                current_id = m.group(0)
                current_title = ln.replace(m.group(0), "").strip(" :-|")[:120]
                buf = [ln]
            elif current_id:
                buf.append(ln)
        if current_id and buf:
            items.append(
                ExtractedItem(
                    id=current_id.upper().replace(" ", "-"),
                    title=current_title,
                    text=" ".join(buf).strip(),
                    source_file=doc.source_name,
                    parent_file=doc.parent_name,
                )
            )
        return items

    headers = [h.strip().lower() for h in lines[header_idx].split("|")]
    for ln in lines[header_idx + 1 :]:
        if set(ln.strip()) <= {"-", "|", " "}:
            continue
        cols = [c.strip() for c in ln.split("|")]
        row = {headers[i]: cols[i] if i < len(cols) else "" for i in range(len(headers))}
        rid = ""
        for key in row:
            if "id" in key:
                rid = row[key]
                break
        if not rid:
            continue
        title = ""
        for key in ("title", "name", "summary"):
            if key in row:
                title = row[key]
                break
        body_parts = [f"{k}: {v}" for k, v in row.items() if v]
        extra = {}
        for key, val in row.items():
            if "req" in key and "id" in key:
                extra["linked_requirement_ids"] = [x.strip() for x in re.split(r"[,;]", val) if x.strip()]
        items.append(
            ExtractedItem(
                id=rid,
                title=title or rid,
                text=" | ".join(body_parts),
                source_file=doc.source_name,
                parent_file=doc.parent_name,
                extra=extra,
            )
        )
    return items


def _llm_extract(doc: ParsedDoc, kind: str) -> list[ExtractedItem]:
    llm = chat_llm()
    prompt_t = REQ_PROMPT if kind == "requirement" else TC_PROMPT
    items: list[ExtractedItem] = []
    for chunk in _chunk(doc.text):
        msg = prompt_t.format(name=doc.source_name, parent=doc.parent_name or "none", text=chunk)
        resp = llm.invoke([SystemMessage(content=EXTRACT_SYS), HumanMessage(content=msg)])
        payload = parse_json_payload(getattr(resp, "content", "") or str(resp))
        if not payload:
            continue
        rows = payload.get("items", payload if isinstance(payload, list) else [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            iid = str(row.get("id") or "").strip()
            text = str(row.get("text") or "").strip()
            if not iid or not text:
                continue
            extra = {k: v for k, v in row.items() if k not in {"id", "title", "text"}}
            items.append(
                ExtractedItem(
                    id=iid,
                    title=str(row.get("title") or iid),
                    text=text,
                    source_file=doc.source_name,
                    parent_file=doc.parent_name,
                    extra=extra,
                )
            )
    return items


def extract_items(docs: list[ParsedDoc], kind: str) -> list[ExtractedItem]:
    collected: list[ExtractedItem] = []
    seen: set[str] = set()
    for doc in docs:
        heuristic = _heuristic_table_items(doc, kind)
        llm_items = _llm_extract(doc, kind)
        # Prefer heuristic rows when they look tabular; otherwise merge both.
        merged = heuristic if len(heuristic) >= 2 else heuristic + llm_items
        if not merged:
            merged = llm_items
        for item in merged:
            key = item.id.strip().upper()
            if key in seen:
                continue
            seen.add(key)
            collected.append(item)
    return collected
