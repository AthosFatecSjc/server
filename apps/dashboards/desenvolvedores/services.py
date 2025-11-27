from django.db import connections


class DesenvolvedoresService:

    @staticmethod
    def get_desenvolvedores_olap():
        """
        Busca dados de desenvolvedores para visualização
        """
        try:
            with connections["default"].cursor() as cursor:
                # Dedupe por nome (case-insensitive), priorizando o registro mais antigo.
                query = """
                    WITH dedup AS (
                        SELECT
                            id,
                            nome,
                            COALESCE(valor_hora, 40.00) AS valor_hora,
                            COALESCE(contrato, 'CLT') AS contrato,
                            ROW_NUMBER() OVER (
                                PARTITION BY LOWER(nome)
                                ORDER BY data_criacao, id
                            ) AS rn
                        FROM funcionario
                    )
                    SELECT id, nome, valor_hora, contrato
                    FROM dedup
                    WHERE rn = 1
                    ORDER BY nome
                """
                cursor.execute(query)
                resultados = cursor.fetchall()

                desenvolvedores = []
                for row in resultados:
                    dev_id, nome, valor_hora, contrato = row
                    contrato = (contrato or "CLT").upper()
                    contrato_label = "Estagiário" if contrato == "ESTAGIARIO" else "CLT"

                    desenvolvedores.append(
                        {
                            "id": dev_id,
                            "nome": nome,
                            "valor_hora": float(valor_hora),
                            "contrato": contrato,
                            "contrato_label": contrato_label,
                            "iniciais": DesenvolvedoresService._gerar_iniciais(nome),
                        }
                    )

                if not desenvolvedores:
                    return DesenvolvedoresService._fallback_desenvolvedores_olap()

                print(
                    f"DEBUG Service: Encontrados {len(desenvolvedores)} desenvolvedores no OLTP"
                )
                return desenvolvedores

        except Exception as e:
            print(f"Erro ao buscar dados OLAP: {e}")
            return DesenvolvedoresService._fallback_desenvolvedores_olap()

    @staticmethod
    def _fallback_desenvolvedores_olap():
        try:
            with connections["olap"].cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, nome, COALESCE(valor_hora, 40.00) as valor_hora
                    FROM dim_funcionario
                    ORDER BY nome
                    """
                )
                resultados = cursor.fetchall()
                desenvolvedores = []
                for dev_id, nome, valor_hora in resultados:
                    desenvolvedores.append(
                        {
                            "id": dev_id,
                            "nome": nome,
                            "valor_hora": float(valor_hora),
                            "contrato": "CLT",
                            "contrato_label": "CLT",
                            "iniciais": DesenvolvedoresService._gerar_iniciais(nome),
                        }
                    )
                return desenvolvedores
        except Exception as exc:
            print(f"Erro fallback OLAP: {exc}")
            return []

    @staticmethod
    def _gerar_iniciais(nome):
        """Gera iniciais a partir do nome"""
        if not nome:
            return "XX"

        partes = nome.split()
        if len(partes) >= 2:
            return (partes[0][0] + partes[1][0]).upper()
        if len(partes) == 1:
            return partes[0][:2].upper()
        return "XX"

    @staticmethod
    def calcular_estatisticas(desenvolvedores):
        """Calcula estatísticas com base na lista de desenvolvedores"""
        if not desenvolvedores:
            return {
                "total_desenvolvedores": 0,
                "valor_medio": 0,
                "menor_valor": 0,
                "maior_valor": 0,
                "soma_total_valor_hora": 0,
            }

        valores = [dev["valor_hora"] for dev in desenvolvedores]
        soma_total = sum(valores)

        estatisticas = {
            "total_desenvolvedores": len(desenvolvedores),
            "valor_medio": round(soma_total / len(valores), 2),
            "menor_valor": min(valores),
            "maior_valor": max(valores),
            "soma_total_valor_hora": round(soma_total, 2),
        }

        return estatisticas

    @staticmethod
    def atualizar_valor_hora_oltp(desenvolvedor_id, nome, novo_valor_hora, contrato):
        """
        Atualiza valor/hora no banco OLTP
        """
        try:
            contrato_normalizado = (contrato or "CLT").upper()
            if contrato_normalizado not in {"CLT", "ESTAGIARIO"}:
                contrato_normalizado = "CLT"
            with connections["default"].cursor() as cursor:
                query = """
                UPDATE funcionario
                SET valor_hora = %s,
                    contrato = %s
                WHERE nome = %s OR id = %s
                """
                cursor.execute(
                    query,
                    [novo_valor_hora, contrato_normalizado, nome, desenvolvedor_id],
                )

                if cursor.rowcount == 0:
                    insert_query = """
                    INSERT INTO funcionario (nome, valor_hora, contrato, data_criacao)
                    VALUES (%s, %s, %s, NOW())
                    """
                    cursor.execute(
                        insert_query, [nome, novo_valor_hora, contrato_normalizado]
                    )
                    print(f"DEBUG Service: Inserido novo funcionário {nome} no OLTP")
                else:
                    print(f"DEBUG Service: Atualizado funcionário {nome} no OLTP")

                DesenvolvedoresService._atualizar_valor_hora_olap(
                    desenvolvedor_id, nome, novo_valor_hora
                )

                return True

        except Exception as e:
            print(f"Erro ao atualizar valor/hora OLTP: {e}")
            return False

    @staticmethod
    def _atualizar_valor_hora_olap(desenvolvedor_id, nome, novo_valor_hora):
        """
        Atualiza valor/hora no banco OLAP também
        """
        try:
            with connections["olap"].cursor() as cursor:
                query = """
                UPDATE dim_funcionario
                SET valor_hora = %s
                WHERE id = %s OR nome = %s
                """
                cursor.execute(query, [novo_valor_hora, desenvolvedor_id, nome])
                print(f"DEBUG Service: Valor/hora atualizado no OLAP para {nome}")

        except Exception as e:
            print(f"Erro ao atualizar valor/hora OLAP: {e}")
