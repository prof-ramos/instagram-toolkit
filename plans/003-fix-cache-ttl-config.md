# Plano 003: Corrigir parsing frágil e código morto de `Config.cache_ttl`

> **Instruções para o executor**: Siga este plano passo a passo. Rode cada
> comando de verificação e confirme o resultado esperado antes de avançar.
> Se algo na seção "Condições de parada" ocorrer, pare e reporte — não
> improvise. Ao terminar, atualize a linha de status deste plano em
> `plans/README.md`.
>
> **Checagem de deriva (rode primeiro)**: `git diff --stat 5cbb7ce..HEAD -- instagram_toolkit/config.py main.py`
> Se `config.py` mudou desde que este plano foi escrito, compare o trecho da
> seção "Estado atual" com o código real antes de prosseguir; em caso de
> divergência, trate como condição de parada.

## Status

- **Prioridade**: P1
- **Esforço**: S
- **Risco**: BAIXO
- **Depende de**: nenhum
- **Categoria**: bug
- **Escrito em**: commit `5cbb7ce`, 2026-07-21

## Por que isso importa

`Config.cache_ttl` (`instagram_toolkit/config.py:47-49`) é lido de
`INSTAGRAM_CACHE_TTL` via `float(os.getenv(...))` **sem nenhum tratamento de
erro**. Se alguém definir `INSTAGRAM_CACHE_TTL=abc` (ou qualquer valor não
numérico) no `.env`, `Config()` levanta um `ValueError` não capturado assim
que é instanciado em `main.py:71` — o programa quebra com um traceback cru
antes mesmo de imprimir o banner, em vez do tratamento gracioso que o resto
do app usa (compare com `AuthenticationError` sendo capturada em
`main.py:95-96`). Pior: esse campo é **código morto** — o TTL de cache
realmente usado em produção vem do argumento `--cache-ttl` do argparse
(`main.py:72`: `RelationsCache(ttl=args.cache_ttl, ...)`), não de
`config.cache_ttl`. O próprio arquivo já tem o padrão certo ao lado, em
`resolve_fetch_limit()` (linhas 21-30), que trata exatamente esse tipo de
entrada inválida sem levantar exceção. Este plano alinha `cache_ttl` ao
mesmo padrão defensivo.

## Estado atual

- `instagram_toolkit/config.py:11-34` — padrão de referência já existente:
  ```python
  MAX_SNAPSHOTS: int = 10
  DEFAULT_TTL: float = 300.0
  ...
  DEFAULT_FETCH_LIMIT: int = 0


  def resolve_fetch_limit() -> int:
      """Retorna o limite de fetch (0 = sem teto). Valores inválidos viram 0."""
      raw = os.getenv("INSTAGRAM_FETCH_LIMIT")
      if raw is None or raw.strip() == "":
          return DEFAULT_FETCH_LIMIT
      try:
          value = int(raw)
      except ValueError:
          return DEFAULT_FETCH_LIMIT
      return max(0, value)


  # Compat: imports legados `from .config import FETCH_LIMIT`
  FETCH_LIMIT: int = resolve_fetch_limit()
  ```
- `instagram_toolkit/config.py:37-49` — o campo problemático, dentro da
  dataclass `Config`:
  ```python
  @dataclass
  class Config:
      username: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_USERNAME"))
      password: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_PASSWORD"))
      session_id: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_SESSION_ID"))
      settings_file: Path = field(default_factory=lambda: Path("instagrapi.json"))
      cookies_file: Path = field(default_factory=lambda: Path("cookies.json"))
      history_file: Path = field(default_factory=lambda: Path("followers_history.json"))
      backup_dir: Path = field(default_factory=lambda: Path("history_backups"))
      fetch_limit: int = field(default_factory=resolve_fetch_limit)
      cache_ttl: float = field(
          default_factory=lambda: float(os.getenv("INSTAGRAM_CACHE_TTL", str(DEFAULT_TTL)))
      )
  ```
- Confirmação de que é código morto: `grep -rn "cache_ttl" --include="*.py" .`
  só retorna a própria definição em `config.py:47` e o uso de `RelationsCache(ttl=args.cache_ttl, ...)`
  em `main.py:72`, que vem do **argparse**, não de `Config`. Nenhum outro
  ponto do código lê `config.cache_ttl`.
- `main.py:33-36` — a fonte real do TTL usado:
  ```python
  parser.add_argument(
      "--cache-ttl", type=int, default=int(DEFAULT_TTL), metavar="SEG",
      help=f"TTL do cache em segundos (padrão: {int(DEFAULT_TTL)})",
  )
  ```

## Comandos que você vai precisar

| Finalidade | Comando | Esperado no sucesso |
|---|---|---|
| Rodar só o teste novo | `uv run pytest -q tests/test_config.py` | todos passam |
| Rodar suíte completa | `uv run pytest -q` | todos passam |

## Escopo

**Dentro do escopo** (únicos arquivos a modificar):
- `instagram_toolkit/config.py`
- `tests/test_config.py` (criar)

**Fora do escopo** (não mexer, mesmo que pareça relacionado):
- `main.py` — **não** troque a fonte do TTL de `args.cache_ttl` para
  `config.cache_ttl`, nem remova o argumento `--cache-ttl`. Isso é uma
  decisão de produto/wiring (qual fonte deve ganhar prioridade), não uma
  correção de bug — fica para o mantenedor decidir separadamente. Este
  plano só torna o campo `Config.cache_ttl` seguro de construir; não muda
  quem o consome.
- `.env.example` / `README.md` — não documente `INSTAGRAM_CACHE_TTL` como
  variável suportada; ela já existia informalmente no campo, mas este plano
  não expande sua superfície de uso.

## Fluxo git

- Branch: `advisor/003-fix-cache-ttl-config`
- Um commit único; mensagem sugerida:
  `fix: guard Config.cache_ttl parsing against invalid env values`
- Não faça push nem abra PR a menos que o operador peça.

## Passos

### Passo 1: Adicionar `resolve_cache_ttl()` espelhando `resolve_fetch_limit()`

Em `instagram_toolkit/config.py`, logo após `resolve_fetch_limit()` e antes
da linha `FETCH_LIMIT: int = resolve_fetch_limit()`, adicione:

```python
def resolve_cache_ttl() -> float:
    """Retorna o TTL do cache em segundos. Valores inválidos viram DEFAULT_TTL."""
    raw = os.getenv("INSTAGRAM_CACHE_TTL")
    if raw is None or raw.strip() == "":
        return DEFAULT_TTL
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_TTL
    return max(0.0, value)
```

**Verificar**: `uv run python -c "from instagram_toolkit.config import resolve_cache_ttl; print(resolve_cache_ttl())"`
→ imprime `300.0` (sem `INSTAGRAM_CACHE_TTL` no ambiente).

### Passo 2: Trocar o `default_factory` do campo `cache_ttl`

Substitua:
```python
    cache_ttl: float = field(
        default_factory=lambda: float(os.getenv("INSTAGRAM_CACHE_TTL", str(DEFAULT_TTL)))
    )
```
por:
```python
    cache_ttl: float = field(default_factory=resolve_cache_ttl)
```

**Verificar**: `INSTAGRAM_CACHE_TTL=abc uv run python -c "from instagram_toolkit.config import Config; print(Config().cache_ttl)"`
→ imprime `300.0` (não levanta `ValueError`).

### Passo 3: Criar `tests/test_config.py`

```python
"""Unit tests for Config env-var parsing helpers (offline)."""

from __future__ import annotations

import pytest

from instagram_toolkit.config import DEFAULT_TTL, Config, resolve_cache_ttl


@pytest.mark.parametrize(
    "env_value,expected",
    [
        (None, DEFAULT_TTL),
        ("", DEFAULT_TTL),
        ("120", 120.0),
        ("120.5", 120.5),
        ("0", 0.0),
        ("-10", 0.0),
        ("abc", DEFAULT_TTL),
        ("  ", DEFAULT_TTL),
    ],
)
def test_resolve_cache_ttl_env_policy(
    monkeypatch: pytest.MonkeyPatch,
    env_value: str | None,
    expected: float,
) -> None:
    if env_value is None:
        monkeypatch.delenv("INSTAGRAM_CACHE_TTL", raising=False)
    else:
        monkeypatch.setenv("INSTAGRAM_CACHE_TTL", env_value)
    assert resolve_cache_ttl() == expected


def test_config_construction_never_raises_on_invalid_cache_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INSTAGRAM_CACHE_TTL", "not-a-number")
    config = Config()
    assert config.cache_ttl == DEFAULT_TTL
```

**Verificar**: `uv run pytest -q tests/test_config.py` → 9 passam (8 casos
parametrizados + 1 teste de construção).

### Passo 4: Suíte completa

**Verificar**: `uv run pytest -q` → todos passam (32 + os novos deste
plano).

## Plano de testes

- Casos cobertos: ausente, vazio, número inteiro, número decimal, zero,
  negativo (deve virar `0.0`, mesma semântica de clamp de
  `resolve_fetch_limit`), texto inválido, string só com espaços.
- Modelo estrutural: `tests/test_relations_cache_policy.py:83-104`
  (`test_fetch_limit_env_policy`), que já parametriza exatamente esse tipo
  de teste para `resolve_fetch_limit`.
- Verificação: `uv run pytest -q` → todos passam, incluindo os 9 novos testes
  de `tests/test_config.py`.

## Critérios de conclusão

Todos devem valer:

- [ ] `resolve_cache_ttl()` existe em `instagram_toolkit/config.py` e segue
      o mesmo padrão defensivo de `resolve_fetch_limit()`
- [ ] `Config.cache_ttl` usa `default_factory=resolve_cache_ttl`
- [ ] `tests/test_config.py` existe e todos os testes passam
- [ ] `uv run pytest -q` sai com exit 0
- [ ] `INSTAGRAM_CACHE_TTL=abc uv run python -c "from instagram_toolkit.config import Config; Config()"` não levanta exceção
- [ ] Nenhum arquivo fora de `instagram_toolkit/config.py` e
      `tests/test_config.py` foi modificado (`git status`)
- [ ] Linha de status deste plano atualizada em `plans/README.md`

## Condições de parada

Pare e reporte (não improvise) se:

- O trecho de `config.py` citado em "Estado atual" não bater com o código
  real (alguém já mexeu no campo `cache_ttl` antes deste plano rodar).
- `DEFAULT_TTL` não for mais `300.0` (ajuste os valores esperados nos testes
  só depois de confirmar a mudança é intencional e documentada em outro
  lugar).
- Você notar que `config.cache_ttl` passou a ser consumido em algum lugar
  além de `config.py` desde que este plano foi escrito — isso mudaria o
  raio de impacto da mudança e precisa de reavaliação antes de prosseguir.

## Notas de manutenção

- Este plano **não** resolve a questão de produto de que `Config.cache_ttl`
  continua sem ser lido por `main.py` (que usa `args.cache_ttl` do
  argparse). Se o mantenedor decidir que `INSTAGRAM_CACHE_TTL` deveria ter
  prioridade sobre `--cache-ttl` (ou vice-versa), isso é um plano separado
  de wiring/produto, não uma correção de bug.
- Se `INSTAGRAM_FETCH_LIMIT` ganhar mais casos de borda no futuro (ex.:
  suporte a sufixos como "1h"), replique a mudança em `resolve_cache_ttl()`
  para manter os dois helpers simétricos.
