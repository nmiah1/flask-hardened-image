import os
from functools import wraps

import requests
from authlib.integrations.flask_client import OAuth
from flask import Flask, redirect, render_template, request, session, url_for, send_from_directory
from jinja2 import ChoiceLoader, FileSystemLoader, PackageLoader, PrefixLoader
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from werkzeug.middleware.proxy_fix import ProxyFix

from govuk_assets import (
    GOVUK_VERSION,
    frontend_release_root,
    javascript_filename,
    stylesheet_filename,
)
from keycloak_admin import update_display_name

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24))
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

app.jinja_env.globals["govukRebrand"] = True
app.jinja_env.lstrip_blocks = True
app.jinja_env.trim_blocks = True
app.jinja_loader = ChoiceLoader(
    [
        FileSystemLoader(os.path.join(app.root_path, "templates")),
        PrefixLoader({"govuk_frontend_jinja": PackageLoader("govuk_frontend_jinja")}),
    ]
)

CLIENT_ID = os.getenv("CLIENT_ID")
OIDC_ISSUER = os.getenv("OIDC_ISSUER")

SERVICE_NAME = os.getenv("SERVICE_NAME", "Internal Access")
PHASE_TAG = os.getenv("PHASE_TAG", "Private Beta")
SIGN_IN_HOST = os.getenv("SIGN_IN_HOST", "sso.service.security.gov.uk")
SERVICE_DESCRIPTION = os.getenv(
    "SERVICE_DESCRIPTION",
    "This is a service for accessing internal UK Government services for civil servants and public sector users.",
)
FEEDBACK_URL = os.getenv("FEEDBACK_URL", "https://www.gov.uk/help")
PRIVACY_URL = os.getenv("PRIVACY_URL", "#")
TERMS_URL = os.getenv("TERMS_URL", "#")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "internal-access@dsit.gov.uk")


def _govuk_release_root():
    return frontend_release_root(app.root_path)


if not CLIENT_ID or not OIDC_ISSUER:
    print("WARNING: CLIENT_ID or OIDC_ISSUER is not set – sign-in will not work until configured.")

oauth = OAuth(app)
if CLIENT_ID and OIDC_ISSUER:
    oauth.register(
        name="keycloak",
        client_id=CLIENT_ID,
        client_secret=os.getenv("CLIENT_SECRET"),
        server_metadata_url=f"{OIDC_ISSUER}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile email", "verify": False},
    )


@app.context_processor
def inject_govuk_frontend():
    """assetPath in templates matches GOV.UK Frontend precompiled layout (/assets, /stylesheets, /javascripts)."""
    return {
        "govuk_version": GOVUK_VERSION,
        "assetPath": "/assets",
        "govuk_stylesheet": url_for("govuk_stylesheets", filename=stylesheet_filename()),
        "govuk_javascript": url_for("govuk_javascripts", filename=javascript_filename()),
    }


def template_context(active_page=None):
    return {
        "user": session.get("user"),
        "active_page": active_page,
        "service_name": SERVICE_NAME,
        "phase_tag": PHASE_TAG,
        "sign_in_host": SIGN_IN_HOST,
        "service_description": SERVICE_DESCRIPTION,
        "feedback_url": FEEDBACK_URL,
        "privacy_url": PRIVACY_URL,
        "terms_url": TERMS_URL,
        "support_email": SUPPORT_EMAIL,
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


@app.route("/assets/<path:path>")
def govuk_assets(path):
    return send_from_directory(
        os.path.join(_govuk_release_root(), "assets"),
        path,
        max_age=86400,
    )


@app.route("/stylesheets/<path:filename>")
def govuk_stylesheets(filename):
    return send_from_directory(_govuk_release_root(), filename, max_age=86400)


@app.route("/javascripts/<path:filename>")
def govuk_javascripts(filename):
    return send_from_directory(_govuk_release_root(), filename, max_age=86400)


@app.route("/")
def home():
    if session.get("user"):
        return redirect(url_for("dashboard"))
    return render_template("home.html", **template_context())


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", **template_context(active_page="dashboard"))


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = session["user"]
    display_name = user.get("display_name") or user.get("name") or ""
    profile_message = None
    profile_error = None

    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        if not display_name:
            profile_error = "Enter a display name."
        else:
            try:
                update_display_name(user["sub"], display_name)
                user["display_name"] = display_name
                user["name"] = display_name
                session["user"] = user
                profile_message = "Your profile has been updated."
            except Exception as exc:
                profile_error = str(exc)

    return render_template(
        "profile.html",
        **template_context(active_page="profile"),
        display_name=display_name,
        profile_message=profile_message,
        profile_error=profile_error,
    )


@app.route("/help")
@login_required
def help():
    return render_template("help.html", **template_context(active_page="help"))


@app.route("/login")
def login():
    if session.get("user"):
        return redirect(url_for("dashboard"))
    if not CLIENT_ID:
        return "System configuration error: CLIENT_ID is missing.", 500

    redirect_uri = url_for("auth", _external=True)
    next_url = request.args.get("next")
    if next_url:
        session["post_login_redirect"] = next_url

    return oauth.keycloak.authorize_redirect(redirect_uri)


@app.route("/auth")
def auth():
    token = oauth.keycloak.authorize_access_token()
    userinfo = token["userinfo"]
    attributes = userinfo.get("displayName") or userinfo.get("display_name")

    session["user"] = {
        "sub": userinfo.get("sub"),
        "name": userinfo.get("name"),
        "email": userinfo.get("email"),
        "username": userinfo.get("preferred_username"),
        "display_name": attributes or userinfo.get("name"),
        "sid": userinfo.get("sid"),
        "roles": userinfo.get("realm_access", {}).get("roles", []),
        "expires_at": token.get("expires_at"),
    }

    destination = session.pop("post_login_redirect", None) or url_for("dashboard")
    return redirect(destination)


@app.route("/logout")
def logout():
    session.clear()
    keycloak_logout_url = (
        f"{OIDC_ISSUER}/protocol/openid-connect/logout"
        f"?post_logout_redirect_uri={url_for('home', _external=True)}"
        f"&client_id={CLIENT_ID}"
    )
    return redirect(keycloak_logout_url)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
