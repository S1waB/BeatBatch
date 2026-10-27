"""
Validate router – POST /api/validate

Accepts a block of raw text (one URL per line) and returns which lines
are valid YouTube video URLs and which are not.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.link_parser import parse_links

router = APIRouter(prefix="/api", tags=["validate"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ValidateRequest(BaseModel):
    """Body accepted by POST /api/validate."""

    text: str = Field(..., max_length=150_000, description="Raw text of YouTube URLs")


class ValidLinkOut(BaseModel):
    """Serialisable representation of a valid YouTube link."""

    video_id: str
    canonical_url: str
    original_url: str


class InvalidLineOut(BaseModel):
    """Serialisable representation of a line that failed validation."""

    line_number: int
    text: str
    reason: str


class ValidateResponse(BaseModel):
    """Full response returned by POST /api/validate."""

    valid_links: list[ValidLinkOut]
    invalid_lines: list[InvalidLineOut]
    total_valid: int
    total_invalid: int


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/validate", response_model=ValidateResponse)
async def validate_links(body: ValidateRequest) -> ValidateResponse:
    """
    Parse and validate a block of YouTube URLs.

    - Skips blank lines and comment lines (``#``).
    - Removes duplicate video IDs, keeping the first occurrence.
    - Returns two lists: **valid_links** and **invalid_lines**.
    """
    valid, invalid = parse_links(body.text)

    return ValidateResponse(
        valid_links=[ValidLinkOut(**v.to_dict()) for v in valid],
        invalid_lines=[InvalidLineOut(**i.to_dict()) for i in invalid],
        total_valid=len(valid),
        total_invalid=len(invalid),
    )
