-- # Script de Limpeza e Inserção de Dados -
TRUNCATE TABLE 
    cargo,
    funcionario,
    projeto,
    controle_horas_equipe_resumo,
    meta_tempo_controle,
    controle_horas_equipe,
    controle_tempo_equipe,
    controle_tempo_resumo
RESTART IDENTITY CASCADE;


-- # Script de Inserção de Dados - Unificado e

-- 1. Inserção na Tabela 'cargo'
INSERT INTO cargo (sigla) VALUES
('Gerente de Projetos'),
('Membro de Equipe'),
('Lider de Equipe');

-- 2. Inserção na Tabela 'projeto' com data_criacao randômica
INSERT INTO projeto (nome, data_criacao)
SELECT
    nome,
    '2025-01-01'::DATE + (random() * (DATE '2025-12-31' - DATE '2025-01-01'))::INT AS data_criacao
FROM (
    VALUES
        ('SOS Mnt'),
        ('SOS Ges'),
        ('SOS Ed'),
        ('Ball Anal'),
        ('Ball LNO'),
        ('Ball PFS'),
        ('Ball Dados'),
        ('Bayer Mak'),
        ('Incra'),
        ('Climatem'),
        ('Comercial'),
        ('Reunião'),
        ('Projeto A'),
        ('Projeto B'),
        ('Projeto C'),
        ('Projeto D'),
        ('Projeto E'),
        ('Projeto F'),
        ('Projeto G'),
        ('Projeto H'),
        ('Projeto I'),
        ('Projeto J')
) AS projetos(nome);

-- 3. Inserção na Tabela 'meta_tempo_controle'
INSERT INTO meta_tempo_controle (objetivo_clt, objetivo_estagiario) VALUES
('7', '6');

-- 4. Inserção na Tabela 'funcionario'
INSERT INTO funcionario (nome, time, cargo_id, gerente_id, data_criacao) VALUES
('Daniel Maturana', 'Squad A', (SELECT id FROM cargo WHERE sigla = 'Gerente de Projetos'), NULL, CURRENT_DATE),
('Aline Dominique', 'Squad A', (SELECT id FROM cargo WHERE sigla = 'Membro de Equipe'), (SELECT id FROM funcionario WHERE nome = 'Daniel Maturana'), CURRENT_DATE),
('Felipe Faria', 'Squad A', (SELECT id FROM cargo WHERE sigla = 'Membro de Equipe'), (SELECT id FROM funcionario WHERE nome = 'Daniel Maturana'), CURRENT_DATE),
('Eric Lourenço', 'Squad A', (SELECT id FROM cargo WHERE sigla = 'Lider de Equipe'), (SELECT id FROM funcionario WHERE nome = 'Daniel Maturana'), CURRENT_DATE),
('Alison Americo', 'Squad B', (SELECT id FROM cargo WHERE sigla = 'Membro de Equipe'), (SELECT id FROM funcionario WHERE nome = 'Daniel Maturana'), CURRENT_DATE),
('Francisco Bustamante', 'Squad B', (SELECT id FROM cargo WHERE sigla = 'Membro de Equipe'), (SELECT id FROM funcionario WHERE nome = 'Daniel Maturana'), CURRENT_DATE),
('Helena Benevenuto', 'Squad B', (SELECT id FROM cargo WHERE sigla = 'Membro de Equipe'), (SELECT id FROM funcionario WHERE nome = 'Daniel Maturana'), CURRENT_DATE),
('João V Menezes', 'Squad B', (SELECT id FROM cargo WHERE sigla = 'Lider de Equipe'), (SELECT id FROM funcionario WHERE nome = 'Daniel Maturana'), CURRENT_DATE),
('Jose Thomazini', 'Squad C', (SELECT id FROM cargo WHERE sigla = 'Membro de Equipe'), (SELECT id FROM funcionario WHERE nome = 'Daniel Maturana'), CURRENT_DATE),
('Lucas Paiva', 'Squad C', (SELECT id FROM cargo WHERE sigla = 'Lider de Equipe'), (SELECT id FROM funcionario WHERE nome = 'Daniel Maturana'), CURRENT_DATE),
('Sérgio Casas', 'Squad C', (SELECT id FROM cargo WHERE sigla = 'Membro de Equipe'), (SELECT id FROM funcionario WHERE nome = 'Daniel Maturana'), CURRENT_DATE);

-- 5. Inserção na Tabela 'controle_tempo_equipe'
INSERT INTO CONTROLE_TEMPO_EQUIPE (
    DIA_SEMANA,
    DIA_MES,
    MES,
    FUNCIONARIO_ID,
    TEMPO_GASTO,
    META_ID
)
SELECT
    TRIM(TO_CHAR(D, 'Day')) AS DIA_SEMANA,
    EXTRACT(DAY FROM D)::INT AS DIA_MES,
    DATE_TRUNC('month', D)::DATE AS MES,
    F.id AS FUNCIONARIO_ID,
    ROUND(
        CASE
            WHEN EXTRACT(DOW FROM D) IN (0,6) THEN 0
            WHEN F.id % 2 = 0 THEN (4 + RANDOM() * 2)::NUMERIC
            ELSE (6 + RANDOM() * 3)::NUMERIC
        END
    , 1) AS TEMPO_GASTO,
    CASE
        WHEN F.id % 2 = 0 THEN (SELECT id FROM meta_tempo_controle WHERE objetivo_estagiario = '6')
        ELSE (SELECT id FROM meta_tempo_controle WHERE objetivo_clt = '7')
    END AS META_ID
FROM
    GENERATE_SERIES('2025-01-01'::DATE, '2025-12-31'::DATE, '1 day') D
    CROSS JOIN funcionario F
ORDER BY
    D,
    F.id;

-- 6. Inserção na Tabela 'controle_tempo_resumo'
INSERT INTO controle_tempo_resumo (
    realizado_equipe,
    total_real,
    total_meta,
    aproveitamento,
    controle_tempo_equipe_id
)
SELECT
    c.tempo_gasto AS realizado_equipe,
    c.tempo_gasto AS total_real,
    CASE
        WHEN mtc.objetivo_clt = '7' THEN 154.0
        WHEN mtc.objetivo_estagiario = '6' THEN 132.0
        ELSE 0
    END AS total_meta,
    CASE
        WHEN c.tempo_gasto > 0 THEN
            ROUND((c.tempo_gasto /
                CASE
                    WHEN mtc.objetivo_clt = '7' THEN 154.0
                    WHEN mtc.objetivo_estagiario = '6' THEN 132.0
                    ELSE 1
                END) * 100, 2)
        ELSE 0
    END AS aproveitamento,
    c.id AS controle_tempo_equipe_id
FROM
    controle_tempo_equipe c
JOIN
    meta_tempo_controle mtc ON c.meta_id = mtc.id
WHERE
    c.tempo_gasto > 0;

-- 7. Geração e Inserção para 'controle_horas_equipe_resumo' e 'controle_horas_equipe'
WITH TotalHorasFuncionarioMes AS (
    SELECT
        DATE_TRUNC('month', mes)::DATE AS mes_referencia,
        funcionario_id,
        SUM(tempo_gasto) AS total_horas
    FROM
        controle_tempo_equipe
    WHERE
        EXTRACT(DOW FROM mes) NOT IN (0,6) AND tempo_gasto > 0
    GROUP BY
        DATE_TRUNC('month', mes), funcionario_id
),
HorasDistribuidaPorProjeto AS (
    SELECT
        thfm.mes_referencia,
        thfm.funcionario_id,
        proj.id AS projeto_id,
        ROUND( (thfm.total_horas * (RANDOM() * 0.7 + 0.3))::numeric, 2 ) AS horas_parciais
    FROM
        TotalHorasFuncionarioMes thfm,
        (SELECT id FROM projeto ORDER BY RANDOM() LIMIT (1 + (RANDOM() * 7)::INT)) AS proj(id)
),
HorasFinaisPorFuncionarioProjetoMes AS (
    SELECT
        hdp.mes_referencia,
        hdp.funcionario_id,
        hdp.projeto_id,
        SUM(hdp.horas_parciais) AS horas_trabalhadas
    FROM
        HorasDistribuidaPorProjeto hdp
    GROUP BY
        hdp.mes_referencia, hdp.funcionario_id, hdp.projeto_id
),
TotaisMensaisResumo AS (
    SELECT
        mes_referencia,
        SUM(horas_trabalhadas) AS total_dev_no_mes,
        SUM(horas_trabalhadas) AS total_projeto_no_mes
    FROM
        HorasFinaisPorFuncionarioProjetoMes
    GROUP BY
        mes_referencia
),
ResumosMensaisGerados AS (
    INSERT INTO controle_horas_equipe_resumo (total_dev, total_projeto)
    SELECT
        tmr.total_dev_no_mes,
        tmr.total_projeto_no_mes
    FROM
        TotaisMensaisResumo tmr
    ORDER BY
        tmr.mes_referencia
    RETURNING id, total_dev, total_projeto, CURRENT_DATE AS mes_referencia
)
INSERT INTO controle_horas_equipe (mes, horas, funcionario_id, projeto_id, resumo_id)
SELECT
    hfp.mes_referencia AS mes,
    hfp.horas_trabalhadas AS horas,
    hfp.funcionario_id,
    hfp.projeto_id,
    (SELECT r.id FROM ResumosMensaisGerados r ORDER BY RANDOM() LIMIT 1) AS resumo_id
FROM
    HorasFinaisPorFuncionarioProjetoMes hfp;

-- # DADOS BRUTOS - Insert individual

-- 5. Inserção na Tabela 'controle_horas_equipe_resumo'
-- Adiciona dados de resumo para simular o total de horas para o mês de agosto.
INSERT INTO controle_horas_equipe_resumo (total_dev, total_projeto) VALUES
(154.00, 154.00);

-- 6. Inserção na Tabela 'controle_horas_equipe'
-- Adiciona os dados de horas por funcionário e projeto para os meses de agosto e julho, para criar um conjunto de dados mais robusto.
INSERT INTO controle_horas_equipe (mes, horas, funcionario_id, projeto_id, resumo_id) VALUES
-- Dados de Agosto (baseados nos relatórios)
('2025-08-01', 78.5, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM projeto WHERE nome = 'Ball Anal'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 3.25, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM projeto WHERE nome = 'Reunião'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 0.5, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM projeto WHERE nome = 'SOS Mnt'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 76.33, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM projeto WHERE nome = 'Ball LNO'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 2.75, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM projeto WHERE nome = 'Ball PFS'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 7, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM projeto WHERE nome = 'Bayer Mak'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 66.67, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM projeto WHERE nome = 'Incra'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 21.75, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM projeto WHERE nome = 'Reunião'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 126.58, (SELECT id FROM funcionario WHERE nome = 'Eric Lourenço'), (SELECT id FROM projeto WHERE nome = 'SOS Ed'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 147.15, (SELECT id FROM funcionario WHERE nome = 'Alison Americo'), (SELECT id FROM projeto WHERE nome = 'Ball LNO'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 20.78, (SELECT id FROM funcionario WHERE nome = 'Alison Americo'), (SELECT id FROM projeto WHERE nome = 'Reunião'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 3, (SELECT id FROM funcionario WHERE nome = 'Francisco Bustamante'), (SELECT id FROM projeto WHERE nome = 'Ball Dados'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 143.83, (SELECT id FROM funcionario WHERE nome = 'Francisco Bustamante'), (SELECT id FROM projeto WHERE nome = 'Climatem'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 1.17, (SELECT id FROM funcionario WHERE nome = 'Francisco Bustamante'), (SELECT id FROM projeto WHERE nome = 'Comercial'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 158.92, (SELECT id FROM funcionario WHERE nome = 'Helena Benevenuto'), (SELECT id FROM projeto WHERE nome = 'Ball LNO'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 9.75, (SELECT id FROM funcionario WHERE nome = 'Helena Benevenuto'), (SELECT id FROM projeto WHERE nome = 'Reunião'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 168, (SELECT id FROM funcionario WHERE nome = 'João V Menezes'), (SELECT id FROM projeto WHERE nome = 'Ball Dados'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 139, (SELECT id FROM funcionario WHERE nome = 'Jose Thomazini'), (SELECT id FROM projeto WHERE nome = 'Incra'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 15.08, (SELECT id FROM funcionario WHERE nome = 'Jose Thomazini'), (SELECT id FROM projeto WHERE nome = 'Reunião'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 160, (SELECT id FROM funcionario WHERE nome = 'Lucas Paiva'), (SELECT id FROM projeto WHERE nome = 'SOS Ges'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 5, (SELECT id FROM funcionario WHERE nome = 'Lucas Paiva'), (SELECT id FROM projeto WHERE nome = 'SOS Ed'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 91.42, (SELECT id FROM funcionario WHERE nome = 'Sérgio Casas'), (SELECT id FROM projeto WHERE nome = 'SOS Mnt'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 2.28, (SELECT id FROM funcionario WHERE nome = 'Sérgio Casas'), (SELECT id FROM projeto WHERE nome = 'SOS Ges'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 7.82, (SELECT id FROM funcionario WHERE nome = 'Sérgio Casas'), (SELECT id FROM projeto WHERE nome = 'SOS Ed'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 3.98, (SELECT id FROM funcionario WHERE nome = 'Sérgio Casas'), (SELECT id FROM projeto WHERE nome = 'Ball PFS'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
('2025-08-01', 19.5, (SELECT id FROM funcionario WHERE nome = 'Sérgio Casas'), (SELECT id FROM projeto WHERE nome = 'Reunião'), (SELECT id FROM controle_horas_equipe_resumo LIMIT 1)),
-- Dados de Julho (amostras para popular o banco)
('2025-07-01', 85, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM projeto WHERE nome = 'Ball Anal'), NULL),
('2025-07-01', 70, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM projeto WHERE nome = 'Incra'), NULL),
('2025-07-01', 110, (SELECT id FROM funcionario WHERE nome = 'Eric Lourenço'), (SELECT id FROM projeto WHERE nome = 'SOS Ed'), NULL),
('2025-07-01', 130, (SELECT id FROM funcionario WHERE nome = 'Alison Americo'), (SELECT id FROM projeto WHERE nome = 'Ball LNO'), NULL);

-- 7. Inserção na Tabela 'controle_tempo_equipe'
-- Dados diários para vários funcionários durante todo o mês de agosto de 2025.
-- A soma das horas diárias para cada funcionário no mês de agosto se aproxima do total no relatório.

INSERT INTO controle_tempo_equipe (dia_semana, dia_mes, mes, tempo_gasto, funcionario_id, meta_id) VALUES
-- Dados para Aline Dominique
('Segunda', 4, '2025-08-01', 7.5, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Terça', 5, '2025-08-01', 8.0, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quarta', 6, '2025-08-01', 8.5, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quinta', 7, '2025-08-01', 7.0, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Sexta', 8, '2025-08-01', 7.5, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Segunda', 11, '2025-08-01', 7.8, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Terça', 12, '2025-08-01', 8.2, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quarta', 13, '2025-08-01', 7.9, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quinta', 14, '2025-08-01', 8.0, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Sexta', 15, '2025-08-01', 8.3, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Segunda', 18, '2025-08-01', 7.6, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Terça', 19, '2025-08-01', 7.8, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quarta', 20, '2025-08-01', 8.1, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quinta', 21, '2025-08-01', 8.4, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Sexta', 22, '2025-08-01', 7.7, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Segunda', 25, '2025-08-01', 7.9, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Terça', 26, '2025-08-01', 8.2, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quarta', 27, '2025-08-01', 8.0, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quinta', 28, '2025-08-01', 7.5, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Sexta', 29, '2025-08-01', 8.0, (SELECT id FROM funcionario WHERE nome = 'Aline Dominique'), (SELECT id FROM meta_tempo_controle LIMIT 1)),

-- Dados para Felipe Faria
('Segunda', 4, '2025-08-01', 7.0, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Terça', 5, '2025-08-01', 7.5, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quarta', 6, '2025-08-01', 8.0, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quinta', 7, '2025-08-01', 6.8, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Sexta', 8, '2025-08-01', 7.2, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Segunda', 11, '2025-08-01', 8.1, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Terça', 12, '2025-08-01', 7.4, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quarta', 13, '2025-08-01', 7.9, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quinta', 14, '2025-08-01', 7.5, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Sexta', 15, '2025-08-01', 7.8, (SELECT id FROM funcionario WHERE nome = 'Felipe Faria'), (SELECT id FROM meta_tempo_controle LIMIT 1)),

-- Dados para Eric Lourenço
('Segunda', 4, '2025-08-01', 8.5, (SELECT id FROM funcionario WHERE nome = 'Eric Lourenço'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Terça', 5, '2025-08-01', 8.2, (SELECT id FROM funcionario WHERE nome = 'Eric Lourenço'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quarta', 6, '2025-08-01', 8.0, (SELECT id FROM funcionario WHERE nome = 'Eric Lourenço'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quinta', 7, '2025-08-01', 7.9, (SELECT id FROM funcionario WHERE nome = 'Eric Lourenço'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Sexta', 8, '2025-08-01', 8.3, (SELECT id FROM funcionario WHERE nome = 'Eric Lourenço'), (SELECT id FROM meta_tempo_controle LIMIT 1)),

-- Dados para Lucas Paiva
('Segunda', 4, '2025-08-01', 8.0, (SELECT id FROM funcionario WHERE nome = 'Lucas Paiva'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Terça', 5, '2025-08-01', 8.5, (SELECT id FROM funcionario WHERE nome = 'Lucas Paiva'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quarta', 6, '2025-08-01', 8.2, (SELECT id FROM funcionario WHERE nome = 'Lucas Paiva'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Quinta', 7, '2025-08-01', 8.3, (SELECT id FROM funcionario WHERE nome = 'Lucas Paiva'), (SELECT id FROM meta_tempo_controle LIMIT 1)),
('Sexta', 8, '2025-08-01', 8.0, (SELECT id FROM funcionario WHERE nome = 'Lucas Paiva'), (SELECT id FROM meta_tempo_controle LIMIT 1));

-- 8. Inserção na Tabela 'controle_tempo_resumo'
-- Dados de resumo diário com base nos dados de 'controle_tempo_equipe'.
-- Gerando resumos para diferentes dias e equipes.
INSERT INTO controle_tempo_resumo (realizado_equipe, total_real, total_meta, aproveitamento, controle_tempo_equipe_id) VALUES
-- Resumo para o dia 4 de agosto
(7.5, 7.5, 7.0, 107.14, (SELECT id FROM controle_tempo_equipe WHERE dia_mes = 4 AND funcionario_id = (SELECT id FROM funcionario WHERE nome = 'Aline Dominique') LIMIT 1)),
(7.0, 7.0, 7.0, 100.00, (SELECT id FROM controle_tempo_equipe WHERE dia_mes = 4 AND funcionario_id = (SELECT id FROM funcionario WHERE nome = 'Felipe Faria') LIMIT 1)),
(8.5, 8.5, 7.0, 121.43, (SELECT id FROM controle_tempo_equipe WHERE dia_mes = 4 AND funcionario_id = (SELECT id FROM funcionario WHERE nome = 'Eric Lourenço') LIMIT 1)),
(8.0, 8.0, 7.0, 114.28, (SELECT id FROM controle_tempo_equipe WHERE dia_mes = 4 AND funcionario_id = (SELECT id FROM funcionario WHERE nome = 'Lucas Paiva') LIMIT 1)),
-- Resumo para o dia 5 de agosto
(8.0, 8.0, 7.0, 114.28, (SELECT id FROM controle_tempo_equipe WHERE dia_mes = 5 AND funcionario_id = (SELECT id FROM funcionario WHERE nome = 'Aline Dominique') LIMIT 1)),
(7.5, 7.5, 7.0, 107.14, (SELECT id FROM controle_tempo_equipe WHERE dia_mes = 5 AND funcionario_id = (SELECT id FROM funcionario WHERE nome = 'Felipe Faria') LIMIT 1));
