from __future__ import annotations

import mimetypes

from pydantic import BaseModel

from services.upstage import UpstageClient

DOCUMENT_PARSE_PATH = "/document-digitization"
MODEL = "document-parse"
DEFAULT_CONTENT_TYPE = "application/pdf"


def _guess_content_type(filename: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or DEFAULT_CONTENT_TYPE


class ParsedElement(BaseModel):
    id: int
    page: int
    category: str
    text: str
    # bbox는 0-1 normalized (페이지 width/height 곱해서 pixel로 변환)
    bbox: tuple[float, float, float, float] | None = None  # (x0, y0, x1, y1)


class DocumentParseResult(BaseModel):
    markdown: str
    elements: list[ParsedElement]


def _coords_to_bbox(coords: list[dict]) -> tuple[float, float, float, float] | None:
    if not coords:
        return None
    xs = [c["x"] for c in coords]
    ys = [c["y"] for c in coords]
    return (min(xs), min(ys), max(xs), max(ys))


async def parse_document(
    client: UpstageClient,
    *,
    file_bytes: bytes,
    filename: str,
) -> DocumentParseResult:
    """Upstage Document Parse 호출 → DocumentParseResult 반환.

    좌표는 0-1 normalized이며 페이지 width/height 곱해서 pixel로 변환 가능.
    """
    files = {"document": (filename, file_bytes, _guess_content_type(filename))}
    data = {
        "model": MODEL,
        "output_formats": '["markdown"]',
        "coordinates": "true",
        "ocr": "auto",
        "mode": "enhanced",  # VLM 기반, 표/체크박스/차트 정밀도↑ (페이지 비용↑)
    }
    raw = await client.post_multipart(DOCUMENT_PARSE_PATH, files=files, data=data)

    markdown = (raw.get("content") or {}).get("markdown", "")
    elements_raw = raw.get("elements") or []

    if not markdown and not elements_raw:
        raise ValueError("Document Parse returned empty content")

    elements = [
        ParsedElement(
            id=e["id"],
            page=e["page"],
            category=e["category"],
            text=(e.get("content") or {}).get("text", ""),
            bbox=_coords_to_bbox(e.get("coordinates") or []),
        )
        for e in elements_raw
    ]
    return DocumentParseResult(markdown=markdown, elements=elements)
