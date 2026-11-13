"""Service de stockage S3 pour les credentials Google Service Account.

Les fichiers JSON des comptes de service Google sont stockés sur un stockage
compatible S3 (MinIO, AWS S3, etc.) et jamais en base de données ni sur le
système de fichiers local de l'application.

Sécurité :
  - Les credentials S3 proviennent exclusivement des variables d'environnement.
  - Jamais exposés au frontend.
  - Jamais retournés dans les réponses API.
  - Jamais journalisés.
  - Les objets S3 sont privés (pas d'accès public).
"""

import logging

from cryptography.fernet import Fernet
import boto3
from botocore.exceptions import BotoCoreError, ClientError
from config import get_settings

logger = logging.getLogger("bces.s3")


class S3ServiceError(Exception):
    """Erreur liée au stockage S3."""


class S3Service:
    """Wrapper autour de boto3 pour stocker/récupérer le JSON du compte de service."""

    def __init__(self) -> None:
        settings = get_settings()
        self._endpoint = settings.s3_endpoint
        self._region = settings.s3_region
        self._bucket = settings.s3_bucket
        self._access_key = settings.s3_access_key
        self._secret_key = settings.s3_secret_key
        self._encryption_key = settings.google_sa_encryption_key
        self._fernet = Fernet(self._encryption_key.encode()) if self._encryption_key else None
        self._client = None
        self._configured = bool(
            self._endpoint and self._bucket and self._access_key and self._secret_key
        )

    @property
    def configured(self) -> bool:
        return self._configured

    def _get_client(self):
        if self._client is None:
            if not self._configured:
                raise S3ServiceError(
                    "Stockage S3 non configuré (variables d'environnement manquantes)."
                )
            session = boto3.session.Session()
            self._client = session.client(
                "s3",
                endpoint_url=self._endpoint or None,
                region_name=self._region,
                aws_access_key_id=self._access_key,
                aws_secret_access_key=self._secret_key,
            )
        return self._client

    def _encrypt(self, data: bytes) -> bytes:
        if self._fernet is None:
            raise S3ServiceError(
                "Clé de chiffrement non configurée (GOOGLE_SA_ENCRYPTION_KEY)."
            )
        return self._fernet.encrypt(data)

    def _decrypt(self, data: bytes) -> bytes:
        if self._fernet is None:
            raise S3ServiceError(
                "Clé de chiffrement non configurée (GOOGLE_SA_ENCRYPTION_KEY)."
            )
        return self._fernet.decrypt(data)

    def upload_service_account(
        self, key: str, content: bytes, content_type: str = "application/json",
        prefix: str = "",
    ) -> str:
        """Upload le JSON du compte de service sur S3.

        Retourne la clé de l'objet stocké.
        """
        full_key = f"{prefix}{key}" if prefix else key
        client = self._get_client()
        try:
            encrypted_content = self._encrypt(content)
            client.put_object(
                Bucket=self._bucket,
                Key=full_key,
                Body=encrypted_content,
                ContentType=content_type,
                # L'objet reste privé : pas d'accès public.
                ACL="private",
            )
            logger.info("Service account JSON uploadé sur S3 (clé=%s).", full_key)
            return full_key
        except ClientError as exc:
            logger.error("Échec S3 upload (clé=%s): %s", full_key, exc.response["Error"]["Code"])
            raise S3ServiceError(
                f"Échec de l'upload vers S3 : {exc.response['Error']['Code']}"
            ) from exc
        except BotoCoreError as exc:
            logger.error("Échec S3 upload (clé=%s): %s", full_key, exc, exc_info=True)
            raise S3ServiceError(f"Échec de l'upload vers S3 : {exc}") from exc

    def download_service_account(self, key: str, prefix: str = "") -> bytes:
        """Télécharge le JSON du compte de service depuis S3."""
        full_key = f"{prefix}{key}" if prefix else key
        client = self._get_client()
        try:
            response = client.get_object(Bucket=self._bucket, Key=full_key)
            encrypted_body = response["Body"].read()
            decrypted_body = self._decrypt(encrypted_body)
            logger.info("Service account JSON téléchargé depuis S3 (clé=%s).", full_key)
            return decrypted_body
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code == "NoSuchKey":
                logger.warning("Service account JSON introuvable sur S3 (clé=%s).", full_key)
                raise S3ServiceError("Aucun compte de service configuré.") from exc
            logger.error(
                "Échec S3 download (clé=%s): %s", full_key, exc.response["Error"]["Code"]
            )
            raise S3ServiceError(
                f"Échec du téléchargement depuis S3 : {code}"
            ) from exc
        except BotoCoreError as exc:
            logger.error("Échec S3 download (clé=%s): %s", full_key, exc, exc_info=True)
            raise S3ServiceError(f"Échec du téléchargement depuis S3 : {exc}") from exc

    def delete_service_account(self, key: str, prefix: str = "") -> None:
        """Supprime le JSON du compte de service de S3."""
        full_key = f"{prefix}{key}" if prefix else key
        client = self._get_client()
        try:
            client.delete_object(Bucket=self._bucket, Key=full_key)
            logger.info("Service account JSON supprimé de S3 (clé=%s).", full_key)
        except ClientError as exc:
            logger.error(
                "Échec S3 delete (clé=%s): %s", full_key, exc.response["Error"]["Code"]
            )
            raise S3ServiceError(
                f"Échec de la suppression depuis S3 : {exc.response['Error']['Code']}"
            ) from exc
        except BotoCoreError as exc:
            logger.error("Échec S3 delete (clé=%s): %s", full_key, exc, exc_info=True)
            raise S3ServiceError(f"Échec de la suppression depuis S3 : {exc}") from exc

    def object_exists(self, key: str, prefix: str = "") -> bool:
        """Vérifie si un objet existe sur S3."""
        full_key = f"{prefix}{key}" if prefix else key
        client = self._get_client()
        try:
            client.head_object(Bucket=self._bucket, Key=full_key)
            return True
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code in ("404", "NoSuchKey"):
                return False
            logger.error(
                "Échec S3 head_object (clé=%s): %s", full_key, exc.response["Error"]["Code"]
            )
            raise S3ServiceError(
                f"Échec de la vérification S3 : {code}"
            ) from exc
        except BotoCoreError as exc:
            logger.error("Échec S3 head_object (clé=%s): %s", full_key, exc, exc_info=True)
            raise S3ServiceError(f"Échec de la vérification S3 : {exc}") from exc


# Instance singleton réutilisée par l'application.
s3_service = S3Service()
