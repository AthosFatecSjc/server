from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST, require_safe

FAKE_USERS = {
    "admin": "123456",
    "demo": "demo",
}


def _is_authenticated(request) -> bool:
    return bool(request.session.get("fake_user"))


@require_safe
def index(request):
    if not _is_authenticated(request):
        return redirect("login")

    return render(
        request,
        "config/index.html",
        {"fake_user": request.session.get("fake_user")},
    )


@method_decorator(require_safe, name="get")
@method_decorator(require_POST, name="post")
class LoginView(View):
    template_name = "auth/login.html"
    http_method_names = ["get", "head", "post"]

    def get(self, request):
        if _is_authenticated(request):
            return redirect("home")

        return render(request, self.template_name, {"error_message": None})

    def post(self, request):
        if _is_authenticated(request):
            return redirect("home")

        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if FAKE_USERS.get(username) == password:
            request.session["fake_user"] = {"username": username}
            request.session.modified = True
            return redirect("home")

        context = {"error_message": "Usuário ou senha inválidos."}
        return render(request, self.template_name, context)


@require_safe
def logout_view(request):
    request.session.flush()
    return redirect("login")
