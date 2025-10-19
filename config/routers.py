# config/routers.py

class OlapRouter:
    """
    Um router para controlar todas as operações de banco de dados
    em modelos no app 'olap_models'.
    """

    def db_for_read(self, model, **_hints):
        """
        Aponta as leituras do app 'olap_models' para o banco 'olap'.
        """
        if model._meta.app_label == 'olap_models':
            return 'olap'
        return None

    def db_for_write(self, model, **_hints):
        """
        Aponta as escritas do app 'olap_models' para o banco 'olap'.
        """
        if model._meta.app_label == 'olap_models':
            return 'olap'
        return None

    def allow_relation(self, obj1, obj2, **_hints):
        """
        Permite relações se ambos os modelos forem do app 'olap_models'.
        """
        if (
            obj1._meta.app_label == 'olap_models' or
            obj2._meta.app_label == 'olap_models'
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, _model_name=None, **_hints):
        """
        Garante que os modelos de 'olap_models' só migrem para o banco 'olap'.
        E que os outros apps não migrem para o banco 'olap'.
        """
        if app_label == 'olap_models':
            return db == 'olap'
        return db == 'default'
