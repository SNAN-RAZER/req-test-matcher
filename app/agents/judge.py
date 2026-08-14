"""Judge agent: candidates come from the knowledge graph, not embeddings."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.base import Blackboard
from app.config import settings
from app.llm import chat_llm, parse_json_payload
from app.models import ExtractedItem, MatchResult

JUDGE_SYS = """You are the Judge Agent. Candidates were selected from a knowledge graph
(shared concepts, cites, nested documents) — not from vector RAG.
Return ONLY JSON:
{"requirement_id":"REQ-x or null","verdict":"aligned|partial|wrong|orphan","rationale":"one short paragraph","issues":["..."]}

Rules:
- aligned: test correctly verifies the requirement.
- partial: related but incomplete or weak expected result.
- wrong: contradicts the requirement, wrong expected result, or cites a missing/fake id.
- orphan: no suitable requirement among the graph neighbors.
"""


def _explicit_link(tc: ExtractedItem) -> list[str]:
    linked = tc.extra.get("linked_requirement_ids") or []
    if isinstance(linked, str):
        linked = [linked]
    return [str(x).strip() for x in linked if str(x).strip()]


class JudgeAgent:
    name = "judge_agent"
    role = "Walk the knowledge graph and flag wrong tests"

    def run(self, board: Blackboard) -> None:
        reqs = {r.id: r for r in board.requirements}
        reqs_upper = {r.id.upper(): r for r in reqs.values()}
        matches: list[MatchResult] = []
        llm = chat_llm()
        kg = board.kg

        for tc in board.test_cases:
            candidates: list[tuple[str, float, str, list[str]]] = []
            seen: set[str] = set()
            for lid in _explicit_link(tc):
                rec = reqs.get(lid) or reqs_upper.get(lid.upper())
                if rec:
                    candidates.append((rec.id, 1.0, f"{rec.id} {rec.title}\n{rec.text}", ["cites"]))
                    seen.add(rec.id)
            if kg is not None:
                for row in kg.candidates_for_test(tc.id, settings.retrieve_k):
                    if row[0] not in seen:
                        candidates.append(row)
                        seen.add(row[0])
            if not candidates:
                matches.append(
                    MatchResult(
                        test_id=tc.id,
                        verdict="orphan",
                        rationale="No graph neighbors linked this test to a requirement.",
                        issues=["No knowledge-graph path"],
                    )
                )
                if kg is not None:
                    kg.apply_verdict(tc.id, None, "orphan")
                board.log(self.name, self.role, "step", f"{tc.id} → orphan")
                continue

            cand_text = "\n\n".join(
                f"- id={cid} graph_score={score:.2f} evidence={','.join(ev)}\n{doc[:1500]}"
                for cid, score, doc, ev in candidates[: settings.retrieve_k]
            )
            prompt = (
                f"TEST CASE id={tc.id} title={tc.title}\n{tc.text}\n\n"
                f"Stated requirement links: {_explicit_link(tc) or 'none'}\n\n"
                f"GRAPH NEIGHBORS:\n{cand_text}\n"
            )
            resp = llm.invoke([SystemMessage(content=JUDGE_SYS), HumanMessage(content=prompt)])
            payload = parse_json_payload(getattr(resp, "content", "") or str(resp)) or {}
            rid = payload.get("requirement_id")
            if rid in {"null", "None", ""}:
                rid = None
            if rid and rid not in reqs and str(rid).upper() in reqs_upper:
                rid = reqs_upper[str(rid).upper()].id
            verdict = payload.get("verdict") or "orphan"
            if verdict not in {"aligned", "partial", "wrong", "orphan"}:
                verdict = "orphan"
            best_score = candidates[0][1] if candidates else 0.0
            if verdict == "aligned" and best_score < settings.match_threshold and not _explicit_link(tc):
                verdict = "partial"
            matches.append(
                MatchResult(
                    test_id=tc.id,
                    requirement_id=rid,
                    score=float(best_score),
                    verdict=verdict,  # type: ignore[arg-type]
                    rationale=str(payload.get("rationale") or ""),
                    issues=[str(x) for x in (payload.get("issues") or [])],
                )
            )
            if kg is not None:
                kg.apply_verdict(tc.id, rid, verdict)
            board.log(
                self.name,
                self.role,
                "step",
                f"{tc.id} → {verdict}" + (f" ({rid})" if rid else ""),
            )

        board.matches = matches
        wrong = sum(1 for m in matches if m.verdict == "wrong")
        board.log(self.name, self.role, "judged", f"{len(matches)} tests via KG, {wrong} marked wrong")
