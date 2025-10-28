from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_safe

FAKE_USERS = {
    "admin": "123456",
    "demo": "demo",
}


def _is_authenticated(request) -> bool:
    """Check whether the current session has a fake authenticated user."""
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


@require_http_methods(["GET", "POST"])
def login_view(request):
    if _is_authenticated(request):
        return redirect("home")

    context = {"error_message": None}

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if FAKE_USERS.get(username) == password:
            request.session["fake_user"] = {"username": username}
            request.session.modified = True
            return redirect("home")

        context["error_message"] = "Usuário ou senha inválidos."

    return render(request, "auth/login.html", context)


@require_safe
def logout_view(request):
    request.session.flush()
    return redirect("login")
