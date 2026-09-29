import os

import pytest

from qr import secrets


def test_secrets_file_is_read_without_overriding_the_environment(tmp_path, monkeypatch):
    path = tmp_path / "secrets.env"
    path.write_text("# comment\nQR_TEST_A=alpha\nQR_TEST_B='beta'\nQR_TEST_EMPTY=\n")
    monkeypatch.setenv("QR_TEST_B", "from-env")
    monkeypatch.delenv("QR_TEST_A", raising=False)
    found = secrets.load(path)
    assert found == {"QR_TEST_A": "alpha", "QR_TEST_B": "beta"}
    assert os.environ["QR_TEST_A"] == "alpha" and os.environ["QR_TEST_B"] == "from-env"


def test_a_missing_key_names_the_variable_not_a_value(monkeypatch, tmp_path):
    monkeypatch.setattr(secrets, "SECRETS_FILE", tmp_path / "none.env")
    monkeypatch.delenv("QR_TEST_MISSING", raising=False)
    with pytest.raises(KeyError, match="QR_TEST_MISSING is not set"):
        secrets.require("QR_TEST_MISSING")
