SELECT
    --p.id AS projeto_id,
    p.nome AS projeto_nome,
    --f.id AS funcionario_id,
    f.nome AS funcionario_nome,
    -- SUM(che.horas) AS total_horas,
    f.valor_hora * SUM(che.horas) AS custo_funcionario
FROM public.projeto p
INNER JOIN public.controle_horas_equipe che ON p.id = che.projeto_id
INNER JOIN public.funcionario f ON f.id = che.funcionario_id
WHERE p.nome = 'SOS'
GROUP BY p.id, p.nome, f.id, f.nome, f.valor_hora;
