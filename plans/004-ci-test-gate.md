# Plano 004: Adicionar workflow de CI que roda a suíte de testes

> **Instruções para o executor**: Siga este plano passo a passo. Rode cada
> comando de verificação e confirme o resultado esperado antes de avançar.
> Se algo na seção "Condições de parada" ocorrer, pare e reporte — não
> improvise. Ao terminar, atualize a linha de status deste plano em
> `plans/README.md`.
>
> **Checagem de deriva (rode primeiro)**: `git diff --stat 5cbb7ce..HEAD -- .github/workflows`
> Se `.github/workflows/` mudou desde que este plano foi escrito, confira se
> já existe um workflow de testes antes de criar um novo; em caso de
> dúvida, trate como condição de parada.

## Status

- **Prioridade**: P2
- **Esforço**: S
- **Risco**: BAIXO
- **Depende de**: nenhum
- **Categoria**: dx
- **Escrito em**: commit `5cbb7ce`, 2026-07-21

## Por que isso importa

O único workflow de GitHub Actions do repositório
(`.github/workflows/deploy.yml`) faz deploy do site Docusaurus e só dispara
quando arquivos em `website/**` mudam. **Não existe nenhum workflow que rode
`pytest` em push ou pull request.** Isso significa que uma mudança que
quebre os 32 testes existentes (ou uma regressão introduzida por qualquer
um dos outros planos deste conjunto) pode ser mergeada sem que ninguém
perceba automaticamente — a suíte só roda se alguém lembrar de rodar
`uv run pytest` manualmente. Este plano fecha essa lacuna com o menor
workflow possível: instalar dependências e rodar a suíde de testes em cada
push/PR que toque código Python.

Escopo deliberadamente contido: **não** inclui lint/typecheck (`ruff`,
`mypy`), porque o repositório não tem configuração nenhuma para essas
ferramentas hoje — introduzir regras de lint do zero é uma decisão de estilo
que cabe ao mantenedor escolher, não algo para decidir dentro de um plano de
correção. Isso fica anotado como follow-up nas notas de manutenção.

## Estado atual

- `.github/workflows/deploy.yml` (arquivo completo, único workflow
  existente):
  ```yaml
  name: Deploy Docusaurus

  on:
    push:
      branches: [main]
      paths:
        - 'website/**'
        - '.github/workflows/deploy.yml'

  permissions:
    contents: write

  jobs:
    deploy:
      runs-on: ubuntu-latest
      defaults:
        run:
          working-directory: website
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-node@v4
          with:
            node-version: 22
            cache: npm
            cache-dependency-path: website/package-lock.json

        - run: npm ci
        - run: npm run build

        - name: Deploy to gh-pages
          uses: peaceiris/actions-gh-pages@v4
          with:
            github_token: ${{ secrets.GITHUB_TOKEN }}
            publish_dir: website/build
  ```
  Note o padrão já estabelecido no repo: `actions/checkout@v4`, um job por
  workflow, `paths:` filtrando o gatilho.
- `pyproject.toml` já define como rodar os testes:
  ```toml
  [dependency-groups]
  dev = [
      "pytest>=9.1.1",
  ]

  [tool.pytest.ini_options]
  pythonpath = ["."]
  testpaths = ["tests"]
  ```
- `.python-version` fixa `3.12`.
- Comando de teste local confirmado neste projeto:
  `uv run pytest -q` → `32 passed in ~17s`.

## Comandos que você vai precisar

| Finalidade | Comando | Esperado no sucesso |
|---|---|---|
| Validar sintaxe YAML | `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/tests.yml'))"` | exit 0, sem exceção |
| Rodar testes localmente (mesma sequência do CI) | `uv sync && uv run pytest -q` | exit 0, todos passam |

## Escopo

**Dentro do escopo** (único arquivo a criar):
- `.github/workflows/tests.yml`

**Fora do escopo** (não mexer, mesmo que pareça relacionado):
- `.github/workflows/deploy.yml` — não toque no workflow de docs existente.
- Qualquer configuração de `ruff`/`mypy`/`black`/pre-commit — não existe
  hoje no repo; adicionar isso é uma decisão de tooling separada, não parte
  deste plano (ver notas de manutenção).
- `pyproject.toml` — não precisa mudar; os comandos de teste já funcionam
  como estão.

## Fluxo git

- Branch: `advisor/004-ci-test-gate`
- Um commit único; mensagem sugerida:
  `ci: run pytest on push and pull request`
- Não faça push nem abra PR a menos que o operador peça.

## Passos

### Passo 1: Criar o workflow

Crie `.github/workflows/tests.yml`:

```yaml
name: Tests

on:
  push:
    branches: [main]
    paths-ignore:
      - 'website/**'
      - 'docs/**'
  pull_request:
    paths-ignore:
      - 'website/**'
      - 'docs/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install uv
        run: pip install uv
      - name: Sync dependencies
        run: uv sync
      - name: Run tests
        run: uv run pytest -q
```

**Verificar**: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/tests.yml'))"`
→ não levanta exceção (YAML válido).

### Passo 2: Confirmar que a sequência de comandos funciona localmente

Rode, na raiz do projeto, exatamente a sequência que o workflow executa:
```
uv sync
uv run pytest -q
```

**Verificar**: ambos saem com exit code 0; a segunda linha mostra
`NN passed` sem falhas.

### Passo 3 (informativo, não bloqueante): confirmar no GitHub após o push

Este passo só pode ser confirmado depois que o branch for de fato enviado
ao GitHub (fora do escopo deste plano, que não deve fazer push sem
autorização). Anote no relatório final: "workflow criado e validado
localmente; confirmação da execução verde no Actions depende de push, que
não foi feito por este plano."

## Plano de testes

- Não há testes de aplicação para escrever — a "cobertura" aqui é o próprio
  workflow de CI executando a suíte já existente.
- Verificação: validação de sintaxe YAML (passo 1) + execução local da
  mesma sequência de comandos do workflow (passo 2).

## Critérios de conclusão

Todos devem valer:

- [ ] `.github/workflows/tests.yml` existe e é YAML válido
- [ ] O workflow dispara em `push` (branch `main`) e `pull_request`,
      ignorando mudanças só em `website/**`/`docs/**`
- [ ] `uv sync && uv run pytest -q` rodado localmente sai com exit 0
- [ ] Nenhum arquivo fora de `.github/workflows/tests.yml` foi modificado
      (`git status`)
- [ ] Linha de status deste plano atualizada em `plans/README.md`

## Condições de parada

Pare e reporte (não improvise) se:

- Já existir um workflow de testes em `.github/workflows/` que este plano
  não conhecia (ver checagem de deriva no topo).
- `uv sync` ou `uv run pytest -q` falharem localmente antes mesmo de tocar
  no workflow — isso indica um problema no ambiente, não relacionado a
  este plano; não tente "consertar" a suíte de testes aqui.

## Notas de manutenção

- Lint/typecheck (`ruff`, `mypy`) ficaram fora deste plano de propósito —
  não há configuração existente no repo para essas ferramentas, e escolher
  regras do zero é uma decisão de estilo que precisa de aprovação do
  mantenedor. Se for adotado depois, o lugar natural é adicionar um segundo
  job (ou steps adicionais) neste mesmo `tests.yml`.
- O Plano 001 (atualização do `pillow`) menciona `pip-audit` como uma
  verificação de segurança recorrente — se isso for adotado, também caberia
  como um step adicional aqui, não como parte deste plano.
- Se o projeto ganhar múltiplas versões de Python suportadas no futuro,
  troque `python-version: '3.12'` por uma matrix.
