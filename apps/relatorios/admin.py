from django.contrib import admin

# Registrando models.
from django.contrib import admin
from .models import Funcionario, Projeto, ControleHorasEquipe, Cargo

admin.site.register(Funcionario)
admin.site.register(Projeto)
admin.site.register(ControleHorasEquipe)
admin.site.register(Cargo)