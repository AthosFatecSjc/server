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
        ('Mnt'),
        ('Ges'),
        ('Ed'),
        ('Ball'),
        ('LNO'),
        ('PFS'),
        ('Dados'),
        ('Mak'),
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
-- Inserimos o gerente primeiro e reaproveitamos o id dele para os demais
WITH daniel AS (
    INSERT INTO funcionario (nome, time, cargo_id, gerente_id, valor_hora, data_criacao)
    VALUES (
        'Daniel Maturana', 'Squad A',
        (SELECT id FROM cargo WHERE sigla = 'Gerente de Projetos'),
        NULL,
        120.00,
        CURRENT_DATE
    )
    RETURNING id
)
INSERT INTO funcionario (nome, time, cargo_id, gerente_id, valor_hora, data_criacao)
SELECT v.nome, v.time, c.id, d.id, v.valor_hora, CURRENT_DATE
FROM (VALUES
    ('Aline Dominique', 'Squad A', 'Membro de Equipe', 70.00),
    ('Felipe Faria', 'Squad A', 'Membro de Equipe', 70.00),
    ('Eric Lourenço', 'Squad A', 'Lider de Equipe', 90.00),
    ('Alison Americo', 'Squad B', 'Membro de Equipe', 70.00),
    ('Francisco Bustamante', 'Squad B', 'Membro de Equipe', 70.00),
    ('Helena Benevenuto', 'Squad B', 'Membro de Equipe', 70.00),
    ('João V Menezes', 'Squad B', 'Lider de Equipe', 90.00),
    ('Jose Thomazini', 'Squad C', 'Membro de Equipe', 70.00),
    ('Lucas Paiva', 'Squad C', 'Lider de Equipe', 90.00),
    ('Sérgio Casas', 'Squad C', 'Membro de Equipe', 70.00)
) AS v(nome, time, cargo_sig, valor_hora)
JOIN cargo c ON c.sigla = v.cargo_sig
CROSS JOIN daniel d;

-- 5. Inserção na Tabela 'controle_tempo_equipe'
INSERT INTO CONTROLE_TEMPO_EQUIPE (
    DIA_SEMANA,
    DIA_MES,
    MES,
    FUNCIONARIO_ID,
    TEMPO_GASTO,
    META_ID
)
WITH metas AS (
    SELECT
        (SELECT id FROM meta_tempo_controle WHERE objetivo_estagiario = '6') AS estagiario_id,
        (SELECT id FROM meta_tempo_controle WHERE objetivo_clt = '7') AS clt_id
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
        WHEN F.id % 2 = 0 THEN metas.estagiario_id
        ELSE metas.clt_id
    END AS META_ID
FROM
    GENERATE_SERIES('2025-01-01'::DATE, '2025-12-31'::DATE, '1 day') D
    CROSS JOIN funcionario F
    CROSS JOIN metas
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
        p.id AS projeto_id,
        ROUND((thfm.total_horas * (RANDOM() * 0.7 + 0.3))::numeric, 2) AS horas_parciais
    FROM
        TotalHorasFuncionarioMes thfm
        JOIN LATERAL (
            SELECT id FROM projeto
            ORDER BY RANDOM()
            LIMIT GREATEST(1, (1 + (RANDOM() * 7)::INT))
        ) p ON TRUE
),
HorasFinaisPorFuncionarioProjetoMes AS (
    SELECT
        hdp.mes_referencia,
        hdp.funcionario_id,
        hdp.projeto_id,
        SUM(hdp.horas_parciais) AS horas_trabalhadas
    FROM
        HorasDistribuidaPorProjeto hdp
    WHERE
        hdp.projeto_id IS NOT NULL
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
    (SELECT r.id FROM ResumosMensaisGerados r ORDER BY RANDOM() LIMIT 1)
FROM
    HorasFinaisPorFuncionarioProjetoMes hfp
WHERE
    hfp.projeto_id IS NOT NULL;
