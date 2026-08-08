# Plano 002: Cobertura de testes para `instagram_toolkit/auth.py`

> **Instruções para o executor**: Siga este plano passo a passo. Rode cada
> comando de verificação e confirme o resultado esperado antes de avançar.
> Se algo na seção "Condições de parada" ocorrer, pare e reporte — não
> improvise. Ao terminar, atualize a linha de status deste plano em
> `plans/README.md`.
>
> **Checagem de deriva (rode primeiro)**: `git diff --stat 5cbb7ce..HEAD -- instagram_toolkit/auth.py instagram_toolkit/config.py`
> Se `auth.py` mudou desde que este plano foi escrito, compare os trechos da
> seção "Estado atual" com o código real antes de prosseguir; em caso de
> divergência, trate como condição de parada.

## Status

- **Prioridade**: P2
- **Esforço**: M
- **Risco**: BAIXO (mudança é só de testes, não toca código de produção)
- **Depende de**: nenhum
- **Categoria**: tests
- **Escrito em**: commit `5cbb7ce`, 2026-07-21

## Por que isso importa

`instagram_toolkit/auth.py` (166 linhas) é o arquivo com mais churn no
histórico do repositório (5 commits, empatado com `relations.py`,
`cli/handlers.py` e `actions.py`) e concentra toda a lógica de autenticação:
login por session ID, por cookies exportados do navegador, por sessão salva
em disco, e por usuário/senha — nessa ordem de fallback. Não existe nenhum
teste para esse arquivo hoje (`tests/` não tem `test_auth.py`). Uma mudança
futura em qualquer um desses quatro caminhos de autenticação pode quebrar
silenciosamente sem que a suíte perceba, e é exatamente o tipo de código
crítico (login é o primeiro passo de tudo que o toolkit faz) que a categoria
"cobertura de testes" do audit prioriza.

## Estado atual

- `instagram_toolkit/auth.py:20-63` — `AuthService.authenticate()`: tenta,
  nessa ordem, `session_id` → `cookies_file` → `settings_file` →
  `username`/`password`; se nenhum estiver configurado, levanta
  `AuthenticationError("Nenhuma forma de autenticação disponível. ...")`.
- `instagram_toolkit/auth.py:65-77` — `_try_session_id`: chama
  `client.login_by_sessionid(session_id)`; captura
  `(ClientLoginRequired, ChallengeRequired, OSError)` e `Exception` genérica,
  retornando `False` em ambos (não propaga).
- `instagram_toolkit/auth.py:79-92` — `_load_cookies_dict`: lê o JSON de
  `cookies_file` e aceita dois formatos — lista de `{"name":..., "value":...}`
  (export de navegador) ou dict simples `{"chave": "valor"}` — via
  `match/case`.
- `instagram_toolkit/auth.py:94-132` — `_try_cookies`: usa
  `_load_cookies_dict()`, procura `sessionid` ou `session_id` nas chaves,
  faz `unquote()` (cookies de navegador costumam vir com `:` como `%3A`),
  chama `client.login_by_sessionid(session_id)`, depois aplica os cookies
  restantes em `client.private.cookies.set(...)` (best-effort, exceções
  engolidas silenciosamente).
- `instagram_toolkit/auth.py:134-146` — `_try_saved_session`: chama
  `client.load_settings(str(settings_file))` e depois
  `client.get_timeline_feed()` (para validar que a sessão ainda é válida).
- `instagram_toolkit/auth.py:148-166` — `_try_credentials`: chama
  `client.login(username, password)`; em sucesso, grava a sessão via
  `self.storage.secure_write_json(settings_file, client.get_settings())`.
  Em `ChallengeRequired`/`ClientLoginRequired`/`OSError`/`Exception` genérica,
  levanta `AuthenticationError` com mensagens específicas por tipo.
- `instagram_toolkit/config.py:37-49` — `Config` é uma `@dataclass` simples;
  `session_id`, `username`, `password` vêm de `os.getenv(...)`;
  `settings_file`/`cookies_file` são `Path` com defaults
  (`instagrapi.json`, `cookies.json`).
- `instagram_toolkit/config.py:56-57` — `AuthenticationError` herda de
  `InstagramToolkitError` (definida no mesmo arquivo).

## Convenções do repositório a seguir

- Testes offline, sem rede real: veja `tests/test_relations_complete_fetch.py`
  (usa `unittest.mock.MagicMock` para simular o `Client` do `instagrapi`) e
  `tests/test_actions.py` (usa `unittest.mock.Mock`, monta um "service"
  helper local `_service(...)`).
- Para `Config` com arquivos em disco, siga o padrão de
  `tests/test_storage_rotate.py:13-18` — um helper `_storage(tmp_path)` que
  constrói `Config(history_file=tmp_path / ..., backup_dir=tmp_path / ...)`.
  Faça o mesmo para `cookies_file`/`settings_file` neste plano.
- Nomes de teste descritivos em inglês, estilo
  `test_<comportamento>_<condição>` (ex.:
  `test_rejected_batch_action_is_failure_without_cache_invalidation` em
  `tests/test_actions.py:22`).
- `from __future__ import annotations` no topo, como todos os outros
  arquivos de teste.

## Comandos que você vai precisar

| Finalidade | Comando | Esperado no sucesso |
|---|---|---|
| Rodar só o arquivo novo | `uv run pytest -q tests/test_auth.py` | todos passam |
| Rodar suíte completa | `uv run pytest -q` | todos passam (baseline 32 + novos) |

## Escopo

**Dentro do escopo** (únicos arquivos a modificar):
- `tests/test_auth.py` (criar)

**Fora do escopo** (não mexer, mesmo que pareça relacionado):
- `instagram_toolkit/auth.py` — este plano é só de testes; se você achar um
  bug real ao escrever os testes, **não corrija inline** — pare e reporte
  como um achado separado (ver condições de parada).
- `instagram_toolkit/config.py`, `instagram_toolkit/storage.py` — use-os
  como estão, só via `Mock`/`Config(...)` real com `tmp_path`.

## Fluxo git

- Branch: `advisor/002-auth-test-coverage`
- Um commit único; mensagem sugerida:
  `test: add coverage for AuthService fallback chain`
- Não faça push nem abra PR a menos que o operador peça.

## Passos

### Passo 1: Criar o arquivo e os helpers básicos

Crie `tests/test_auth.py` com:
```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from instagrapi.exceptions import ChallengeRequired, ClientLoginRequired

from instagram_toolkit.auth import AuthService
from instagram_toolkit.config import AuthenticationError, Config
from instagram_toolkit.storage import HistoryStorage


def _config(tmp_path: Path, **overrides) -> Config:
    base = dict(
        username=None,
        password=None,
        session_id=None,
        settings_file=tmp_path / "instagrapi.json",
        cookies_file=tmp_path / "cookies.json",
    )
    base.update(overrides)
    return Config(**base)


def _service(tmp_path: Path, **overrides) -> AuthService:
    config = _config(tmp_path, **overrides)
    storage = HistoryStorage(config)
    return AuthService(config, storage)
```

**Verificar**: `uv run pytest -q tests/test_auth.py --collect-only` → coleta
sem erro (0 testes ainda, mas sem `ImportError`/`CollectError`).

### Passo 2: Caminho de sucesso via `session_id`

Adicione:
```python
def test_authenticate_succeeds_via_session_id(tmp_path: Path) -> None:
    svc = _service(tmp_path, session_id="abc%3A123")
    client = MagicMock()

    assert svc.authenticate(client) is True
    client.login_by_sessionid.assert_called_once_with("abc:123")
```

Repare: `session_id` é passado por `unquote()` antes de ir pro client
(`instagram_toolkit/auth.py:68`) — por isso `abc%3A123` vira `abc:123`.

**Verificar**: `uv run pytest -q tests/test_auth.py::test_authenticate_succeeds_via_session_id`
→ passa.

### Passo 3: Fallback quando `session_id` falha

```python
def test_session_id_failure_falls_through_to_no_auth_error(tmp_path: Path) -> None:
    svc = _service(tmp_path, session_id="bad")
    client = MagicMock()
    client.login_by_sessionid.side_effect = ClientLoginRequired("nope")

    with pytest.raises(AuthenticationError, match="Nenhuma forma de autenticação"):
        svc.authenticate(client)
```

Isso cobre: `_try_session_id` retorna `False` em `ClientLoginRequired`
(`auth.py:72-74`), não há `cookies_file`/`settings_file`/credenciais
configurados, então cai na mensagem final de `auth.py:55-58`.

**Verificar**: `uv run pytest -q tests/test_auth.py -k session_id` → 2 passam.

### Passo 4: Cookies — formato lista e formato dict

```python
def test_load_cookies_dict_accepts_list_format(tmp_path: Path) -> None:
    cookies_file = tmp_path / "cookies.json"
    cookies_file.write_text(
        '[{"name": "sessionid", "value": "sid%3A1"}, {"name": "csrftoken", "value": "x"}]'
    )
    svc = _service(tmp_path, cookies_file=cookies_file)

    assert svc._load_cookies_dict() == {"sessionid": "sid%3A1", "csrftoken": "x"}


def test_load_cookies_dict_accepts_plain_dict_format(tmp_path: Path) -> None:
    cookies_file = tmp_path / "cookies.json"
    cookies_file.write_text('{"sessionid": "sid123"}')
    svc = _service(tmp_path, cookies_file=cookies_file)

    assert svc._load_cookies_dict() == {"sessionid": "sid123"}


def test_try_cookies_missing_sessionid_key_returns_false(tmp_path: Path) -> None:
    cookies_file = tmp_path / "cookies.json"
    cookies_file.write_text('{"csrftoken": "x"}')
    svc = _service(tmp_path, cookies_file=cookies_file)
    client = MagicMock()

    assert svc._try_cookies(client) is False
    client.login_by_sessionid.assert_not_called()
```

**Verificar**: `uv run pytest -q tests/test_auth.py -k cookies` → 3 passam.

### Passo 5: Sessão salva (`_try_saved_session`)

```python
def test_try_saved_session_success(tmp_path: Path) -> None:
    settings_file = tmp_path / "instagrapi.json"
    settings_file.write_text("{}")
    svc = _service(tmp_path, settings_file=settings_file)
    client = MagicMock()

    assert svc._try_saved_session(client) is True
    client.load_settings.assert_called_once_with(str(settings_file))
    client.get_timeline_feed.assert_called_once()


def test_try_saved_session_expired_returns_false(tmp_path: Path) -> None:
    settings_file = tmp_path / "instagrapi.json"
    settings_file.write_text("{}")
    svc = _service(tmp_path, settings_file=settings_file)
    client = MagicMock()
    client.get_timeline_feed.side_effect = ChallengeRequired("expired")

    assert svc._try_saved_session(client) is False
```

**Verificar**: `uv run pytest -q tests/test_auth.py -k saved_session` → 2 passam.

### Passo 6: Credenciais (`_try_credentials`)

```python
def test_try_credentials_success_persists_settings(tmp_path: Path) -> None:
    settings_file = tmp_path / "instagrapi.json"
    svc = _service(tmp_path, username="u", password="p", settings_file=settings_file)
    client = MagicMock()
    client.get_settings.return_value = {"cookies": {}}

    assert svc._try_credentials(client) is True
    client.login.assert_called_once_with("u", "p")
    assert settings_file.exists()


def test_try_credentials_challenge_required_raises_authentication_error(
    tmp_path: Path,
) -> None:
    svc = _service(tmp_path, username="u", password="p")
    client = MagicMock()
    client.login.side_effect = ChallengeRequired("challenge")

    with pytest.raises(AuthenticationError, match="Desafio de segurança"):
        svc._try_credentials(client)
```

**Verificar**: `uv run pytest -q tests/test_auth.py -k credentials` → 2 passam.

### Passo 7: Suíte completa

**Verificar**: `uv run pytest -q` → todos passam (32 + os novos deste plano).

## Plano de testes

- Casos cobertos (resumo): sucesso via session_id; fallback quando
  session_id falha e nada mais está configurado; parsing de cookies em
  formato lista e formato dict; cookies sem chave `sessionid`; sessão salva
  válida e expirada; credenciais válidas persistindo a sessão; credenciais
  com `ChallengeRequired`.
- Padrão estrutural: `tests/test_relations_complete_fetch.py` (MagicMock do
  `Client`) e `tests/test_storage_rotate.py` (`Config` real com `tmp_path`).
- Verificação final: `uv run pytest -q` → todos passam, incluindo os novos
  testes de `tests/test_auth.py`.

## Critérios de conclusão

Todos devem valer:

- [ ] `tests/test_auth.py` existe com pelo menos 9 funções de teste cobrindo
      os passos 2–6
- [ ] `uv run pytest -q` sai com exit 0, todos os testes passam
- [ ] Nenhum arquivo fora de `tests/test_auth.py` foi modificado
      (`git status`)
- [ ] Linha de status deste plano atualizada em `plans/README.md`

## Condições de parada

Pare e reporte (não improvise) se:

- O código em `instagram_toolkit/auth.py` não bater com os trechos citados
  em "Estado atual" (a assinatura de algum método mudou).
- Algum teste revelar um comportamento que parece um bug real (ex.: uma
  exceção não capturada, uma mensagem de erro que não corresponde ao tipo
  de falha) — não conserte o código de produção neste plano; documente o
  achado no relatório final em vez de alterar `auth.py`.
- Um passo de verificação falhar duas vezes após uma tentativa razoável de
  ajuste no teste (não no código de produção).

## Notas de manutenção

- Se no futuro `auth.py` ganhar um quinto caminho de autenticação, adicione
  o teste correspondente seguindo o mesmo padrão de helper `_service(...)`.
- Estes testes não cobrem o comportamento real do `instagrapi.Client` (ex.:
  se a API dele mudar assinatura), só o contrato que `AuthService` espera
  dele — é uma limitação aceitável de teste unitário com mock, não um gap
  deste plano.
