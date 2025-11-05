import json

from django.test import SimpleTestCase

from apps.dashboards.templatetags.dashboard_filters import jsonify


class DashboardFiltersTests(SimpleTestCase):
    def test_jsonify_converte_para_string_json(self):
        data = {"foo": "bar", "numbers": [1, 2, 3]}

        result = jsonify(data)

        self.assertEqual(result, json.dumps(data))
