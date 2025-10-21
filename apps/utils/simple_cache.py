"""Módulo de gerenciamento de cache simples para dados do JIRA."""

import datetime
from typing import Any, Dict, Optional

from django.conf import settings


class SimpleCache:
    """Gerenciador de cache simples usando variável em memória."""

    _cache_storage = {"data": {}, "timestamp": None, "validade": None}

    @classmethod
    def set(cls, data: Dict[str, Any]) -> None:
        """
        Define os dados no cache com timestamp atual.

        Args:
            data: Dicionário com os dados a serem cacheados
        """
        cls._cache_storage["data"] = data
        cls._cache_storage["timestamp"] = datetime.datetime.now()
        cls._cache_storage["validade"] = settings.CACHE_JIRA["validade"]

    @classmethod
    def get(cls) -> Optional[Dict[str, Any]]:
        """
        Retorna os dados do cache se ainda forem válidos.

        Returns:
            Dados do cache ou None se expirado ou vazio
        """
        if not cls._cache_storage["timestamp"]:
            return None

        # Verificar se o cache ainda é válido
        tempo_decorrido = datetime.datetime.now() - cls._cache_storage["timestamp"]

        if tempo_decorrido > cls._cache_storage["validade"]:
            # Cache expirado
            cls.clear()
            return None

        return cls._cache_storage["data"]

    @classmethod
    def is_valid(cls) -> bool:
        """
        Verifica se o cache está válido.

        Returns:
            True se o cache existe e ainda é válido, False caso contrário
        """
        return cls.get() is not None

    @classmethod
    def get_timestamp(cls) -> Optional[datetime.datetime]:
        """
        Retorna o timestamp de quando o cache foi criado.

        Returns:
            Datetime do cache ou None se vazio
        """
        return cls._cache_storage["timestamp"]

    @classmethod
    def get_tempo_restante(cls) -> Optional[datetime.timedelta]:
        """
        Retorna quanto tempo resta até o cache expirar.

        Returns:
            Timedelta com tempo restante ou None se cache vazio/expirado
        """
        if not cls._cache_storage["timestamp"]:
            return None

        tempo_decorrido = datetime.datetime.now() - cls._cache_storage["timestamp"]
        tempo_restante = cls._cache_storage["validade"] - tempo_decorrido

        if tempo_restante.total_seconds() <= 0:
            return None

        return tempo_restante

    @classmethod
    def clear(cls) -> None:
        """Limpa todos os dados do cache."""
        cls._cache_storage["data"] = {}
        cls._cache_storage["timestamp"] = None
        cls._cache_storage["validade"] = None

    @classmethod
    def get_info(cls) -> Dict[str, Any]:
        """
        Retorna informações sobre o estado do cache.

        Returns:
            Dicionário com informações do cache
        """
        tempo_restante = cls.get_tempo_restante()

        return {
            "esta_valido": cls.is_valid(),
            "timestamp": cls._cache_storage["timestamp"],
            "tempo_restante": tempo_restante,
            "validade_configurada": cls._cache_storage["validade"],
            "tem_dados": bool(cls._cache_storage["data"]),
        }
