# config/routers.py


class OlapRouter:
    """
    Um router para controlar todas as operações de banco de dados
    em modelos no app 'olap_models'.
    """

    route_app_labels = {"olap_models"}

    def _is_olap_model(self, model) -> bool:
        return getattr(model._meta, "app_label", None) in self.route_app_labels

    def db_for_read(self, model, **_hints):
        """
        Aponta as leituras do app 'olap_models' para o banco 'olap'.
        """
        if self._is_olap_model(model):
            return "olap"
        return "default"

    def db_for_write(self, model, **_hints):
        """
        Aponta as escritas do app 'olap_models' para o banco 'olap'.
        """
        if self._is_olap_model(model):
            return "olap"
        return "default"

    def allow_relation(self, obj1, obj2, **_hints):
        """
        Permite relações se ambos os modelos forem do app 'olap_models'.
        """
        if {
            getattr(obj1._meta, "app_label", None),
            getattr(obj2._meta, "app_label", None),
        } & self.route_app_labels:
            return True
        return None

    def allow_migrate(self, db, app_label, _model_name=None, **_hints):
        """
        Garante que os modelos de 'olap_models' só migrem para o banco 'olap'.
        E que os outros apps não migrem para o banco 'olap'.
        """
        if app_label in self.route_app_labels:
            return db == "olap"
        return db == "default"
