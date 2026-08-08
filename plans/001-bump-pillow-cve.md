# Plano 001: Atualizar `pillow` transitivo para eliminar 20 CVEs conhecidos

> **Instruções para o executor**: Siga este plano passo a passo. Rode cada
> comando de verificação e confirme o resultado esperado antes de avançar.
> Se algo na seção "Condições de parada" ocorrer, pare e reporte — não
> improvise. Ao terminar, atualize a linha de status deste plano em
> `plans/README.md`.
>
> **Checagem de deriva (rode primeiro)**: `git diff --stat 5cbb7ce..HEAD -- uv.lock pyproject.toml`
> Se `uv.lock` mudou desde que este plano foi escrito, confira a versão atual
> do pillow (`grep -A2 'name = "pillow"' uv.lock`) antes de prosseguir; se já
> estiver em `12.3.0` ou superior, este plano já está resolvido — pare e
> atualize o status para DONE com uma nota.

## Status

- **Prioridade**: P1
- **Esforço**: S
- **Risco**: BAIXO
- **Depende de**: nenhum
- **Categoria**: security
- **Escrito em**: commit `5cbb7ce`, 2026-07-21

## Por que isso importa

`pillow` não é dependência direta do projeto (não aparece em `pyproject.toml`),
mas entra transitivamente via `instagrapi` e está travado em `12.2.0` no
`uv.lock`. Rodando `pip-audit` sobre o lockfile exportado, essa versão tem
**20 vulnerabilidades conhecidas** (múltiplos PYSEC-2026-* e CVE-2026-54058,
CVE-2026-59197/59198/59200/59204), todas corrigidas a partir da `12.3.0`.
Como é uma lib de processamento de imagem usada indiretamente pelo
`instagrapi` para lidar com mídia do Instagram, o risco é real ainda que
indireto. A correção é uma atualização de lockfile, sem mudança de código.

## Estado atual

- `pyproject.toml` — dependências diretas: `instagrapi>=2.7.10`,
  `requests>=2.31.0`, `phonenumbers>=8.13.0`, `pycountry>=22.3.5`,
  `python-dotenv>=1.0.0`. Nenhuma menção a `pillow`.
- `uv.lock:191-193`:
  ```
  [[package]]
  name = "pillow"
  version = "12.2.0"
  source = { registry = "https://pypi.org/simple" }
  ```
- `uv.lock:161` mostra que `pillow` está listado nas `dependencies` de outro
  pacote do lockfile (dependência transitiva, não direta).

## Comandos que você vai precisar

| Finalidade | Comando | Esperado no sucesso |
|---|---|---|
| Atualizar apenas pillow no lock | `uv lock --upgrade-package pillow` | exit 0, `uv.lock` modificado |
| Sincronizar venv | `uv sync` | exit 0 |
| Rodar testes | `uv run pytest -q` | todos passam (32 no momento deste plano) |
| Confirmar CVEs resolvidos | `uv export --no-hashes --format requirements-txt -o /tmp/req.txt && uvx pip-audit -r /tmp/req.txt` | `pillow` não aparece mais na lista de vulnerabilidades (ou versão >= 12.3.0) |

## Escopo

**Dentro do escopo** (únicos arquivos que devem mudar):
- `uv.lock` (gerado automaticamente pelo comando `uv lock --upgrade-package pillow`)

**Fora do escopo** (não mexer, mesmo que pareça relacionado):
- `pyproject.toml` — não adicione um pin direto de `pillow` a menos que o
  passo 1 falhe (ver condições de parada). O objetivo é resolver via
  atualização normal do lockfile, mantendo `pillow` transitivo.
- Qualquer outro pacote do lockfile — não rode `uv lock --upgrade` (sem
  `--upgrade-package`), que atualizaria tudo e sairia do escopo deste plano.

## Fluxo git

- Branch: `advisor/001-bump-pillow-cve`
- Um commit único; siga o estilo do repositório (mensagens curtas,
  imperativas, ex.: `perf: harden relation cache, auth cookies, and offline
  tests` do histórico). Sugestão: `chore: bump pillow to patch known CVEs`
- Não faça push nem abra PR a menos que o operador peça.

## Passos

### Passo 1: Atualizar o lock do pillow

Rode:
```
uv lock --upgrade-package pillow
```

**Verificar**: `grep -A2 'name = "pillow"' uv.lock` → versão exibida deve ser
`>= 12.3.0`.

Se o comando não conseguir resolver uma versão `>= 12.3.0` compatível com as
demais restrições do lockfile (ex.: `instagrapi` fixando um teto de versão
para `pillow`), isso é uma condição de parada — ver abaixo.

### Passo 2: Sincronizar o ambiente

```
uv sync
```

**Verificar**: exit code 0, sem erros de resolução.

### Passo 3: Rodar a suíte de testes

```
uv run pytest -q
```

**Verificar**: saída `NN passed` sem falhas (o baseline no momento deste
plano é `32 passed`; se outros planos já rodaram antes deste, o número pode
ser maior — o que importa é zero falhas).

### Passo 4: Confirmar que as vulnerabilidades sumiram

```
uv export --no-hashes --format requirements-txt -o /tmp/req.txt
uvx pip-audit -r /tmp/req.txt
```

**Verificar**: `pillow` não aparece mais na tabela de vulnerabilidades
encontradas (ou aparece com uma versão `>= 12.3.0` e zero advisories listados
para ela).

## Plano de testes

- Não é necessário escrever testes novos — esta é uma atualização de
  dependência. A suíte existente (`uv run pytest -q`, 32 testes) é a
  verificação de regressão.

## Critérios de conclusão

Todos devem valer:

- [ ] `uv.lock` mostra `pillow >= 12.3.0`
- [ ] `uv run pytest -q` sai com exit 0, todos os testes passam
- [ ] `uvx pip-audit -r <lockfile exportado>` não lista mais CVEs para `pillow`
- [ ] Nenhum arquivo fora de `uv.lock` foi modificado (`git status`)
- [ ] Linha de status deste plano atualizada em `plans/README.md`

## Condições de parada

Pare e reporte (não improvise) se:

- `uv lock --upgrade-package pillow` não conseguir resolver uma versão
  `>= 12.3.0` (provável teto de versão em alguma dependência transitiva) —
  reporte qual pacote está travando a resolução; não adicione overrides ou
  pins manuais sem aprovação.
- A suíte de testes falhar após a atualização e a falha parecer relacionada
  ao pillow (ex.: erro de import, mudança de API) — não é esperado, já que
  este projeto não importa `pillow` diretamente, mas confirme antes de
  assumir que é incidental.
- `uv.lock` já estiver em `pillow >= 12.3.0` antes mesmo do passo 1 (ver
  checagem de deriva no topo) — trate como já resolvido.

## Notas de manutenção

- `pillow` é transitivo via `instagrapi`; uma futura atualização do
  `instagrapi` pode reintroduzir uma versão antiga. Vale considerar um
  `pip-audit` periódico — o Plano 004 (gate de CI) é o lugar natural para
  isso, se for adotado depois.
- Nenhum código do projeto importa `pillow` diretamente, então o raio de
  impacto de uma regressão aqui é essencialmente zero fora do que o
  `instagrapi` já testa internamente.
