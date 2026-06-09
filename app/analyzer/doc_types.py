"""
app/analyzer/doc_types.py
─────────────────────────────────────────────────────────────────────────────
Registry of known document types with detection keywords and descriptions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocType:
    code: str
    label: str
    keywords: tuple[str, ...]
    llm_context: str


DOC_TYPES: list[DocType] = [
    DocType("HLD", "High Level Design", ("high level design", "hld", "high-level design", "architecture design"), "Architecture and design document describing high-level system components, integrations, and design decisions."),
    DocType("LLD", "Low Level Design", ("low level design", "lld", "low-level design", "detailed design"), "Detailed technical design document with implementation-level specifications, configurations, and data flows."),
    DocType("SOP", "Standard Operating Procedure", ("standard operating procedure", "sop", "operating procedure", "runbook", "run book"), "Operational procedure document with step-by-step instructions for recurring tasks."),
    DocType("RFC", "Request for Comments", ("request for comments", "rfc", "change request", "change proposal"), "Proposal document describing a change, its rationale, and expected impact."),
    DocType("BRD", "Business Requirements Document", ("business requirements", "brd", "requirements document", "business requirement"), "Business requirements document defining functional and non-functional expectations."),
    DocType("REPORT", "Report", ("report", "analysis", "assessment", "audit", "review"), "Analytical or assessment report presenting findings, data, and recommendations."),
    DocType("POLICY", "Policy Document", ("policy", "governance", "compliance framework", "data protection policy"), "Policy or governance document defining rules, responsibilities, and compliance requirements."),
    DocType("GUIDE", "Guide / Manual", ("guide", "manual", "handbook", "user guide", "admin guide", "installation guide"), "Instructional document providing guidance for configuration, installation, or use."),
    DocType("PLAN", "Project / Implementation Plan", ("implementation plan", "project plan", "deployment plan", "migration plan", "rollout"), "Planning document with phases, milestones, roles, and timelines."),
    DocType("UNKNOWN", "Document", (), "Technical or business document."),
]


def detect_doc_type(title: str = "", headings: list[str] | tuple[str, ...] | None = None) -> DocType:
    headings = headings or []
    corpus = f"{title} {' '.join(headings)}".lower().replace("_", " ").replace("-", " ")

    for doc_type in DOC_TYPES:
        if doc_type.code == "UNKNOWN":
            continue

        for keyword in doc_type.keywords:
            normalized = keyword.lower().replace("_", " ").replace("-", " ")
            if normalized in corpus:
                return doc_type

    return DOC_TYPES[-1]
