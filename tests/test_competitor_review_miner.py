"""Offline checks for growth.competitor_review_miner — no model calls, no network requests."""

import json
import re
from pathlib import Path

PACKAGE_DIR = Path(__file__).parents[1] / "workflow_packages/growth.competitor_review_miner"
REPO_ROOT = Path(__file__).parents[1]
KEY = "growth.competitor_review_miner"
QUALIFICATION_FILE = REPO_ROOT / f"workflow_evals/{KEY}/qualification.json"

# ---------------------------------------------------------------------------
# Manifest checks
# ---------------------------------------------------------------------------


def test_manifest_key_matches_folder_name():
    manifest = json.loads((PACKAGE_DIR / "workflow.json").read_text())
    assert manifest["definition"]["key"] == KEY


def test_manifest_has_required_fields():
    manifest = json.loads((PACKAGE_DIR / "workflow.json").read_text())
    definition = manifest["definition"]
    assert manifest["package_format"] == "tin-workflow-package-v1"
    assert definition["executor"] == "codex.procedure"
    assert "on_demand" in definition["schedule_modes"]
    assert definition["title"].strip()
    assert definition["description"].strip()
    assert definition["version"]


def test_manifest_input_schema_has_required_properties():
    manifest = json.loads((PACKAGE_DIR / "workflow.json").read_text())
    schema = manifest["definition"]["input_schema"]
    props = schema["properties"]
    required = schema["required"]
    assert "project_id" in required
    assert "competitor_name" in required
    assert "reviews_text" in required
    assert "maxLength" in props["competitor_name"]
    assert "maxLength" in props["reviews_text"]
    assert "focus" in props


def test_manifest_procedure_paths_are_valid():
    manifest = json.loads((PACKAGE_DIR / "workflow.json").read_text())
    proc = manifest["definition"]["procedure"]
    assert (PACKAGE_DIR / proc["prompt_path"]).is_file()
    assert (PACKAGE_DIR / proc["skills_path"]).is_dir()
    for f in proc["skill_files"]:
        assert (PACKAGE_DIR / f).is_file(), f"Missing skill file: {f}"
    entry_skill_dir = PACKAGE_DIR / proc["skills_path"] / proc["entry_skill"]
    assert entry_skill_dir.is_dir()
    assert (entry_skill_dir / "SKILL.md").is_file()


def test_manifest_output_is_project_artifact():
    manifest = json.loads((PACKAGE_DIR / "workflow.json").read_text())
    output = manifest["definition"]["procedure"]["output"]
    assert output["kind"] == "project.artifact"
    assert output["path"].startswith("reports/")
    assert output["media_type"] == "text/markdown"
    assert output["max_bytes"] > 0


def test_manifest_sandbox_is_fenced_and_isolated():
    manifest = json.loads((PACKAGE_DIR / "workflow.json").read_text())
    sandbox = manifest["definition"]["procedure"]["sandbox"]
    assert sandbox["profile"] == "isolated"
    assert sandbox["egress"] == "fenced"
    assert sandbox["timeout_seconds"] <= 900


# ---------------------------------------------------------------------------
# SKILL.md checks
# ---------------------------------------------------------------------------


def test_skill_frontmatter_name_matches_directory():
    skill_path = PACKAGE_DIR / "skills/competitor-review-miner/SKILL.md"
    content = skill_path.read_text()
    match = re.search(r"^name:\s*(.+)$", content, re.MULTILINE)
    assert match, "SKILL.md missing frontmatter 'name:'"
    assert match.group(1).strip() == "competitor-review-miner"


def test_skill_frontmatter_description_is_non_empty():
    skill_path = PACKAGE_DIR / "skills/competitor-review-miner/SKILL.md"
    content = skill_path.read_text()
    match = re.search(r"^description:\s*(.+)$", content, re.MULTILINE)
    assert match, "SKILL.md missing frontmatter 'description:'"
    assert len(match.group(1).strip()) > 10


def test_skill_defines_required_analysis_buckets():
    skill_text = (PACKAGE_DIR / "skills/competitor-review-miner/SKILL.md").read_text()
    required_buckets = [
        "Pain Points",
        "Loved Features",
        "Switching Triggers",
        "Pricing Signals",
        "Missed Use Cases",
    ]
    for bucket in required_buckets:
        assert bucket in skill_text, f"SKILL.md missing bucket: {bucket}"


def test_skill_defines_report_sections():
    skill_text = (PACKAGE_DIR / "skills/competitor-review-miner/SKILL.md").read_text()
    required_sections = [
        "Signal summary",
        "Pain Points",
        "Loved Features",
        "Switching Triggers",
        "Pricing Signals",
        "Missed Use Cases",
        "Three growth moves",
        "Evidence notes",
    ]
    for section in required_sections:
        assert section in skill_text, f"SKILL.md missing section: {section}"


def test_skill_enforces_anti_hallucination_rule():
    skill_text = (PACKAGE_DIR / "skills/competitor-review-miner/SKILL.md").read_text()
    assert "verbatim" in skill_text.lower(), "SKILL.md should require verbatim quotes from reviews"
    assert "paraphrased" in skill_text.lower(), (
        "SKILL.md should require (paraphrased) label if exact quote is not used"
    )


def test_skill_restricts_safe_files_and_forbids_sensitive_files():
    skill_text = (PACKAGE_DIR / "skills/competitor-review-miner/SKILL.md").read_text()
    prompt_text = (PACKAGE_DIR / "PROMPT.md").read_text()
    for text in (skill_text, prompt_text):
        assert ".env" in text
        assert "credentials" in text
        assert "session histories" in text
        assert "explicitly safe" in text


def test_skill_defines_diagnostic_report_format():
    skill_text = (PACKAGE_DIR / "skills/competitor-review-miner/SKILL.md").read_text()
    assert "Competitor Review Miner — Diagnostic Report" in skill_text
    assert "Status: invalid input" in skill_text


def test_skill_caps_processing_at_200_reviews():
    skill_text = (PACKAGE_DIR / "skills/competitor-review-miner/SKILL.md").read_text()
    assert "200" in skill_text, "SKILL.md should mention the 200 review processing cap"


# ---------------------------------------------------------------------------
# PROMPT.md checks
# ---------------------------------------------------------------------------


def test_prompt_forbids_dangerous_actions():
    prompt = (PACKAGE_DIR / "PROMPT.md").read_text()
    assert "untrusted" in prompt.lower()
    assert "do not publish" in prompt.lower()
    assert "credentials" in prompt.lower()


def test_prompt_names_correct_output_path():
    manifest = json.loads((PACKAGE_DIR / "workflow.json").read_text())
    declared_path = manifest["definition"]["procedure"]["output"]["path"]
    prompt = (PACKAGE_DIR / "PROMPT.md").read_text()
    assert declared_path in prompt


# ---------------------------------------------------------------------------
# Community validator check
# ---------------------------------------------------------------------------


async def test_package_passes_community_validator():
    from tin_lite.community import ContributedPackage, validate

    package = ContributedPackage(key=KEY, path=PACKAGE_DIR)
    # Should not raise; CI runs the same check via `uv run tin-lite validate-community`
    await validate(package)


async def test_all_declared_skill_files_exist_on_disk():
    manifest = json.loads((PACKAGE_DIR / "workflow.json").read_text())
    for skill_file in manifest["definition"]["procedure"]["skill_files"]:
        target = PACKAGE_DIR / skill_file
        assert target.is_file(), f"Declared skill_file not found on disk: {skill_file}"


# ---------------------------------------------------------------------------
# Workflow qualification checks
# ---------------------------------------------------------------------------


async def test_workflow_qualification_contract():
    from tin_lite.workflow_packages import decode_workflow_source
    from tin_lite.workflow_qualification import Qualification, check_package

    assert QUALIFICATION_FILE.is_file(), f"Qualification file missing: {QUALIFICATION_FILE}"
    contract = Qualification.model_validate_json(QUALIFICATION_FILE.read_bytes())
    assert contract.version == 1
    case_ids = {case.id for case in contract.cases}
    assert "ordinary_reviews" in case_ids
    assert "boundary_csv_and_cap" in case_ids
    assert "insufficient_reviews_diagnostic" in case_ids
    assert len(contract.rubric) >= 2

    raw_manifest = (PACKAGE_DIR / "workflow.json").read_bytes()
    manifest_rel = f"workflow_packages/{KEY}/workflow.json"
    source = decode_workflow_source(raw_manifest, definition_path=manifest_rel)
    files = {manifest_rel: raw_manifest}
    for res in source.resource_paths.values():
        files[res] = (REPO_ROOT / res).read_bytes()

    report = await check_package(files, manifest_rel, contract)
    assert report["shape"]["status"] == "passed"
    assert report["cost"]["configured_ceiling_usd"] == "5"
    assert report["cost"]["basis"] == "unmeasured"
    assert report["safety"]["status"] == "review_required"


async def test_qualification_cli_checkout():
    from tin_lite.workflow_qualification_cli import check_checkout

    manifest_rel = f"workflow_packages/{KEY}/workflow.json"
    await check_checkout(REPO_ROOT, manifest_rel)


def test_qualification_fixtures_evaluation():
    from tin_lite.workflow_qualification import Qualification, assess_output

    contract = Qualification.model_validate_json(QUALIFICATION_FILE.read_bytes())
    cases_by_id = {c.id: c for c in contract.cases}

    ordinary_output = (
        "# Competitor review intelligence: AcmeDesk\n\n"
        "## Signal summary\n| Bucket | Reviews | Score |\n\n"
        "## Pain Points\n- Slow sync and crashes\n\n"
        "## Loved Features\n- Clean dashboard\n\n"
        "## Switching Triggers\n- Customer switched because pricing jumped 40%\n\n"
        "## Pricing Signals\n- Pricing sudden hike\n\n"
        "## Missed Use Cases\n- Large queue handling\n\n"
        "## Three growth moves\n1. Target switched AcmeDesk users.\n\n"
        "## Evidence notes\n- Units processed: 3\n"
    )
    result_ord = assess_output(
        cases_by_id["ordinary_reviews"],
        status="succeeded",
        content=ordinary_output.encode(),
    )
    assert result_ord["status"] == "passed"

    boundary_output = (
        "# Competitor review intelligence: LegacyCRM\n\n"
        "## Signal summary\n| Bucket | Reviews | Score |\n\n"
        "## Pain Points\n- Export timeout\n\n"
        "## Loved Features\n- Sequences\n\n"
        "## Switching Triggers\n- Cancelled subscription\n\n"
        "## Pricing Signals\n- Hidden SSO fees\n\n"
        "## Missed Use Cases\n- Webhooks\n\n"
        "## Three growth moves\nLegacyCRM migration plays.\n\n"
        "## Evidence notes\n- Input format detected: CSV (column 'review')\n- Units processed: 5\n"
    )
    result_bnd = assess_output(
        cases_by_id["boundary_csv_and_cap"],
        status="succeeded",
        content=boundary_output.encode(),
    )
    assert result_bnd["status"] == "passed"

    diag_output = (
        "# Competitor Review Miner — Diagnostic Report\n\n"
        "Status: invalid input\n\n"
        "Reason: insufficient reviews supplied (minimum 2 lines or CSV data rows required)."
    )
    result_diag = assess_output(
        cases_by_id["insufficient_reviews_diagnostic"],
        status="succeeded",
        content=diag_output.encode(),
    )
    assert result_diag["status"] == "passed"


# ---------------------------------------------------------------------------
# Input validation semantics (document plausible/unusable inputs)
# ---------------------------------------------------------------------------


VALID_REVIEWS_PLAIN = "\n".join(
    [
        "The export feature is completely broken, I've filed 3 tickets and nothing.",
        "Love the dashboard, it's the cleanest I've seen. Highly recommend.",
        "Way too expensive for a solo founder, can't justify the cost.",
        "I switched from Acme after their support ignored me for two weeks.",
        "I wish it integrated with Notion — I have to copy everything manually.",
        "Onboarding was confusing, took me an hour to connect my first integration.",
        "The CSV export dropped half my records. Lost a whole afternoon to this.",
        "Best part is the API — I can automate everything I need.",
        "Pricing jumped 40% with no warning. Looking for alternatives.",
        "There's no mobile app. That's a dealbreaker for me.",
    ]
)

VALID_REVIEWS_CSV = (
    "id,review,rating\n"
    '1,"Worst support I have ever encountered. Three weeks, no reply.",1\n'
    '2,"Clean UI, quick to set up — genuinely the best tool in this space.",5\n'
    '3,"Moved from CompetitorY because it crashed twice during demos.",2\n'
    '4,"$299/month is insane for what you get. Cancelling next month.",1\n'
    '5,"No batch export. I have to download one file at a time.",2\n'
)


def test_plain_text_reviews_are_recognisable():
    lines = [line for line in VALID_REVIEWS_PLAIN.splitlines() if line.strip()]
    assert len(lines) >= 2, "Fixture should have at least two non-empty review lines"


def test_csv_reviews_contain_recognisable_header():
    first_line = VALID_REVIEWS_CSV.splitlines()[0].lower()
    assert "review" in first_line, "CSV fixture should have a 'review' column"


def test_unusable_model_result_is_documented():
    """Documents what a diagnostic output looks like for this workflow."""
    diagnostic_output = (
        "# Competitor Review Miner — Diagnostic Report\n\n"
        "Status: invalid input\n\n"
        "No reviews could be parsed from the supplied input.\n"
    )
    assert "Diagnostic Report" in diagnostic_output
    assert "Status: invalid input" in diagnostic_output
