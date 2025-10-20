"  " "Serviços para geração de relatórios de atividade." ""

from collections import defaultdict
from datetime import datetime
from io import BytesIO

import matplotlib
import matplotlib.pyplot as plt
from django.db.models import Count, Sum
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, legal
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.relatorios.models import ControleHorasEquipe

matplotlib.use("Agg")


class AtividadeService:
    """Oferece métodos para processar e gerar relatórios de atividades.

    Esta classe funciona como uma camada de serviço, encapsulando a lógica
    de negócio para consultar o banco de dados, agregar dados de horas
    trabalhadas e exportar os resultados em diferentes formatos, como
    dicionários Python ou relatórios PDF completos usando a biblioteca ReportLab.

    Todos os métodos são estáticos, indicando que a classe é usada como
    um agrupador de funcionalidades relacionadas, sem a necessidade de
    gerir um estado interno.

    Attributes:
        MESES_PORTUGUES (dict): Um dicionário de classe que mapeia o número
            do mês (int) para o seu nome correspondente em português (str).
    """

    MESES_PORTUGUES = {
        1: "Janeiro",
        2: "Fevereiro",
        3: "Março",
        4: "Abril",
        5: "Maio",
        6: "Junho",
        7: "Julho",
        8: "Agosto",
        9: "Setembro",
        10: "Outubro",
        11: "Novembro",
        12: "Dezembro",
    }

    @staticmethod
    def _criar_estilo_tabela_base():
        """Cria e retorna o estilo base para as tabelas do relatório PDF.

        O estilo define uma aparência padrão e consistente para as tabelas,
        configurando cores de fundo e texto para o cabeçalho, fontes,
        alinhamentos e as linhas da grade.

        Returns:
            TableStyle: Um objeto `TableStyle` do ReportLab pré-configurado
                e pronto para ser aplicado a uma tabela.

        """
        return TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0000FF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("ALIGN", (0, 1), (-1, -1), "LEFT"),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )

    @staticmethod
    def _criar_tabela_com_estilo(data, col_widths, align_right_cols=None):
        """Cria um objeto Table do ReportLab com um estilo padrão.

        Esta função recebe os dados e a configuração das colunas, constrói
        uma tabela e aplica um estilo base. Opcionalmente, pode alinhar
        colunas específicas ao centro.

        Args:
            data (list): Uma lista de listas contendo os dados da tabela.
            col_widths (list): Uma lista com as larguras das colunas em
                unidades do ReportLab (ex: polegadas).
            align_right_cols (list, optional): Uma lista de índices de
                colunas (baseado em zero) que devem ter o seu conteúdo
                alinhado ao centro. O padrão é None.

        Returns:
            tuple: Uma tupla contendo o objeto `Table` e o objeto `TableStyle`
                aplicado a ele.

        """
        table = Table(data, colWidths=col_widths)
        style = AtividadeService._criar_estilo_tabela_base()

        if align_right_cols:
            for col in align_right_cols:
                style.add("ALIGN", (col, 1), (col, -1), "CENTER")

        table.setStyle(style)
        return table, style

    @staticmethod
    def _criar_subtitulo(texto: str, styles, space_after=0.1):
        """Cria um componente de subtítulo para o relatório PDF.

        Esta função gera uma lista contendo um parágrafo de subtítulo
        estilizado e um espaçador (`Spacer`) para adicionar um espaço
        vertical após o texto.

        Args:
            texto (str): O conteúdo textual que será exibido no subtítulo.
            styles (StyleSheet): O objeto de folha de estilos do ReportLab
                usado como base para a formatação.
            space_after (float, optional): A altura do espaçamento em
                polegadas a ser adicionado após o subtítulo. O padrão é 0.1.

        Returns:
            list: Uma lista de objetos 'flowable' do ReportLab, contendo
                o `Paragraph` do subtítulo e o `Spacer`.
        """
        subtitle_style = ParagraphStyle(
            "SubTitle",
            parent=styles["Heading2"],
            fontSize=12,
            spaceAfter=10,
            alignment=0,
        )
        return [Paragraph(texto, subtitle_style), Spacer(1, space_after * inch)]

    @staticmethod
    def _buscar_horas_detalhadas(ano: int, mes: int):
        """Busca horas detalhadas por funcionário e projeto.

        Args:
            ano (int): Ano para filtrar os dados.
            mes (int): Mês para filtrar os dados.

        Returns:
            QuerySet: Dados agregados de horas por funcionário e projeto.
        """
        return (
            ControleHorasEquipe.objects.filter(  # pylint: disable=no-member
                mes__year=ano, mes__month=mes
            )
            .values("funcionario_id__nome", "projeto_id__nome")
            .annotate(total_horas=Sum("horas"))
            .order_by("funcionario_id__nome", "projeto_id__nome")
        )

    @staticmethod
    def _processar_dados_horas_detalhadas(dados):
        """Processa os dados de horas, criando estruturas para por_projeto e totais.

        Args:
            dados: QuerySet com dados de horas por funcionário e projeto.

        Returns:
            tuple: Tupla contendo (por_projeto, total_por_dev).
        """
        totais = defaultdict(float)
        por_projeto = []

        for item in dados:
            funcionario = item["funcionario_id__nome"]
            projeto = item["projeto_id__nome"]
            total_horas = float(item["total_horas"])

            por_projeto.append(
                {
                    "funcionario": funcionario,
                    "projeto": projeto,
                    "total_horas": total_horas,
                }
            )
            totais[funcionario] += total_horas

        total_por_dev = [
            {"funcionario": funcionario, "total_horas": total}
            for funcionario, total in totais.items()
        ]

        return por_projeto, total_por_dev

    @staticmethod
    def horas_por_dev_e_projeto_por_mes(ano: int, mes: int) -> dict[list, list]:
        """Lista horas detalhadas por projeto e totais por desenvolvedor.

        Coordena a consulta ao banco de dados e o processamento dos dados
        para um mês e ano específicos, delegando responsabilidades para
        métodos auxiliares especializados.

        Args:
            ano (int): O ano para o qual o relatório será gerado.
            mes (int): O mês para o qual o relatório será gerado.

        Returns:
            dict: Um dicionário contendo duas chaves:
                'por_projeto' (list): Uma lista de dicionários, cada um
                    representando o total de horas de um dev em um projeto.
                'total_por_dev' (list): Uma lista de dicionários, cada um
                    com o total de horas de um desenvolvedor no mês.
        """
        dados = AtividadeService._buscar_horas_detalhadas(ano, mes)
        por_projeto, total_por_dev = AtividadeService._processar_dados_horas_detalhadas(
            dados
        )

        return {"por_projeto": por_projeto, "total_por_dev": total_por_dev}

    @staticmethod
    def soma_horas_por_dev_por_mes(ano: int, mes: int) -> list[dict[str, float]]:
        """Soma as horas agrupadas por desenvolvedor em um mês.

        Args:
            ano (int): Ano para geração do relatório.
            mes (int): Mês para geração do relatório.

        Returns:
            list[dict[str, float]]: Lista de dicionários com as chaves
                'funcionario' e 'total_horas'.
        """
        return list(
            ControleHorasEquipe.objects.filter(  # pylint: disable=no-member
                mes__year=ano, mes__month=mes
            )
            .values("funcionario_id__nome")
            .annotate(total_horas=Sum("horas"))
            .order_by("funcionario_id__nome")
        )

    @staticmethod
    def _buscar_dados_base(ano: int, mes: int):
        """Busca os dados base do banco de dados para o relatório.

        Args:
            ano (int): Ano para geração do relatório.
            mes (int): Mês para geração do relatório.

        Returns:
            QuerySet: Dados filtrados e otimizados do ControleHorasEquipe.
        """
        return (
            ControleHorasEquipe.objects.filter(  # pylint: disable=no-member
                mes__year=ano, mes__month=mes
            )
            .select_related("funcionario", "projeto")
            .order_by("funcionario__nome")
        )

    @staticmethod
    def _processar_dados_por_colaborador(queryset):
        """Organiza os dados por colaborador e projeto.

        Args:
            queryset: QuerySet com os dados do ControleHorasEquipe.

        Returns:
            tuple: Tupla contendo (dados_por_colaborador, projetos_nomes, dados_tabela).
        """
        dados_por_colaborador = defaultdict(lambda: defaultdict(float))
        for registro in queryset:
            dados_por_colaborador[registro.funcionario.nome][
                registro.projeto.nome
            ] += float(registro.horas)

        projetos_nomes = sorted(set(queryset.values_list("projeto__nome", flat=True)))

        dados_tabela = [
            {
                "colaborador_nome": colaborador,
                "horas": [projetos.get(p_nome, 0) for p_nome in projetos_nomes],
                "total_colaborador": sum(projetos.values()),
            }
            for colaborador, projetos in dados_por_colaborador.items()
        ]

        return projetos_nomes, dados_tabela

    @staticmethod
    def _calcular_totais_projeto(queryset, projetos_nomes):
        """Calcula os totais por projeto e total geral.

        Args:
            queryset: QuerySet com os dados do ControleHorasEquipe.
            projetos_nomes (list): Lista com nomes dos projetos.

        Returns:
            tuple: Tupla contendo (resumo_projetos, totais_por_projeto, total_geral_horas).
        """
        total_geral_horas = queryset.aggregate(total=Sum("horas"))["total"] or 0

        resumo_projetos = (
            queryset.values("projeto__nome")
            .annotate(
                total_horas=Sum("horas"),
                devs_no_projeto=Count("funcionario", distinct=True),
            )
            .order_by("-total_horas")
        )

        resumo_projetos_dict = {item["projeto__nome"]: item for item in resumo_projetos}

        totais_por_projeto = [
            resumo_projetos_dict.get(p_nome, {}).get("total_horas", 0)
            for p_nome in projetos_nomes
        ]

        return resumo_projetos, totais_por_projeto, total_geral_horas

    @staticmethod
    def _gerar_dados_cards(resumo_projetos, total_geral_horas):
        """Gera os dados formatados para os cards de resumo.

        Args:
            resumo_projetos: Lista com o resumo dos projetos.
            total_geral_horas (float): Total geral de horas.

        Returns:
            list: Lista de dicionários com dados dos cards.
        """
        return [
            {
                "projeto_nome": item["projeto__nome"],
                "total_horas": float(item["total_horas"]),
                "percentual": (
                    round(
                        (float(item["total_horas"]) / float(total_geral_horas)) * 100, 1
                    )
                    if total_geral_horas > 0
                    else 0
                ),
                "desenvolvedores": item["devs_no_projeto"],
            }
            for item in resumo_projetos
        ]

    @staticmethod
    def gerar_dados_relatorio_atividade(ano: int, mes: int) -> dict:
        """Gera os dados completos para o relatório de atividade.

        Esta função orquestra a geração de dados, delegando responsabilidades
        específicas para métodos auxiliares, mantendo a função principal
        focada apenas na coordenação do processo.

        Args:
            ano (int): Ano para geração do relatório.
            mes (int): Mês para geração do relatório.

        Returns:
            dict: Dados formatados e prontos para geração do relatório.
        """
        queryset = AtividadeService._buscar_dados_base(ano, mes)

        projetos_nomes, dados_tabela = (
            AtividadeService._processar_dados_por_colaborador(queryset)
        )

        resumo_projetos, totais_por_projeto, total_geral_horas = (
            AtividadeService._calcular_totais_projeto(queryset, projetos_nomes)
        )

        dados_cards = AtividadeService._gerar_dados_cards(
            resumo_projetos, total_geral_horas
        )

        return {
            "dados_tabela": dados_tabela,
            "dados_cards": dados_cards,
            "projetos_nomes": projetos_nomes,
            "totais_por_projeto": totais_por_projeto,
            "total_geral": total_geral_horas,
        }

    @staticmethod
    def _gerar_grafico_pizza(dados, titulo, label_key, value_key):
        """
        Método genérico para gerar gráficos de pizza.

        Args:
            dados (list): Lista de dicionários com os dados.
            titulo (str): Título do gráfico.
            label_key (str): Chave para extrair os labels dos dados.
            value_key (str): Chave para extrair os valores dos dados.

        Returns:
            BytesIO: Buffer com a imagem do gráfico em formato PNG ou None se não há dados.
        """
        if not dados or len(dados) == 0:
            return None

        plt.rcParams["font.family"] = "sans-serif"
        plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]

        _, ax = plt.subplots(figsize=(8, 6))  # noqa: F841

        labels = [item[label_key] for item in dados]
        sizes = [item[value_key] for item in dados]

        colors_palette = [
            "#3b82f6",
            "#10b981",
            "#f59e0b",
            "#ef4444",
            "#8b5cf6",
            "#06b6d4",
            "#f97316",
            "#84cc16",
            "#ec4899",
            "#6b7280",
            "#d97706",
            "#0ea5e9",
            "#9333ea",
            "#22c55e",
            "#dc2626",
        ]
        colors_list = [
            colors_palette[i % len(colors_palette)] for i in range(len(labels))
        ]

        _, _, autotexts = ax.pie(
            sizes,
            labels=labels,
            colors=colors_list,
            autopct="%1.1f%%",
            startangle=90,
            textprops={"fontsize": 10, "color": "black"},
        )

        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontweight("bold")
            autotext.set_fontsize(9)

        ax.set_title(titulo, fontsize=14, fontweight="bold", pad=20)

        ax.axis("equal")

        buffer = BytesIO()
        plt.savefig(
            buffer, format="png", dpi=150, bbox_inches="tight", facecolor="white"
        )
        plt.close()
        buffer.seek(0)

        return buffer

    @staticmethod
    def _gerar_grafico_pizza_projetos(dados_cards):
        """
        Gera um gráfico de pizza para distribuição de horas por projeto.

        Args:
            dados_cards (list): Lista de dicionários com dados dos projetos.

        Returns:
            BytesIO: Buffer com a imagem do gráfico em formato PNG.
        """
        return AtividadeService._gerar_grafico_pizza(
            dados_cards,
            "Distribuição de Horas por Projeto",
            "projeto_nome",
            "total_horas",
        )

    @staticmethod
    def _gerar_grafico_pizza_desenvolvedores(dados_tabela):
        """
        Gera um gráfico de pizza para distribuição de horas por desenvolvedor.

        Args:
            dados_tabela (list): Lista de dicionários com dados dos desenvolvedores.

        Returns:
            BytesIO: Buffer com a imagem do gráfico em formato PNG.
        """
        return AtividadeService._gerar_grafico_pizza(
            dados_tabela,
            "Distribuição de Horas por Desenvolvedor",
            "colaborador_nome",
            "total_colaborador",
        )

    @staticmethod
    def _gerar_tabela_horas_por_dev_e_projeto(dados, styles):
        """
        Gera a seção da tabela de horas detalhadas por desenvolvedor e projeto.

        Esta função cria um subtítulo, formata os dados de entrada em uma
        lista de listas e constrói um objeto `Table` do ReportLab com
        estilo. Apenas as entradas com horas maiores que zero são incluídas
        na tabela.

        Args:
            dados (dict): Um dicionário contendo os dados processados do
                relatório. Espera-se que contenha as chaves 'dados_tabela'
                e 'projetos_nomes'.
            styles (StyleSheet): O objeto de folha de estilos do ReportLab,
                usado para formatar o subtítulo.

        Returns:
            list: Uma lista de objetos 'flowable' do ReportLab (Parágrafo,
                Tabela, Espaçador) prontos para serem adicionados ao
                documento PDF.
        """
        elements = AtividadeService._criar_subtitulo(
            "Horas por Desenvolvedor e Projeto", styles
        )
        table_data = [["Desenvolvedor", "Projeto", "Horas"]]
        for registro in dados["dados_tabela"]:
            for i, projeto_nome in enumerate(dados["projetos_nomes"]):
                horas = registro["horas"][i]
                if horas > 0:
                    table_data.append(
                        [registro["colaborador_nome"], projeto_nome, f"{horas:.1f}h"]
                    )
        table, _ = AtividadeService._criar_tabela_com_estilo(
            table_data, [2.5 * inch, 3 * inch, 1 * inch], align_right_cols=[2]
        )
        elements.append(table)
        elements.append(Spacer(1, 0.3 * inch))
        return elements

    @staticmethod
    def _gerar_tabela_total_horas_por_dev(dados, styles):
        """Gera a seção da tabela com o total de horas por desenvolvedor.

        Esta função cria uma tabela que resume o total de horas trabalhadas
        por cada colaborador durante o período. Adiciona também uma linha
        de "TOTAL GERAL" ao final, que é estilizada com uma cor de fundo
        diferente e texto em negrito para destaque.

        Args:
            dados (dict): Um dicionário contendo os dados processados do
                relatório. Espera-se que contenha as chaves 'dados_tabela'
                e 'total_geral'.
            styles (StyleSheet): O objeto de folha de estilos do ReportLab,
                usado para formatar o subtítulo.

        Returns:
            list: Uma lista de objetos 'flowable' do ReportLab (Parágrafo,
                Tabela, Espaçador) prontos para serem adicionados ao
                documento PDF."""
        elements = AtividadeService._criar_subtitulo(
            "Total de Horas por Desenvolvedor", styles
        )
        table_data = [["Desenvolvedor", "Total de Horas"]] + [
            [registro["colaborador_nome"], f"{registro['total_colaborador']:.1f}h"]
            for registro in dados["dados_tabela"]
        ]
        table_data.append(["TOTAL GERAL", f"{dados['total_geral']:.1f}h"])
        table, table_style = AtividadeService._criar_tabela_com_estilo(
            table_data, [4 * inch, 2 * inch], align_right_cols=[1]
        )
        total_row = len(table_data) - 1
        table_style.add(
            "BACKGROUND", (0, total_row), (-1, total_row), colors.HexColor("#e9d5ff")
        )
        table_style.add("FONTNAME", (0, total_row), (-1, total_row), "Helvetica-Bold")
        table.setStyle(table_style)
        elements.append(table)
        elements.append(Spacer(1, 0.3 * inch))
        return elements

    @staticmethod
    def _gerar_tabela_total_horas_por_projeto(dados, styles):
        """
        Gera a seção da tabela com o total de horas consolidadas por projeto.

        Esta função cria uma tabela que resume o total de horas trabalhadas
        em cada projeto durante o período. Os dados são extraídos da chave
        'dados_cards' do dicionário de entrada.

        Args:
            dados (dict): Um dicionário contendo os dados processados do
                relatório. Espera-se que contenha a chave 'dados_cards'.
            styles (StyleSheet): O objeto de folha de estilos do ReportLab,
                usado para formatar o subtítulo.

        Returns:
            list: Uma lista de objetos 'flowable' do ReportLab (Parágrafo,
                Tabela, Espaçador) prontos para serem adicionados ao
                documento PDF.
        """
        elements = AtividadeService._criar_subtitulo(
            "Total de Horas por Projeto", styles
        )
        table_data = [["Projeto", "Total de Horas"]] + [
            [registro["projeto_nome"], f"{registro['total_horas']:.1f}h"]
            for registro in dados["dados_cards"]
        ]
        table, _ = AtividadeService._criar_tabela_com_estilo(
            table_data, [4 * inch, 2 * inch], align_right_cols=[1]
        )
        elements.append(table)
        elements.append(Spacer(1, 0.2 * inch))
        return elements

    @staticmethod
    def _gerar_secao_grafico_projetos(dados):
        """
        Gera a seção do gráfico de pizza para distribuição por projeto.

        Args:
            dados (dict): Dados processados do relatório.

        Returns:
            list: Lista de elementos do ReportLab para o gráfico.
        """
        elements = []

        grafico_buffer = AtividadeService._gerar_grafico_pizza_projetos(
            dados["dados_cards"]
        )

        if grafico_buffer:
            img = Image(grafico_buffer, width=6 * inch, height=4.5 * inch)
            elements.append(img)
            elements.append(Spacer(1, 0.3 * inch))

        return elements

    @staticmethod
    def _gerar_secao_grafico_desenvolvedores(dados):
        """
        Gera a seção do gráfico de pizza para distribuição por desenvolvedor.

        Args:
            dados (dict): Dados processados do relatório.

        Returns:
            list: Lista de elementos do ReportLab para o gráfico.
        """
        elements = []

        grafico_buffer = AtividadeService._gerar_grafico_pizza_desenvolvedores(
            dados["dados_tabela"]
        )

        if grafico_buffer:
            img = Image(grafico_buffer, width=6 * inch, height=4.5 * inch)
            elements.append(img)
            elements.append(Spacer(1, 0.3 * inch))

        return elements

    @staticmethod
    def _gerar_footer(styles):
        """
        Cria o parágrafo de rodapé para o relatório PDF.

        Esta função gera um objeto `Paragraph` do ReportLab que contém
        a data e a hora exatas em que o relatório foi gerado. O estilo
        do texto é definido para ter uma fonte menor, apropriada para
        um rodapé.

        Args:
            styles (StyleSheet): O objeto de folha de estilos do ReportLab,
                usado como base para o estilo do parágrafo do rodapé.

        Returns:
            Paragraph: Um objeto `Paragraph` do ReportLab contendo o
                texto do rodapé formatado.
        """
        return Paragraph(
            f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            ParagraphStyle("DateStyle", parent=styles["Normal"], fontSize=8),
        )

    @staticmethod
    def _configurar_documento_pdf(buffer):
        """Configura o documento PDF com tamanho e margens adequadas.

        Args:
            buffer: Buffer de bytes onde o PDF será escrito.

        Returns:
            SimpleDocTemplate: Documento PDF configurado.
        """
        return SimpleDocTemplate(
            buffer,
            pagesize=landscape(legal),
            leftMargin=0.2 * inch,
            rightMargin=0.2 * inch,
            topMargin=0.3 * inch,
            bottomMargin=0.3 * inch,
        )

    @staticmethod
    def _criar_titulo_relatorio(mes, ano, styles):
        """Cria o título formatado do relatório.

        Args:
            mes (int): Mês do relatório.
            ano (int): Ano do relatório.
            styles: Estilos do ReportLab.

        Returns:
            list: Lista com elementos do título e espaçamento.
        """
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=16,
            spaceAfter=20,
            alignment=1,
        )

        title_text = f'''Relatório de Atividades - {
            AtividadeService.MESES_PORTUGUES.get(mes)}/{ano}'''
        return [Paragraph(title_text, title_style), Spacer(1, 0.2 * inch)]

    @staticmethod
    def _combinar_elementos_relatorio(dados, styles):
        """Combina todos os elementos do relatório em uma lista.

        Args:
            dados (dict): Dados processados do relatório.
            styles: Estilos do ReportLab.

        Returns:
            list: Lista completa de elementos para o PDF.
        """
        elements = []

        elements += AtividadeService._gerar_tabela_horas_por_dev_e_projeto(
            dados, styles
        )
        elements += AtividadeService._gerar_tabela_total_horas_por_dev(dados, styles)
        elements += AtividadeService._gerar_tabela_total_horas_por_projeto(
            dados, styles
        )

        # type: ignore
        elements += AtividadeService._gerar_secao_grafico_projetos(dados)
        elements += AtividadeService._gerar_secao_grafico_desenvolvedores(
            dados
        )  # type: ignore

        elements.append(AtividadeService._gerar_footer(styles))
        return elements

    @staticmethod
    def exportar_atividade_pdf(mes, ano, dados):
        """Orquestra a geração completa do relatório de atividades em PDF.

        Esta função coordena a criação do PDF, delegando responsabilidades
        específicas para métodos auxiliares, mantendo-a focada apenas na
        orquestração do processo de geração.

        Args:
            mes (int): O mês para o qual o relatório será gerado.
            ano (int): O ano para o qual o relatório será gerado.
            dados (dict): Um dicionário contendo todos os dados já
                processados e necessários para popular as tabelas.

        Returns:
            bytes: Os bytes brutos do arquivo PDF gerado, prontos para
                serem usados em uma resposta HTTP.
        """
        buffer = BytesIO()
        doc = AtividadeService._configurar_documento_pdf(buffer)
        styles = getSampleStyleSheet()

        elements = []
        elements += AtividadeService._criar_titulo_relatorio(mes, ano, styles)
        elements += AtividadeService._combinar_elementos_relatorio(dados, styles)

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf
