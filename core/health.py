from django.http import JsonResponse
from django.views.decorators.http import require_safe


@require_safe
def health(request):
    # Liveness: não consulta o banco nem carrega contexto de templates.
    return JsonResponse({"status": "ok"})
