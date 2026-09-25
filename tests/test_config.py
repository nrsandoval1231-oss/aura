"""`.env` loading.

Credentials never reach the repository, so the only thing tested here is the
parsing and precedence — in particular that a file on disk cannot silently
override a variable someone deliberately exported.
"""

from __future__ import annotations

import os

import pytest

from forge.config import ENV_FILE, load_env


@pytest.fixture
def env_file(tmp_path):
    def write(body: str):
        path = tmp_path / ".env"
        path.write_text(body, encoding="utf-8")
        return path

    return write


def test_values_are_loaded(env_file, monkeypatch):
    monkeypatch.delenv("FORGE_TEST_KEY", raising=False)
    loaded = load_env(env_file("FORGE_TEST_KEY=abc123\n"))

    assert loaded == {"FORGE_TEST_KEY": "abc123"}
    assert os.environ["FORGE_TEST_KEY"] == "abc123"


def test_an_existing_variable_wins_over_the_file(env_file, monkeypatch):
    """A shell export is a deliberate act; a file should not quietly beat it."""
    monkeypatch.setenv("FORGE_TEST_KEY", "from-shell")
    loaded = load_env(env_file("FORGE_TEST_KEY=from-file\n"))

    assert loaded == {}
    assert os.environ["FORGE_TEST_KEY"] == "from-shell"


def test_override_is_available_when_asked_for(env_file, monkeypatch):
    monkeypatch.setenv("FORGE_TEST_KEY", "from-shell")
    load_env(env_file("FORGE_TEST_KEY=from-file\n"), override=True)

    assert os.environ["FORGE_TEST_KEY"] == "from-file"


def test_blank_placeholders_are_skipped(env_file, monkeypatch):
    """An unfilled `.env.example` line must not look configured.

    Setting the variable to empty would pass a presence check and then fail
    later, further from the cause.
    """
    monkeypatch.delenv("FORGE_TEST_KEY", raising=False)
    assert load_env(env_file("FORGE_TEST_KEY=\n")) == {}
    assert "FORGE_TEST_KEY" not in os.environ


def test_comments_and_blank_lines_are_ignored(env_file, monkeypatch):
    monkeypatch.delenv("FORGE_TEST_KEY", raising=False)
    loaded = load_env(env_file("# a comment\n\n   \nFORGE_TEST_KEY=value\n"))
    assert loaded == {"FORGE_TEST_KEY": "value"}


def test_quotes_are_stripped_and_inner_characters_survive(env_file, monkeypatch):
    monkeypatch.delenv("FORGE_TEST_KEY", raising=False)
    monkeypatch.delenv("FORGE_TEST_OTHER", raising=False)
    loaded = load_env(env_file("FORGE_TEST_KEY=\"a b#c\"\nFORGE_TEST_OTHER='x y'\n"))

    assert loaded["FORGE_TEST_KEY"] == "a b#c"
    assert loaded["FORGE_TEST_OTHER"] == "x y"


def test_export_prefix_is_tolerated(env_file, monkeypatch):
    monkeypatch.delenv("FORGE_TEST_KEY", raising=False)
    assert load_env(env_file("export FORGE_TEST_KEY=value\n")) == {"FORGE_TEST_KEY": "value"}


def test_a_missing_file_is_not_an_error(tmp_path):
    assert load_env(tmp_path / "absent.env") == {}


def test_default_path_is_the_repository_root():
    assert ENV_FILE.name == ".env"
    assert (ENV_FILE.parent / "pyproject.toml").is_file()


def test_env_is_ignored_by_git():
    """The whole scheme rests on this one line staying in .gitignore."""
    ignore = (ENV_FILE.parent / ".gitignore").read_text(encoding="utf-8").split("\n")
    assert ".env" in ignore


def test_example_names_every_variable_the_code_reads():
    """A credential the code wants but the example omits is a silent stop later."""
    from forge.providers.model_provider import CAPABILITY_MODEL_ENV, PROVIDERS

    example = (ENV_FILE.parent / ".env.example").read_text(encoding="utf-8")
    for spec in PROVIDERS.values():
        assert spec.api_key_env in example, spec.api_key_env
        assert spec.model_env in example, spec.model_env
    # Capability-keyed model ids are what the primary routes actually read (F11).
    for model_env in CAPABILITY_MODEL_ENV.values():
        assert model_env in example, model_env
    assert "TYPESAFE_API_KEY" not in example


def test_example_carries_no_values_at_all():
    """DEC-010: the example carries every name and no value.

    This assertion used to be narrowed to keys ending `_API_KEY`, which is how
    audit F13 found two committed model ids sitting in a file whose own header
    said it carried names only. A model id is not a secret, but committing one
    re-creates the decay DEC-008 exists to prevent — and a gate that checks a
    subset of a rule reports compliance with the rule.
    """
    example = (ENV_FILE.parent / ".env.example").read_text(encoding="utf-8")
    offenders = []
    for line in example.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if value.strip():
            offenders.append(key.strip())
    assert offenders == [], (
        f"{offenders} carry values in .env.example. Names belong here, values in .env "
        "(DEC-010). If one is a real credential it has been committed and must be rotated."
    )
