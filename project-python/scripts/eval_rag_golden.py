#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG 黄金集离线评估。

用法:
  python scripts/eval_rag_golden.py --dataset scripts/fixtures/golden_rag_sample.jsonl --dry-run
  python scripts/eval_rag_golden.py --fail-under 0.8
  python scripts/eval_rag_golden.py --mode stub
  python scripts/eval_rag_golden.py --use-ragas

默认 --mode pipeline：将黄金集 contexts 写入向量库，经真实 HybridRetriever + RagService 检索后评分。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 确保从 project-python 根目录可 import app
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

REQUIRED_FIELDS = {"id", "question", "contexts", "ground_truth"}
EVAL_TENANT = "golden-eval"


@dataclass
class GoldenCase:
    id: str
    question: str
    contexts: list[str]
    ground_truth: str
    expected_doc_ids: list[str] | None = None
    should_refuse: bool = False


def load_jsonl(path: Path) -> list[GoldenCase]:
    cases: list[GoldenCase] = []
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"行 {line_no} JSON 无效: {e}") from e
            missing = REQUIRED_FIELDS - set(raw.keys())
            if missing:
                raise ValueError(f"行 {line_no} 缺少字段: {sorted(missing)}")
            if not isinstance(raw["contexts"], list) or not raw["contexts"]:
                raise ValueError(f"行 {line_no} contexts 必须为非空列表")
            cases.append(
                GoldenCase(
                    id=str(raw["id"]),
                    question=str(raw["question"]),
                    contexts=[str(c) for c in raw["contexts"]],
                    ground_truth=str(raw["ground_truth"]),
                    expected_doc_ids=raw.get("expected_doc_ids"),
                    should_refuse=bool(raw.get("should_refuse", False)),
                )
            )
    return cases


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def score_match(pred_text: str, gold: str) -> bool:
    p, g = normalize(pred_text), normalize(gold)
    if not g:
        return False
    if g in p or p in g:
        return True
    # 数字答案（如 7天 vs 7 日内）
    nums = re.findall(r"\d+", g)
    if nums and all(n in p for n in nums):
        return True
    return False


def predict_answer_stub(case: GoldenCase) -> str:
    if case.should_refuse:
        return "根据提供的文档，未提及该信息。"
    joined = " ".join(case.contexts)
    if case.ground_truth in joined:
        return case.ground_truth
    return joined[:80]


async def _build_pipeline(cases: list[GoldenCase]):
    from app.config import get_settings
    from app.core.rag.bm25_registry import TenantBm25Registry
    from app.core.rag.hybrid_retriever import HybridRetriever
    from app.core.rag.service import RagService
    from app.infrastructure.embeddings import get_embedder
    from app.infrastructure.vectordb.base import VectorRecord
    from app.infrastructure.vectordb.factory import build_vector_store

    settings = get_settings()
    store = build_vector_store()
    embedder = get_embedder()
    reg = TenantBm25Registry()
    chunk_ids: list[str] = []

    records: list[VectorRecord] = []
    bm25_map: dict[str, str] = {}
    for case in cases:
        for i, ctx in enumerate(case.contexts):
            cid = f"{case.id}_c{i}"
            chunk_ids.append(cid)
            emb = embedder.embed_documents([ctx])[0]
            records.append(
                VectorRecord(
                    id=cid,
                    content=ctx,
                    embedding=emb,
                    document_id=case.id,
                    metadata={"case_id": case.id},
                )
            )
            bm25_map[cid] = ctx

    if records:
        await store.upsert(records, namespace=EVAL_TENANT)
    reg.replace_tenant_corpus(EVAL_TENANT, bm25_map)

    hybrid = HybridRetriever(store, embedder, reg) if settings.rag_hybrid_enabled else None
    svc = RagService(
        vector_store=store,
        embedder=embedder,
        generator=None,
        hybrid=hybrid,
        tenant_id=EVAL_TENANT,
    )
    return store, chunk_ids, svc


async def predict_via_pipeline(case: GoldenCase, svc) -> str:
    """用真实 RagService 检索，拼接 top 上下文作为「预测文本」供启发式打分。"""
    hits = await svc.retrieve(case.question, top_k=5)
    if not hits:
        return ""
    return "\n".join(h.content for h in hits if h.content)


async def run_pipeline_eval(cases: list[GoldenCase]) -> dict[str, Any]:
    store, chunk_ids, svc = await _build_pipeline(cases)
    hits = 0
    details: list[dict[str, Any]] = []
    try:
        for c in cases:
            pred = await predict_via_pipeline(c, svc)
            if c.should_refuse:
                ok = score_match(pred, c.ground_truth) or "未提及" in pred or "工单" in pred
            else:
                ok = score_match(pred, c.ground_truth)
            hits += int(ok)
            details.append(
                {
                    "id": c.id,
                    "question": c.question,
                    "predicted_excerpt": pred[:200],
                    "ground_truth": c.ground_truth,
                    "pass": ok,
                }
            )
    finally:
        if chunk_ids:
            await store.delete(chunk_ids, namespace=EVAL_TENANT)
        await store.close()

    n = len(cases) or 1
    return {
        "mode": "rag_pipeline_retrieval",
        "total": len(cases),
        "pass": hits,
        "accuracy": round(hits / n, 4),
        "details": details,
    }


def run_heuristic_eval(cases: list[GoldenCase]) -> dict[str, Any]:
    hits = 0
    details: list[dict[str, Any]] = []
    for c in cases:
        pred = predict_answer_stub(c)
        ok = score_match(pred, c.ground_truth)
        hits += int(ok)
        details.append(
            {
                "id": c.id,
                "question": c.question,
                "predicted": pred,
                "ground_truth": c.ground_truth,
                "pass": ok,
            }
        )
    n = len(cases) or 1
    return {
        "mode": "heuristic_substring",
        "total": len(cases),
        "pass": hits,
        "accuracy": round(hits / n, 4),
        "details": details,
    }


def run_ragas_eval(cases: list[GoldenCase]) -> dict[str, Any]:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import answer_relevancy, context_precision, faithfulness
    except ImportError as e:
        raise SystemExit("RAGAS 未安装。请执行: pip install -r requirements-eval.txt") from e

    preds = [predict_answer_stub(c) for c in cases]
    data = {
        "question": [c.question for c in cases],
        "answer": preds,
        "contexts": [c.contexts for c in cases],
        "ground_truth": [c.ground_truth for c in cases],
    }
    ds = Dataset.from_dict(data)
    result = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy, context_precision],
    )
    return {"mode": "ragas", "metrics": dict(result)}


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG golden-set evaluator")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("scripts/fixtures/golden_rag_sample.jsonl"),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--use-ragas", action="store_true")
    parser.add_argument(
        "--mode",
        choices=("pipeline", "stub"),
        default="pipeline",
        help="pipeline=真实 RagService 检索；stub=子串占位",
    )
    parser.add_argument("--fail-under", type=float, default=None)
    args = parser.parse_args()

    if not args.dataset.is_file():
        print(f"数据集不存在: {args.dataset}", file=sys.stderr)
        return 1

    cases = load_jsonl(args.dataset)
    print(f"已加载 {len(cases)} 条黄金样本: {args.dataset}")

    if args.dry_run:
        print("dry-run 通过：字段与 JSON 格式合法。")
        return 0

    if args.use_ragas:
        report = run_ragas_eval(cases)
    elif args.mode == "pipeline":
        report = asyncio.run(run_pipeline_eval(cases))
    else:
        report = run_heuristic_eval(cases)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    acc_modes = ("heuristic_substring", "rag_pipeline_retrieval")
    if args.fail_under is not None and report.get("mode") in acc_modes:
        acc = float(report.get("accuracy", 0.0))
        if acc < args.fail_under:
            print(
                f"未达门禁: accuracy={acc} < fail_under={args.fail_under}",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
