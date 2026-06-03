# -*- coding: utf-8 -*-
"""输入/输出护栏：提示注入检测、PII 脱敏、输出安全（Epic 3 将扩展接入链路）。"""

from __future__ import annotations

import re
from dataclasses import dataclass

# 常见提示注入模式（启发式，非穷尽）
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+(your\s+)?(system\s+)?prompt",
        r"you\s+are\s+now\s+(in\s+)?(developer|admin|root)\s+mode",
        r"<\s*script\b",
        r"\bjailbreak\b",
    )
)

_PII_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b1[3-9]\d{9}\b"), "[PHONE]"),
    (re.compile(r"\b\d{17}[\dXx]\b"), "[ID_CARD]"),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[EMAIL]",
    ),
)

# 输出中不应原样回显的敏感片段（启发式）
_OUTPUT_BLOCKLIST: tuple[str, ...] = (
    "sk-",
    "api_key=",
    "password=",
    "BEGIN RSA PRIVATE KEY",
)


@dataclass(frozen=True)
class GuardrailResult:
    """护栏检查结果。"""

    allowed: bool
    reason: str = ""
    sanitized_text: str | None = None


def detect_prompt_injection(text: str) -> bool:
    """若文本疑似包含提示注入，返回 True。"""
    if not text or not text.strip():
        return False
    return any(p.search(text) for p in _INJECTION_PATTERNS)


def redact_pii(text: str) -> str:
    """对常见 PII 做占位符替换。"""
    out = text
    for pattern, repl in _PII_RULES:
        out = pattern.sub(repl, out)
    return out


def check_output_safety(text: str) -> GuardrailResult:
    """检查模型输出是否含明显敏感泄露；不通过时 allowed=False。"""
    lowered = text.lower()
    for token in _OUTPUT_BLOCKLIST:
        if token.lower() in lowered:
            return GuardrailResult(
                allowed=False,
                reason=f"输出含敏感片段: {token!r}",
            )
    return GuardrailResult(allowed=True, sanitized_text=text)


def sanitize_user_input(text: str) -> GuardrailResult:
    """组合：注入检测 + PII 脱敏。注入命中则拒绝；否则返回脱敏文本。"""
    if detect_prompt_injection(text):
        return GuardrailResult(allowed=False, reason="疑似提示注入")
    return GuardrailResult(allowed=True, sanitized_text=redact_pii(text))
