-- =================================================================================
-- Script de carga para o OLTP (baseado em apps/relatorios/models.py)
-- =================================================================================
DO $$
DECLARE
    c_marina_nome CONSTANT TEXT := 'Marina Costa';
    c_rafael_nome CONSTANT TEXT := 'Rafael Nogueira';
    c_plat_key    CONSTANT TEXT := 'PLAT-1';
    c_mkt_key     CONSTANT TEXT := 'MKT-42';
    c_data_key    CONSTANT TEXT := 'DATA-7';
    c_status_wip  CONSTANT TEXT := 'Em progresso';
    c_status_done CONSTANT TEXT := 'Concluída';
BEGIN
    -- =================================================================================
    -- 0. Limpeza das tabelas base
    -- =================================================================================
    TRUNCATE TABLE
        issue,
        tipo_issue,
        projeto,
        funcionario,
        cargo
    RESTART IDENTITY CASCADE;

    -- =================================================================================
    -- 1. Inserção na tabela 'cargo'
    -- =================================================================================
    INSERT INTO cargo (sigla) VALUES
    ('PM'),
    ('TECH_LEAD'),
    ('DEV_BACKEND'),
    ('DEV_FRONTEND'),
    ('QA');

    -- =================================================================================
    -- 2. Inserção na tabela 'funcionario'
    -- =================================================================================
    INSERT INTO funcionario (nome, time, cargo_id, gerente_id, data_criacao, valor_hora) VALUES
    (c_marina_nome, 'Discovery', (SELECT id FROM cargo WHERE sigla = 'PM'), NULL, '2023-10-01', 190.00);

    INSERT INTO funcionario (nome, time, cargo_id, gerente_id, data_criacao, valor_hora) VALUES
    (c_rafael_nome, 'Platform', (SELECT id FROM cargo WHERE sigla = 'TECH_LEAD'), (SELECT id FROM funcionario WHERE nome = c_marina_nome), '2023-11-15', 160.00),
    ('Clara Mendes', 'Platform', (SELECT id FROM cargo WHERE sigla = 'DEV_BACKEND'), (SELECT id FROM funcionario WHERE nome = c_rafael_nome), '2024-01-10', 125.00),
    ('Otavio Ramos', 'Marketing Tech', (SELECT id FROM cargo WHERE sigla = 'DEV_FRONTEND'), (SELECT id FROM funcionario WHERE nome = c_rafael_nome), '2024-01-22', 115.00),
    ('Beatriz Lopes', 'Data', (SELECT id FROM cargo WHERE sigla = 'QA'), (SELECT id FROM funcionario WHERE nome = c_marina_nome), '2024-02-05', 110.00);

    -- =================================================================================
    -- 3. Inserção na tabela 'projeto'
    -- =================================================================================
    INSERT INTO projeto (jira_id, jira_key, nome, data_criacao, orcamento_previsto) VALUES
    (9101, c_plat_key, 'Plataforma de Pagamentos', '2024-02-15', 250000.00),
    (9102, c_mkt_key, 'Motor de Campanhas', '2023-11-01', 175000.00),
    (9103, c_data_key, 'Lakehouse Observability', '2024-04-20', 150000.00);

    -- =================================================================================
    -- 4. Inserção na tabela 'tipo_issue'
    -- =================================================================================
    WITH tipo_dados (projeto_key, nome, descricao, jira_id, data_criacao) AS (
        VALUES
            (c_plat_key, 'Bug', 'Correções críticas de checkout', 1201, '2024-03-01'),
            (c_plat_key, 'Feature', 'Funcionalidades de pagamento', 1202, '2024-03-05'),
            (c_mkt_key, 'Bug', 'Falhas em integrações de mídia', 2201, '2024-05-12'),
            (c_mkt_key, 'Melhoria', 'Ajustes incrementais da régua', 2202, '2024-05-15'),
            (c_data_key, 'Pesquisa', 'Spikes exploratórios', 3201, '2024-06-01'),
            (c_data_key, 'Tarefa', 'Trabalho operacional do time', 3202, '2024-06-03')
    )
    INSERT INTO tipo_issue (nome, descricao, jira_id, projeto_id, data_criacao)
    SELECT
        td.nome,
        td.descricao,
        td.jira_id,
        p.id,
        td.data_criacao
    FROM tipo_dados td
    JOIN projeto p ON p.jira_key = td.projeto_key;

    -- =================================================================================
    -- 5. Inserção na tabela 'issue'
    -- =================================================================================
    WITH issue_dados (
        projeto_key,
        tipo_nome,
        jira_id,
        jira_key,
        titulo,
        responsavel,
        criado_em,
        atualizado_em,
        tempo_estimado,
        tempo_gasto,
        status
    ) AS (
        VALUES
            (c_plat_key, 'Feature', 6001, 'PLAT-101', 'Checkout internacional', 'Clara Mendes', '2024-05-10 09:00:00', '2024-05-14 17:12:00', 36000, 37200, c_status_wip),
            (c_plat_key, 'Bug', 6002, 'PLAT-145', 'Timeout na conciliação', 'Beatriz Lopes', '2024-05-11 14:00:00', '2024-05-12 09:35:00', 14400, 10800, c_status_done),
            (c_mkt_key, 'Melhoria', 7001, 'MKT-420', 'Segmentação por região', c_rafael_nome, '2024-05-03 10:15:00', '2024-05-09 16:48:00', 28800, 32400, c_status_wip),
            (c_mkt_key, 'Bug', 7002, 'MKT-432', 'Eventos duplicados', 'Otavio Ramos', '2024-05-07 08:50:00', '2024-05-07 19:05:00', 21600, 19800, c_status_done),
            (c_data_key, 'Pesquisa', 8001, 'DATA-702', 'Avaliar formato Iceberg', c_marina_nome, '2024-06-01 11:00:00', '2024-06-04 18:20:00', 43200, 39600, c_status_wip),
            (c_data_key, 'Tarefa', 8002, 'DATA-715', 'Rotina de vacuum autom.', NULL, '2024-06-05 09:30:00', '2024-06-06 13:10:00', 14400, 12600, 'Backlog')
    )
    INSERT INTO issue (
        jira_id,
        jira_key,
        projeto_id,
        titulo,
        tipo_issue_id,
        criado_em,
        tempo_gasto_seconds,
        tempo_estimado_seconds,
        funcionario_id,
        atualizado_em,
        status
    )
    SELECT
        dados.jira_id,
        dados.jira_key,
        p.id AS projeto_id,
        dados.titulo,
        ti.id AS tipo_issue_id,
        dados.criado_em::TIMESTAMP,
        dados.tempo_gasto,
        dados.tempo_estimado,
        f.id AS funcionario_id,
        dados.atualizado_em::TIMESTAMP,
        dados.status
    FROM issue_dados dados
    JOIN projeto p ON p.jira_key = dados.projeto_key
    JOIN tipo_issue ti ON ti.projeto_id = p.id AND ti.nome = dados.tipo_nome
    LEFT JOIN funcionario f ON f.nome = dados.responsavel;
END $$;
