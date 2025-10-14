# Registrando models.
from django.contrib import admin

from .models import Cargo, ControleHorasEquipe, Funcionario, Projeto

admin.site.register(Funcionario)
admin.site.register(Projeto)
admin.site.register(ControleHorasEquipe)
admin.site.register(Cargo)
