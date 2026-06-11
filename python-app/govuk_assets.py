"""GOV.UK Frontend paths: Jinja templates from govuk-frontend-jinja, CSS/JS from govuk-frontend release."""

import os
from pathlib import Path

import govuk_frontend_jinja

# Matches govuk-frontend-jinja 4.x → GOV.UK Frontend 6.0.x (see compatibility table on GitHub)
GOVUK_VERSION = os.getenv("GOVUK_VERSION", "6.0.0")
GOVUK_FRONTEND_DIR = os.getenv("GOVUK_FRONTEND_DIR", "govuk_frontend")


def jinja_package_root() -> Path:
    """Installed govuk_frontend_jinja package directory (templates only)."""
    return Path(govuk_frontend_jinja.__file__).resolve().parent


def frontend_release_root(app_root: str) -> Path:
    """Precompiled GOV.UK Frontend release (CSS, JS, /assets) paired with the Jinja macros."""
    return Path(app_root) / GOVUK_FRONTEND_DIR


def stylesheet_filename() -> str:
    return f"govuk-frontend-{GOVUK_VERSION}.min.css"


def javascript_filename() -> str:
    return f"govuk-frontend-{GOVUK_VERSION}.min.js"
