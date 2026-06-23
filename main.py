# Tales Oliveira
# 22/06/2026

import argparse
import logging
import os
import re
from dataclasses import dataclass

import requests
from dotenv import load_dotenv
from supabase import Client, create_client

MESSAGE_TEMPLATE = "Olá, {nome_contato} tudo bem com você?"
REQUEST_TIMEOUT_SECONDS = 30

# Credenciais do arquivo .env
@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_key: str
    supabase_table: str
    zapi_instance_id: str
    zapi_instance_token: str
    zapi_client_token: str
    default_country_code: str
    max_contacts: int

# Contato inserido no banco
@dataclass(frozen=True)
class Contact:
    name: str
    phone: str

# ================================== Funções ==================================
# usei para testar no terminal
def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

# logs do terminal, para ocultar o telefone "*********X123"
def mask_phone(phone: str) -> str:
    return "****" if len(phone) <= 4 else f"{'*' * (len(phone) - 4)}{phone[-4:]}"

# lê o arquivo .env
def get_env(name: str, *, required: bool = True, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    if required and not value:
        raise RuntimeError(f"Variável não encontrada: {name}")
    return value

# valida todas as configurações tanto do Supabase quando do Z-API
def load_settings(require_zapi: bool) -> Settings:
    load_dotenv()

    try:
        max_contacts = int(get_env("MAX_CONTACTS", required=False, default="3"))
    except ValueError as exc:
        raise RuntimeError("MAX_CONTACTS precisa ser um número inteiro.") from exc

    if not 1 <= max_contacts <= 3:
        raise RuntimeError(
            f"MAX_CONTACTS precisa estar entre 1 e 3."
        )

    default_country_code = get_env(
        "DEFAULT_COUNTRY_CODE",
        required=False,
        default="55",
    )

    if not default_country_code.isdigit():
        raise RuntimeError("DEFAULT_COUNTRY_CODE deve conter somente números.")

    return Settings(
        supabase_url=get_env("SUPABASE_URL"),
        supabase_key=get_env("SUPABASE_KEY"),
        supabase_table=get_env("SUPABASE_TABLE", required=False, default="contatos"),

        zapi_instance_id=get_env("ZAPI_INSTANCE_ID", required=require_zapi),
        zapi_instance_token=get_env("ZAPI_INSTANCE_TOKEN", required=require_zapi),
        zapi_client_token=get_env("ZAPI_CLIENT_TOKEN", required=require_zapi),

        default_country_code=default_country_code,
        max_contacts=max_contacts,
    )

# Formatar o telefone brasileiro para DDI + DDD + número. Remove caracteres que não sejam números
def normalize_phone(raw_phone: str | None, country_code: str) -> str | None:
    phone = re.sub(r"\D", "", raw_phone or "")

    if len(phone) in (10, 11):
        phone = f"{country_code}{phone}"

    expected_lengths = {
        len(country_code) + 10,
        len(country_code) + 11,
    }
    if not phone.startswith(country_code) or len(phone) not in expected_lengths:
        return None

    return phone

# Cria o cliente do Supabase
def build_supabase_client(settings: Settings) -> Client:
    return create_client(settings.supabase_url, settings.supabase_key)

# Monta a consulta ao Supabase
def fetch_contacts(
    supabase: Client,
    settings: Settings,
) -> list[Contact]:
    query = (
        supabase.table(settings.supabase_table)
        .select(
            "nome_contato,"
            "telefones!inner(telefone,ativo,created_at)"
        )
        .eq("telefones.ativo", True)
    )

    rows = (
        query.order("nome_contato", desc=False)
        .order("created_at", desc=False, foreign_table="telefones")
        .limit(settings.max_contacts)
        .limit(3, foreign_table="telefones")
        .execute()
        .data
        or []
    )
    contacts: list[Contact] = []

    for row in rows:
        name = str(row.get("nome_contato") or "").strip()

        if not name:
            logging.warning("Contato ignorado: nome vazio.")
            continue

        for phone_row in row.get("telefones") or []:
            phone = normalize_phone(
                phone_row.get("telefone"),
                settings.default_country_code,
            )

            if not phone:
                logging.warning(
                    "Telefone inválido ignorado. Nome: %s",
                    name,
                )
                continue

            contacts.append(Contact(name=name, phone=phone))

    return contacts

# Monta a mensagem a ser enviada ao Whatsapp
def send_zapi_text(
    settings: Settings,
    contact: Contact,
    *,
    dry_run: bool,
) -> bool:
    message = MESSAGE_TEMPLATE.format(nome_contato=contact.name)

    if dry_run:
        logging.info(
            "DRY RUN | Para: %s | Mensagem: %s",
            mask_phone(contact.phone),
            message,
        )
        return True

    url = (
        "https://api.z-api.io/instances/"
        f"{settings.zapi_instance_id}/token/"
        f"{settings.zapi_instance_token}/send-text"
    )

    try:
        response = requests.post(
            url,
            headers={"Client-Token": settings.zapi_client_token},
            json={"phone": contact.phone, "message": message},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        response = exc.response
        status_code = response.status_code if response is not None else "sem status"
        response_text = response.text[:500] if response is not None else ""

        logging.error(
            "Erro ao enviar para %s | tipo=%s | status=%s | resposta=%s",
            mask_phone(contact.phone),
            type(exc).__name__,
            status_code,
            response_text,
        )
        return False

    try:
        result = response.json()
    except ValueError:
        result = {}

    message_id = None
    if isinstance(result, dict):
        message_id = (
            result.get("messageId")
            or result.get("zaapId")
            or result.get("id")
        )

    logging.info(
        "Mensagem aceita pela Z-API para %s | id=%s",
        mask_phone(contact.phone),
        message_id or "não informado",
    )
    return True

# fiz para testar o envio, sem enviar a mensagem para o whatsapp
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Envia mensagens Z-API para contatos ativos do Supabase."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra o envio sem chamar a Z-API.",
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()

    try:
        settings = load_settings(require_zapi=not args.dry_run)
        supabase = build_supabase_client(settings)
        contacts = fetch_contacts(supabase, settings)
    except Exception as exc:
        logging.exception("Falha ao iniciar o fluxo: %s", exc)
        return 1

    if not contacts:
        logging.warning("Nenhum contato ativo encontrado.")
        return 0

    logging.info("Contatos selecionados: %s", len(contacts))

    successes = sum(
        send_zapi_text(settings, contact, dry_run=args.dry_run)
        for contact in contacts
    )
    failures = len(contacts) - successes
    result_label = "simulados" if args.dry_run else "aceitos"

    logging.info(
        "Fluxo finalizado | %s=%s | falhas=%s",
        result_label,
        successes,
        failures,
    )
    return 0 if failures == 0 else 2

# ================================== MAIN ==================================
if __name__ == "__main__":
    raise SystemExit(main())
