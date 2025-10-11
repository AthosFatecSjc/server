from django.http import HttpResponse


def index(request):
    return HttpResponse("Bem-vindo à página inicial!")
