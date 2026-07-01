"""Контрактный тест: Python verify_answer vs tests/fixtures/rag_verify_contract.json."""

import json
from pathlib import Path

import pytest
from langchain_core.documents import Document

from rag.verifier import verify_answer

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "rag_verify_contract.json"


def _load_cases():
    with _FIXTURE.open(encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


@pytest.mark.parametrize("case", _load_cases(), ids=lambda c: c["id"])
def test_verify_contract_python(case):
    fragments = [
        Document(page_content=fr["content"], metadata={"filename": fr.get("filename", "test.txt")})
        for fr in case["fragments"]
    ]
    ok, reason = verify_answer("contract", case["answer"], fragments)
    assert ok == case["expect_pass"], f"{case['id']}: expected pass={case['expect_pass']}, got {ok!r}, reason={reason!r}"
    substr = case.get("expect_reason_substr")
    if substr and not ok:
        assert substr in reason, f"{case['id']}: reason {reason!r} should contain {substr!r}"
