#!/usr/bin/env python3
"""
Toutatis Integration — OSINT data do Instagram: email, telefone, metadados da conta.

Integra as técnicas do toutatis (megadose/toutatis) no Instagram Toolkit,
usando a sessão já autenticada do instagrapi para extrair dados que a API
pública não expõe: email ofuscado, telefone ofuscado, WhatsApp vinculado, etc.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from instagram_toolkit.rate_limiter import RateLimiter
from urllib.parse import quote_plus

import phonenumbers
import pycountry
from phonenumbers.phonenumberutil import region_code_for_country_code
from requests import Session as RequestsSession

logger = logging.getLogger("toutatis")

# ---------------------------------------------------------------------------
# Constantes da API do Instagram (mesmas do toutatis original)
# ---------------------------------------------------------------------------
IG_APP_ID_WEB = "936619743392459"
IG_APP_ID_LOOKUP = "124024574287414"
USER_AGENT_IPHONE = "Instagram 64.0.0.14.96"
USER_AGENT_LOOKUP = "Instagram 101.0.0.15.120"


# ---------------------------------------------------------------------------
# Funções principais
# ---------------------------------------------------------------------------


def extract_session_id(instagrapi_client: Any) -> str | None:
    """Extrai o sessionid da sessão do instagrapi."""
    try:
        settings = instagrapi_client.get_settings()
        cookies = settings.get("cookies", {}) or {}
        for key in ("sessionid", "session_id", "sessionid_login"):
            if key in cookies:
                return cookies[key]
        return None
    except Exception as e:
        logger.warning("Falha ao extrair sessionid: %s", e)
        return None


def get_user_info_via_api(
    username: str | None = None,
    user_id: int | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """
    Busca informações completas do usuário via API interna do Instagram.
    Retorna o mesmo que o endpoint /users/<id>/info/.
    """
    if not session_id:
        return {"error": "Session ID é obrigatório"}

    # Resolve user_id se só veio username
    if user_id is None and username:
        resolved = _resolve_user_id(username, session_id)
        if resolved.get("error"):
            return resolved
        user_id = resolved["id"]

    if not user_id:
        return {"error": "Username ou user_id é obrigatório"}

    ses = RequestsSession()
    ses.cookies.set("sessionid", session_id)
    ses.headers.update({"User-Agent": USER_AGENT_IPHONE})

    try:
        resp = ses.get(
            f"https://i.instagram.com/api/v1/users/{user_id}/info/",
            timeout=15,
        )
        if resp.status_code == 429:
            return {"error": "Rate limit"}
        resp.raise_for_status()
        data = resp.json().get("user")
        if not data:
            return {"error": "Usuário não encontrado"}
        data["userID"] = str(user_id)
        return {"user": data, "error": None}
    except Exception as e:
        return {"error": str(e)}


def _resolve_user_id(username: str, session_id: str) -> dict[str, Any]:
    """Resolve username → user_id via web_profile_info."""
    ses = RequestsSession()
    ses.cookies.set("sessionid", session_id)
    ses.headers.update(
        {"User-Agent": "iphone_ua", "x-ig-app-id": IG_APP_ID_WEB}
    )
    try:
        resp = ses.get(
            f"https://i.instagram.com/api/v1/users/web_profile_info/"
            f"?username={username}",
            timeout=15,
        )
        if resp.status_code == 404:
            return {"id": None, "error": "User not found"}
        uid = resp.json()["data"]["user"]["id"]
        return {"id": uid, "error": None}
    except json.JSONDecodeError:
        return {"id": None, "error": "Rate limit"}
    except Exception as e:
        return {"id": None, "error": str(e)}


def advanced_lookup(username: str, session_id: str) -> dict[str, Any]:
    """
    POST /users/lookup/ — retorna dados ofuscados (email e telefone).
    É o que diferencia o toutatis da API normal.
    """
    payload = json.dumps(
        {"q": username, "skip_recovery": "1"}, separators=(",", ":")
    )
    body = "signed_body=SIGNATURE." + quote_plus(payload)

    ses = RequestsSession()
    ses.cookies.set("sessionid", session_id)
    ses.headers.update(
        {
            "Accept-Language": "en-US",
            "User-Agent": USER_AGENT_LOOKUP,
            "Content-Type": (
                "application/x-www-form-urlencoded; charset=UTF-8"
            ),
            "X-IG-App-ID": IG_APP_ID_LOOKUP,
            "Accept-Encoding": "gzip, deflate",
            "Host": "i.instagram.com",
            "Connection": "keep-alive",
        }
    )
    try:
        resp = ses.post(
            "https://i.instagram.com/api/v1/users/lookup/",
            data=body,
            timeout=15,
        )
        return {"user": resp.json(), "error": None}
    except json.JSONDecodeError:
        return {"user": None, "error": "rate limit"}
    except Exception as e:
        return {"user": None, "error": str(e)}


def format_phone(phone: str, country_code: str | int | None) -> str:
    """Formata telefone com nome do país."""
    full = f"+{country_code} {phone}" if country_code else phone
    try:
        pn = phonenumbers.parse(full)
        cc = region_code_for_country_code(pn.country_code)
        country = pycountry.countries.get(alpha_2=cc)
        if country:
            full += f" ({country.name})"
    except Exception:
        pass
    return full


def osint_profile(
    username: str | None = None,
    user_id: int | None = None,
    session_id: str | None = None,
    instagrapi_client: Any | None = None,
    rate_limiter: RateLimiter | None = None,
) -> dict[str, Any]:
    """
    Coleta tudo que o toutatis extrai de um perfil Instagram.
    Aceita session_id direto ou extrai do instagrapi client.
    """
    if session_id is None and instagrapi_client is not None:
        session_id = extract_session_id(instagrapi_client)

    if not session_id:
        return {"error": "Session ID é obrigatório"}

    result: dict[str, Any] = {}

    # 1. Info básica via API
    info = get_user_info_via_api(
        username=username, user_id=user_id, session_id=session_id
    )
    if info.get("error"):
        # Tenta resolver username se não veio
        if username and not user_id:
            resolved = _resolve_user_id(username, session_id)
            if resolved.get("id"):
                info = get_user_info_via_api(
                    user_id=resolved["id"], session_id=session_id
                )
            else:
                return {"error": resolved.get("error", "Falha na consulta")}
        else:
            return {"error": info["error"]}

    user = info["user"]
    result["username"] = user.get("username")
    result["userID"] = user.get("userID")
    result["full_name"] = user.get("full_name")
    result["is_verified"] = user.get("is_verified", False)
    result["is_business"] = user.get("is_business", False)
    result["is_private"] = user.get("is_private", False)
    result["follower_count"] = user.get("follower_count", 0)
    result["following_count"] = user.get("following_count", 0)
    result["media_count"] = user.get("media_count", 0)
    result["external_url"] = user.get("external_url")
    result["total_igtv_videos"] = user.get("total_igtv_videos", 0)
    result["biography"] = user.get("biography", "")
    result["is_whatsapp_linked"] = user.get("is_whatsapp_linked", False)
    result["is_memorialized"] = user.get("is_memorialized", False)
    result["is_new_to_instagram"] = user.get("is_new_to_instagram", False)
    result["profile_pic_url"] = (
        user.get("hd_profile_pic_url_info", {}) or {}
    ).get("url")

    # Email público
    if user.get("public_email"):
        result["public_email"] = user["public_email"]

    # Telefone público
    if user.get("public_phone_number"):
        result["public_phone"] = format_phone(
            user["public_phone_number"],
            user.get("public_phone_country_code"),
        )

    # 2. Advanced lookup (email/phone ofuscados)
    if rate_limiter is not None:
        rate_limiter.delay()
    lookup = advanced_lookup(user.get("username", ""), session_id)
    if lookup.get("error"):
        result["lookup_error"] = lookup["error"]
    elif lookup.get("user"):
        lu = lookup["user"]
        if lu.get("obfuscated_email"):
            result["obfuscated_email"] = lu["obfuscated_email"]
        if lu.get("obfuscated_phone"):
            result["obfuscated_phone"] = lu["obfuscated_phone"]
        if lu.get("message"):
            result["lookup_message"] = lu["message"]

    return result


def print_osint_report(data: dict[str, Any]) -> None:
    """Exibe o resultado formatado igual ao toutatis original."""
    if "error" in data:
        print(f"❌ Erro: {data['error']}")
        return

    lines = [
        ("Informations about", data.get("username")),
        ("userID", data.get("userID")),
        ("Full Name", data.get("full_name")),
        (
            "Verified",
            f'{data.get("is_verified")} | Is business Account: {data.get("is_business")}',
        ),
        ("Is private Account", str(data.get("is_private"))),
        (
            "Follower",
            f'{data.get("follower_count")} | Following: {data.get("following_count")}',
        ),
        ("Number of posts", str(data.get("media_count"))),
    ]
    if data.get("external_url"):
        lines.append(("External url", data["external_url"]))
    lines.append(("IGTV posts", str(data.get("total_igtv_videos"))))

    bio = data.get("biography", "")
    if bio:
        lines.append(("Biography", ("\n" + " " * 25).join(bio.split("\n"))))

    lines.append(("Linked WhatsApp", str(data.get("is_whatsapp_linked"))))
    lines.append(("Memorial Account", str(data.get("is_memorialized"))))
    lines.append(("New Instagram user", str(data.get("is_new_to_instagram"))))

    if data.get("public_email"):
        lines.append(("Public Email", data["public_email"]))
    if data.get("public_phone"):
        lines.append(("Public Phone number", data["public_phone"]))

    # Lookup results
    if data.get("lookup_error") == "rate limit":
        lines.append(
            (
                "Lookup",
                "Rate limit — aguarde alguns minutos antes de tentar novamente",
            )
        )
    elif data.get("lookup_message") == "No users found":
        lines.append(("Lookup", "Não foi possível fazer lookup desta conta"))
    elif data.get("lookup_message"):
        lines.append(("Lookup", data["lookup_message"]))
    else:
        if data.get("obfuscated_email"):
            lines.append(("Obfuscated email", data["obfuscated_email"]))
        if data.get("obfuscated_phone"):
            lines.append(("Obfuscated phone", data["obfuscated_phone"]))

    lines.append(("─" * 24, ""))
    if data.get("profile_pic_url"):
        lines.append(("Profile Picture", data["profile_pic_url"]))

    for label, value in lines:
        if value:
            print(f"{label:<24}: {value}")
