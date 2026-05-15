"""Article retention policy helpers."""

from __future__ import annotations

from dataclasses import dataclass


METADATA_LEVEL = "metadata"
CONTENT_LEVEL = "content"
FULL_ARCHIVE_LEVEL = "full_archive"

ARCHIVE_NOT_REQUESTED = "not_requested"
ARCHIVE_PENDING = "pending"


@dataclass(frozen=True)
class RetentionDecision:
    retention_level: str
    archive_status: str
    reason: str


def retention_decision_for_score(
    importance_score: float,
    content_threshold: float = 0.45,
    archive_threshold: float = 0.75,
) -> RetentionDecision:
    """Map an article importance score to a storage-retention tier."""
    if importance_score >= archive_threshold:
        return RetentionDecision(
            retention_level=FULL_ARCHIVE_LEVEL,
            archive_status=ARCHIVE_PENDING,
            reason=f"importance_score >= {archive_threshold}; keep content and queue image archival",
        )
    if importance_score >= content_threshold:
        return RetentionDecision(
            retention_level=CONTENT_LEVEL,
            archive_status=ARCHIVE_NOT_REQUESTED,
            reason=f"importance_score >= {content_threshold}; keep article content and asset URLs",
        )
    return RetentionDecision(
        retention_level=METADATA_LEVEL,
        archive_status=ARCHIVE_NOT_REQUESTED,
        reason=f"importance_score < {content_threshold}; keep metadata only by policy",
    )
