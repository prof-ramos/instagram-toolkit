# Plano 006: Reconectar `toutatis_integration.py` ao menu como opção 16

> **Instruções para o executor**: Siga este plano passo a passo. Rode cada
> comando de verificação e confirme o resultado esperado antes de avançar.
> Se algo na seção "Condições de parada" ocorrer, pare e reporte — não
> improvise. Ao terminar, atualize a linha de status deste plano em
> `plans/README.md`.
>
> **Checagem de deriva (rode primeiro)**: `git diff --stat 5cbb7ce..HEAD -- toutatis_integration.py instagram_toolkit/cli/handlers.py instagram_toolkit/cli/menu.py main.py`
> Se algum desses arquivos mudou desde que este plano foi escrito, compare
> os trechos da seção "Estado atual" com o código real antes de prosseguir;
> em caso de divergência, trate como condição de parada.

## Status

- **Prioridade**: P2
- **Esforço**: M
- **Risco**: MÉDIO (toca 4 arquivos e adiciona uma chamada de rede nova ao menu; mitigado por confirmação explícita e rate limiting)
- **Depende de**: nenhum (plano 005, que investigou e decidiu esta direção, já concluiu)
- **Categoria**: direction / feature
- **Escrito em**: commit `5cbb7ce`, 2026-07-21

## Por que isso importa

O plano 005 (spike de investigação) apurou que `toutatis_integration.py`
nasceu conectado ao menu interativo como opção 17 (commit `e50abd9`), e foi
**desconectado por acidente** num commit de performance (`c7e7407`) que
removeu o wiring sem mencionar isso na mensagem do commit. O refactor de
modularização seguinte (`86bd2bc`, v3.0) herdou esse estado sem OSINT e
nunca o trouxe de volta. Hoje o módulo (314 linhas, OSINT completo:
email/telefone ofuscados, status de WhatsApp vinculado) segue no
repositório, testado manualmente no passado, mas inacessível pelo menu.

Este plano reconecta a feature, mas com dois cuidados que o design original
(2026, commit `e50abd9`) não tinha e que o plano 005 identificou como
lacunas: (1) as chamadas HTTP do módulo não usam o `RateLimiter` do resto do
toolkit — vamos adicionar um delay entre as duas chamadas internas; (2) os
dados expostos (email/telefone ofuscados) são mais sensíveis que qualquer
outra opção do menu — vamos exigir confirmação explícita antes de rodar.

**Decisão deliberada de escopo**: este plano NÃO reescreve o tratamento de
erro interno de `toutatis_integration.py` (hoje baseado em dicts
`{"error": ...}`) para a hierarquia `InstagramToolkitError`. Isso foi
cogitado no plano 005, mas exigiria reescrever a assinatura de 3 funções
internas do módulo para um ganho marginal — o decorator `cli_safe` (já
usado por todos os outros handlers do menu) já captura qualquer exceção não
tratada, e `print_osint_report()` já imprime uma mensagem amigável quando o
dict de retorno tem uma chave `"error"`. Se o mantenedor quiser essa
unificação depois, é um plano separado.

## Estado atual

- `toutatis_integration.py:170-249` — `osint_profile()`, função principal
  (assinatura atual):
  ```python
  def osint_profile(
      username: str | None = None,
      user_id: int | None = None,
      session_id: str | None = None,
      instagrapi_client: Any | None = None,
  ) -> dict[str, Any]:
      ...
      info = get_user_info_via_api(
          username=username, user_id=user_id, session_id=session_id
      )
      ...
      # 2. Advanced lookup (email/phone ofuscados)
      lookup = advanced_lookup(user.get("username", ""), session_id)
      ...
  ```
  Entre a chamada a `get_user_info_via_api()` (linha ~189) e `advanced_lookup()`
  (linha ~237) não há nenhum delay — são duas requisições HTTP sequenciais
  sem coordenação com o resto do toolkit.
- `toutatis_integration.py:38-49` — `extract_session_id(instagrapi_client)`:
  já existe e extrai o `sessionid` das cookies salvas do client autenticado.
- `toutatis_integration.py:252-315` — `print_osint_report(data)`: já trata o
  caso de erro (`if "error" in data: print(f"❌ Erro: {data['error']}"); return`),
  então a UI de erro já está pronta — não precisa de tratamento extra no
  handler novo.
- `instagram_toolkit/cli/handlers.py:37-56` — `MenuHandlers.__init__` atual:
  ```python
  class MenuHandlers:
      def __init__(
          self,
          relations: "RelationsService",
          actions: "ActionsService",
          tracker: "TrackerService",
          storage: "HistoryStorage",
          cache: "RelationsCache",
      ) -> None:
          self.relations = relations
          self.actions = actions
          self.tracker = tracker
          self.storage = storage
          self.cache = cache
  ```
  Não recebe `client` (instagrapi) nem `rate_limiter` hoje — precisam ser
  adicionados para o novo handler funcionar.
- `instagram_toolkit/cli/handlers.py:307-313` — helpers privados já
  existentes que o novo handler deve reusar:
  ```python
  def _ask_int(prompt: str, default: int) -> int:
      raw = input(prompt).strip()
      return int(raw) if raw.isdigit() else default


  def _confirm(prompt: str) -> bool:
      return input(f"{prompt} (s/n): ").strip().lower() == "s"
  ```
- `instagram_toolkit/cli/menu.py:12-37` — `InteractiveMenu.__init__`, dispatch
  table com 15 entradas (`"1"` a `"15"`), sem OSINT.
- `instagram_toolkit/cli/menu.py:43` — prompt de escolha:
  `input("\n👉 Escolha uma opção (0-15): ")`.
- `main.py:40-54` — `wire_dependencies()`, que hoje instancia
  `MenuHandlers(relations, actions, tracker, storage, cache)` sem passar
  `client`/`rate_limiter`.
- `instagram_toolkit/rate_limiter.py` — `RateLimiter.delay(min_sec=None, max_sec=None)`
  já existe e é o método certo para reusar (pausa aleatória entre os
  limites, ou os defaults `base_delay_min`/`base_delay_max` da instância).

## Comandos que você vai precisar

| Finalidade | Comando | Esperado no sucesso |
|---|---|---|
| Rodar suíte completa | `uv run pytest -q` | todos passam |
| Checar sintaxe/import | `uv run python -c "import main"` | exit 0, sem erro de import |

## Escopo

**Dentro do escopo** (únicos arquivos a modificar):
- `toutatis_integration.py` — adicionar parâmetro opcional `rate_limiter` a
  `osint_profile()`.
- `instagram_toolkit/cli/handlers.py` — `MenuHandlers.__init__` ganha
  `client`/`rate_limiter`; novo método `osint_lookup()`.
- `instagram_toolkit/cli/menu.py` — nova entrada `"16"` no dispatch, nova
  linha de menu, prompt atualizado para `(0-16)`.
- `main.py` — `wire_dependencies()` passa `client`/`rate_limiter` para
  `MenuHandlers`.
- `tests/test_osint_handler.py` (criar) — testes offline do novo handler.

**Fora do escopo** (não mexer, mesmo que pareça relacionado):
- Tratamento de erro interno de `toutatis_integration.py` (dicts
  `{"error": ...}`) — não converter para `InstagramToolkitError` (ver
  "Por que isso importa" acima).
- `README.md` — não atualizar a contagem de opções do menu neste plano;
  isso é uma frase de documentação separada, não parte do wiring.
- Qualquer mudança em `get_user_info_via_api()` ou `_resolve_user_id()` além
  do necessário para aceitar/propagar `rate_limiter` — não redesenhe essas
  funções.

## Fluxo git

- Branch: `advisor/006-wire-toutatis-menu`
- Um commit único; mensagem sugerida:
  `feat: reconnect toutatis OSINT integration as menu option 16`
- Não faça push nem abra PR a menos que o operador peça.

## Passos

### Passo 1: Adicionar `rate_limiter` opcional a `osint_profile()`

Em `toutatis_integration.py`, mude a assinatura de `osint_profile` para:
```python
def osint_profile(
    username: str | None = None,
    user_id: int | None = None,
    session_id: str | None = None,
    instagrapi_client: Any | None = None,
    rate_limiter: Any | None = None,
) -> dict[str, Any]:
```
E, logo antes da chamada a `advanced_lookup(...)` (a que hoje começa com o
comentário `# 2. Advanced lookup (email/phone ofuscados)`), adicione:
```python
    if rate_limiter is not None:
        rate_limiter.delay()
```
Não importe `RateLimiter` de `instagram_toolkit.rate_limiter` — o parâmetro
é duck-typed (`Any`, só precisa responder a `.delay()`) para manter este
módulo desacoplado do pacote `instagram_toolkit`, como já é hoje.

**Verificar**: `uv run python -c "from toutatis_integration import osint_profile; import inspect; print(inspect.signature(osint_profile))"`
→ mostra `rate_limiter` no final da assinatura.

### Passo 2: `MenuHandlers` recebe `client` e `rate_limiter`

Em `instagram_toolkit/cli/handlers.py`, adicione ao bloco `if TYPE_CHECKING:`
do topo:
```python
if TYPE_CHECKING:
    from instagrapi import Client

    from ..actions import ActionsService
    from ..cache import RelationsCache
    from ..rate_limiter import RateLimiter
    from ..relations import RelationsService
    from ..storage import HistoryStorage
    from ..tracker import TrackerService
```
E mude `__init__`:
```python
    def __init__(
        self,
        relations: "RelationsService",
        actions: "ActionsService",
        tracker: "TrackerService",
        storage: "HistoryStorage",
        cache: "RelationsCache",
        client: "Client",
        rate_limiter: "RateLimiter",
    ) -> None:
        self.relations = relations
        self.actions = actions
        self.tracker = tracker
        self.storage = storage
        self.cache = cache
        self.client = client
        self.rate_limiter = rate_limiter
```

**Verificar**: `uv run python -c "import instagram_toolkit.cli.handlers"` →
exit 0 (sem erro de sintaxe/import).

### Passo 3: Novo handler `osint_lookup`

Ainda em `instagram_toolkit/cli/handlers.py`, adicione um novo método
público na classe `MenuHandlers` (sugestão: logo após `show_recent_posts`,
antes do bloco `# EXPORTAÇÕES`):

```python
    # ------------------------------------------------------------------
    # OSINT
    # ------------------------------------------------------------------

    @cli_safe
    def osint_lookup(self) -> None:
        identifier = input("Username (@) ou ID: ").strip()
        if not identifier:
            return
        print(
            "\n⚠️  Esta opção consulta dados adicionais (email/telefone "
            "ofuscados, status de conta) via API interna do Instagram, "
            "usando sua sessão autenticada."
        )
        if not _confirm("Confirmar consulta OSINT"):
            print("Cancelado.")
            return

        from toutatis_integration import extract_session_id, osint_profile, print_osint_report

        session_id = extract_session_id(self.client)
        if not session_id:
            print("❌ Não foi possível extrair o session ID da sessão autenticada.")
            return

        username = None if identifier.isdigit() else identifier.lstrip("@")
        user_id = int(identifier) if identifier.isdigit() else None

        print(f"\n🕵️  Consultando dados de @{identifier}...")
        data = osint_profile(
            username=username,
            user_id=user_id,
            session_id=session_id,
            rate_limiter=self.rate_limiter,
        )
        print_osint_report(data)
```

O import de `toutatis_integration` fica local à função (não no topo do
arquivo) para não acoplar todo `cli/handlers.py` a um módulo de nível de
repositório — siga o mesmo estilo já usado em `watch_mode()`
(`from .watch import run_watch_loop`, importado dentro do método).

**Verificar**: `uv run python -c "import instagram_toolkit.cli.handlers"` →
exit 0.

### Passo 4: Menu — opção 16

Em `instagram_toolkit/cli/menu.py`, adicione ao dispatch (depois de `"15":`):
```python
            "16": handlers.osint_lookup,
```
E, em `_show_menu()`, adicione uma linha depois de "15. 👥 Seguidores mútuos"
e antes do separador final:
```python
        print("16. 🕵️  OSINT completo (email/telefone ofuscados)")
```
Atualize o prompt de escolha em `run()`:
```python
                choice = input("\n👉 Escolha uma opção (0-16): ").strip()
```

**Verificar**: `grep -c '": handlers\.' instagram_toolkit/cli/menu.py` → `16`.

### Passo 5: `main.py` — passar `client`/`rate_limiter`

Em `main.py`, dentro de `wire_dependencies()`, mude:
```python
    handlers = MenuHandlers(relations, actions, tracker, storage, cache)
```
para:
```python
    handlers = MenuHandlers(
        relations, actions, tracker, storage, cache,
        client=client, rate_limiter=rate_limiter,
    )
```
(`client` e `rate_limiter` já existem como variáveis locais nessa função —
não precisa criar nada novo, só passar adiante.)

**Verificar**: `uv run python -c "import main"` → exit 0, sem erro.

### Passo 6: Teste offline do novo handler

Crie `tests/test_osint_handler.py`:
```python
"""Offline tests for MenuHandlers.osint_lookup (no real Instagram network)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from instagram_toolkit.cli.handlers import MenuHandlers


def _handlers(client=None, rate_limiter=None) -> MenuHandlers:
    return MenuHandlers(
        relations=MagicMock(),
        actions=MagicMock(),
        tracker=MagicMock(),
        storage=MagicMock(),
        cache=MagicMock(),
        client=client or MagicMock(),
        rate_limiter=rate_limiter or MagicMock(),
    )


def test_osint_lookup_cancelled_without_confirmation(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "alice")
    h = _handlers()
    with patch("instagram_toolkit.cli.handlers._confirm", return_value=False):
        h.osint_lookup()
    # Nenhuma chamada de rede deve ocorrer sem confirmação.


def test_osint_lookup_calls_rate_limiter_and_prints_report(monkeypatch) -> None:
    inputs = iter(["alice"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    client = MagicMock()
    rate_limiter = MagicMock()
    h = _handlers(client=client, rate_limiter=rate_limiter)

    with (
        patch("instagram_toolkit.cli.handlers._confirm", return_value=True),
        patch("toutatis_integration.extract_session_id", return_value="sid123"),
        patch("toutatis_integration.osint_profile", return_value={"username": "alice"}) as m_profile,
        patch("toutatis_integration.print_osint_report") as m_report,
    ):
        h.osint_lookup()

    m_profile.assert_called_once()
    assert m_profile.call_args.kwargs["rate_limiter"] is rate_limiter
    m_report.assert_called_once_with({"username": "alice"})


def test_osint_lookup_missing_session_id_prints_error_and_skips_lookup(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "alice")
    h = _handlers()

    with (
        patch("instagram_toolkit.cli.handlers._confirm", return_value=True),
        patch("toutatis_integration.extract_session_id", return_value=None),
        patch("toutatis_integration.osint_profile") as m_profile,
    ):
        h.osint_lookup()

    m_profile.assert_not_called()
```

**Verificar**: `uv run pytest -q tests/test_osint_handler.py` → 3 passam.

Nota: os `patch("toutatis_integration.X", ...)` funcionam porque o import
de `toutatis_integration` dentro de `osint_lookup()` é feito em tempo de
execução (`from toutatis_integration import ...` dentro do método) — o
patch no módulo `toutatis_integration` é resolvido antes da chamada.

### Passo 7: Suíte completa

**Verificar**: `uv run pytest -q` → todos passam (baseline + 3 novos deste
plano).

## Plano de testes

- Casos cobertos: cancelamento sem confirmação (sem chamada de rede);
  fluxo de sucesso com `rate_limiter` propagado corretamente para
  `osint_profile()`; ausência de `session_id` extraído interrompe antes de
  qualquer chamada a `osint_profile()`.
- Modelo estrutural: `unittest.mock.MagicMock`/`patch`, no padrão de
  `tests/test_actions.py`.
- Verificação: `uv run pytest -q` → todos passam, incluindo os 3 novos.

## Critérios de conclusão

Todos devem valer:

- [ ] `osint_profile()` aceita `rate_limiter` opcional e chama
      `rate_limiter.delay()` entre as duas requisições internas
- [ ] `MenuHandlers` recebe `client`/`rate_limiter` e expõe `osint_lookup()`
- [ ] Menu mostra opção 16 e o dispatch tem 16 entradas
      (`grep -c '": handlers\.' instagram_toolkit/cli/menu.py` → `16`)
- [ ] `main.py` passa `client`/`rate_limiter` para `MenuHandlers`
- [ ] `tests/test_osint_handler.py` existe com 3 testes, todos passam
- [ ] `uv run pytest -q` sai com exit 0
- [ ] `uv run python -c "import main"` sai com exit 0
- [ ] Nenhum arquivo fora do escopo listado foi modificado (`git status`)
- [ ] Linha de status deste plano atualizada em `plans/README.md`

## Condições de parada

Pare e reporte (não improvise) se:

- Algum dos trechos citados em "Estado atual" não bater com o código real
  (a assinatura de alguma função mudou desde que este plano foi escrito).
- `extract_session_id()` ou `osint_profile()` exigirem mudanças mais
  profundas do que adicionar um parâmetro opcional para funcionar
  corretamente com o `rate_limiter`.
- Você perceber que testar `osint_lookup()` exige mockar `instagrapi.Client`
  de um jeito significativamente mais complexo do que o previsto no Passo 6
  (ex.: se `extract_session_id` precisar de um client real, não um Mock).

## Notas de manutenção

- Este plano deliberadamente NÃO unifica o tratamento de erro de
  `toutatis_integration.py` com `InstagramToolkitError`. Se isso for feito
  depois, `osint_lookup()` precisará de um `try/except` explícito em vez de
  confiar só no `cli_safe` genérico.
- Se o mantenedor decidir atualizar a contagem "16 opções" do `README.md`
  (hoje já correta coincidentemente, já que o menu agora tem 16 entradas
  reais 1-16 + "0. Sair"), isso é uma edição de documentação trivial, fora
  deste plano.
- `rate_limiter.delay()` usa os defaults da instância
  (`base_delay_min=1.8`, `base_delay_max=3.8`) — se o OSINT precisar de um
  intervalo diferente (ex. mais conservador, como `follow_delay`/
  `unfollow_delay`), ajustar a chamada em `osint_profile()` para passar
  `min_sec`/`max_sec` explícitos.
