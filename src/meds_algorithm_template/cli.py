"""Small version-bound frontend to Copier's public API."""

import argparse
from importlib.metadata import version
from pathlib import Path

import yaml
from copier import run_copy

TEMPLATE_REPOSITORY = "https://github.com/McDermottHealthAI/MEDS_algorithm_template.git"


def main(argv: list[str] | None = None) -> None:
    release = version("meds-algorithm-template")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=release)
    parser.add_argument("destination", type=Path, help="Directory for the generated repository")
    parser.add_argument(
        "--defaults", action="store_true", help="Use defaults instead of interactive questions"
    )
    parser.add_argument("--data-file", type=Path, help="YAML mapping of Copier answers")
    parser.add_argument("--trust", action="store_true", help="Trust the reviewed template's Copier features")
    args = parser.parse_args(argv)
    answers = None
    if args.data_file is not None:
        try:
            answers = yaml.safe_load(args.data_file.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            parser.error(f"Cannot read answers: {error}")
        if not isinstance(answers, dict) or any(not isinstance(key, str) for key in answers):
            parser.error("The answers file must contain a mapping with string keys")
    run_copy(
        TEMPLATE_REPOSITORY,
        args.destination,
        vcs_ref=f"v{release}",
        data=answers,
        defaults=args.defaults,
        unsafe=args.trust,
    )
