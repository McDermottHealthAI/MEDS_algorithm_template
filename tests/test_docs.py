"""Documentation embedding keeps one canonical prompt and inert source text."""

import importlib.util
import json
import re
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def load_hooks():
    spec = importlib.util.spec_from_file_location("docs_hooks", ROOT / "docs/hooks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prompt_builder_embeds_the_canonical_readme_prompt():
    hooks = load_hooks()
    page = SimpleNamespace(file=SimpleNamespace(src_uri="prompt-builder.md"))
    result = hooks.on_page_markdown((ROOT / "docs/prompt-builder.md").read_text(), page)
    payload = re.search(r"data-prompt-template>(.*?)</script>", result, re.DOTALL).group(1)
    readme = (ROOT / "README.md").read_text()
    section = readme.split("<!-- --8<-- [start:implementation-prompt] -->")[1].split(
        "<!-- --8<-- [end:implementation-prompt] -->"
    )[0]
    expected = re.search(r"```text\n(.*?)\n```", section, re.DOTALL).group(1)
    assert json.loads(payload) == expected
    assert "<!-- prompt-template -->" not in result


def test_algorithm_release_guide_uses_generated_source():
    hooks = load_hooks()
    page = SimpleNamespace(file=SimpleNamespace(src_uri="publishing-algorithms.md"))
    result = hooks.on_page_markdown((ROOT / "docs/publishing-algorithms.md").read_text(), page)
    assert "<!-- algorithm-release-guide -->" not in result
    assert "{{" not in result
    assert "scripts/check_distribution.sh" in result
    assert "my-algorithm==$version" in result


def test_prompt_source_cannot_close_its_json_script_element(tmp_path, monkeypatch):
    hooks = load_hooks()
    monkeypatch.setattr(hooks, "__file__", str(tmp_path / "docs/hooks.py"))
    prompt = '</script><script>alert("source text")</script>'
    (tmp_path / "README.md").write_text(
        "<!-- --8<-- [start:implementation-prompt] -->\n```text\n"
        + prompt
        + "\n```\n<!-- --8<-- [end:implementation-prompt] -->"
    )
    page = SimpleNamespace(file=SimpleNamespace(src_uri="prompt-builder.md"))
    result = hooks.on_page_markdown("<!-- prompt-template -->", page)
    assert result.count("</script>") == 1
    assert json.loads(result.split("data-prompt-template>", 1)[1].split("</script>", 1)[0]) == prompt
