#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG 黄金集离线评估（美国 NG Eval 练习用）。

用法:
  python scripts/eval_rag_golden.py --dataset scripts/fixtures/golden_rag_sample.jsonl --dry-run
  python scripts/eval_rag_golden.py --dataset scripts/fixtures/golden_rag_sample.jsonl
  python scripts/eval_rag_golden.py --dataset scripts/fixtures/golden_rag_sample.jsonl --use-ragas

--dry-run 仅校验 JSONL 字段；默认用简单子串匹配模拟「生成答案」与 ground_truth 对比。
接入真实 RAG 管道时，将 predict_answer() 替换为对 app.core.rag 的调用。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {"id", "question", "contexts", "ground_truth"}


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


def predict_answer_stub(case: GoldenCase) -> str:
    """占位：用检索上下文拼接模拟 RAG 输出。替换为真实 generator 即可。"""
    if case.should_refuse:
        return "根据提供的文档，未提及该信息。"
    joined = " ".join(case.contexts)
    if case.ground_truth in joined:
        return case.ground_truth
    return joined[:80]


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def score_exact(pred: str, gold: str) -> bool:
    p, g = normalize(pred), normalize(gold)
    return g in p or p in g


def run_heuristic_eval(cases: list[GoldenCase]) -> dict[str, Any]:
    hits = 0
    details: list[dict[str, Any]] = []
    for c in cases:
        pred = predict_answer_stub(c)
        ok = score_exact(pred, c.ground_truth)
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
        raise SystemExit(
            "RAGAS 未安装。请执行: pip install -r requirements-eval.txt"
        ) from e

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
        help="JSONL 黄金集路径",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅校验数据集格式，不跑评分",
    )
    parser.add_argument(
        "--use-ragas",
        action="store_true",
        help="使用 RAGAS（需安装 requirements-eval.txt）",
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="准确率低于该阈值时退出码为 1（CI 门禁用，如 0.8）",
    )
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
    else:
        report = run_heuristic_eval(cases)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.fail_under is not None and report.get("mode") == "heuristic_substring":
        acc = report.get("accuracy", 0.0)
        if acc < args.fail_under:
            print(
                f"未达门禁: accuracy={acc} < fail_under={args.fail_under}",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
