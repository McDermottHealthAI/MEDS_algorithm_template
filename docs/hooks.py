"""Render the installed core specification without maintaining a second source."""

import json
import re
from pathlib import Path

from meds_algorithm.spec import architecture, specification, validation_guide


def on_page_markdown(markdown, page, **kwargs):
    if page.file.src_uri == "reference/spec.md":
        return markdown + "\n\n" + specification()
    if page.file.src_uri == "reference/architecture.md":
        return architecture().replace("(src/meds_algorithm/CONTRACT.md)", "(spec.md)")
    if page.file.src_uri == "reference/tests.md":
        return validation_guide()
    if page.file.src_uri == "prompt-builder.md":
        readme = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
        section = readme.split("<!-- --8<-- [start:implementation-prompt] -->", 1)[1].split(
            "<!-- --8<-- [end:implementation-prompt] -->", 1
        )[0]
        prompt = re.search(r"```text\n(.*?)\n```", section, re.DOTALL).group(1)
        # JSON lives inside an HTML script element: escape '<' so source text cannot close it.
        payload = json.dumps(prompt).replace("<", "\\u003c")
        return markdown.replace(
            "<!-- prompt-template -->",
            f'<script type="application/json" data-prompt-template>{payload}</script>',
        )
    return markdown
