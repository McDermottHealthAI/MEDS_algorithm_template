"""Render the installed core specification without maintaining a second source."""

from meds_model_core.spec import specification


def on_page_markdown(markdown, page, **kwargs):
    if page.file.src_uri == "reference/spec.md":
        return markdown + "\n\n" + specification()
    return markdown
