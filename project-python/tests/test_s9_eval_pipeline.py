"""Epic 9：黄金集真实 RAG 管道评估。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def test_golden_pipeline_meets_threshold():
    script = _ROOT / "scripts" / "eval_rag_golden.py"
    dataset = _ROOT / "scripts" / "fixtures" / "golden_rag_sample.jsonl"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--dataset",
            str(dataset),
            "--mode",
            "pipeline",
            "--fail-under",
            "0.8",
        ],
        cwd=str(_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
