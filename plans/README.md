# Planos de Implementação

Gerados pela skill `/improve` em 2026-07-21, a partir do commit `5cbb7ce`.
Nenhum destes planos depende de outro — todos podem ser executados em
paralelo, em qualquer ordem. Cada executor: leia o plano inteiro antes de
começar, respeite as "Condições de parada", e atualize sua linha ao
terminar.

## Ordem de execução e status

| Plano | Título | Prioridade | Esforço | Depende de | Status |
|-------|--------|------------|---------|------------|--------|
| 001   | Atualizar `pillow` transitivo (20 CVEs conhecidos) | P1 | S | — | BLOCKED (instagrapi==2.7.10 pin exato de Pillow==12.2.0; precisa avaliar upgrade do instagrapi) |
| 002   | Cobertura de testes para `auth.py` | P2 | M | — | DONE (branch `advisor/002-auth-test-coverage`, commit `8db8cc0`) |
| 003   | Corrigir parsing frágil de `Config.cache_ttl` | P1 | S | — | DONE (branch `advisor/003-fix-cache-ttl-config`, commits `2130d8e` + `8554fa2` — 2º commit corrige achados do code-review: unifica com resolve_fetch_limit e rejeita inf/nan) |
| 004   | Workflow de CI rodando a suíte de testes | P2 | S | — | DONE (branch `advisor/004-ci-test-gate`, commits `6817ade` + `c4061ed` — 2º commit troca para astral-sh/setup-uv com cache e python-version-file) |
| 005   | Spike: decidir destino de `toutatis_integration.py` | P3 | S | — | DONE (decisão: conectar ao menu; ver plano 006) |
| 006   | Reconectar `toutatis_integration.py` como opção 16 do menu | P2 | M | — | DONE (branch `advisor/006-wire-toutatis-menu`, commit `f67ce92`) |

Valores de status: TODO | IN PROGRESS | DONE | BLOCKED (com motivo em uma
linha) | REJECTED (com justificativa em uma linha).

## Notas de dependência

Nenhuma dependência real entre os planos — todos tocam arquivos
completamente distintos:

- 001 → só `uv.lock`
- 002 → só `tests/test_auth.py` (novo)
- 003 → `instagram_toolkit/config.py` + `tests/test_config.py` (novo)
- 004 → só `.github/workflows/tests.yml` (novo)
- 005 → investigação + (opcionalmente) `README.md`

Se todos rodarem em paralelo em branches separadas, o merge final não deve
gerar conflito, já que não há sobreposição de arquivos.

## Achados considerados e rejeitados

- Nenhum. Todos os achados do audit (segurança, testes, bug, DX, direção)
  foram selecionados para virar plano nesta rodada.

## Achados fora do escopo desta rodada

- `website/` (site Docusaurus) e `docs/` não foram auditados nesta
  passagem — fora do escopo declarado no início do audit.
