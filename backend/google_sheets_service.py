"""Service d'intégration Google Sheets avec configuration dynamique.

La configuration (identifiant du spreadsheet, nom d'onglet, délai d'attente,
clé S3 du compte de service) est fournie via le constructeur et provient de la
base de données (table ApplicationSetting), jamais de config.py ni de .env.

Les credentials du compte de service (JSON) sont stockés sur S3 et téléchargés
à la demande. Jamais journalisés, jamais exposés au frontend.
"""

import asyncio
import json
import logging
import socket
import time
from contextlib import contextmanager
from typing import Any

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.ext.asyncio import AsyncSession

from s3_service import S3ServiceError, s3_service

logger = logging.getLogger("bces.google_sheets")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DEFAULT_S3_KEY = "google-service-account.json"
GOOGLE_SHEETS_TIMEOUT = 10.0
# Cache en mémoire du JSON du compte de service (évite un téléchargement S3 à chaque appel).
SERVICE_ACCOUNT_CACHE_TTL = 300.0  # secondes
_service_account_cache: dict[str, tuple[float, dict[str, Any]]] = {}

_original_getaddrinfo = socket.getaddrinfo


@contextmanager
def _force_ipv4():
    """Force la résolution DNS en IPv4 uniquement.

    Certains réseaux échouent en IPv6 (timeout WinError 10060) alors qu'IPv4
    fonctionne. Ce contexte restreint getaddrinfo à AF_INET pour forcer
    httplib2/googleapiclient à utiliser IPv4.
    """

    def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = _ipv4_only
    try:
        yield
    finally:
        socket.getaddrinfo = _original_getaddrinfo


class GoogleSheetsError(Exception):
    """Erreur liée à l'intégration Google Sheets."""


class GoogleSheetsService:
    """Client Google Sheets configuré dynamiquement depuis la base de données."""

    def __init__(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        timeout_seconds: int = 15,
        s3_key: str = DEFAULT_S3_KEY,
    ) -> None:
        self._spreadsheet_id = spreadsheet_id or ""
        self._sheet_name = sheet_name or ""
        self._timeout_seconds = max(1, int(timeout_seconds or 15))
        self._s3_key = s3_key or DEFAULT_S3_KEY

    @property
    def configured(self) -> bool:
        """True si le spreadsheet, l'onglet et les credentials S3 sont présents."""
        if not self._spreadsheet_id or not self._sheet_name:
            return False
        try:
            return s3_service.object_exists(self._s3_key, prefix="credentials/")
        except S3ServiceError:
            # S3 non configuré ou erreur transitoire : considéré comme non configuré.
            return False

    def _download_service_account_info(self) -> dict[str, Any]:
        """Télécharge et parse le JSON du compte de service depuis S3 (avec cache TTL)."""
        now = time.monotonic()
        cached = _service_account_cache.get(self._s3_key)
        if cached is not None and now - cached[0] < SERVICE_ACCOUNT_CACHE_TTL:
            return cached[1]
        try:
            content = s3_service.download_service_account(self._s3_key, prefix="credentials/")
        except S3ServiceError as exc:
            raise GoogleSheetsError(
                f"Impossible de récupérer les credentials depuis S3 (clé={self._s3_key})."
            ) from exc
        try:
            info = json.loads(content)
        except json.JSONDecodeError as exc:
            raise GoogleSheetsError(
                f"Le JSON du compte de service sur S3 est invalide : {exc}"
            ) from exc
        _service_account_cache[self._s3_key] = (now, info)
        return info

    def _build_service(self) -> Any:
        """Construit le client API Google Sheets authentifié."""
        info = self._download_service_account_info()
        credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
        with _force_ipv4():
            return build("sheets", "v4", credentials=credentials, cache_discovery=False)

    def _execute_sync(self, call: Any) -> Any:
        """Exécute un appel API Google Sheets synchrone (bloquant) dans un thread.

        HttpRequest.execute() n'accepte pas de request_timeout dans cette
        version de googleapiclient ; le délai d'attente n'est donc pas
        appliqué au transport HTTP (valeur par défaut de httplib2).
        """
        with _force_ipv4():
            return call.execute(num_retries=2)

    async def _execute(self, call: Any) -> Any:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._execute_sync, call)

    async def test_connection(self) -> dict[str, Any]:
        """Teste la connexion et retourne des infos non sensibles sur le spreadsheet."""
        if not self._spreadsheet_id:
            return {
                "connected": False,
                "error": "Spreadsheet ID manquant.",
                "spreadsheet_title": None,
                "sheet_names": [],
                "target_sheet_found": False,
            }
        if not self._sheet_name:
            return {
                "connected": False,
                "error": "Nom d'onglet manquant.",
                "spreadsheet_title": None,
                "sheet_names": [],
                "target_sheet_found": False,
            }
        try:
            service = self._build_service()
        except GoogleSheetsError as exc:
            return {
                "connected": False,
                "error": str(exc),
                "spreadsheet_title": None,
                "sheet_names": [],
                "target_sheet_found": False,
            }
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Erreur lors de la construction du client Google Sheets.")
            return {
                "connected": False,
                "error": f"Erreur d'authentification : {type(exc).__name__}",
                "spreadsheet_title": None,
                "sheet_names": [],
                "target_sheet_found": False,
            }

        try:
            spreadsheet = await self._execute(
                service.spreadsheets().get(spreadsheetId=self._spreadsheet_id)
            )
        except HttpError as exc:
            return self._handle_http_error(exc)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Erreur lors de la lecture du spreadsheet Google Sheets.")
            return {
                "connected": False,
                "error": f"Erreur inattendue : {type(exc).__name__}",
                "spreadsheet_title": None,
                "sheet_names": [],
                "target_sheet_found": False,
            }

        title = spreadsheet.get("properties", {}).get("title")
        sheets = spreadsheet.get("sheets", [])
        sheet_names = [
            s.get("properties", {}).get("title", "")
            for s in sheets
            if s.get("properties", {}).get("title")
        ]
        target_sheet_found = self._sheet_name in sheet_names

        return {
            "connected": True,
            "error": None,
            "spreadsheet_title": title,
            "sheet_names": sheet_names,
            "target_sheet_found": target_sheet_found,
        }

    async def read_cell(self, cell_ref: str) -> str | None:
        """Lit une seule cellule sur l'onglet configuré.

        Retourne la valeur de la cellule, ou None si vide/erreur.
        """
        if not self.configured:
            raise GoogleSheetsError("Google Sheets non configuré.")
        try:
            service = self._build_service()
        except GoogleSheetsError:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Erreur lors de la construction du client Google Sheets.")
            raise GoogleSheetsError(f"Erreur d'authentification : {exc}") from exc

        try:
            result = await asyncio.wait_for(
                self._execute(
                    service.spreadsheets()
                    .values()
                    .get(
                        spreadsheetId=self._spreadsheet_id,
                        range=f"{self._sheet_name}!{cell_ref}",
                    )
                ),
                timeout=GOOGLE_SHEETS_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("Délai dépassé lors de la lecture de la cellule %s.", cell_ref)
            raise GoogleSheetsError(f"Délai dépassé lors de la lecture de la cellule {cell_ref}.")
        except HttpError as exc:
            raise self._http_error_to_gs_error(exc) from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Erreur lors de la lecture de la cellule Google Sheets.")
            raise GoogleSheetsError(f"Erreur inattendue : {type(exc).__name__}") from exc

        values = result.get("values", [])
        if not values or not values[0]:
            return None
        return str(values[0][0])

    async def write_values(
        self,
        values: list[list[Any]],
        range_name: str,
        value_input_option: str = "USER_ENTERED",
    ) -> dict[str, Any]:
        """Écrit des valeurs sur l'onglet configuré."""
        if not self.configured:
            raise GoogleSheetsError("Google Sheets non configuré.")
        try:
            service = self._build_service()
        except GoogleSheetsError:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Erreur lors de la construction du client Google Sheets.")
            raise GoogleSheetsError(f"Erreur d'authentification : {exc}") from exc

        body = {"values": values}
        try:
            result = await asyncio.wait_for(
                self._execute(
                    service.spreadsheets()
                    .values()
                    .update(
                        spreadsheetId=self._spreadsheet_id,
                        range=f"{self._sheet_name}!{range_name}",
                        valueInputOption=value_input_option,
                        body=body,
                    )
                ),
                timeout=GOOGLE_SHEETS_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("Délai dépassé lors de l'écriture Google Sheets (%s).", range_name)
            raise GoogleSheetsError(f"Délai dépassé lors de l'écriture Google Sheets ({range_name}).")
        except HttpError as exc:
            raise self._http_error_to_gs_error(exc) from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Erreur lors de l'écriture Google Sheets.")
            raise GoogleSheetsError(f"Erreur inattendue : {type(exc).__name__}") from exc

        return result

    async def write_values_batch(
        self,
        ranges: list[tuple[str, list[list[Any]]]],
        value_input_option: str = "USER_ENTERED",
    ) -> dict[str, Any]:
        """Écrit plusieurs plages en UNE seule requête (values.batchUpdate).

        `ranges` est une liste de tuples (range_name, values).
        """
        if not self.configured:
            raise GoogleSheetsError("Google Sheets non configuré.")
        try:
            service = self._build_service()
        except GoogleSheetsError:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Erreur lors de la construction du client Google Sheets.")
            raise GoogleSheetsError(f"Erreur d'authentification : {exc}") from exc

        body = {
            "valueInputOption": value_input_option,
            "data": [
                {
                    "range": f"{self._sheet_name}!{range_name}",
                    "values": values,
                }
                for range_name, values in ranges
            ],
        }
        try:
            result = await asyncio.wait_for(
                self._execute(
                    service.spreadsheets()
                    .values()
                    .batchUpdate(spreadsheetId=self._spreadsheet_id, body=body)
                ),
                timeout=GOOGLE_SHEETS_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("Délai dépassé lors de l'écriture batch Google Sheets.")
            raise GoogleSheetsError("Délai dépassé lors de l'écriture batch Google Sheets.")
        except HttpError as exc:
            raise self._http_error_to_gs_error(exc) from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Erreur lors de l'écriture batch Google Sheets.")
            raise GoogleSheetsError(f"Erreur inattendue : {type(exc).__name__}") from exc

        return result

    async def append_values(
        self,
        values: list[list[Any]],
        range_name: str,
        value_input_option: str = "USER_ENTERED",
    ) -> dict[str, Any]:
        """Ajoute des valeurs en fin de plage sur l'onglet configuré."""
        if not self.configured:
            raise GoogleSheetsError("Google Sheets non configuré.")
        try:
            service = self._build_service()
        except GoogleSheetsError:
            raise
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Erreur lors de la construction du client Google Sheets.")
            raise GoogleSheetsError(f"Erreur d'authentification : {exc}") from exc

        body = {"values": values}
        try:
            result = await asyncio.wait_for(
                self._execute(
                    service.spreadsheets()
                    .values()
                    .append(
                        spreadsheetId=self._spreadsheet_id,
                        range=f"{self._sheet_name}!{range_name}",
                        valueInputOption=value_input_option,
                        insertDataOption="INSERT_ROWS",
                        body=body,
                    )
                ),
                timeout=GOOGLE_SHEETS_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("Délai dépassé lors de l'ajout Google Sheets (%s).", range_name)
            raise GoogleSheetsError(f"Délai dépassé lors de l'ajout Google Sheets ({range_name}).")
        except HttpError as exc:
            raise self._http_error_to_gs_error(exc) from exc
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Erreur lors de l'ajout Google Sheets.")
            raise GoogleSheetsError(f"Erreur inattendue : {type(exc).__name__}") from exc

        return result

    @staticmethod
    def _handle_http_error(exc: HttpError) -> dict[str, Any]:
        status = exc.resp.status if exc.resp else 0
        if status == 404:
            error = "Spreadsheet introuvable ou accès refusé."
        elif status in (401, 403):
            error = "Credentials du compte de service invalides ou insuffisants."
        elif status == 429:
            error = "Quota Google Sheets dépassé, réessayez plus tard."
        else:
            error = f"Erreur API Google Sheets (HTTP {status})."
        logger.warning("Erreur API Google Sheets : %s", error)
        return {
            "connected": False,
            "error": error,
            "spreadsheet_title": None,
            "sheet_names": [],
            "target_sheet_found": False,
        }

    @staticmethod
    def _http_error_to_gs_error(exc: HttpError) -> GoogleSheetsError:
        status = exc.resp.status if exc.resp else 0
        if status == 404:
            msg = "Spreadsheet introuvable ou accès refusé."
        elif status in (401, 403):
            msg = "Credentials du compte de service invalides ou insuffisants."
        elif status == 429:
            msg = "Quota Google Sheets dépassé."
        else:
            msg = f"Erreur API Google Sheets (HTTP {status})."
        logger.warning("Erreur API Google Sheets : %s", msg)
        return GoogleSheetsError(msg)


async def load_settings_from_db(db: AsyncSession) -> dict[str, str | int | bool]:
    """Lit la configuration Google Sheets depuis la table ApplicationSetting.

    Retourne un dictionnaire avec les clés : enabled, spreadsheet_id, sheet_name,
    timeout_seconds, s3_key. Aucune valeur sensible n'est retournée.
    """
    from models import ApplicationSetting

    async def _get(key: str, default: str = "") -> str:
        row = await db.get(ApplicationSetting, key)
        return row.value if row is not None else default

    enabled_raw = await _get("google_sheets_enabled", "false")
    spreadsheet_id = await _get("google_sheets_spreadsheet_id", "")
    sheet_name = await _get("google_sheets_sheet_name", "")
    timeout_raw = await _get("google_sheets_timeout_seconds", "15")
    s3_key = await _get("google_sheets_s3_key", DEFAULT_S3_KEY)

    read_enabled_raw = await _get("google_sheets_read_enabled", "false")
    read_spreadsheet_id = await _get("google_sheets_read_spreadsheet_id", "")
    read_sheet_name = await _get("google_sheets_read_sheet_name", "")
    read_lses_cell = await _get("google_sheets_read_lses_cell", "B3")
    read_safd_cell = await _get("google_sheets_read_safd_cell", "D3")

    write_name_cell = await _get("google_sheets_write_name_cell", "A1")
    write_phone_cell = await _get("google_sheets_write_phone_cell", "B1")
    write_hospital_cell = await _get("google_sheets_write_hospital_cell", "C1")
    write_info_cell = await _get("google_sheets_write_info_cell", "D1")

    try:
        timeout_seconds = int(timeout_raw)
    except (TypeError, ValueError):
        timeout_seconds = 15
    return {
        "enabled": enabled_raw.strip().lower() in ("1", "true", "yes", "on"),
        "spreadsheet_id": spreadsheet_id,
        "sheet_name": sheet_name,
        "timeout_seconds": max(1, timeout_seconds),
        "s3_key": s3_key or DEFAULT_S3_KEY,
        "read_enabled": read_enabled_raw.strip().lower() in ("1", "true", "yes", "on"),
        "read_spreadsheet_id": read_spreadsheet_id,
        "read_sheet_name": read_sheet_name,
        "read_lses_cell": read_lses_cell or "B3",
        "read_safd_cell": read_safd_cell or "D3",
        "write_name_cell": write_name_cell or "A1",
        "write_phone_cell": write_phone_cell or "B1",
        "write_hospital_cell": write_hospital_cell or "C1",
        "write_info_cell": write_info_cell or "D1",
    }


async def build_from_db(db: AsyncSession) -> GoogleSheetsService:
    """Construit une GoogleSheetsService configurée depuis la base de données."""
    settings = await load_settings_from_db(db)
    return GoogleSheetsService(
        spreadsheet_id=str(settings["spreadsheet_id"]),
        sheet_name=str(settings["sheet_name"]),
        timeout_seconds=int(settings["timeout_seconds"]),
        s3_key=str(settings["s3_key"]),
    )
