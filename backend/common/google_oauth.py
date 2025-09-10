import os
from django.conf import settings
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from vendor.models import GoogleOAuthCredential
import logging

# Allow HTTP for localhost development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

logger = logging.getLogger(__name__)


def _client_config() -> dict:
    if not settings.GOOGLE_OAUTH_CLIENT_ID or not settings.GOOGLE_OAUTH_CLIENT_SECRET:
        raise RuntimeError("Google OAuth client is not configured")
    return {
        "web": {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_OAUTH_REDIRECT_URI],
        }
    }


def build_flow(state: str | None = None) -> Flow:
    scopes = list(getattr(settings, "GOOGLE_SCOPES", [])) or [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    flow = Flow.from_client_config(_client_config(), scopes=scopes, state=state)
    flow.redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI
    logger.info(f"Flow redirect_uri set to: {flow.redirect_uri}")
    return flow


def get_authorization_url(state: str | None = None) -> str:
    flow = build_flow(state)
    url, _ = flow.authorization_url(
        access_type="offline",
        # Do not merge previously granted scopes; keeps the request minimal
        prompt="consent" if getattr(settings, "GOOGLE_OAUTH_FORCE_CONSENT", True) else None,
    )
    logger.info(f"Generated authorization URL: {url}")
    return url


def exchange_code(authorization_response_url: str) -> Credentials:
    logger.info(f"Exchanging code from URL: {authorization_response_url}")
    flow = build_flow()
    
    # Debug: Check if the URL contains the code parameter
    if 'code=' not in authorization_response_url:
        raise ValueError(f"No code parameter found in URL: {authorization_response_url}")
    
    try:
        # Prevent oauthlib from validating returned scope by clearing the requested scope
        try:
            flow.oauth2session.scope = None  # Some versions validate against this attribute
        except Exception:
            pass

        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            flow.fetch_token(authorization_response=authorization_response_url)
        logger.info("Successfully exchanged code for credentials")
        return flow.credentials
    except Exception as e:
        logger.error(f"Error exchanging code: {e}")
        raise


def persist_credentials(user_email: str, creds: Credentials) -> GoogleOAuthCredential:
    desired_scopes = list(getattr(settings, "GOOGLE_SCOPES", [])) or [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets",
    ]
    obj, _ = GoogleOAuthCredential.objects.update_or_create(
        user_email=user_email,
        client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
        defaults={
            "google_user_id": (getattr(creds, "id_token", {}) or {}).get("sub", ""),
            "access_token": creds.token,
            "refresh_token": creds.refresh_token or "",
            "token_uri": creds.token_uri,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "scopes": ",".join(desired_scopes),
            "expiry": getattr(creds, "expiry", None),
        },
    )
    return obj


def load_user_credentials(user_email: str) -> Credentials | None:
    try:
        obj = GoogleOAuthCredential.objects.get(user_email=user_email, client_id=settings.GOOGLE_OAUTH_CLIENT_ID)
    except GoogleOAuthCredential.DoesNotExist:
        return None
    creds = Credentials(
        token=obj.access_token,
        refresh_token=obj.refresh_token or None,
        token_uri=obj.token_uri,
        client_id=obj.client_id,
        client_secret=obj.client_secret,
        scopes=obj.scopes.split(",") if obj.scopes else None,
    )
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        obj.access_token = creds.token
        obj.expiry = getattr(creds, "expiry", None)
        obj.save(update_fields=["access_token", "expiry", "updated_at"])
    return creds 