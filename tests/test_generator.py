"""The packaged command must select the corresponding release and preserve Copier options."""

import pytest

from meds_algorithm_template import cli


def test_generator_binds_installed_version_and_forwards_answers(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(cli, "version", lambda name: "0.4.0a1")
    monkeypatch.setattr(cli, "run_copy", lambda *args, **kwargs: calls.append((args, kwargs)))
    answers = tmp_path / "answers.yaml"
    answers.write_text("algorithm_name: Example\nprofiles: [supervised, probe]\n")
    destination = tmp_path / "algorithm"
    cli.main([str(destination), "--defaults", "--trust", "--data-file", str(answers)])
    assert calls == [
        (
            ("https://github.com/McDermottHealthAI/MEDS_algorithm_template.git", destination),
            {
                "vcs_ref": "v0.4.0a1",
                "data": {"algorithm_name": "Example", "profiles": ["supervised", "probe"]},
                "defaults": True,
                "unsafe": True,
            },
        )
    ]
    calls.clear()
    cli.main([str(destination)])
    assert calls[0][1]["defaults"] is False and calls[0][1]["unsafe"] is False


@pytest.mark.parametrize("content", ["[one, two]", "null", "1: example", "bad: ["])
def test_bad_answers_fail_before_copy(monkeypatch, tmp_path, content):
    def forbidden(*args, **kwargs):
        pytest.fail("Copier must not run with invalid answers")

    monkeypatch.setattr(cli, "run_copy", forbidden)
    answers = tmp_path / "bad.yaml"
    answers.write_text(content)
    with pytest.raises(SystemExit) as error:
        cli.main([str(tmp_path / "output"), "--data-file", str(answers)])
    assert error.value.code == 2


def test_version_does_not_generate(monkeypatch, capsys):
    monkeypatch.setattr(cli, "version", lambda name: "0.4.0a1")
    with pytest.raises(SystemExit) as error:
        cli.main(["--version"])
    assert error.value.code == 0
    assert capsys.readouterr().out.strip() == "0.4.0a1"
