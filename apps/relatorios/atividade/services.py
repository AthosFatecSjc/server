from collections import defaultdict
from django.db.models import Sum, Count
from apps.relatorios.models import ControleHorasEquipe
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import landscape, legal
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch


class AtividadeService:
    """Service responsável por gerar relatórios de horas trabalhadas."""

    MESES_PORTUGUES = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }

    @staticmethod
    def _criar_estilo_tabela_base():
        """
        Cria o estilo base para tabelas utilizadas no PDF de relatório.

    Returns:
        TableStyle: Objeto configurado com o estilo padrão de cabeçalho, fonte, alinhamento e bordas para uso em tabelas do PDF.
        
        """
        return TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0000FF')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ])

    @staticmethod
    def _criar_tabela_com_estilo(data, col_widths, align_right_cols=None):
        """
         Cria e retorna o estilo base para tabelas utilizadas nos relatórios PDF.

    O estilo define configurações de cor de fundo, cor do texto, alinhamento, 
    fonte, tamanho da fonte, preenchimento, grade e alinhamento vertical para as células da tabela.

    Returns:
        TableStyle: Objeto com as configurações de estilo para aplicação em tabelas do ReportLab.
        
        """
        table = Table(data, colWidths=col_widths)
        style = AtividadeService._criar_estilo_tabela_base()

        if align_right_cols:
            for col in align_right_cols:
                style.add('ALIGN', (col, 1), (col, -1), 'CENTER')

        table.setStyle(style)
        return table, style

    @staticmethod
    def _criar_subtitulo(texto: str, styles, space_after=0.1):
        """
        Cria um parágrafo de subtítulo para ser utilizado em relatórios PDF.

        Este método gera um subtítulo estilizado com espaçamento padrão após o texto,
        utilizando o estilo base fornecido.

         Args:
        texto (str): Texto que será exibido como subtítulo.
        styles: Coleção de estilos do ReportLab para formatação do subtítulo.
        space_after (float, opcional): Espaçamento (em polegadas) após o subtítulo. Padrão é 0.1.

         Returns:
        list: Lista contendo um objeto Paragraph estilizado e um Spacer para espaçamento.
        """
        subtitle_style = ParagraphStyle(
            'SubTitle',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=10,
            alignment=0
        )
        return [
            Paragraph(texto, subtitle_style),
            Spacer(1, space_after * inch)
        ]

    @staticmethod
    def horas_por_dev_e_projeto_por_mes(ano: int, mes: int) -> dict[list, list]:
        """
        Lista as horas de cada dev por projeto e o total por dev para um mês específico.

    Args:
        ano (int): Ano para geração do relatório.
        mes (int): Mês para geração do relatório.

    Returns:
        dict[list, list]: Dicionário com duas listas: 'por_projeto' e 'total_por_dev'.
        
        
        """
        dados = (
            ControleHorasEquipe.objects
            .filter(mes__year=ano, mes__month=mes)
            .values('funcionario_id__nome', 'projeto_id__nome')
            .annotate(total_horas=Sum('horas'))
            .order_by('funcionario_id__nome', 'projeto_id__nome')
        )

        totais = defaultdict(float)
        por_projeto = []

        for item in dados:
            funcionario = item['funcionario_id__nome']
            projeto = item['projeto_id__nome']
            total_horas = float(item['total_horas'])

            por_projeto.append({
                'funcionario': funcionario,
                'projeto': projeto,
                'total_horas': total_horas
            })
            totais[funcionario] += total_horas

        total_por_dev = [
            {'funcionario': funcionario, 'total_horas': total}
            for funcionario, total in totais.items()
        ]

        return {
            'por_projeto': por_projeto,
            'total_por_dev': total_por_dev
        }

    @staticmethod
    def soma_horas_por_dev_por_mes(ano: int, mes: int) -> list[dict[str, float]]:
        """
         Soma as horas agrupadas por desenvolvedor em um mês.
        Parameters:
            ano (int): Ano para geração do relatório
            mes (int): Mes para geração do relatório
        
        Returns:
            List: Lista de dicionários com 'funcionario', 'total_horas'
        """
        return list(
            ControleHorasEquipe.objects
            .filter(mes__year=ano, mes__month=mes)
            .values('funcionario_id__nome')
            .annotate(total_horas=Sum('horas'))
            .order_by('funcionario_id__nome')
        )

    @staticmethod
    def gerar_dados_relatorio_atividade(ano: int, mes: int) -> dict:
        """
        Essa função gera os dados de relatório de atividade
        Parameters:
            ano (int): Ano para geração do relatório
            mes (int): Mes para geração do relatório
        Returns:
            dict: Dados filtrados para geração da tabela
        """
        queryset = ControleHorasEquipe.objects.filter(
            mes__year=ano,
            mes__month=mes
        ).select_related('funcionario', 'projeto').order_by('funcionario__nome')

        dados_por_colaborador = defaultdict(lambda: defaultdict(float))
        for registro in queryset:
            dados_por_colaborador[registro.funcionario.nome][registro.projeto.nome] += float(registro.horas)

        projetos_nomes = sorted(set(queryset.values_list('projeto__nome', flat=True)))

        dados_tabela = [
            {
                'colaborador_nome': colaborador,
                'horas': [projetos.get(p_nome, 0) for p_nome in projetos_nomes],
                'total_colaborador': sum(projetos.values())
            }
            for colaborador, projetos in dados_por_colaborador.items()
        ]

        total_geral_horas = queryset.aggregate(total=Sum('horas'))['total'] or 0

        resumo_projetos = queryset.values('projeto__nome').annotate(
            total_horas=Sum('horas'),
            devs_no_projeto=Count('funcionario', distinct=True)
        ).order_by('-total_horas')

        resumo_projetos_dict = {item['projeto__nome']: item for item in resumo_projetos}

        totais_por_projeto = [
            resumo_projetos_dict.get(p_nome, {}).get('total_horas', 0) for p_nome in projetos_nomes
        ]

        dados_cards = [
            {
                'projeto_nome': item['projeto__nome'],
                'total_horas': float(item['total_horas']),
                'percentual': round((float(item['total_horas']) / float(total_geral_horas)) * 100, 1)
                if total_geral_horas > 0 else 0,
                'desenvolvedores': item['devs_no_projeto'],
            }
            for item in resumo_projetos
        ]

        return {
            'dados_tabela': dados_tabela,
            'dados_cards': dados_cards,
            'projetos_nomes': projetos_nomes,
            'totais_por_projeto': totais_por_projeto,
            'total_geral': total_geral_horas
        }

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
        elements = AtividadeService._criar_subtitulo("Horas por Desenvolvedor e Projeto", styles)
        table_data = [["Desenvolvedor", "Projeto", "Horas"]]
        for registro in dados['dados_tabela']:
            for i, projeto_nome in enumerate(dados['projetos_nomes']):
                horas = registro['horas'][i]
                if horas > 0:
                    table_data.append([registro['colaborador_nome'], projeto_nome, f"{horas:.1f}h"])
        table, _ = AtividadeService._criar_tabela_com_estilo(
            table_data, [2.5*inch, 3*inch, 1*inch], align_right_cols=[2]
        )
        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))
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
        elements = AtividadeService._criar_subtitulo("Total de Horas por Desenvolvedor", styles)
        table_data = [["Desenvolvedor", "Total de Horas"]] + [
            [registro['colaborador_nome'], f"{registro['total_colaborador']:.1f}h"]
            for registro in dados['dados_tabela']
        ]
        table_data.append(["TOTAL GERAL", f"{dados['total_geral']:.1f}h"])
        table, table_style = AtividadeService._criar_tabela_com_estilo(
            table_data, [4*inch, 2*inch], align_right_cols=[1]
        )
        total_row = len(table_data) - 1
        table_style.add('BACKGROUND', (0, total_row), (-1, total_row), colors.HexColor('#e9d5ff'))
        table_style.add('FONTNAME', (0, total_row), (-1, total_row), 'Helvetica-Bold')
        table.setStyle(table_style)
        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))
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
        elements = AtividadeService._criar_subtitulo("Total de Horas por Projeto", styles)
        table_data = [["Projeto", "Total de Horas"]] + [
            [registro['projeto_nome'], f"{registro['total_horas']:.1f}h"]
            for registro in dados['dados_cards']
        ]
        table, _ = AtividadeService._criar_tabela_com_estilo(
            table_data, [4*inch, 2*inch], align_right_cols=[1]
        )
        elements.append(table)
        elements.append(Spacer(1, 0.2*inch))
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
            ParagraphStyle('DateStyle', parent=styles['Normal'], fontSize=8)
        )

    @staticmethod
    def exportar_atividade_pdf(mes, ano, dados):
        """
        Orquestra a geração completa do relatório de atividades em PDF.

        Esta função é o ponto de entrada para a exportação. Ela configura
        o documento PDF (tamanho da página e margens), define o título
        com base no mês e ano, e chama os métodos auxiliares para construir
        cada seção do relatório. O resultado final é um arquivo PDF completo
        gerado em memória.

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
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(legal),
            leftMargin=0.2*inch,
            rightMargin=0.2*inch,
            topMargin=0.3*inch,
            bottomMargin=0.3*inch
        )
        elements = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1
        )

        title_text = f"Relatório de Atividades - {AtividadeService.MESES_PORTUGUES.get(mes)}/{ano}"
        elements.append(Paragraph(title_text, title_style))
        elements.append(Spacer(1, 0.2*inch))

        elements += AtividadeService._gerar_tabela_horas_por_dev_e_projeto(dados, styles)
        elements += AtividadeService._gerar_tabela_total_horas_por_dev(dados, styles)
        elements += AtividadeService._gerar_tabela_total_horas_por_projeto(dados, styles)
        elements.append(AtividadeService._gerar_footer(styles))

        doc.build(elements)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf