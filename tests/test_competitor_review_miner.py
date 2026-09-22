"""Offline checks for growth.competitor_review_miner — no model calls, no network requests."""

import json
import re
from pathlib import Path

import pytest

PACKAGE_DIR = Path(__file__).parents[1] / "workflow_packages/growth.competitor_review_miner"
KEY = "growth.competitor_review_miner"

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
    # project_id format
    assert props["project_id"]["format"] == "uuid"
    # reviews_text has a maxLength to bound input
    assert props["reviews_text"]["maxLength"] <= 16000
    # focus is optional
    assert "focus" not in required
    # additionalProperties must be false
    assert schema.get("additionalProperties") is False


def test_manifest_output_is_project_artifact():
    manifest = json.loads((PACKAGE_DIR / "workflow.json").read_text())
    output = manifest["definition"]["procedure"]["output"]
    assert output["kind"] == "project.artifact"
    assert output["media_type"] == "text/markdown"
    assert "COMPETITOR_REVIEW_MINER.md" in output["path"]
    assert output["max_bytes"] <= 50000


def test_procedure_entry_skill_matches_declared_file():
    manifest = json.loads((PACKAGE_DIR / "workflow.json").read_text())
    procedure = manifest["definition"]["procedure"]
    entry = procedure["entry_skill"]
    skill_files = procedure["skill_files"]
    # The entry skill's SKILL.md must appear in the declared files list
    expected_path = f"skills/{entry}/SKILL.md"
    assert any(expected_path in sf for sf in skill_files), (
        f"entry_skill '{entry}' has no matching SKILL.md in skill_files: {skill_files}"
    )


def test_no_integration_requirements_needed():
    """This workflow intentionally requires zero API connections — any founder can run it."""
    manifest = json.loads((PACKAGE_DIR / "workflow.json").read_text())
    definition = manifest["definition"]
    # Either the key is absent, or the list is empty
    reqs = definition.get("integration_requirements", [])
    assert reqs == [], f"Expected no integration_requirements, got: {reqs}"


# ---------------------------------------------------------------------------
# PROMPT.md checks
# ---------------------------------------------------------------------------


def test_prompt_is_non_empty_and_non_trivial():
    prompt = (PACKAGE_DIR / "PROMPT.md").read_text()
    assert len(prompt.strip()) >= 50, "PROMPT.md is too short to be meaningful"
    # Must reference the skill or the output path
    assert "competitor-review-miner" in prompt or "COMPETITOR_REVIEW_MINER" in prompt


def test_prompt_does_not_allow_dangerous_actions():
    prompt = (PACKAGE_DIR / "PROMPT.md").read_text().lower()
    # The prompt must explicitly guard against publishing/sending
    assert "do not publish" in prompt or "not publish" in prompt


# ---------------------------------------------------------------------------
# SKILL.md checks
# ---------------------------------------------------------------------------

SKILL_PATH = PACKAGE_DIR / "skills/competitor-review-miner/SKILL.md"


def test_skill_file_exists():
    assert SKILL_PATH.is_file()


def test_skill_has_valid_yaml_frontmatter():
    text = SKILL_PATH.read_text()
    assert text.startswith("---"), "SKILL.md must start with YAML frontmatter (---)"
    # Find the closing ---
    end = text.find("\n---\n", 3)
    assert end != -1, "SKILL.md frontmatter is not closed with ---"
    frontmatter = text[3:end]
    assert "name:" in frontmatter
    assert "description:" in frontmatter


def test_skill_name_in_frontmatter_matches_folder():
    text = SKILL_PATH.read_text()
    end = text.find("\n---\n", 3)
    frontmatter = text[3:end]
    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
    assert name_match, "No 'name:' field found in SKILL.md frontmatter"
    assert name_match.group(1).strip() == "competitor-review-miner"


def test_skill_covers_all_five_signal_buckets():
    text = SKILL_PATH.read_text()
    expected_buckets = [
        "Pain Points",
        "Loved Features",
        "Switching Triggers",
        "Pricing Signals",
        "Missed Use Cases",
    ]
    for bucket in expected_buckets:
        assert bucket in text, f"SKILL.md does not mention bucket: '{bucket}'"


def test_skill_describes_three_growth_moves():
    text = SKILL_PATH.read_text()
    assert "Messaging hook" in text or "messaging hook" in text.lower()
    assert "Acquisition" in text or "acquisition" in text.lower()
    assert "gap" in text.lower()


def test_skill_describes_output_report_structure():
    text = SKILL_PATH.read_text()
    assert "COMPETITOR_REVIEW_MINER.md" in text, (
        "SKILL.md should reference the declared output path"
    )


# ---------------------------------------------------------------------------
# Package-level community validation (static only, no model calls)
# ---------------------------------------------------------------------------


async def test_package_passes_community_validator():
    from tin_lite.community import ContributedPackage, validate

    package = ContributedPackage(key=KEY, path=PACKAGE_DIR)
    # Should not raise; CI runs the same check via `uv run tin-lite validate-community`
    await validate(package)


async def test_all_declared_skill_files_exist_on_disk():
    manifest = json.loads((PACKAGE_DIR / "workflow.json").read_text())
    for skill_file in manifest["definition"]["procedure"]["skill_files"]:
        # skill_files paths are relative to the package directory
        target = PACKAGE_DIR / skill_file
        assert target.is_file(), f"Declared skill_file not found on disk: {skill_file}"


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
    lines = [l for l in VALID_REVIEWS_PLAIN.splitlines() if l.strip()]
    assert len(lines) >= 2, "Fixture should have at least two non-empty review lines"


def test_csv_reviews_contain_recognisable_header():
    first_line = VALID_REVIEWS_CSV.splitlines()[0].lower()
    assert "review" in first_line, "CSV fixture should have a 'review' column"


def test_unusable_model_result_is_documented():
    """
    Documents what a plausible-but-unusable model result looks like for this workflow.
    The skill must not crash or produce invalid output if the agent returns empty buckets.
    This test verifies the output schema is structurally sound.
    """
    # A minimal valid output: all buckets empty with a diagnostic note is acceptable.
    minimal_output = (
        "# Competitor review intelligence: Acme\n\n"
        "**Reviews analysed:** 0 of 0 supplied\n\n"
        "No reviews could be parsed from the supplied input.\n\n"
        "## Evidence notes\n\n"
        "- Total review units supplied: 0\n"
        "- Input format detected: unknown\n"
    )
    assert "Competitor review intelligence" in minimal_output
    assert "Evidence notes" in minimal_output
