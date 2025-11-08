# pylint: disable=protected-access

import datetime

from django.test import SimpleTestCase, override_settings

from apps.utils.simple_cache import SimpleCache


class SimpleCacheTests(SimpleTestCase):
    def tearDown(self):
        SimpleCache.clear()

    @override_settings(CACHE_JIRA={"validade": datetime.timedelta(minutes=10)})
    def test_set_and_get_returns_cached_data_while_valid(self):
        payload = {"value": 42}

        SimpleCache.set(payload)

        self.assertTrue(SimpleCache.is_valid())
        self.assertEqual(SimpleCache.get(), payload)
        self.assertIsNotNone(SimpleCache.get_timestamp())
        tempo_restante = SimpleCache.get_tempo_restante()
        self.assertIsNotNone(tempo_restante)
        self.assertGreater(tempo_restante.total_seconds(), 0)

        info = SimpleCache.get_info()
        self.assertTrue(info["esta_valido"])
        self.assertTrue(info["tem_dados"])
        self.assertEqual(info["validade_configurada"], datetime.timedelta(minutes=10))

    @override_settings(CACHE_JIRA={"validade": datetime.timedelta(seconds=1)})
    def test_get_returns_none_when_cache_expired(self):
        SimpleCache.set({"value": 1})
        SimpleCache._cache_storage["timestamp"] = (
            datetime.datetime.now() - datetime.timedelta(seconds=5)
        )

        result = SimpleCache.get()

        self.assertIsNone(result)
        self.assertFalse(SimpleCache.get_info()["tem_dados"])
        self.assertIsNone(SimpleCache.get_timestamp())

    def test_get_tempo_restante_returns_none_when_no_timestamp(self):
        SimpleCache.clear()
        self.assertIsNone(SimpleCache.get_tempo_restante())

    @override_settings(CACHE_JIRA={"validade": datetime.timedelta(seconds=5)})
    def test_get_tempo_restante_handles_expired_cache(self):
        SimpleCache._cache_storage = {
            "data": {"foo": "bar"},
            "timestamp": datetime.datetime.now() - datetime.timedelta(seconds=10),
            "validade": datetime.timedelta(seconds=5),
        }

        self.assertIsNone(SimpleCache.get_tempo_restante())
        info = SimpleCache.get_info()
        self.assertFalse(info["esta_valido"])
        self.assertFalse(info["tem_dados"])
