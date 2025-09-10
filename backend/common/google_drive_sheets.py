import os
import json
import base64
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from django.conf import settings

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request


logger = logging.getLogger(__name__)


@dataclass
class GoogleConfig:
    scopes: Sequence[str]
    credentials_file: Optional[str] = None
    credentials_json_b64: Optional[str] = None


class GoogleDriveSheetsClient:
    """
    High-level client for Google Drive and Google Sheets operations.

    Authentication
    --------------
    Uses a Google Cloud service account. Provide credentials via either:
    - settings.GOOGLE_CREDENTIALS_FILE: absolute path to the JSON key
    - settings.GOOGLE_CREDENTIALS_JSON_B64: base64-encoded JSON key contents

    Scopes are read from settings.GOOGLE_SCOPES. Defaults allow Drive and Sheets read/write.

    Common Operations
    -----------------
    - list_drive_files(q): Search files in Drive using Drive v3 query syntax
    - upload_file(...): Uploads a local file into Drive (optionally into a folder)
    - read_values(...): Read a range from a Sheet (A1 notation)
    - write_values(...): Overwrite values in a range
    - append_values(...): Append rows at the end of the sheet
    - clear_values(...): Clear a range
    - create_spreadsheet(title, sheet_titles): Create a new spreadsheet
    """

    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        # Disable discovery cache for server environments
        self.drive = build("drive", "v3", credentials=self.credentials, cache_discovery=False)
        self.sheets = build("sheets", "v4", credentials=self.credentials, cache_discovery=False)

    @classmethod
    def from_django_settings(cls) -> "GoogleDriveSheetsClient":
        scopes = getattr(
            settings,
            "GOOGLE_SCOPES",
            [
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets",
            ],
        )
        credentials_file = getattr(settings, "GOOGLE_CREDENTIALS_FILE", None)
        credentials_b64 = getattr(settings, "GOOGLE_CREDENTIALS_JSON_B64", None)
        credentials = cls._load_service_account_credentials(scopes, credentials_file, credentials_b64)
        return cls(credentials)

    @classmethod
    def from_primary_user(cls) -> "GoogleDriveSheetsClient":
        """Instantiate using stored 3LO credentials for the single owner email."""
        try:
            from .google_oauth import load_user_credentials
        except Exception as e:
            raise RuntimeError("google_oauth helper not available; ensure 3LO is configured") from e
        email = getattr(settings, "GOOGLE_OAUTH_PRIMARY_EMAIL", None)
        if not email:
            raise RuntimeError("GOOGLE_OAUTH_PRIMARY_EMAIL is not configured")
        creds = load_user_credentials(email)
        if not creds:
            raise RuntimeError("No OAuth credentials stored for primary user. Visit /rest/oauth2-credential/start once.")
        if not creds.valid and creds.refresh_token:
            creds.refresh(Request())
        return cls(creds)

    @staticmethod
    def _load_service_account_credentials(
        scopes: Sequence[str],
        credentials_file: Optional[str],
        credentials_b64: Optional[str],
    ) -> Credentials:
        if credentials_b64:
            try:
                json_bytes = base64.b64decode(credentials_b64)
                info = json.loads(json_bytes.decode("utf-8"))
                return Credentials.from_service_account_info(info=info, scopes=list(scopes))
            except Exception as exc:
                raise ValueError("Invalid GOOGLE_CREDENTIALS_JSON_B64. Ensure it's base64 of the full JSON key.") from exc
        if credentials_file and os.path.exists(credentials_file):
            return Credentials.from_service_account_file(credentials_file, scopes=list(scopes))
        raise RuntimeError(
            "Google credentials not configured. Set GOOGLE_CREDENTIALS_FILE or GOOGLE_CREDENTIALS_JSON_B64."
        )

    # ----------------------------- Drive methods -----------------------------
    def list_drive_files(self, q: str, page_size: int = 100, fields: Optional[str] = None) -> List[Dict[str, Any]]:
        """List Drive files matching a query.

        Args:
            q: Drive v3 query string, e.g. "mimeType='application/vnd.google-apps.spreadsheet' and name contains 'Report'".
            page_size: Max page size per API call.
            fields: Fields to return. Defaults to id, name, mimeType, owners, modifiedTime.
        """
        fields = fields or "nextPageToken, files(id, name, mimeType, owners, modifiedTime)"
        results: List[Dict[str, Any]] = []
        page_token: Optional[str] = None
        while True:
            try:
                resp = (
                    self.drive.files()
                    .list(q=q, pageSize=page_size, pageToken=page_token, fields=fields)
                    .execute()
                )
            except HttpError as e:
                logger.exception("Drive API list error: %s", e)
                raise
            results.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return results

    def upload_file(
        self,
        file_path: str,
        name: Optional[str] = None,
        mime_type: Optional[str] = None,
        folder_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Upload a local file to Drive. Returns the created file resource."""
        media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
        metadata: Dict[str, Any] = {"name": name or os.path.basename(file_path)}
        if folder_id:
            metadata["parents"] = [folder_id]
        try:
            file = self.drive.files().create(body=metadata, media_body=media, fields="id, name").execute()
            return file
        except HttpError as e:
            logger.exception("Drive API upload error: %s", e)
            raise

    # ---------------------------- Sheets methods -----------------------------
    def read_values(self, spreadsheet_id: str, range_a1: str) -> List[List[Any]]:
        """Read values from a Sheet range (A1 notation)."""
        try:
            resp = self.sheets.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_a1).execute()
            return resp.get("values", [])
        except HttpError as e:
            logger.exception("Sheets API read error: %s", e)
            raise

    def write_values(
        self,
        spreadsheet_id: str,
        range_a1: str,
        values: List[List[Any]],
        value_input_option: str = "RAW",
    ) -> Dict[str, Any]:
        """Overwrite a range with the provided 2D values array."""
        body = {"values": values}
        try:
            resp = (
                self.sheets.spreadsheets()
                .values()
                .update(
                    spreadsheetId=spreadsheet_id,
                    range=range_a1,
                    valueInputOption=value_input_option,
                    body=body,
                )
                .execute()
            )
            return resp
        except HttpError as e:
            logger.exception("Sheets API write error: %s", e)
            raise

    def append_values(
        self,
        spreadsheet_id: str,
        range_a1: str,
        values: List[List[Any]],
        value_input_option: str = "RAW",
    ) -> Dict[str, Any]:
        """Append rows to the end of a sheet or table."""
        body = {"values": values}
        try:
            resp = (
                self.sheets.spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range=range_a1,
                    valueInputOption=value_input_option,
                    insertDataOption="INSERT_ROWS",
                    body=body,
                )
                .execute()
            )
            return resp
        except HttpError as e:
            logger.exception("Sheets API append error: %s", e)
            raise

    def clear_values(self, spreadsheet_id: str, range_a1: str) -> Dict[str, Any]:
        """Clear a range of values."""
        try:
            resp = (
                self.sheets.spreadsheets()
                .values()
                .clear(spreadsheetId=spreadsheet_id, range=range_a1, body={})
                .execute()
            )
            return resp
        except HttpError as e:
            logger.exception("Sheets API clear error: %s", e)
            raise

    def create_spreadsheet(self, title: str, sheet_titles: Optional[Sequence[str]] = None) -> Dict[str, Any]:
        """Create a new spreadsheet and optional tabs. Returns the spreadsheet resource."""
        body: Dict[str, Any] = {
            "properties": {"title": title},
        }
        if sheet_titles:
            body["sheets"] = [{"properties": {"title": t}} for t in sheet_titles]
        try:
            return self.sheets.spreadsheets().create(body=body, fields="spreadsheetId, properties/title").execute()
        except HttpError as e:
            logger.exception("Sheets API create spreadsheet error: %s", e)
            raise


def get_google_client() -> GoogleDriveSheetsClient:
    """Convenience accessor using Django settings."""
    return GoogleDriveSheetsClient.from_django_settings() 