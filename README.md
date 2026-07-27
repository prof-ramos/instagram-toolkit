# Instagram Toolkit

[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/gerenciado%20com-uv-DE5FE9?logo=astral&logoColor=white)](https://docs.astral.sh/uv/)
[![Deploy Docusaurus](https://github.com/prof-ramos/instagram-toolkit/actions/workflows/deploy.yml/badge.svg)](https://github.com/prof-ramos/instagram-toolkit/actions/workflows/deploy.yml)

CLI em Python para consultar relações, executar ações e acompanhar mudanças de seguidores em uma conta do Instagram. A aplicação usa a API não oficial fornecida pelo `instagrapi`.

> A interface atual se identifica como **v3.0** e oferece **15 ações**. A versão de distribuição registrada em `pyproject.toml` permanece `0.1.0`.

## Recursos

O menu interativo oferece:

1. Listar meus seguidores
2. Listar quem eu sigo
3. Seguir usuário por `@username` ou ID
4. Deixar de seguir por `@username` ou ID
5. Ver informações de um usuário
6. Identificar quem não segue de volta
7. Exportar seguidores em JSON
8. Exportar seguidos em JSON
9. Rastrear ganhos e perdas de seguidores
10. Executar o rastreamento periódico em modo Watch
11. Seguir de volta em lote
12. Deixar de seguir não seguidores em lote
13. Exibir estatísticas de crescimento
14. Exibir posts recentes de um usuário
15. Listar seguidores mútuos

Também estão disponíveis:

- cache em memória com TTL, distinção entre consultas parciais e completas e invalidação após alterações;
- busca completa para análises, exportações e rastreamento;
- atrasos entre ações em lote e backoff em consultas do rastreador;
- histórico local com backups rotativos e escritas JSON atômicas.

## Instalação

### Pré-requisitos

- Python 3.12 ou superior;
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/prof-ramos/instagram-toolkit.git
cd instagram-toolkit
uv sync
```

## Configuração e autenticação

Copie o arquivo de exemplo e preencha ao menos uma forma de autenticação:

```bash
cp .env.example .env
```

Consulte o template [`.env.example`](.env.example). O toolkit tenta autenticar, nesta ordem, por:

1. `INSTAGRAM_SESSION_ID` definido no `.env`;
2. `cookies.json` no diretório do projeto;
3. sessão previamente salva em `instagrapi.json`;
4. `INSTAGRAM_USERNAME` e `INSTAGRAM_PASSWORD` definidos no `.env`.

Não publique `.env`, `cookies.json`, `instagrapi.json`, históricos ou exportações. Esses caminhos já estão previstos no `.gitignore`, mas a proteção final das credenciais continua sendo responsabilidade do usuário.

## Uso

### Menu interativo

```bash
uv run main.py
```

### Rastreamento único

```bash
uv run main.py --track
```

### Rastreamento periódico

O valor de `--watch` é o intervalo em minutos:

```bash
uv run main.py --watch 45
```

### Cache

```bash
uv run main.py --no-cache
uv run main.py --cache-ttl 600
```

Use `uv run main.py --help` para consultar todos os argumentos disponíveis.

## Segurança e dados locais

- `.env`, arquivos de sessão e dados gerados são ignorados pelo Git.
- Arquivos JSON gravados pelo toolkit usam um arquivo temporário e substituição atômica.
- Sessões salvas, históricos, backups e exportações escritos pelo toolkit recebem permissão `0600` em sistemas que suportam essa operação.
- O histórico mantém até 10 snapshots de dados, acompanhados de metadados locais.
- Operações em lote pedem confirmação no menu e aplicam intervalos entre requisições.

Essas medidas reduzem riscos locais, mas não tornam a automação isenta de bloqueios, desafios de login ou restrições da plataforma.

## Testes

A suíte é offline e cobre cache, política de consultas completas, ações em lote e rotação de backups:

```bash
uv run pytest
```

Não há workflow de CI de testes configurado neste repositório; o badge no topo representa somente o workflow de publicação da documentação.

## Documentação

- Fontes da documentação: [`website/docs/`](website/docs/)
- Workflow de publicação: [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)

Quando há alterações em `website/**` ou no próprio workflow na branch `main`, o workflow **Deploy Docusaurus** gera o site e envia `website/build` para a branch `gh-pages`.

## Uso responsável

Este projeto utiliza endpoints não oficiais do Instagram. Use-o somente em contas e dados para os quais você tenha autorização, respeite os Termos de Uso da plataforma, a privacidade de terceiros e a legislação aplicável. Automação excessiva pode causar limitação temporária, desafios de autenticação ou suspensão da conta. Você é responsável pelas ações executadas e pelos dados coletados ou exportados.

Este repositório não contém arquivo de licença. Na ausência de uma licença explícita, não presuma permissão para copiar, modificar ou redistribuir o código.
