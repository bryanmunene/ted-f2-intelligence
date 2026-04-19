from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "docs" / "cBrain_TED_F2_Intelligence_Presentation_Summary.docx"


@dataclass(frozen=True)
class Paragraph:
    text: str
    kind: str = "body"


def _paragraph_xml(paragraph: Paragraph) -> str:
    text = escape(paragraph.text)
    if paragraph.kind == "title":
        return (
            '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="220"/></w:pPr>'
            '<w:r><w:rPr><w:b/><w:sz w:val="34"/></w:rPr>'
            f"<w:t>{text}</w:t></w:r></w:p>"
        )
    if paragraph.kind == "subtitle":
        return (
            '<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="220"/></w:pPr>'
            '<w:r><w:rPr><w:color w:val="4D627C"/><w:sz w:val="24"/></w:rPr>'
            f"<w:t>{text}</w:t></w:r></w:p>"
        )
    if paragraph.kind == "heading1":
        return (
            '<w:p><w:pPr><w:spacing w:before="280" w:after="140"/></w:pPr>'
            '<w:r><w:rPr><w:b/><w:color w:val="17315F"/><w:sz w:val="28"/></w:rPr>'
            f"<w:t>{text}</w:t></w:r></w:p>"
        )
    if paragraph.kind == "heading2":
        return (
            '<w:p><w:pPr><w:spacing w:before="180" w:after="100"/></w:pPr>'
            '<w:r><w:rPr><w:b/><w:color w:val="2F67D8"/><w:sz w:val="24"/></w:rPr>'
            f"<w:t>{text}</w:t></w:r></w:p>"
        )
    if paragraph.kind == "bullet":
        return (
            '<w:p><w:pPr><w:ind w:left="720" w:hanging="360"/><w:spacing w:after="80"/></w:pPr>'
            '<w:r><w:rPr><w:b/><w:color w:val="2F67D8"/></w:rPr><w:t xml:space="preserve">• </w:t></w:r>'
            f'<w:r><w:rPr><w:sz w:val="22"/></w:rPr><w:t>{text}</w:t></w:r></w:p>'
        )
    if paragraph.kind == "small":
        return (
            '<w:p><w:pPr><w:spacing w:after="120"/></w:pPr>'
            '<w:r><w:rPr><w:color w:val="73849C"/><w:sz w:val="20"/></w:rPr>'
            f"<w:t>{text}</w:t></w:r></w:p>"
        )
    return (
        '<w:p><w:pPr><w:spacing w:after="110"/></w:pPr>'
        '<w:r><w:rPr><w:sz w:val="22"/></w:rPr>'
        f"<w:t>{text}</w:t></w:r></w:p>"
    )


def _document_xml(paragraphs: list[Paragraph]) -> str:
    body = "".join(_paragraph_xml(paragraph) for paragraph in paragraphs)
    sect = (
        '<w:sectPr>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" w:header="720" w:footer="720" w:gutter="0"/>'
        "</w:sectPr>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas" '
        'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" '
        'xmlns:o="urn:schemas-microsoft-com:office:office" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" '
        'xmlns:v="urn:schemas-microsoft-com:vml" '
        'xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:w10="urn:schemas-microsoft-com:office:word" '
        'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
        'xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup" '
        'xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk" '
        'xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml" '
        'xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape" '
        'mc:Ignorable="w14 wp14">'
        f"<w:body>{body}{sect}</w:body></w:document>"
    )


def _styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:docDefaults>
    <w:rPrDefault>
      <w:rPr>
        <w:rFonts w:ascii="Aptos" w:hAnsi="Aptos" w:eastAsia="Aptos" w:cs="Aptos"/>
        <w:sz w:val="22"/>
        <w:szCs w:val="22"/>
        <w:color w:val="142033"/>
      </w:rPr>
    </w:rPrDefault>
  </w:docDefaults>
</w:styles>
"""


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>
"""


def _root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def _document_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>
"""


def _core_xml(now_iso: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:dcterms="http://purl.org/dc/terms/"
 xmlns:dcmitype="http://purl.org/dc/dcmitype/"
 xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>cBrain TED F2 Intelligence - Presentation Summary</dc:title>
  <dc:subject>Project summary</dc:subject>
  <dc:creator>cBrain TED F2 Intelligence project workspace</dc:creator>
  <cp:keywords>TED,F2,cBrain,procurement,intelligence</cp:keywords>
  <dc:description>Presentation-ready summary of the cBrain TED F2 Intelligence application.</dc:description>
  <cp:lastModifiedBy>cBrain TED F2 Intelligence project workspace</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{now_iso}</dcterms:modified>
</cp:coreProperties>
"""


def _app_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
 xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Microsoft Office Word</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <Company>cBrain</Company>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>16.0000</AppVersion>
</Properties>
"""


def build_paragraphs() -> list[Paragraph]:
    today = datetime.now().strftime("%d %B %Y")
    paragraphs = [
        Paragraph("cBrain TED F2 Intelligence", "title"),
        Paragraph("Presentation Summary", "subtitle"),
        Paragraph(f"Prepared for internal presentation use | {today}", "small"),
        Paragraph("Executive Overview", "heading1"),
        Paragraph(
            "This application was built as a focused internal intelligence tool for identifying and assessing TED tender opportunities that fit cBrain F2. The solution is TED-only, API-first, audit-oriented, and designed to evolve into a maintainable internal service that can run in a controlled enterprise environment.",
            "body",
        ),
        Paragraph("What the App Was Built to Solve", "heading1"),
        Paragraph("cBrain needed a way to move from broad tender browsing to focused F2 opportunity triage.", "bullet"),
        Paragraph("The goal was not to find generic IT tenders, but to detect tenders where F2 is commercially and functionally relevant.", "bullet"),
        Paragraph("Every result needed to explain what the notice is, why it matters for F2, what weakens it, and whether it deserves follow-up.", "bullet"),
        Paragraph("Core Product Decisions", "heading1"),
        Paragraph("Official TED public interfaces were used as the sole source of truth.", "bullet"),
        Paragraph("The TED Search API became the canonical notice discovery mechanism.", "bullet"),
        Paragraph("TED-specific request and response logic was isolated from scoring, persistence, and UI layers.", "bullet"),
        Paragraph("Scoring was implemented as deterministic, explainable, and auditable rather than black-box ranking.", "bullet"),
        Paragraph("The app was designed for future internal hosting on cBrain infrastructure, with security, maintainability, and auditability in mind.", "bullet"),
        Paragraph("Core Technical Stack", "heading1"),
        Paragraph("Backend: FastAPI with server-oriented service and repository layers.", "bullet"),
        Paragraph("Database: PostgreSQL model design with SQLAlchemy and Alembic migrations.", "bullet"),
        Paragraph("UI: Jinja templates for the core web app plus a Streamlit shell for lightweight demo and review use.", "bullet"),
        Paragraph("TED integration: httpx-based API client with caching, retries, throttling, and request accounting.", "bullet"),
        Paragraph("Validation and config: Pydantic and environment-driven settings.", "bullet"),
        Paragraph("End-to-End Processing Flow", "heading1"),
        Paragraph("TED retrieval", "heading2"),
        Paragraph("The app queries TED through the official Search API using broad candidate-generation queries rather than over-constraining retrieval at the query level.", "body"),
        Paragraph("Normalization", "heading2"),
        Paragraph("TED payloads are normalized into a stable internal notice schema so downstream logic does not depend on TED field irregularities, link variations, or schema differences between notices.", "body"),
        Paragraph("Scoring and classification", "heading2"),
        Paragraph("After normalization, each notice is scored for F2 fit, classified, ranked, and stored with reasoning, signals, and qualification questions.", "body"),
        Paragraph("Persistence and review", "heading2"),
        Paragraph("Scored notices, scan runs, analyst notes, triage actions, and audit events are stored so the app supports repeatable review rather than one-off searching.", "body"),
        Paragraph("TED Integration Work Completed", "heading1"),
        Paragraph("Built a dedicated TED API client around the official Search API.", "bullet"),
        Paragraph("Added pagination handling, retry logic, rate-limit awareness, request budgeting, and short-term caching.", "bullet"),
        Paragraph("Centralized TED expert query construction so candidate generation can evolve independently from scoring logic.", "bullet"),
        Paragraph("Implemented official TED notice links and PDF access paths inside the review experience.", "bullet"),
        Paragraph("Kept TED-specific handling behind a service boundary so the rest of the app works only with normalized notice data.", "bullet"),
        Paragraph("Data Model and Auditability Work", "heading1"),
        Paragraph("Defined and persisted normalized notice records with publication, deadline, buyer, CPV, source, and raw TED payload storage.", "bullet"),
        Paragraph("Stored analysis fields including score, fit label, priority bucket, confidence, lock signals, timing flags, reasoning, and qualification questions.", "bullet"),
        Paragraph("Added scan-run persistence for request counts, timing-filter totals, conditional counts, ignored counts, and rate-limit events.", "bullet"),
        Paragraph("Added saved triage, dismissal state, analyst notes, saved searches, app settings, and audit events.", "bullet"),
        Paragraph("Scoring and Ranking Work Completed", "heading1"),
        Paragraph("Started with configurable keyword-pack scoring aligned to F2 language such as case management, workflow, records, correspondence, citizen services, and e-government.", "bullet"),
        Paragraph("Added platform-lock logic to distinguish hard locks, soft locks, and openness signals.", "bullet"),
        Paragraph("Added explanation modules that show which terms and domains made an opportunity eligible.", "bullet"),
        Paragraph("Introduced checklist cross-reference support against a cBrain tender review template.", "bullet"),
        Paragraph("Reworked the scoring layer into a TED-only model applied immediately after normalization, while keeping ingestion untouched.", "bullet"),
        Paragraph("Final TED-only scoring logic now scores against title, summary, buyer, lot text, CPVs, timing, poor-fit scope, and platform-lock conditions.", "bullet"),
        Paragraph("Current scoring behavior", "heading2"),
        Paragraph("Hard timing filters are still respected for decision-making, but content fit is preserved so stale notices no longer collapse to meaningless zero scores.", "body"),
        Paragraph("Classification uses YES, CONDITIONAL, and NO, with priority buckets HIGH, GOOD, WATCHLIST, and IGNORE.", "body"),
        Paragraph("Ranking now prioritizes priority bucket first, fit class second, score third, and deadline fourth.", "body"),
        Paragraph("User Experience and Review Workflow Work", "heading1"),
        Paragraph("Built dashboard, scan, results, detail, and admin views in the main app.", "bullet"),
        Paragraph("Added a Streamlit shell to support rapid review, demo access, and temporary sharing without replacing the production-oriented backend architecture.", "bullet"),
        Paragraph("Added direct TED notice actions, official PDF actions, checklist generation, keyword evidence modules, and richer filters.", "bullet"),
        Paragraph("Added back navigation and state preservation so users do not need to rerun scan setup while moving between results and detail views.", "bullet"),
        Paragraph("Repeatedly reworked the UI to simplify it, reduce density, and move it away from the previous tenderwatch-style treatment.", "bullet"),
        Paragraph("Current review-focused behaviors", "heading2"),
        Paragraph("Expired tenders are now hidden by default in the review board.", "body"),
        Paragraph("Results can be filtered by score, fit, priority, confidence, publication date, deadline range, and lock posture.", "body"),
        Paragraph("Each notice detail page shows reasoning, score evidence, qualification questions, TED source actions, and checklist cross-reference output.", "body"),
        Paragraph("Stability and Hosting Readiness Work", "heading1"),
        Paragraph("Added Docker support, environment-driven settings, and production-oriented health endpoints.", "bullet"),
        Paragraph("Kept secrets out of the repository and aligned runtime configuration to enterprise deployment patterns.", "bullet"),
        Paragraph("Stabilized the Streamlit-hosted experience with fixes for packaging, SQLite/threading behavior, session state issues, and deployment compatibility.", "bullet"),
        Paragraph("Resolved multiple SQLAlchemy reload and mapper issues that surfaced in the hosted runtime.", "bullet"),
        Paragraph("Improved TED rate-limit handling and request tracking.", "bullet"),
        Paragraph("Testing and Quality Work", "heading1"),
        Paragraph("Added tests for TED client mapping and rate-limit behavior.", "bullet"),
        Paragraph("Added scoring tests for strong F2 fit, hard timing rejection, hard platform locks, missing deadlines, stale publication windows, and poor-fit hardware notices.", "bullet"),
        Paragraph("Added repository tests for filters, country handling, score windows, and result ordering.", "bullet"),
        Paragraph("Added Streamlit-specific regression tests for results metrics and default filter behavior.", "bullet"),
        Paragraph("The current local verification status is a passing test suite and successful Streamlit import validation.", "bullet"),
        Paragraph("Major Delivery Milestones", "heading1"),
        Paragraph("Phase 1 build: project scaffold, config, database models, migrations, TED API client, normalization, scoring engine, initial UI, Docker, and tests.", "bullet"),
        Paragraph("Review workflow expansion: richer filters, saved searches, notes, qualification explanations, checklist cross-reference, and official TED actions.", "bullet"),
        Paragraph("Hosted demo support: Streamlit shell, sharing support, lighter UI flows, back navigation, and hosted-runtime stability work.", "bullet"),
        Paragraph("Scoring modernization: shift to TED-only scoring logic and ranking without touching ingestion.", "bullet"),
        Paragraph("Current State of the App", "heading1"),
        Paragraph("The app is now a TED-only F2 intelligence workspace that can retrieve official TED notices, normalize them, score them, rank them, and present them in a structured review workflow.", "body"),
        Paragraph("It supports traceable scoring, repeatable scanning, official TED links, PDF retrieval, qualification prompts, and analyst review tooling.", "body"),
        Paragraph("The solution is not just a demo front end; it has a backend architecture, persistence model, and service boundaries that can continue into production hosting.", "body"),
        Paragraph("Recommended Talking Points for Presentation", "heading1"),
        Paragraph("The project moved from generic tender search toward a deterministic F2-fit review engine.", "bullet"),
        Paragraph("The solution now separates TED candidate retrieval from cBrain-specific commercial judgment.", "bullet"),
        Paragraph("The build deliberately favors official integration surfaces, traceability, maintainability, and enterprise deployment readiness.", "bullet"),
        Paragraph("A large share of the work was not just feature creation, but making the system stable, explainable, and presentable for real internal use.", "bullet"),
        Paragraph("Suggested Next Steps", "heading1"),
        Paragraph("Run more live TED scans and tune the TED-only scoring thresholds against real F2 opportunities.", "bullet"),
        Paragraph("Add scheduled scans and internal notifications for shortlisted opportunities.", "bullet"),
        Paragraph("Prepare role-based access and SSO-aligned authentication for internal deployment.", "bullet"),
        Paragraph("Refine analyst workflow features such as exporting, sharing, and review state management.", "bullet"),
    ]
    return paragraphs


def build_docx(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", _content_types_xml())
        archive.writestr("_rels/.rels", _root_rels_xml())
        archive.writestr("docProps/core.xml", _core_xml(now_iso))
        archive.writestr("docProps/app.xml", _app_xml())
        archive.writestr("word/document.xml", _document_xml(build_paragraphs()))
        archive.writestr("word/styles.xml", _styles_xml())
        archive.writestr("word/_rels/document.xml.rels", _document_rels_xml())
    return output_path


if __name__ == "__main__":
    path = build_docx(OUTPUT_PATH)
    print(path)
