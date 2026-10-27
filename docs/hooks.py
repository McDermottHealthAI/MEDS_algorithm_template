"""Render the installed core specification without maintaining a second source."""

from meds_algorithm_core.spec import architecture, specification


def on_page_markdown(markdown, page, **kwargs):
    if page.file.src_uri == "reference/spec.md":
        return markdown + "\n\n" + specification()
    if page.file.src_uri == "reference/architecture.md":
        return architecture().replace("(src/meds_algorithm_core/CONTRACT.md)", "(spec.md)")
    return markdown
