from django.http import HttpResponseRedirect, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from common.google_oauth import get_authorization_url, exchange_code, persist_credentials
import logging

logger = logging.getLogger(__name__)


def oauth2_start(request):
    try:
        url = get_authorization_url()
        logger.info(f"Redirecting to: {url}")
        return HttpResponseRedirect(url)
    except Exception as e:
        logger.exception("Error starting OAuth")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
def oauth2_callback(request):
    try:
        # Log everything we receive
        authorization_response = request.build_absolute_uri()
        logger.info(f"OAuth callback received")
        logger.info(f"Full URL: {authorization_response}")
        logger.info(f"GET params: {dict(request.GET)}")
        logger.info(f"Method: {request.method}")
        
        # Check for error parameter from Google
        if 'error' in request.GET:
            error = request.GET.get('error')
            error_description = request.GET.get('error_description', '')
            logger.error(f"OAuth error from Google: {error} - {error_description}")
            return JsonResponse({
                "success": False, 
                "error": f"OAuth error: {error}",
                "description": error_description
            }, status=400)
        
        # Check for code parameter
        if 'code' not in request.GET:
            logger.error("No code parameter in callback")
            return JsonResponse({
                "success": False, 
                "error": "No authorization code received from Google",
                "received_params": dict(request.GET),
                "full_url": authorization_response
            }, status=400)
        
        # Try to exchange the code
        creds = exchange_code(authorization_response)
        persist_credentials(settings.GOOGLE_OAUTH_PRIMARY_EMAIL, creds)
        
        logger.info("OAuth flow completed successfully")
        return JsonResponse({"success": True, "message": "Credentials stored successfully"})
        
    except Exception as e:
        logger.exception("OAuth callback error")
        return JsonResponse({"success": False, "error": str(e)}, status=400) 