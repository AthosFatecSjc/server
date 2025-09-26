from collections import defaultdict
from django.db.models import Sum, Count
from apps.relatorios.models import ControleHorasEquipe
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch


class AtividadeService:
    """Service para gerar relatórios de horas trabalhadas."""

    @staticmethod
    def _criar_estilo_tabela_base():
        """Cria estilo base para tabelas do PDF."""
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
        """Cria tabela com estilo padrão."""
        table = Table(data, colWidths=col_widths)
        style = AtividadeService._criar_estilo_tabela_base()
        
        if align_right_cols:
            for col in align_right_cols:
                style.add('ALIGN', (col, 1), (col, -1), 'CENTER')
        
        table.setStyle(style)
        return table, style

    @staticmethod
    def horas_por_dev_e_projeto_por_mes(ano: int, mes: int) -> dict[list, list]:
        """Lista as horas de cada dev por projeto e o total por dev para um mês específico."""

        # Horas por projeto
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
        """Soma as horas agrupadas por desenvolvedor em um mês."""

        dados = (
            ControleHorasEquipe.objects
            .filter(mes__year=ano, mes__month=mes)
            .values('funcionario_id__nome')
            .annotate(total_horas=Sum('horas'))
            .order_by('funcionario_id__nome')
        )

        return list(dados)

    @staticmethod
    def gerar_dados_relatorio_atividade(ano: int, mes: int) -> dict:
        """Gera os dados de relatório de atividade."""

        queryset = ControleHorasEquipe.objects.filter(
            mes__year=ano,
            mes__month=mes
        ).select_related('funcionario', 'projeto').order_by('funcionario__nome')

        dados_por_colaborador = defaultdict(lambda: defaultdict(float))
        for registro in queryset:
            nome_colaborador = registro.funcionario.nome
            nome_projeto = registro.projeto.nome
            dados_por_colaborador[nome_colaborador][nome_projeto] += float(registro.horas)

        projetos_nomes = sorted(set(queryset.values_list('projeto__nome', flat=True)))
        
        dados_tabela = []
        for colaborador, projetos in dados_por_colaborador.items():
            total_colaborador = sum(projetos.values())
            horas_ordenadas = [projetos.get(p_nome, 0) for p_nome in projetos_nomes]
            dados_tabela.append({
                'colaborador_nome': colaborador,
                'horas': horas_ordenadas,
                'total_colaborador': total_colaborador
            })

        total_geral_horas = queryset.aggregate(total=Sum('horas'))['total'] or 0
        
        resumo_projetos = queryset.values('projeto__nome').annotate(
            total_horas=Sum('horas'),
            devs_no_projeto=Count('funcionario', distinct=True)
        ).order_by('-total_horas')

        resumo_projetos_dict = {item['projeto__nome']: item for item in resumo_projetos}

        totais_por_projeto = [
            resumo_projetos_dict.get(p_nome, {}).get('total_horas', 0) for p_nome in projetos_nomes
        ]

        dados_cards = []
        for item in resumo_projetos:
            total_horas = float(item['total_horas'])
            dados_cards.append({
                'projeto_nome': item['projeto__nome'],
                'total_horas': total_horas,
                'percentual': round((total_horas / float(total_geral_horas)) * 100, 1) if total_geral_horas > 0 else 0,
                'desenvolvedores': item['devs_no_projeto'],
            })

        context = {
            'dados_tabela': dados_tabela,
            'dados_cards': dados_cards,
            'projetos_nomes': projetos_nomes,
            'totais_por_projeto': totais_por_projeto,
            'total_geral': total_geral_horas
        }
        
        return context

    @staticmethod
    def exportar_atividade_pdf(mes, ano, dados):
        """Gera um PDF com o relatório de atividades."""
        MESES_PORTUGUES = {
            1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
            5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
            9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
        }
        
        from reportlab.lib.pagesizes import legal
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(legal),
                               leftMargin=0.2*inch,
                               rightMargin=0.2*inch,
                               topMargin=0.3*inch,
                               bottomMargin=0.3*inch)
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=20,
            alignment=1
        )
        
        title_text = f"Relatório de Atividades - {MESES_PORTUGUES.get(mes)}/{ano}"
        elements.append(Paragraph(title_text, title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        subtitle_style = ParagraphStyle(
            'SubTitle',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=10,
            alignment=0
        )
        
        elements.append(Paragraph("Horas por Desenvolvedor e Projeto", subtitle_style))
        elements.append(Spacer(1, 0.1*inch))
        
        table_data = [["Desenvolvedor", "Projeto", "Horas"]]
        
        for registro in dados['dados_tabela']:
            colaborador_nome = registro['colaborador_nome']
            horas_por_projeto = registro['horas']
            projetos_nomes = dados['projetos_nomes']
            
            for i, projeto_nome in enumerate(projetos_nomes):
                horas = horas_por_projeto[i]
                if horas > 0:  
                    table_data.append([
                        colaborador_nome,
                        projeto_nome,
                        f"{horas:.1f}h"
                    ])

        table1, _ = AtividadeService._criar_tabela_com_estilo(
            table_data, 
            [2.5*inch, 3*inch, 1*inch], 
            align_right_cols=[2]
        )
        elements.append(table1)
        elements.append(Spacer(1, 0.3*inch))
        
        elements.append(Paragraph("Total de Horas por Desenvolvedor", subtitle_style))
        elements.append(Spacer(1, 0.1*inch))
        
        table_data2 = [["Desenvolvedor", "Total de Horas"]]
        
        for registro in dados['dados_tabela']:
            table_data2.append([
                registro['colaborador_nome'],
                f"{registro['total_colaborador']:.1f}h"
            ])
        
        table_data2.append([
            "TOTAL GERAL",
            f"{dados['total_geral']:.1f}h"
        ])
        
        table2, table2_style = AtividadeService._criar_tabela_com_estilo(
            table_data2, 
            [4*inch, 2*inch], 
            align_right_cols=[1]
        )
        
        total_row = len(table_data2) - 1
        table2_style.add('BACKGROUND', (0, total_row), (-1, total_row), colors.HexColor('#e9d5ff'))
        table2_style.add('FONTNAME', (0, total_row), (-1, total_row), 'Helvetica-Bold')
        table2.setStyle(table2_style)
        
        elements.append(table2)
        elements.append(Spacer(1, 0.3*inch))
        
        elements.append(Paragraph("Total de Horas por Projeto", subtitle_style))
        elements.append(Spacer(1, 0.1*inch))
        
        table_data3 = [["Projeto", "Total de Horas"]]
        
        for registro in dados['dados_cards']:
            table_data3.append([
                registro['projeto_nome'],
                f"{registro['total_horas']:.1f}h"
            ])
        
        table3, _ = AtividadeService._criar_tabela_com_estilo(
            table_data3, 
            [4*inch, 2*inch], 
            align_right_cols=[1]
        )
        elements.append(table3)
        
        elements.append(Spacer(1, 0.2*inch))
        
        gen_date = Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 
                             ParagraphStyle('DateStyle', parent=styles['Normal'], fontSize=8))
        elements.append(gen_date)
        
        doc.build(elements)
        
        pdf = buffer.getvalue()
        buffer.close()
        
        return pdf
