import traceback
from rest_framework.views import exception_handler
from rest_framework.response import Response
from django.conf import settings


def custom_exception_handler(exc, context):
    # Call DRF's default handler first
    response = exception_handler(exc, context)

    # If DRF didn't handle it (i.e. it's a 500-level error) and DEBUG is on,
    # return the full traceback as JSON so we can see it in the browser
    if response is None and settings.DEBUG:
        tb = traceback.format_exc()
        return Response(
            {
                'error': str(exc),
                'type':  type(exc).__name__,
                'traceback': tb,
            },
            status=500,
        )

    return response