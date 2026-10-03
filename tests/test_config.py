import logging

import pytest
from pydantic import ValidationError

from commodity_scalper.config import DEMO_REST_URL, Settings
from commodity_scalper.utils.logging import RedactingFilter


def test_demo_configuration():
    settings = Settings(_env_file=None, capital_env="demo")
    assert settings.rest_url == DEMO_REST_URL


def test_live_is_always_blocked():
    with pytest.raises(ValidationError, match="DEMO only"):
        Settings(_env_file=None, capital_env="live", phase1_allow_live=False)
    with pytest.raises(ValidationError, match="live access is disabled"):
        Settings(_env_file=None, capital_env="demo", phase1_allow_live=True)


def test_credentials_are_required():
    with pytest.raises(ValueError, match="CAPITAL_API_KEY"):
        Settings(_env_file=None).require_credentials()


def test_redaction(caplog):
    logger = logging.getLogger("redaction-test")
    logger.addFilter(RedactingFilter(["super-secret"]))
    with caplog.at_level(logging.INFO):
        logger.info("password=abc token super-secret CST='xyz'")
    text = caplog.text
    assert "abc" not in text and "super-secret" not in text and "xyz" not in text
