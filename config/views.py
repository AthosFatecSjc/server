from django.views.decorators.http import require_safe
from django.http import HttpResponse

@require_safe
def index(request):
    return HttpResponse("Bem-vindo à página inicial!")