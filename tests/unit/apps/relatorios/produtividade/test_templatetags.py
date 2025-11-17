from django.test import SimpleTestCase

from apps.relatorios.produtividade.templatetags.dict_filters import get_item


class DictFiltersTests(SimpleTestCase):
    def test_get_item(self):
        data = {1: "um", "dois": 2}
        self.assertEqual(get_item(data, 1), "um")
        self.assertIsNone(get_item(data, "inexistente"))
