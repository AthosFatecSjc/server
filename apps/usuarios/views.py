"""Views responsáveis pelo módulo de gestão de usuários."""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from apps.relatorios.models import Usuario

from .forms import UsuarioCreateForm, UsuarioFiltroForm, UsuarioUpdateForm
from .services import alterar_status_usuario, listar_usuarios


class UsuarioListView(View):
    """Lista de usuários com filtros combinados."""

    template_name = "usuarios/index.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        filtro_form = UsuarioFiltroForm(request.GET or None)
        filtro_form.is_valid()
        usuarios = listar_usuarios(filtro_form.cleaned_data)
        contexto = {
            "filtro_form": filtro_form,
            "usuarios": usuarios,
            "usuarios_count": usuarios.count(),
        }
        return render(request, self.template_name, contexto)


class UsuarioCreateView(View):
    """Tela de criação de usuário."""

    template_name = "usuarios/formulario.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        form = UsuarioCreateForm()
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "titulo": "Cadastrar Novo Usuário",
                "descricao": "Preencha todos os dados do usuário. Todos os campos são obrigatórios.",
                "submit_label": "Cadastrar Usuário",
                "usuario": None,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        form = UsuarioCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuário criado com sucesso.")
            return redirect("usuarios:lista")

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "titulo": "Cadastrar Novo Usuário",
                "descricao": "Preencha todos os dados do usuário. Todos os campos são obrigatórios.",
                "submit_label": "Cadastrar Usuário",
                "usuario": None,
            },
        )


class UsuarioUpdateView(View):
    """Tela de edição de usuário."""

    template_name = "usuarios/formulario.html"

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        usuario = get_object_or_404(Usuario, pk=pk)
        form = UsuarioUpdateForm(instance=usuario)
        return render(
            request,
            self.template_name,
            {
                "form": form,
                "titulo": "Editar Usuário",
                "descricao": "Atualize os dados do usuário. Deixe a senha em branco para manter a atual.",
                "usuario": usuario,
                "submit_label": "Salvar alterações",
            },
        )

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        usuario = get_object_or_404(Usuario, pk=pk)
        form = UsuarioUpdateForm(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuário atualizado com sucesso.")
            return redirect("usuarios:detalhe", pk=usuario.pk)

        return render(
            request,
            self.template_name,
            {
                "form": form,
                "titulo": "Editar Usuário",
                "descricao": "Atualize os dados do usuário. Deixe a senha em branco para manter a atual.",
                "usuario": usuario,
                "submit_label": "Salvar alterações",
            },
        )


class UsuarioDetailView(View):
    """Página de detalhes de um usuário específico."""

    template_name = "usuarios/detalhe.html"

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        usuario = get_object_or_404(Usuario, pk=pk)
        return render(
            request,
            self.template_name,
            {"usuario": usuario},
        )


class UsuarioStatusToggleView(View):
    """Ativa ou desativa um usuário conforme o status atual."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        usuario = get_object_or_404(Usuario, pk=pk)
        acao = request.POST.get("acao")
        if acao not in {"ativar", "desativar"}:
            messages.error(request, "Ação inválida para atualização de status.")
            redirect_url = request.POST.get("next") or reverse("usuarios:lista")
            return redirect(redirect_url)

        novo_status = acao == "ativar"
        alterar_status_usuario(usuario, ativo=novo_status)

        if novo_status:
            messages.success(request, "Usuário reativado com sucesso.")
        else:
            messages.success(request, "Usuário desativado com sucesso.")

        redirect_url = request.POST.get("next") or reverse("usuarios:lista")
        return redirect(redirect_url)
