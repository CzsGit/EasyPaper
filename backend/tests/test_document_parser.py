from __future__ import annotations

import fitz

from app.services.document_parser import parse_document, validate_evidence


def _pdf() -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((60, 80), "1 Introduction", fontsize=16)
    page.insert_text((60, 110), "This method improves results. It keeps the limitation visible.", fontsize=10)
    page.insert_text((60, 145), "2 Methods", fontsize=16)
    page.insert_text((60, 175), "We evaluate the model on a dataset and report accuracy.", fontsize=10)
    data = document.tobytes()
    document.close()
    return data


def test_parse_document_keeps_order_and_stable_anchors() -> None:
    source = _pdf()
    first = parse_document(source, "paper.pdf")
    second = parse_document(source, "paper.pdf")

    assert [block["type"] for block in first["blocks"]] == ["heading", "paragraph", "heading", "paragraph"]
    assert [block["id"] for block in first["blocks"]] == [block["id"] for block in second["blocks"]]
    assert first["sections"][1]["block_id"] == first["blocks"][2]["id"]
    assert len(first["blocks"][1]["sentences"]) == 2


def test_validate_evidence_removes_model_invented_ids() -> None:
    document = parse_document(_pdf(), "paper.pdf")
    data = {"answer": "supported", "evidence_refs": [document["blocks"][1]["id"], "invented"]}

    checked = validate_evidence(data, document["blocks"])

    assert [ref["block_id"] for ref in checked["evidence_refs"]] == [document["blocks"][1]["id"]]
    assert checked["evidence_refs"][0]["page"] == 1
