"""Optional Keycloak Admin API helpers for updating user profile attributes."""

import os

import requests


def _issuer_parts():
    issuer = os.getenv("OIDC_ISSUER", "")
    if "/realms/" not in issuer:
        raise ValueError("OIDC_ISSUER must include /realms/{realm}")
    base, realm = issuer.rsplit("/realms/", 1)
    return base, realm


def _admin_token():
    client_id = os.getenv("KEYCLOAK_ADMIN_CLIENT_ID")
    client_secret = os.getenv("KEYCLOAK_ADMIN_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    base = os.getenv("KEYCLOAK_ADMIN_URL")
    if not base:
        base, _ = _issuer_parts()

    admin_realm = os.getenv("KEYCLOAK_ADMIN_REALM", "master")
    response = requests.post(
        f"{base}/realms/{admin_realm}/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        verify=False,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["access_token"], base


def update_display_name(user_id: str, display_name: str) -> None:
    if not user_id:
        raise ValueError("Missing Keycloak user id")

    _, user_realm = _issuer_parts()
    token_data = _admin_token()
    if not token_data:
        raise RuntimeError(
            "Profile updates need KEYCLOAK_ADMIN_CLIENT_ID and KEYCLOAK_ADMIN_CLIENT_SECRET "
            "(service account with manage-users)."
        )

    token, base = token_data
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    user_url = f"{base}/admin/realms/{user_realm}/users/{user_id}"

    user = requests.get(user_url, headers=headers, verify=False, timeout=15)
    user.raise_for_status()
    payload = user.json()

    payload["firstName"] = display_name
    attributes = payload.get("attributes") or {}
    attributes["displayName"] = [display_name]
    payload["attributes"] = attributes

    response = requests.put(user_url, headers=headers, json=payload, verify=False, timeout=15)
    response.raise_for_status()
