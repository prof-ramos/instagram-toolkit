# 🚀 Instagram Toolkit v2.2

Uma ferramenta de linha de comando (CLI) completa, robusta e segura para automação, análise e gerenciamento de contas do Instagram, escrita em Python 3.12+ e gerenciada com o moderno ecossistema `uv`.

---

## 🌟 Funcionalidades

O script unificado oferece um menu com **16 opções organizadas** e prontas para uso interativo:

### 👥 Gerenciamento de Relações
1. **Listar Seguidores**: Exibe a lista de contas que seguem você com limite configurável.
2. **Listar Seguidos**: Exibe as contas que você segue.
3. **Seguir Usuário**: Segue uma conta a partir do `@username` ou do ID numérico.
4. **Deixar de Seguir**: Deixa de seguir uma conta.
5. **Informações do Usuário**: Exibe detalhes da conta (seguidores, postagens, biografia, site, status privado/verificado).
6. **Quem não segue de volta**: Identifica de forma rápida e precisa quem você segue mas não te segue de volta.
7. **Exportar Seguidores**: Gera um arquivo JSON contendo a lista completa de seus seguidores.
8. **Exportar Seguidos (JSON)**: Exporta a lista de contas que você segue em formato JSON estruturado.

### 🤖 Automações Avançadas
9. **Auto Seguir de Volta**: Segue de volta de forma automatizada (com intervalo aleatório humano) contas que te seguem mas que você ainda não segue.
10. **Deixar de seguir em massa**: Remove de forma automatizada e segura seguimentos não recíprocos.
11. **Exibir posts recentes**: Exibe as últimas postagens de qualquer conta com número de curtidas e comentários.
12. **Seguidores Mútuos**: Filtra e lista a interseção perfeita de contatos mútuos.

### 📊 Rastreamento & Auditoria de Histórico
13. **Rastrear seguidores agora**: Compara o estado atual dos seus seguidores com o último snapshot salvo localmente, apontando quem te deu *unfollow* ou novos seguidores.
14. **Modo Watch**: Rastreamento automático e periódico em loop com tempo de intervalo configurável (ex: a cada 30 minutos).
15. **Estatísticas de Crescimento**: Analisa os logs históricos locais e gera um relatório detalhado de ganho e perda diária média de seguidores ao longo do tempo.

---

## 🔒 Segurança e Robustez

* **Concorrência Otimizada**: Chamadas pesadas de API (como buscar seguidores e seguidos simultaneamente) rodam em paralelo via `ThreadPoolExecutor`, cortando o tempo de execução pela metade.
* **Escrita Atômica**: Gravações em arquivos locais geram arquivos intermediários `.tmp` antes de serem substituídos atomicamente pelo sistema operacional, evitando a corrupção de dados históricos.
* **Proteção de Credenciais**: Arquivos locais sensíveis de sessão (`instagrapi.json` e `cookies.json`) são salvos com permissões Unix restritas (`chmod 600`), garantindo que apenas o usuário proprietário possa lê-los no sistema local.

---

## 🛠️ Instalação e Configuração

Esta ferramenta utiliza o **`uv`** como gerenciador rápido de pacotes e ambientes Python.

### 1. Pré-requisitos
Certifique-se de ter o `uv` instalado. Se não possuir, instale facilmente:
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Configurar Variáveis de Ambiente
Copie o arquivo de exemplo de variáveis de ambiente [.env.example](file:///Users/gabrielramos/instagram-toolkit/.env.example) para criar o seu arquivo local de ambiente:
```bash
cp .env.example .env
```

Edite o arquivo `.env` e defina suas credenciais:
```env
INSTAGRAM_USERNAME=seu_usuario
INSTAGRAM_PASSWORD=sua_senha

# Opcional (altamente recomendado para evitar bloqueios temporários de login):
INSTAGRAM_SESSION_ID=seu_session_id_aqui
```

---

## 🚀 Como Executar

### Modo Interativo (Menu Principal)
Inicie o menu interativo com todas as 16 opções executando:
```bash
uv run main.py
```

### Argumentos de Linha de Comando (Modo Direto)
Execute tarefas específicas sem passar pelo menu principal:

* **Modo Watch** (executa o rastreamento em loop a cada 45 minutos):
  ```bash
  uv run main.py --watch 45
  ```

* **Rastreamento Único** (executa uma checagem rápida no histórico e finaliza):
  ```bash
  uv run main.py --track
  ```
