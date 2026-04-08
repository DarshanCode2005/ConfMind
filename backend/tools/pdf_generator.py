"""
pdf_generator.py — Jinja2 + WeasyPrint sponsorship proposal PDF generator.

Renders a polished HTML sponsorship proposal from a SponsorSchema and event
metadata dict, then converts it to a PDF using WeasyPrint.

Environment variables
─────────────────────
None required.  The Jinja2 template path is resolved relative to this file's
parent so it works regardless of CWD.

Public interface
────────────────
render_proposal(sponsor, event_meta)          -> bytes  (raw PDF bytes)
save_proposal(sponsor, event_meta, out_path)  -> str    (absolute file path)

Usage example
─────────────
    from backend.tools.pdf_generator import save_proposal
    from backend.models.schemas import SponsorSchema

    sponsor = SponsorSchema(name="TechCorp", industry="AI", tier="Gold", relevance_score=8.5)
    event_meta = {"event_name": "AI Summit 2025", "city": "Berlin", "date": "2025-09-15"}
    path = save_proposal(sponsor, event_meta, "/tmp/techcorp_proposal.pdf")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML  # type: ignore[import-untyped]

from backend.models.schemas import SponsorSchema

# Template directory lives at backend/templates/ (sibling of backend/tools/)
_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
_TEMPLATE_NAME = "sponsorship_proposal.html"


def _get_jinja_env() -> Environment:
    """Build a Jinja2 Environment pointed at the templates directory."""
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )


def render_proposal(
    sponsor: SponsorSchema,
    event_meta: dict[str, Any],
) -> bytes:
    """Render a sponsorship proposal to PDF bytes.

    Args:
        sponsor:    The sponsor this proposal is addressed to.
        event_meta: A dict with keys: event_name, city, date (ISO 8601),
                    and optionally organiser, contact_email, audience_size.

    Returns:
        Raw PDF bytes (starts with b'%PDF').
    """
    env = _get_jinja_env()
    template = env.get_template(_TEMPLATE_NAME)
    html_str = template.render(sponsor=sponsor, event=event_meta)
    pdf_bytes: bytes = HTML(string=html_str).write_pdf()
    return pdf_bytes


def save_proposal(
    sponsor: SponsorSchema,
    event_meta: dict[str, Any],
    output_path: str,
) -> str:
    """Render a sponsorship proposal and write it to disk.

    Args:
        sponsor:     The sponsor this proposal is for.
        event_meta:  Same as render_proposal.
        output_path: Absolute or relative path for the output PDF.

    Returns:
        Absolute path of the written file.
    """
    pdf_bytes = render_proposal(sponsor, event_meta)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf_bytes)
    return str(path.resolve())
