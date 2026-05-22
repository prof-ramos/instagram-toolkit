---
sidebar_position: 2
---

# Autenticação

O toolkit suporta três formas de autenticação, em ordem de preferência:

## 1. Session ID (Recomendado)

Mais rápido e evita bloqueios temporários.

```bash
export INSTAGRAM_SESSION_ID="seu_session_id_aqui"
uv run main.py
```

### Como obter o Session ID
1. Acesse instagram.com no navegador
2. Abra o DevTools (F12) → Application → Cookies
3. Copie o valor do cookie `sessionid`

## 2. Cookies

Salve os cookies em `cookies.json` no formato de exportação do navegador.

## 3. Usuário e Senha

```env
INSTAGRAM_USERNAME=seu_usuario
INSTAGRAM_PASSWORD=sua_senha
```

## Arquivo .env

Copie o template e edite:

```bash
cp .env.example .env
# Edite com suas credenciais
```
