from rest_framework.views import exception_handler


def kharandi_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is not None:
        errors  = response.data
        message = ""
        if isinstance(errors, dict):
            for key, val in errors.items():
                if isinstance(val, list) and val:
                    message = str(val[0])
                elif isinstance(val, str):
                    message = val
                if message:
                    break
        elif isinstance(errors, list) and errors:
            message = str(errors[0])
        response.data = {
            "success": False,
            "message": message or "Erreur de validation.",
            "errors":  errors,
        }
    return response
