from django.http import HttpResponse
from django.views.decorators.http import require_safe


@require_safe
def index(request):
    return HttpResponse("Bem-vindo à página inicial!")
