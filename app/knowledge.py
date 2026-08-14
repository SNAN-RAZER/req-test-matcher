"""Local knowledge graph (NetworkX). No vector RAG, no cloud."""

from __future__ import annotations

import json
import re
from pathlib import Path

import networkx as nx

from app.config import settings
from app.models import ExtractedItem

STOP = {
    "the", "and", "for", "with", "that", "this", "from", "shall", "should", "must",
    "after", "then", "when", "user", "system", "into", "onto", "have", "been",
    "will", "via", "using", "each", "also", "only", "than", "them", "they",
}

TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")
ID_TOKEN = re.compile(r"\b(?:REQ|FR|NFR|TC|TEST|UT)[-_ ]?\d{1,5}\b", re.I)


def _nid(kind: str, raw: str) -> str:
    return f"{kind}:{raw.strip()}"


def concept_terms(text: str, limit: int = 24) -> list[str]:
    counts: dict[str, int] = {}
    for tok in TOKEN.findall(text or ""):
        low = tok.lower()
        if low in STOP or low.isdigit():
            continue
        counts[low] = counts.get(low, 0) + 1
    ranked = sorted(counts, key=lambda t: (-counts[t], t))
    return ranked[:limit]


class KnowledgeGraph:
    def __init__(self) -> None:
        self.g = nx.MultiDiGraph()

    def add_node(self, nid: str, **attrs) -> None:
        if self.g.has_node(nid):
            self.g.nodes[nid].update({k: v for k, v in attrs.items() if v is not None})
        else:
            self.g.add_node(nid, **attrs)

    def add_edge(self, src: str, dst: str, rel: str, **attrs) -> None:
        if not src or not dst or src == dst:
            return
        if not self.g.has_node(src) or not self.g.has_node(dst):
            return
        for _, data in self.g.get_edge_data(src, dst, default={}).items():
            if data.get("rel") == rel:
                return
        self.g.add_edge(src, dst, rel=rel, **attrs)

    def add_requirement(self, item: ExtractedItem) -> str:
        nid = _nid("REQ", item.id)
        self.add_node(
            nid,
            kind="requirement",
            label=item.id,
            title=item.title,
            text=item.text[:2000],
            source=item.source_file,
        )
        if item.source_file:
            doc = _nid("DOC", item.source_file)
            self.add_node(doc, kind="document", label=item.source_file)
            self.add_edge(nid, doc, "extracted_from")
            if item.parent_file:
                parent = _nid("DOC", item.parent_file)
                self.add_node(parent, kind="document", label=item.parent_file)
                self.add_edge(doc, parent, "nested_in")
        self._attach_concepts(nid, f"{item.id} {item.title} {item.text}")
        return nid

    def add_test(self, item: ExtractedItem) -> str:
        nid = _nid("TC", item.id)
        self.add_node(
            nid,
            kind="test",
            label=item.id,
            title=item.title,
            text=item.text[:2000],
            source=item.source_file,
        )
        if item.source_file:
            doc = _nid("DOC", item.source_file)
            self.add_node(doc, kind="document", label=item.source_file)
            self.add_edge(nid, doc, "extracted_from")
            if item.parent_file:
                parent = _nid("DOC", item.parent_file)
                self.add_node(parent, kind="document", label=item.parent_file)
                self.add_edge(doc, parent, "nested_in")
        linked = item.extra.get("linked_requirement_ids") or []
        if isinstance(linked, str):
            linked = [linked]
        for lid in linked:
            lid = str(lid).strip()
            if not lid:
                continue
            rid = _nid("REQ", lid)
            if not self.g.has_node(rid):
                self.add_node(rid, kind="requirement", label=lid, missing=True)
            self.add_edge(nid, rid, "cites")
        for m in ID_TOKEN.findall(item.text or ""):
            if m.upper().startswith(("REQ", "FR", "NFR")):
                rid = _nid("REQ", m.upper().replace(" ", "-"))
                if self.g.has_node(rid):
                    self.add_edge(nid, rid, "mentions_id")
        self._attach_concepts(nid, f"{item.id} {item.title} {item.text}")
        return nid

    def _attach_concepts(self, nid: str, text: str) -> None:
        for term in concept_terms(text):
            cid = _nid("CONCEPT", term)
            self.add_node(cid, kind="concept", label=term)
            self.add_edge(nid, cid, "mentions")

    def add_relation(self, src_kind: str, src_id: str, dst_kind: str, dst_id: str, rel: str) -> None:
        self.add_edge(_nid(src_kind, src_id), _nid(dst_kind, dst_id), rel)

    def candidates_for_test(self, test_id: str, k: int = 5) -> list[tuple[str, float, str, list[str]]]:
        """Return (requirement_id, score, text, evidence_rels) via graph neighborhood, not embeddings."""
        tc = _nid("TC", test_id)
        if not self.g.has_node(tc):
            return []
        scores: dict[str, float] = {}
        evidence: dict[str, list[str]] = {}

        def bump(req_nid: str, amount: float, why: str) -> None:
            if not req_nid.startswith("REQ:") or not self.g.has_node(req_nid):
                return
            if self.g.nodes[req_nid].get("missing"):
                bump_missing = amount * 0.2
                scores[req_nid] = scores.get(req_nid, 0) + bump_missing
            else:
                scores[req_nid] = scores.get(req_nid, 0) + amount
            evidence.setdefault(req_nid, []).append(why)

        for _, dst, data in self.g.out_edges(tc, data=True):
            rel = data.get("rel")
            if rel in {"cites", "mentions_id", "tests", "maps_to"}:
                bump(dst, 1.0 if rel == "cites" else 0.85, rel)
            if rel == "mentions" and self.g.nodes[dst].get("kind") == "concept":
                for pred in self.g.predecessors(dst):
                    if pred != tc and self.g.nodes[pred].get("kind") == "requirement":
                        bump(pred, 0.35, f"shared_concept:{self.g.nodes[dst].get('label')}")

        # 2-hop through documents
        for _, doc, data in self.g.out_edges(tc, data=True):
            if data.get("rel") != "extracted_from":
                continue
            for pred in self.g.predecessors(doc):
                if self.g.nodes[pred].get("kind") == "requirement":
                    bump(pred, 0.15, "same_document")

        ranked = sorted(scores.items(), key=lambda kv: -kv[1])[:k]
        out: list[tuple[str, float, str, list[str]]] = []
        for req_nid, score in ranked:
            node = self.g.nodes[req_nid]
            rid = req_nid.split(":", 1)[1]
            text = f"{rid} {node.get('title') or ''}\n{node.get('text') or ''}"
            out.append((rid, float(score), text, evidence.get(req_nid, [])))
        return out

    def apply_verdict(self, test_id: str, requirement_id: str | None, verdict: str) -> None:
        tc = _nid("TC", test_id)
        if not self.g.has_node(tc):
            return
        if requirement_id:
            rid = _nid("REQ", requirement_id)
            if self.g.has_node(rid):
                self.add_edge(tc, rid, verdict)
        self.g.nodes[tc]["verdict"] = verdict

    def snapshot(self, compact: bool = True) -> dict:
        hide: set[str] = set()
        if compact:
            for nid, data in self.g.nodes(data=True):
                if data.get("kind") == "concept" and self.g.degree(nid) < 3:
                    hide.add(nid)
        nodes = []
        for nid, data in self.g.nodes(data=True):
            if nid in hide:
                continue
            nodes.append(
                {
                    "id": nid,
                    "kind": data.get("kind", "unknown"),
                    "label": data.get("label") or nid,
                    "title": data.get("title") or "",
                    "verdict": data.get("verdict") or "",
                }
            )
        edges = []
        for src, dst, data in self.g.edges(data=True):
            if src in hide or dst in hide:
                continue
            edges.append({"source": src, "target": dst, "rel": data.get("rel", "related")})
        return {"nodes": nodes, "edges": edges, "node_count": self.g.number_of_nodes(), "edge_count": self.g.number_of_edges()}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = nx.node_link_data(self.g, edges="links")
        except TypeError:
            payload = nx.node_link_data(self.g)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
