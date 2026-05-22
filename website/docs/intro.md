---
sidebar_position: 1
---

# Instagram Toolkit

**Instagram Toolkit v2.2** é uma ferramenta de linha de comando completa, segura e moderna para automação, análise e gerenciamento de contas do Instagram.

## Funcionalidades

### 👥 Gerenciamento de Relações
- **Listar Seguidores** — exibe contas que te seguem
- **Listar Seguidos** — exibe contas que você segue
- **Seguir / Deixar de Seguir** — gerencie manualmente
- **Quem não segue de volta** — identifique não recíprocos
- **Seguidores Mútuos** — interseção perfeita
- **Exportar listas** — seguidores e seguidos em JSON

### 🤖 Automações
- **Auto Seguir de Volta** — com intervalo humano aleatório
- **Unfollow em Massa** — seguro, com delays

### 📊 Rastreamento e Auditoria
- **Rastrear Seguidores** — compare com snapshot anterior
- **Modo Watch** — rastreamento automático em loop
- **Estatísticas de Crescimento** — ganho/perda diária média

### 📱 Conteúdo
- **Posts Recentes** — visualize com curtidas/comentários

## Stack

- **Python 3.12+** com `uv` como gerenciador de pacotes
- **instagrapi** — cliente não-oficial da API do Instagram
- **Escrita atômica** — arquivos `.tmp` antes de substituição
- **chmod 600** automático em arquivos de sessão
