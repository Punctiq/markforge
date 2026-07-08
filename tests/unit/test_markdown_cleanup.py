from pathlib import Path

from app.services.markdown_cleanup import clean_broken_emphasis_artifacts, cleanup_markdown


def test_generic_broken_heading_cleanup():
    markdown = "\n".join(
        [
            "# **Example Scope of ****Service**",
            "## **S****ervice**** Architecture**** Overview**",
            "### **A****pplication Landing Zones**",
        ]
    )

    result = cleanup_markdown(markdown)

    assert result.markdown == "\n".join(
        [
            "# Example Scope of Service",
            "## Service Architecture Overview",
            "### Application Landing Zones",
        ]
    )


def test_generic_broken_caption_cleanup():
    markdown = "\n".join(
        [
            "*Figure **12**: **H**igh-level architectural diagram of Example **S**ervices*",
            "*Table **4**: Version History*",
            "*Figure** 2**: **Management subscription** service elements *",
        ]
    )

    result = cleanup_markdown(markdown)

    assert result.markdown == "\n".join(
        [
            "*Figure 12: High-level architectural diagram of Example Services*",
            "*Table 4: Version History*",
            "*Figure 2: Management subscription service elements*",
        ]
    )


def test_split_word_bold_cleanup_helper_is_conservative():
    assert clean_broken_emphasis_artifacts("**S****ervice**") == "Service"
    assert clean_broken_emphasis_artifacts("**Cloud**** Platform**") == "Cloud Platform"
    assert clean_broken_emphasis_artifacts("**H**igh-level") == "High-level"
    assert clean_broken_emphasis_artifacts("**P**roposal") == "Proposal"
    assert clean_broken_emphasis_artifacts("Keep **important** text") == "Keep **important** text"
    assert clean_broken_emphasis_artifacts("**First** **Second**") == "**First** **Second**"


def test_full_document_cleanup_preserves_structures():
    fixture = Path("tests/fixtures/markdown/docx_artifacts.md").read_text(encoding="utf-8")

    result = cleanup_markdown(fixture)

    assert 'title: "**Keep Metadata Untouched**"' in result.markdown
    assert "Main sections: **Do Not Normalize Here**" in result.markdown
    assert "# Example Scope of Service" in result.markdown
    assert "![Figure 1](figures/figure-1.png)" in result.markdown
    assert "*Figure 1: High-level architecture*" in result.markdown
    assert "| **Keep** | **Bold table text** |" in result.markdown
    assert "Regular **important** text stays bold." in result.markdown


def test_normal_links_and_inline_image_links_are_preserved():
    markdown = "\n".join(
        [
            "See [**P**roposal](https://example.test/docs/**P**roposal) for details.",
            "Inline image ![**P**review](figures/**P**review.png) stays intact.",
        ]
    )

    result = cleanup_markdown(markdown)

    assert result.markdown == markdown


def test_code_blocks_are_preserved():
    markdown = "\n".join(
        [
            "```",
            "# **Do Not Clean Code**",
            "echo '**P**roposal'",
            "```",
        ]
    )

    result = cleanup_markdown(markdown)

    assert result.markdown == markdown
