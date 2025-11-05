"""Formulários utilizados no módulo de gestão de usuários."""

from __future__ import annotations

from django import forms
from django.contrib.auth import password_validation

from apps.relatorios.models import PerfilAcessoChoices, Usuario


class UsuarioFiltroForm(forms.Form):
    """Formulário para filtros de listagem."""

    busca = forms.CharField(
        required=False,
        label="Pesquisa",
        widget=forms.TextInput(
            attrs={"placeholder": "Buscar por nome, username ou e-mail"}
        ),
    )
    perfil_acesso = forms.ChoiceField(
        required=False,
        label="Perfil de Acesso",
        choices=[("", "Todos os perfis")] + list(PerfilAcessoChoices.choices),
    )
    status = forms.ChoiceField(
        required=False,
        label="Status",
        choices=[
            ("", "Todos"),
            ("ativo", "Ativo"),
            ("inativo", "Inativo"),
        ],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            base_classes = "block w-full rounded-full border border-gray-200 bg-gray-50 py-2.5 pl-10 pr-4 text-sm text-gray-700 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", base_classes)
                widget.attrs.setdefault("data-input-type", "select")
            elif isinstance(widget, forms.TextInput):
                widget.attrs.setdefault("class", base_classes)
                widget.attrs.setdefault("data-input-type", "search")


class BaseUsuarioForm(forms.ModelForm):
    """Form base responsável por campos compartilhados."""

    class Meta:
        model = Usuario
        fields = [
            "nome_completo",
            "username",
            "email",
            "contrato",
            "cargo",
            "perfil_acesso",
            "ativo",
        ]
        widgets = {
            "contrato": forms.RadioSelect(),
            "perfil_acesso": forms.RadioSelect(),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        qs = Usuario.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um usuário com este e-mail.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"]
        qs = Usuario.objects.filter(username=username)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um usuário com este username.")
        return username

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        text_input_classes = (
            "mt-1 block w-full rounded-lg border border-gray-200 bg-gray-50 px-4 py-2.5 text-sm text-gray-700 "
            "focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
        )
        checkbox_classes = "h-4 w-4 text-blue-600 border-gray-300 rounded"
        radio_container_classes = "space-y-2"

        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.RadioSelect):
                widget.attrs.setdefault("class", radio_container_classes)
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", checkbox_classes)
            else:
                widget.attrs.setdefault("class", text_input_classes)

        placeholders = {
            "nome_completo": "Digite o nome completo",
            "username": "Digite o username (ex: joao.silva)",
            "email": "Digite o e-mail",
            "cargo": "Selecione o cargo",
        }
        for field_name, placeholder in placeholders.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.setdefault(
                    "placeholder", placeholder
                )


class UsuarioCreateForm(BaseUsuarioForm):
    """Form para criação de usuários que exige senha."""

    senha = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput,
        help_text=password_validation.password_validators_help_text_html(),
    )
    confirmar_senha = forms.CharField(
        label="Confirmar Senha",
        widget=forms.PasswordInput,
        help_text="Confirme a senha informada acima.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["senha"].widget.attrs.setdefault("placeholder", "Digite a senha")
        self.fields["confirmar_senha"].widget.attrs.setdefault(
            "placeholder", "Confirme a senha"
        )
        self.fields["perfil_acesso"].widget.attrs.setdefault(
            "aria-label", "Selecione o perfil de acesso"
        )
        self.fields["contrato"].widget.attrs.setdefault(
            "aria-label", "Selecione o tipo de contrato"
        )

    def clean_senha(self):
        senha = self.cleaned_data["senha"]
        password_validation.validate_password(senha, self.instance)
        return senha

    def clean(self):
        cleaned = super().clean()
        senha = cleaned.get("senha")
        confirmar = cleaned.get("confirmar_senha")
        if senha and confirmar and senha != confirmar:
            self.add_error("confirmar_senha", "As senhas informadas não coincidem.")
        return cleaned

    def save(self, commit=True):
        usuario: Usuario = super().save(commit=False)
        usuario.set_password(self.cleaned_data["senha"])
        if commit:
            usuario.save()
        return usuario


class UsuarioUpdateForm(BaseUsuarioForm):
    """Form para atualização de usuários com possibilidade de trocar senha."""

    nova_senha = forms.CharField(
        label="Nova Senha",
        widget=forms.PasswordInput,
        required=False,
        help_text="Informe para atualizar a senha. Deixe em branco para manter a atual.",
    )
    confirmar_nova_senha = forms.CharField(
        label="Confirmar Nova Senha",
        widget=forms.PasswordInput,
        required=False,
        help_text="Confirme a nova senha informada acima.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nova_senha"].widget.attrs.setdefault(
            "placeholder", "Deixe em branco para manter a atual"
        )
        self.fields["confirmar_nova_senha"].widget.attrs.setdefault(
            "placeholder", "Confirme a nova senha"
        )

    def clean_nova_senha(self):
        senha = self.cleaned_data["nova_senha"]
        if senha:
            password_validation.validate_password(senha, self.instance)
        return senha

    def clean(self):
        cleaned = super().clean()
        nova = cleaned.get("nova_senha")
        confirmar = cleaned.get("confirmar_nova_senha")
        if (nova or confirmar) and nova != confirmar:
            self.add_error(
                "confirmar_nova_senha", "As senhas informadas não coincidem."
            )
        return cleaned

    def save(self, commit=True):
        usuario: Usuario = super().save(commit=False)
        nova_senha = self.cleaned_data.get("nova_senha")
        if nova_senha:
            usuario.set_password(nova_senha)
        if commit:
            usuario.save()
        return usuario
