# Plano 005 (spike): Decidir o destino de `toutatis_integration.py`

> **Instruções para o executor**: Este é um plano de investigação/decisão,
> não de implementação. Siga os passos, preencha a seção "Decisão" ao final
> com o que foi apurado e escolhido, e **não implemente a opção "conectar ao
> menu"** neste mesmo plano — se essa for a decisão, pare no passo indicado
> e reporte de volta pedindo um plano de build separado. Ao terminar,
> atualize a linha de status deste plano em `plans/README.md`.
>
> **Checagem de deriva (rode primeiro)**: `git diff --stat 5cbb7ce..HEAD -- toutatis_integration.py instagram_toolkit/cli/menu.py README.md`
> Se algum desses arquivos mudou desde que este plano foi escrito (por
> exemplo, se alguém já conectou o módulo ao menu), compare com os trechos
> abaixo antes de prosseguir; em caso de divergência relevante, trate como
> condição de parada.

## Status

- **Prioridade**: P3
- **Esforço**: S (só a investigação/decisão; um eventual build fica para um
  plano futuro)
- **Risco**: BAIXO (este plano não muda comportamento de runtime, só decide
  e, no máximo, corrige uma frase do README)
- **Depende de**: nenhum
- **Categoria**: direction
- **Escrito em**: commit `5cbb7ce`, 2026-07-21

## Por que isso importa

`toutatis_integration.py` é um módulo de 314 linhas (~12% do código do
projeto) que implementa uma feature completa de OSINT (busca email/telefone
ofuscados, status de WhatsApp vinculado, etc. via API interna do Instagram),
mas **não é importado por nenhum outro arquivo do projeto** — nem
`main.py`, nem `instagram_toolkit/cli/handlers.py`, nem nenhum teste.
`grep -rn "toutatis_integration\|osint_profile\|print_osint_report"` fora do
próprio arquivo não retorna nada.

O commit que introduziu o módulo (`e50abd9`) se chama *"feat: integração
Toutatis — OSINT completo (email/telefone/dados ocultos)"*, o que sugere
que era pra ser uma funcionalidade entregue, não um rascunho esquecido. Ao
mesmo tempo, o `README.md` anuncia duas vezes "16 opções organizadas"
(linhas 9 e 73), mas o menu interativo (`instagram_toolkit/cli/menu.py:22-36`)
só liga 15 opções numeradas (1 a 15, mais "0. Sair"). A coincidência entre
"módulo OSINT construído e nunca conectado" e "README promete uma 16ª opção
que não existe" é um sinal (não uma prova) de intenção não finalizada.

Este plano não decide sozinho o que fazer — ele investiga o suficiente para
o mantenedor (ou uma próxima rodada de planejamento) decidir com contexto
completo, e documenta essa decisão.

## Estado atual

- `toutatis_integration.py:170-249` — `osint_profile()`, a função principal:
  aceita `username`/`user_id`/`session_id` ou um `instagrapi_client` (extrai
  o `session_id` dele via `extract_session_id()`), chama
  `get_user_info_via_api()` e depois `advanced_lookup()`, e monta um dict
  consolidado com campos como `obfuscated_email`, `obfuscated_phone`,
  `is_whatsapp_linked`.
- `toutatis_integration.py:118-153` — `advanced_lookup()` faz um POST direto
  para `https://i.instagram.com/api/v1/users/lookup/` usando uma
  `requests.Session` **própria**, criada ali mesmo — não usa
  `instagram_toolkit.rate_limiter.RateLimiter` nem passa pelo `Client` do
  `instagrapi`. Isso significa que, se conectado ao menu como está, ele
  bate na API do Instagram sem nenhum delay/backoff coordenado com o resto
  do toolkit.
- `toutatis_integration.py:52-92` — `get_user_info_via_api()` e
  `_resolve_user_id()` seguem o mesmo padrão: `RequestsSession` própria,
  sem retry/backoff, erros retornados como `{"error": str(e)}` em vez de
  levantar as exceções de `instagram_toolkit.config`
  (`InstagramToolkitError`, `RateLimitError`, etc.) que o resto do projeto
  usa.
- `instagram_toolkit/cli/menu.py:21-37` — dispatch table completo, 15
  entradas (`"1"` a `"15"`), sem nenhuma referência a OSINT/toutatis.
- `README.md:9`: `O script unificado oferece um menu com **16 opções
  organizadas** e prontas para uso interativo:` — mas a lista enumerada
  logo abaixo (linhas 12-30) só vai até o item 15.
- `README.md:73`: `Inicie o menu interativo com todas as 16 opções
  executando:` — mesma alegação repetida.

## Comandos que você vai precisar

| Finalidade | Comando | Esperado |
|---|---|---|
| Ver o commit original | `git show e50abd9 --stat` | lista de arquivos tocados no commit que introduziu o módulo |
| Confirmar que segue desconectado | `grep -rn "toutatis_integration\|osint_profile\|print_osint_report" --include="*.py" . \| grep -v "^./toutatis_integration.py"` | nenhuma saída |
| Confirmar contagem real do menu | `grep -c '": handlers\.' instagram_toolkit/cli/menu.py` | `15` |

## Escopo

**Dentro do escopo desta investigação**:
- Leitura de `toutatis_integration.py`, `instagram_toolkit/cli/menu.py`,
  `README.md`, e histórico do commit `e50abd9`.
- Se a decisão for "manter como script standalone": editar **só** as duas
  frases do `README.md` citadas acima (trocar "16 opções" por "15 opções")
  e adicionar um parágrafo curto documentando `toutatis_integration.py`
  como script/módulo auxiliar de uso opcional, fora do menu interativo.

**Fora do escopo** (não implementar neste plano):
- Qualquer mudança em `instagram_toolkit/cli/menu.py`,
  `instagram_toolkit/cli/handlers.py` ou `toutatis_integration.py` para de
  fato conectar a feature ao menu. Se a decisão apontar nessa direção, o
  passo final deste plano instrui a **parar e reportar**, não a construir.

## Fluxo git

- Branch: `advisor/005-toutatis-direction-spike`
- Se a decisão for "manter standalone" e o README for ajustado: um commit
  único, mensagem sugerida: `docs: correct menu option count and document
  toutatis_integration.py as standalone`
- Se a decisão for "conectar ao menu": **não crie commit de código**; só
  documente a decisão (ver Passo 3) e pare.
- Não faça push nem abra PR a menos que o operador peça.

## Passos

### Passo 1: Investigar a intenção original

Rode `git show e50abd9 --stat` e leia a mensagem completa do commit
(`git show e50abd9 --format=%B --no-patch`). Anote: o commit menciona
alguma intenção de conectar ao menu (ex.: uma opção "16")? Ou já foi
apresentado como script/integração separada desde o início?

**Verificar**: você tem uma resposta de uma frase para "o autor original
pretendia conectar isso ao menu interativo?" (sim / não / não fica claro).

### Passo 2: Avaliar o custo de conectar, caso se opte por isso

Sem implementar nada, avalie e anote os pontos de fricção já identificados
em "Estado atual": a função bate direto na API sem usar `RateLimiter`; os
erros vêm como dicts `{"error": ...}` em vez da hierarquia
`InstagramToolkitError`; e a feature expõe dados mais sensíveis
(email/telefone ofuscados) que as demais opções do menu, então mereceria
uma confirmação explícita extra antes de rodar (no padrão de
`_confirm(...)` já usado em `cli/handlers.py:277,295` para ações em massa).

### Passo 3: Registrar a decisão

Escolha uma das três opções e preencha a seção "## Decisão" no final deste
arquivo (adicione a seção, com a escolha e uma frase de justificativa):

1. **Conectar ao menu como opção 16** — recomendado se o Passo 1 indicar
   intenção original de entregar isso como feature, e se o mantenedor
   aceitar o custo extra de rate limiting/tratamento de erro consistente
   descrito no Passo 2. **Se escolher esta opção, pare aqui.** Não
   implemente a conexão neste plano — reporte de volta pedindo um plano de
   build dedicado (ele precisará cobrir: reuso do `RateLimiter`, conversão
   dos retornos de erro para `InstagramToolkitError`, e um prompt de
   confirmação extra dado o caráter mais sensível dos dados).
2. **Manter como script/módulo standalone documentado** — se a avaliação
   apontar que era sempre para ser uma ferramenta auxiliar separada (ex.:
   para uso via `python -c "from toutatis_integration import ..."` ou um
   script futuro `osint.py` fora do menu principal). Nesse caso, prossiga
   para o Passo 4.
3. **Remover** — se o módulo for considerado obsoleto/não mantido e
   ninguém pretender usá-lo. Esta opção também deve **parar sem
   implementar**: reporte de volta recomendando a remoção para confirmação
   explícita do mantenedor antes de apagar 314 linhas de código.

### Passo 4 (só se a opção 2 foi escolhida): Corrigir o README

Em `README.md`, troque:
- Linha 9: `**16 opções organizadas**` → `**15 opções organizadas**`
- Linha 73: `todas as 16 opções` → `todas as 15 opções`

E adicione, em uma seção nova ao final do README (ou próximo à seção de
instalação), um parágrafo como:

```markdown
## 🔎 Módulo OSINT opcional (`toutatis_integration.py`)

O arquivo `toutatis_integration.py` na raiz do projeto é um módulo auxiliar,
independente do menu interativo, que reaproveita a sessão autenticada do
`instagrapi` para consultar dados adicionais expostos pela API interna do
Instagram (email/telefone ofuscados, status de conta). Use-o importando
diretamente as funções `osint_profile()` e `print_osint_report()` em um
script próprio — ele não é acessível pelo menu principal.
```

**Verificar**: `grep -n "16 opções" README.md` → nenhuma ocorrência.

## Plano de testes

- Não há código de produção sendo alterado (fora a documentação, se a
  opção 2 for escolhida), então não há testes novos a escrever.
- Verificação: `grep -n "16 opções" README.md` retorna vazio (se a opção 2
  foi escolhida); caso contrário, nenhuma mudança de arquivo é esperada.

## Critérios de conclusão

Todos devem valer:

- [ ] Seção "## Decisão" preenchida neste arquivo com a opção escolhida e a
      justificativa
- [ ] Se opção 1 ou 3 foi escolhida: nenhum arquivo de código foi
      modificado; o relatório final pede explicitamente um plano de
      acompanhamento ao operador
- [ ] Se opção 2 foi escolhida: `README.md` não contém mais "16 opções" e
      tem o novo parágrafo documentando o módulo
- [ ] Nenhum arquivo fora de `README.md` e deste plano foi modificado
      (`git status`)
- [ ] Linha de status deste plano atualizada em `plans/README.md`

## Condições de parada

Pare e reporte (não improvise) se:

- A decisão apontar para "conectar ao menu" (opção 1) ou "remover"
  (opção 3) — **nenhuma das duas deve ser implementada por este plano**,
  apenas decidida e documentada.
- `instagram_toolkit/cli/menu.py` já tiver uma 16ª entrada quando você
  checar (alguém já resolveu isso de outra forma) — trate como já
  resolvido, atualize o status para DONE com uma nota, sem tocar em nada.

## Notas de manutenção

- Se a opção 1 ("conectar ao menu") for escolhida em uma rodada futura, o
  plano de build resultante deve tratar `advanced_lookup()` e
  `get_user_info_via_api()` como precisando de retry/backoff via
  `RateLimiter`, não como estão hoje (uma `RequestsSession` avulsa sem
  nenhuma coordenação com o resto do toolkit).
- Os dados que essa feature expõe (email/telefone ofuscados, vínculo de
  WhatsApp) são mais sensíveis que os demais itens do menu — qualquer
  wiring futuro deve ter uma confirmação explícita própria, não reaproveitar
  cegamente o padrão de confirmação das ações em massa existentes.

## Decisão

<!-- Preencher ao executar este plano. -->
