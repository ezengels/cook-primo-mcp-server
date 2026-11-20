# Primo MCP Server: Towson University (Cook Library OneSearch)

MCP server for OneSearch, the discovery system of Towson University's Albert
S. Cook Library (Ex Libris Primo VE, shared through the USMAI consortium of
Maryland libraries). It lets Claude search Towson's catalogue, the other USMAI
libraries' catalogues, and the Central Discovery Index of articles, and
returns record details, access links, citations, and exports.

This repository is a fork of
[Aaron Tay's SMU fork](https://github.com/aarontaycheehsien/primo-mcp-server)
of [geheharidas/primo-mcp-server](https://github.com/geheharidas/primo-mcp-server)
(MIT licence), reconfigured for Towson and packaged as a Claude Code plugin
for a small group of pilot testers. The changes are listed under
[Changes from upstream](#changes-from-upstream).

The server uses only OneSearch's public search interface, the same requests
the OneSearch web page makes for a signed-out visitor. It needs no Towson
login, no Primo API key, and no Ex Libris developer account, and it sees only
what a signed-out visitor sees.

## Install the plugin

The plugin runs in Claude Code: the VS Code extension, the **Code** tab of
the Claude desktop app, or `claude` in a terminal. All three read the same
plugin settings, so installing it in one makes it available in the others.
It doesn't reach the desktop app's Chat tab or Cowork.

### 1. Install Git and uv (once)

Claude Code downloads the plugin with Git; without it, the install fails
with "'git' not found". [uv](https://docs.astral.sh/uv/) starts the server.
The first time, uv downloads the server's packages and, if your computer has
no Python 3.11 to 3.14, Python itself: up to about 40 MB in all.

- Git on Windows, in PowerShell: `winget install --id Git.Git -e`, or the
  installer from [git-scm.com](https://git-scm.com/downloads/win). On a Mac,
  run `git --version` in Terminal and accept the offer to install the
  developer tools.
- uv on Windows, in PowerShell:
  `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- uv on macOS or Linux, in a terminal:
  `curl -LsSf https://astral.sh/uv/install.sh | sh`

uv's [installation page](https://docs.astral.sh/uv/getting-started/installation/)
lists other ways to install it.

Then quit VS Code or the Claude desktop app completely and open it again, so
that it can find uv. In VS Code, use **File > Exit**: closing or reloading one
window isn't enough, because every window keeps the environment VS Code
started with. To check the install, run `uv --version` in a new terminal.

### 2. Install the plugin

**VS Code:** in the Claude Code panel, type `/plugins` to open **Manage
plugins**. On the **Marketplaces** tab, add `ezengels/cook-primo-mcp-server`.
On the **Plugins** tab, find **primo-towson**, click **Install**, and choose
**Install for you**.

**Terminal:** run this in PowerShell or a terminal (not inside a Claude
session):

```text
claude plugin install primo-towson --marketplace ezengels/cook-primo-mcp-server
```

Inside a `claude` session, `/plugin install primo-towson --marketplace
ezengels/cook-primo-mcp-server` does the same.

**Claude desktop app:** the Code tab can't run `/plugin` commands (it answers
that they aren't available in this environment). Use the terminal command
above instead; the desktop app reads the same settings, so the plugin appears
in your next Code session. If you don't have the `claude` command, install
it first and open a new terminal window:

- Windows, in PowerShell: `irm https://claude.ai/install.ps1 | iex`
- macOS or Linux: `curl -fsSL https://claude.ai/install.sh | bash`

### 3. Check that it works

Start a new conversation. In VS Code or a terminal, type `/mcp`:
**plugin:primo-towson:primo** should show as connected. In the desktop app,
the plugin is listed under **Customize** (or **Plugins**) in the sidebar, or
just ask a OneSearch question. The first start takes 5 to 15 seconds while uv
sets up; later starts take about a second.

If the server shows **Failed** with "Connection closed", Claude Code can't
find uv. Check that `uv --version` works in a new terminal, quit the app
completely (in VS Code, **File > Exit**), reopen it, and click **Reconnect**.
If it still fails, sign out of your computer and back in.

Then ask, for example:

> Search Towson's OneSearch for Saotome et al. 2018, "Structure of the
> mechanically activated ion channel Piezo1", and tell me whether Towson has
> full-text access.

> Search Towson's catalogue for books by Frederick Douglass.

Claude Code asks for permission the first time it uses a OneSearch tool;
choose the option that stops it asking again. Links in the answers open
OneSearch or the library's link resolver in your browser, where you sign in
with your NetID as usual.

Searches of everything usually take 1 to 5 seconds. When OneSearch's article
index is slow, the server repeats the search, which can take up to about 15
seconds, and it double-checks any search that reports no articles at all. If
the article index still has not answered, the results say so and contain only
catalogue records; ask Claude to run the search again later.

### Updates and removal

Plugins from this marketplace don't update automatically unless you turn
that on. In a terminal session, run `/plugin`, open the **Marketplaces** tab,
select **cook-library**, and choose **Update marketplace**; the same menu
turns on auto-update. From a shell,
`claude plugin update primo-towson@cook-library` updates the plugin. Then
run `/reload-plugins` or start a new conversation.

To remove the plugin, uninstall it from the plugin manager or run
`/plugin uninstall primo-towson@cook-library`. The Python environment that uv
made for it lives in the plugin's own folder and is removed with it.

## Changes from upstream

- Towson OneSearch defaults in `config.py`: the Primo VE host, view ID,
  institution name, and the tab and scope behind each of the three canonical
  scopes (see [Scope Behaviour](#scope-behaviour)).
- Tool descriptions and server instructions name Towson's Cook Library
  instead of SMU, describe Towson's scopes, and tell Claude that a title held
  only by another USMAI library is not a Towson holding.
- New scope aliases: `network`, `usmai`, `usmai_network` and
  `new_discovery_network` for the USMAI network catalogue, and `dn_and_ci`.
- `mcp` is capped below 2.0. mcp 2.x renamed `McpError` to `MCPError`, which
  breaks the import in `librarian_llm.py`; `uv.lock` pins 1.28.1, but a plain
  `pip install -e .` would pull 2.x.
- Facet retry: right after a search of millions of results, Primo can return
  an empty facet list while it computes facets in the background (at Towson,
  "music" had 0 facets at +0 s and 14 at +1 s). The client now retries once,
  after 1 s, for searches of 100,000 results or more.
- Tests: a check that the defaults build Towson OneSearch links; the SMU link
  tests now use a complete SMU fixture; the live checks use Towson-relevant
  queries, and the date-filter check is recalibrated, with the evidence
  recorded in the test.
- Article-index retry: when OneSearch's article index (CDI) is slow, Primo
  answers after about five seconds with catalogue records only and reports
  the article count as `-1`. Searches of everything now repeat the request
  up to twice. If the article index still has not answered, or reports 0 only
  after timing out, the result says the articles are missing instead of
  implying none exist. Without this, a slow article index made searches look
  catalogue-only.
- Cached failures: Primo stores a failed article search as 0 articles, and a
  later repeat of the same search gets that 0 straight from its cache, with
  no `-1` to give it away. Any reported 0 is now checked once more with
  `disableCache=true`, which makes Primo search again. Searches that saw a
  `-1` or a 0 are logged with Primo's own article-index search time, so the
  next real failure shows whether that check works (it could not be watched
  live: the article index answered throughout the tests).
- Sorting: `/pnxs` reads `sort`, not `sortby`, so `sort_by` was silently
  ignored and every search came back in relevance order. The client now
  sends `sort` with Primo's codes (`date_d` for newest first, `date_a` for
  oldest, `title`, `author`), and the OneSearch links use the same codes.
- Re-run links: the "Queries attempted" links now carry `facet_filters` and
  `facet_exclusions` as well, so they reproduce the search that actually
  ran. Coded facet values may be given as the result landscape prints them
  ("review article" for `review_article`, "online" for `online_resources`);
  before, those labels matched nothing and silently filtered nothing.
- Availability: results show Primo's status for each record ("Available
  online", "Available in the library", "Not held here", "Check holdings"),
  worded after Towson's own OneSearch labels, instead of the delivery
  category ("Alma-P", "Alma-E"), which only says what kind of record it is.
  The label table covers every status code in Towson's OneSearch labels,
  including the `ext_*` codes of open-repository records such as MD-SOAR's.
  Records held by other USMAI libraries list them, with their status.
- Citations and exports: co-authors catalogued as authors in `addata.addau`
  are kept (Kim and Karrila's *Microhydrodynamics* was cited under Kim
  alone); APA has its comma before "&" and article numbers ("Article A16");
  APA gives the publisher without its place, and the other styles give
  "Place: Publisher"; Chicago no longer doubles the period after initials;
  IEEE puts "and" between two book authors; initials keep romanisation
  ligatures (Posudin's ALA-LC "I" + U+FE20 + "U" + U+FE21 was cut to "I.").
  BibTeX, RIS and CSV give the place separately (`address`, `CY`, a Place
  column) and put an article number where the pages go (`pages`, `SP`,
  Pages). `primo_cite` and `primo_export` name any record IDs they could not
  find; `primo_export` puts that note in a separate text block, so the
  export stays importable as it is.
- Smaller output fixes: HTML character references that Primo leaves in some
  names and titles ("M&#233;xico") are decoded; a quoted phrase query is no
  longer printed with doubled quotes; an invalid `sort_by` names the values
  the tool description documents.
- Tool description order: Claude Code cuts tool descriptions at 4,096
  characters, which dropped the notes on `facet_filters`, `facet_exclusions`
  and `clauses`. The `primo_search` description now gives the arguments
  first and the policy prose last; the policy is also in the server
  instructions.
- Claude Code plugin: `.claude-plugin/plugin.json` starts the server with
  `uv run`, and `.claude-plugin/marketplace.json` makes this repository a
  one-plugin marketplace (see [The plugin](#the-plugin)). `uv.lock` is
  refreshed for the `mcp` cap.

## Features

- Search Primo catalogue, Primo Central Index, books/videos scopes, and subscribed databases
- Always return direct Primo search links and individual record links
- Get record details including title, authors, identifiers, subjects, description, source, availability, and record ID
- Preserve Chinese and other Unicode metadata in search results, details, citations, and exports
- Generate citations in APA 7th, Harvard, Chicago, IEEE, and Vancouver styles
- Export records to BibTeX, RIS, or UTF-8-sig CSV
- Reject invalid search scopes instead of silently falling back to Everything
- Recommend configured librarians from search queries and Primo metadata (off by default; no Towson librarian directory is configured)
- Append a "Result landscape" facet summary (resource types, top subjects, creators, journals, languages, availability, publication years) so zero-result and too-many-result searches can be refined from data instead of guesswork
- Act on that landscape with generic facet filters: `facet_filters={"topic": "Economics"}` narrows to a facet value, `facet_exclusions` removes one (any Primo facet, e.g. topic, lang, jtitle, tlevel, library)
- Compound boolean queries: multi-clause AND/OR/NOT with contains/exact/begins_with operators for known-item lookups (title AND creator), exact-title checks, and OR expansion
- Show physical shelf locations (library, location, call number, availability status) and direct full-text access links (proxied resource links, Alma link-resolver openurl) in search results and record details

## Development

```bash
git clone https://github.com/ezengels/cook-primo-mcp-server.git
cd cook-primo-mcp-server
uv sync --extra dev
uv run pytest
```

Towson's OneSearch settings are the defaults, so no `.env` file is needed.

### Live checks

Every test above mocks Primo. `tests/test_live_primo.py` instead calls the
real Primo API (Towson OneSearch by default), one test per behaviour the code
relies on: scope and tab
names, query separators, date and resource-type filters, facets under
concurrent searches, guest-token record lookup for Alma and CDI records,
citation and export on real records, autocomplete, date sorting, availability
status, co-authors and article numbers on two known records, the other
USMAI libraries named on network records, and transliterated initials in a
citation. They are skipped by default and never run in CI (about 40
requests per run):

```bash
uv run pytest -m live -v
```

A failure means Primo behaves differently from what the code assumes, or
that Primo has changed; investigate it rather than loosening the test.

### The plugin

`.claude-plugin/plugin.json` declares one MCP server, `primo`, which Claude
Code starts with

```text
uv run --directory ${CLAUDE_PLUGIN_ROOT} --frozen primo-mcp-server
```

and one environment variable, `UV_PYTHON=>=3.11,<3.15`, which keeps uv off
Python 3.15, for which the locked `pydantic-core` has no wheels yet. Raise
the bound once `uv.lock` pins versions with 3.15 wheels.

uv makes the virtual environment in `.venv` inside `${CLAUDE_PLUGIN_ROOT}`,
which is a separate folder for each plugin version, the way Claude Code
itself installs a plugin's Node.js packages. Do not move it to the shared
`${CLAUDE_PLUGIN_DATA}`: with one environment for every version, the first
start after an update has to reinstall the project, and on Windows that
fails while any open session still runs the old server
(`failed to remove file ... primo-mcp-server.exe ... (os error 32)`, shown
as "Connection closed"). Claude Code deletes an old version's folder, and
its environment, 14 days after an update.

`--frozen` installs exactly what `uv.lock` pins, so run `uv lock` after any
dependency change. `--directory` starts the server in the plugin's own
directory, away from the user's project. The tools appear in Claude Code as
`mcp__plugin_primo-towson_primo__<tool>`; the longest name is 61 characters,
so keep new tool names short enough to stay under 64.

The manifest has no `version`, so every commit to `main` is a new version,
and testers get it the next time they update the marketplace. To try a change
before pushing:

```bash
claude plugin validate .
claude --plugin-dir .   # this checkout replaces the installed plugin for one session
```

### Without the plugin

To register a checkout as a plain MCP server instead:

```bash
claude mcp add primo-towson --scope user -- uv run --directory /path/to/cook-primo-mcp-server primo-mcp-server
```

## Tools

| Tool | Description |
|------|-------------|
| `primo_search` | Search Primo with field, scope, type, date, and peer-review filters |
| `primo_get_record` | Get full details for a record by Primo record ID |
| `primo_suggest` | Get autocomplete suggestions |
| `primo_recommend_librarians` | Recommend configured librarian help for a query or selected records |
| `primo_submit_librarian_choice` | Validate a caller-reasoned librarian choice against the configured directory and format it |
| `primo_list_librarians` | List every configured librarian profile with contact and coverage |
| `primo_cite` | Generate formatted citations |
| `primo_export` | Export records as BibTeX, RIS, or CSV |
| `primo_rag_retrieve` | Retrieve top records (default 5) and pin them to a session for guarded RAG answering |
| `primo_rag_validate` | Validate a draft's [R#] citations against the pinned session and build the reference list |

## RAG Citation Guardrails

`primo_rag_retrieve` and `primo_rag_validate` implement a guarded RAG loop
where deterministic code — not the model — enforces that citations point to
retrieved sources:

1. `primo_rag_retrieve` searches Primo, pins the top records to a session
   labelled `[1]`-`[n]`, and returns them with drafting rules.
2. The calling model drafts an answer citing only structured numeric `[n]`
   tags (e.g. `[1]` or grouped `[2, 4]`).
3. `primo_rag_validate` extracts every `[n]` tag, checks each ID against
   the pinned records, and on any invalid ID returns regeneration feedback
   instead of an answer.
4. Only when all IDs validate does it assemble the final answer, building
   the reference list from the pinned records' metadata (never from model
   text) in the session's citation style.

Honest limits, stated in every success response: the check proves a cited
ID *was retrieved*, not that the source supports the claim; prose citations
and uncited claims bypass it (a warn-only heuristic flags author-year
patterns); and errors in Primo metadata are reproduced as-is. Sessions are
in-memory and last only for the server process lifetime.

`demo_rag_citation_guard.py` is a dependency-free sketch of the same
pipeline with a stubbed LLM and toy corpus.

## Scope Behaviour

Use these canonical scopes. At Towson they map to these OneSearch tabs and
Primo scopes:

| Scope | Towson tab / scope | Covers | Common aliases |
|-------|--------------------|--------|----------------|
| `everything` (default) | `Everything` / `DN_and_CI` | OneSearch's default search: Towson's catalogue, the other USMAI libraries' catalogues, and article-index (CDI) records Towson can access | `all`, `combined`, `pci`, `dn_and_ci`, `myinst_and_ci` |
| `catalogue` | `TULibraryCatalog` / `MyInstitution` | Towson's own holdings only (books, ebooks, journals, databases, videos); no article index | `catalog`, `local`, `myinstitution`, `my_institution` |
| `books_videos` | `New_Network_Catalog` / `New_Discovery_Network` | The USMAI network catalogue: catalogue records from every USMAI library, no article index. Towson has no books/videos tab, so this slot is reused | `network`, `usmai`, `usmai_network`, `books/videos` |

`MyInstitution` is not listed in Towson's view configuration, but Primo serves
it and returns Towson's local records only. A title that appears under
`everything` only because another USMAI library holds it is not a Towson
holding, though Towson users can request it.

Recommended caller policy:

- For books, databases, and videos, start with `scope="catalogue"`.
- For articles, start with `scope="everything"`.
- For dataset or data-source requests, start with `scope="catalogue"` and `resource_type="databases"` to find subscribed data platforms first. Expand to articles or books only after database results are weak, irrelevant, or empty, and say that the search was expanded beyond databases.
- For catalogue searches with no results, retry with `scope="everything"` only when the user did not ask for catalogue-only results.
- For any zero-result search, reason about why the query failed and try revised `primo_search` calls up to five total attempts. Good retries may broaden an over-specific phrase, use synonyms or related concepts, try singular/plural variants, switch fields, relax filters, widen scope when permitted, search directly for likely database names, or use OR queries for close alternatives.
- When summarising an iterative search, combine all relevant results found across attempts and report the attempted queries.
- Every user-facing answer must carry a `Queries attempted:` list naming each query run and the number of results it returned, including attempts that returned zero results. Every `primo_search` result is prefixed with a `## Required search transparency` banner and carries the same obligation as `search_transparency.caller_action` in its structured content.
- For access or subscription checks, use Primo results as the evidence source rather than websites or LibGuides.

## Compound Queries

`primo_search` accepts an optional `clauses` list that compiles to Primo's
multi-clause boolean syntax and replaces the single `query`/`field` pair as
the retrieval query (`query` should still carry a short plain-text summary;
it drives librarian recommendations and display). Each clause has a `value`,
optional `field` (`any`, `title`, `creator`, `sub`, `isbn`, `issn`,
`oclcnum`), optional `operator` (`contains`, `exact`, `begins_with`), and
optional `connector` (`AND`, `OR`, `NOT`) joining it to the next clause:

```json
{
  "query": "piketty capital",
  "clauses": [
    {"field": "title", "value": "capital", "connector": "AND"},
    {"field": "creator", "value": "piketty"}
  ]
}
```

Use compound queries for known-item lookups (title AND creator), exact-title
subscription checks, genuine OR expansion across synonyms, or NOT exclusion.
The result header links to the equivalent Primo advanced search.

## Towson Configuration

Towson is the default configuration for this fork, so no `.env` file is
needed. For reference, the values are:

```env
PRIMO_BASE_URL=https://usmai-tu.primo.exlibrisgroup.com/primaws/rest/pub
PRIMO_DISCOVERY_BASE_URL=https://usmai-tu.primo.exlibrisgroup.com/discovery
PRIMO_VID=01USMAI_TU:01USMAI_TU
PRIMO_INSTITUTION_NAME=Towson University

PRIMO_TAB_EVERYTHING=Everything
PRIMO_TAB_CATALOGUE=TULibraryCatalog
PRIMO_TAB_BOOKS_VIDEOS=New_Network_Catalog

PRIMO_SCOPE_COMBINED=DN_and_CI
PRIMO_SCOPE_LOCAL=MyInstitution
PRIMO_SCOPE_BOOKS_VIDEOS=New_Discovery_Network
```

The tab and scope names come from the view's public configuration,
`https://usmai-tu.primo.exlibrisgroup.com/primaws/rest/pub/configuration/vid/01USMAI_TU:01USMAI_TU`;
the `Everything` / `DN_and_CI` pair is also what the search box on the
library home page uses.

A `.env` file is read from the directory the server starts in. The plugin
starts it in its own install directory, so a `.env` file in your project has
no effect. To change a value for every tester, add the `PRIMO_` variable to
the server's `env` in `.claude-plugin/plugin.json`. To change it only for
yourself, register the server without the plugin (see
[Without the plugin](#without-the-plugin)) and pass the value, e.g.
`claude mcp add primo-towson --scope user -e PRIMO_DEFAULT_RESULTS=20 -- ...`.

## Configuration Reference

Defaults are set for Towson. Other institutions can override these values
with environment variables (upstream's README has the SMU values):

| Variable | Default | Description |
|----------|---------|-------------|
| `PRIMO_BASE_URL` | `https://usmai-tu.primo.exlibrisgroup.com/primaws/rest/pub` | Primo API base URL |
| `PRIMO_DISCOVERY_BASE_URL` | Derived from `PRIMO_BASE_URL` | Primo web app base URL for record and search links |
| `PRIMO_VID` | `01USMAI_TU:01USMAI_TU` | Primo view ID |
| `PRIMO_INSTITUTION_CODE` | Derived from `PRIMO_VID` | Institution code for the guest JWT endpoint |
| `PRIMO_INSTITUTION_NAME` | `Towson University` | Display name |
| `PRIMO_TAB_EVERYTHING` | `Everything` | Primo tab for combined searches (`everything`) |
| `PRIMO_TAB_CATALOGUE` | `TULibraryCatalog` | Primo tab for local catalogue searches (`catalogue`) |
| `PRIMO_TAB_BOOKS_VIDEOS` | `New_Network_Catalog` | Primo tab for the third scope (`books_videos`; at Towson, the USMAI network catalogue) |
| `PRIMO_SCOPE_COMBINED` | `DN_and_CI` | Primo scope for combined searches: USMAI catalogues plus CDI |
| `PRIMO_SCOPE_LOCAL` | `MyInstitution` | Primo scope for Towson's local catalogue |
| `PRIMO_SCOPE_BOOKS_VIDEOS` | `New_Discovery_Network` | Primo scope for the third scope (at Towson, the USMAI network catalogue) |
| `PRIMO_REQUEST_TIMEOUT` | `30.0` | HTTP timeout in seconds |
| `PRIMO_REQUEST_RETRY_ATTEMPTS` | `1` | Extra attempts after a transient Primo failure (timeout, connection error, HTTP 429/5xx); `0` disables retries |
| `PRIMO_REQUEST_RETRY_MAX_DELAY` | `5.0` | Cap in seconds on the retry backoff, including a server-sent `Retry-After` |
| `PRIMO_MAX_RESULTS_PER_REQUEST` | `50` | Maximum results per search request |
| `PRIMO_DEFAULT_RESULTS` | `10` | Default results per search |
| `PRIMO_LANGUAGE` | `en` | Primo language parameter |
| `PRIMO_INCLUDE_UNAVAILABLE` | `false` | Include CDI records without full text access in search results |
| `PRIMO_SEARCH_FACETS` | `true` | Fetch the facet summary after each search and append a "Result landscape" section. At Towson every scope serves facets (at SMU only Everything does). An empty facet list for a search of 100,000+ results is retried once after 1 s, because Primo computes facets for large searches in the background |
| `PRIMO_LIBRARIANS_FILE` | unset | External JSON librarian directory used for recommendations |
| `PRIMO_INLINE_LIBRARIAN_RECOMMENDATIONS` | `false` | Put matched, evidence-bearing librarian referrals before `primo_search` results. Off by default — every librarian switch ships off, since no profile data is bundled |
| `PRIMO_LIBRARIAN_MIN_SCORE` | `5.0` | Minimum deterministic match score required before showing a recommendation |
| `PRIMO_RECOMMEND_LOG_FILE` | unset | Opt-in JSONL log of recommendation outcomes (query, status, match/near-miss ids and scores, and the matcher-relevant catalogue fields of the search records used as evidence) for triaging real queries into the golden eval set with `primo-triage`. Privacy note: this log captures raw user query text on local disk; enable it only with a retention policy in mind |
| `PRIMO_LIBRARIAN_SEMANTIC_FALLBACK` | `false` | Enable the embedding path used when keyword matching finds nothing or matches weakly |
| `PRIMO_EMBEDDING_PROVIDER` | `gemini` | `gemini` for Google's hosted API, `local` for an OpenAI-compatible local endpoint (Ollama, LM Studio, llama.cpp) with no quota |
| `PRIMO_EMBEDDING_API_KEY` | unset | Google Gemini API key for the `gemini` provider (never sent to local endpoints) |
| `PRIMO_EMBEDDING_LOCAL_API_KEY` | unset | Optional Bearer token for `local` runtimes that check one |
| `PRIMO_EMBEDDING_MODEL` | `gemini-embedding-001` | Embedding model for the `gemini` provider |
| `PRIMO_EMBEDDING_API_URL` | `https://generativelanguage.googleapis.com/v1beta` | Embedding API base URL for the `gemini` provider |
| `PRIMO_EMBEDDING_LOCAL_URL` | `http://localhost:11434/v1` | OpenAI-compatible base URL for the `local` provider (default: Ollama) |
| `PRIMO_EMBEDDING_LOCAL_MODEL` | `embeddinggemma` | Model name for the `local` provider |
| `PRIMO_EMBEDDING_LOCAL_QUERY_PREFIX` | EmbeddingGemma query prompt | Prompt prefixed to query text (stands in for Gemini's taskType); for nomic-embed-text use `search_query: ` |
| `PRIMO_EMBEDDING_LOCAL_DOCUMENT_PREFIX` | EmbeddingGemma document prompt | Prompt prefixed to profile terms; for nomic-embed-text use `search_document: `; changing it rebuilds the cache |
| `PRIMO_LIBRARIAN_SEMANTIC_MIN_SIMILARITY` | `0.60` | Absolute cosine floor for a semantic recommendation |
| `PRIMO_LIBRARIAN_SEMANTIC_MARGIN` | `0.08` | Self-calibrating margin: a match must exceed the mean similarity across all profiles by this much |
| `PRIMO_LIBRARIAN_SEMANTIC_MARGIN_MIN_PROFILES` | `4` | Directory size at which the margin rule starts applying |
| `PRIMO_LIBRARIAN_SEMANTIC_MIN_TOP_GAP` | `0.05` | Below the margin's profile minimum, the top match must lead the runner-up by this cosine gap (top-1 only) |
| `PRIMO_LIBRARIAN_SEMANTIC_MIN_QUERY_TOKENS` | `2` | Skip the semantic fallback (no embedding call) for queries with fewer topical words; `1` disables the gate |
| `PRIMO_LIBRARIAN_SEMANTIC_SECOND_GUESS_SCORE` | `12.0` | Keyword scores below this are second-guessed by the semantic path (`0` = strict miss-only cascade) |
| `PRIMO_EMBEDDING_DIMENSIONS` | unset | Optional Matryoshka truncation (e.g. `768`) to cut cache size and latency |
| `PRIMO_EMBEDDING_CACHE_FILE` | next to `PRIMO_LIBRARIANS_FILE` | Where profile embeddings are cached |
| `PRIMO_EMBEDDING_TIMEOUT` | `10.0` | HTTP timeout for embedding requests in seconds |
| `PRIMO_EMBEDDING_INLINE_TIMEOUT` | `2.5` | Tighter embedding budget for inline `primo_search` recommendations |
| `PRIMO_EMBEDDING_RETRY_ATTEMPTS` | `3` | How many times an HTTP 429 is waited out and retried (never on the inline path) |
| `PRIMO_EMBEDDING_RETRY_MAX_DELAY` | `65.0` | Cap in seconds on the wait honoured from the server's `Retry-After`/`RetryInfo` advice |
| `PRIMO_LIBRARIAN_LLM_FALLBACK` | `false` | Enable the tier-3 LLM reasoning fallback (runs only when keyword and embedding tiers both miss) |
| `PRIMO_LLM_PROVIDER` | `caller` | `caller` asks the calling model to route and validates its choice via `primo_submit_librarian_choice`; `sampling` uses MCP sampling; `openai` uses the settings below |
| `PRIMO_LLM_MAX_TOKENS` | `512` | Token budget for the reasoning completion |
| `PRIMO_LLM_URL` | `http://localhost:11434/v1` | OpenAI-compatible chat-completions endpoint (Ollama, LM Studio, vLLM, OpenAI, OpenRouter, Gemini OpenAI-compat) |
| `PRIMO_LLM_MODEL` | `gemma3:4b` | Model used for the reasoning tier |
| `PRIMO_LLM_API_KEY` | unset | Bearer token for the endpoint above; kept separate from `PRIMO_EMBEDDING_API_KEY` |
| `PRIMO_LLM_TIMEOUT` | `20.0` | HTTP timeout for the reasoning call in seconds |
| `PRIMO_LIBRARIAN_LLM_MIN_CONFIDENCE` | `0.6` | Floor on the model's self-reported confidence; a coarse gate, not a calibrated threshold |
| `PRIMO_LIBRARIAN_LLM_INLINE` | `false` | Allow the reasoning tier on inline `primo_search` recommendations (free for the `caller` backend; leave off for backends that call out) |

See `.env.example` for a commented template.

### Semantic fallback (optional)

Keyword matching is exact (after light stemming), so a query whose wording
doesn't overlap any profile term returns no recommendation. Enabling
`PRIMO_LIBRARIAN_SEMANTIC_FALLBACK=true` adds an embedding-based path that runs
when keyword matching **finds nothing or matches only weakly** (best score
below `PRIMO_LIBRARIAN_SEMANTIC_SECOND_GUESS_SCORE`), so embeddings are
computed only when keywords are unconvincing. Keyword matches stay primary and
are never displaced; a passing semantic candidate for a different librarian is
appended within the limit. It uses Google's `gemini-embedding-001` (free tier —
get a key at <https://aistudio.google.com/apikey>). Each profile term is
embedded as its own vector and a profile scores by its best term (max cosine),
so a sharp hit on one configured topic is never averaged away by the rest of a
large profile. Terms are embedded in batched `batchEmbedContents` requests,
cached to a sidecar file keyed by term content (terms shared by several
profiles are embedded once), and recomputed only when a term, the model, or
the output dimensionality changes. The cache is written after every batch,
so a rate-limited cold rebuild keeps its progress; rate-limit responses
(HTTP 429) are waited out and retried, honouring the API's own
`Retry-After`/`RetryInfo` advice, except on the latency-bounded inline
`primo_search` path, which fails closed fast instead of sleeping.

Acceptance is self-calibrating rather than a single tuned constant, with
three regimes by directory size: with at least
`PRIMO_LIBRARIAN_SEMANTIC_MARGIN_MIN_PROFILES` profiles the top matches must
exceed the mean similarity across all profiles by
`PRIMO_LIBRARIAN_SEMANTIC_MARGIN`; smaller directories accept only the top
profile and only when it leads the runner-up by
`PRIMO_LIBRARIAN_SEMANTIC_MIN_TOP_GAP`; a single-profile directory falls back
to the absolute cosine floor alone. Queries with fewer than
`PRIMO_LIBRARIAN_SEMANTIC_MIN_QUERY_TOKENS` topical words (stopwords and
filler words don't count) skip the semantic path entirely -- short or vague
queries are where cosine similarity is least reliable, and the skip happens
before any embedding call is made. Skips are reported in the output the same
way errors are, so they are never mistaken for a genuine no-match. To set the
floor, margin, and gap empirically for your own directory, print the
similarity distribution for representative test queries:

```bash
python -m primo_mcp_server.calibrate_embeddings "systematic review screening" "GIS data for urban planning"
```

#### Local embeddings (no quota)

The Gemini free tier is rate-limited; `PRIMO_EMBEDDING_PROVIDER=local`
switches the same fallback to any OpenAI-compatible `/embeddings` endpoint
running on your own machine -- Ollama, LM Studio, or a llama.cpp server --
with no quota and no key. The workload is small: a directory of up to ~30
profiles embeds once (then cached), and each search costs one query
embedding, so a small CPU model is entirely sufficient. With Ollama:

```bash
ollama pull embeddinggemma
```

```env
PRIMO_LIBRARIAN_SEMANTIC_FALLBACK=true
PRIMO_EMBEDDING_PROVIDER=local
# Defaults already target Ollama + EmbeddingGemma; override for other
# runtimes or models:
# PRIMO_EMBEDDING_LOCAL_URL=http://localhost:1234/v1   (LM Studio)
# PRIMO_EMBEDDING_LOCAL_MODEL=nomic-embed-text
# PRIMO_EMBEDDING_LOCAL_QUERY_PREFIX=search_query: 
# PRIMO_EMBEDDING_LOCAL_DOCUMENT_PREFIX=search_document: 
```

The query/document prefixes stand in for Gemini's `taskType` parameter
(EmbeddingGemma and nomic both use asymmetric retrieval prompts); set both
empty if your runtime applies its own prompt template. Two caveats: the
cosine floor default (0.60) was tuned for `gemini-embedding-001`, so re-run
`calibrate_embeddings` after switching models (the mean+margin rule
self-calibrates, the floor does not); and the first request after the
runtime starts may load the model into memory, which can exceed the tight
inline-search budget -- the explicit `primo_recommend_librarians` tool has
the full timeout and will warm it up.

The layer fails closed — only configured profiles are ever returned, and any
embedding error degrades to the keyword outcome — but not silently: errors are
logged to stderr and surfaced in the output as a
`semantic fallback errored` note so an invalid API key is distinguishable from
a genuine no-match. Semantic matches are labelled
`Status: matched (semantic fallback)` and report their cosine similarity so
callers can reason about confidence. Identifier-shaped queries (DOIs, ISBNs,
ISSNs, Alma/CDI record ids) skip librarian recommendations entirely on both
paths.

### LLM reasoning fallback (optional, tier 3)

Keyword matching and embedding similarity both compare surface forms, so
both are blind to a query whose subject is plain to a person but shares no
vocabulary with any profile — "autism" against a profile that says
"behavioural science, wellbeing, survey data" scores near zero on each, and
the min-token gate skips embedding for one-word queries entirely.

Set `PRIMO_LIBRARIAN_LLM_FALLBACK=true` to add a third tier that asks a model
to reason about that gap. It runs **only when the first two tiers return
nothing**, so the cost falls on a miss, never on a hit.

Three backends, selected with `PRIMO_LLM_PROVIDER`:

- **`caller`** (default) hands the decision to the model already calling
  this server. When keyword matching finds no librarian, the output prints
  the configured directory and asks the caller to reason about it, then to
  submit its choice to `primo_submit_librarian_choice` — which re-applies
  every validation rule in code before anything can be shown. Same two-step
  shape as `primo_rag_retrieve`/`primo_rag_validate`: the model reasons in
  the middle, code decides what may be displayed. No API key, no endpoint,
  no sampling support required, and no server-side latency — which is why
  this backend is safe to run inline on ordinary searches.
- **`sampling`** uses [MCP sampling](https://modelcontextprotocol.io/docs/concepts/sampling):
  the server asks the connected client to run the completion on the model
  already driving the conversation. No API key, no second endpoint, nothing
  extra to keep alive. Sampling is an optional part of the protocol, so a
  client may not implement it or may decline a request; either surfaces as a
  tier error and the recommendation degrades to the earlier tiers. The
  offline eval harness has no client session and must use `openai`.
  Note: Claude Code answers sampling requests with `METHOD_NOT_FOUND`, so
  `caller` is the working option for that client.
- **`openai`** points `PRIMO_LLM_URL` / `PRIMO_LLM_MODEL` at any
  OpenAI-compatible chat-completions endpoint (Ollama, LM Studio, vLLM,
  OpenAI, OpenRouter, or Gemini's OpenAI-compatible endpoint).
  `PRIMO_LLM_API_KEY` is kept separate from `PRIMO_EMBEDDING_API_KEY` so a
  Gemini key never travels to another host.

The tier is constrained in code, not by prompt alone: only ids present in the
directory survive validation (an invented id is logged and discarded, never
rendered), curator `excludes` deny-lists are re-applied afterwards, and a
choice that gives no reason is dropped, because evidence is mandatory for any
librarian shown to a user. Matches are labelled
`Status: matched (LLM reasoning)` and report the model's **self-reported
confidence** — deliberately named, since unlike a cosine it is not comparable
across queries and is never fed into the embedding tier's self-calibrating
threshold.

Like every recommendation switch, it ships off. Set
`PRIMO_LIBRARIAN_LLM_INLINE=true` to let it run on inline searches — cheap
with the `caller` backend, which makes no network call of its own, but with
`openai` or `sampling` the round trip can push inline recommendations past
their ~2.5s budget.

When `PRIMO_INLINE_LIBRARIAN_RECOMMENDATIONS=true` and a configured profile
meets the score threshold, `primo_search` puts a Markdown section headed
`## Required librarian referral` before the results. Callers MUST include every
recommended librarian's name, title, contact, and evidence in the user-facing
response. The same evidence-bearing recommendation is also exposed in the MCP
structured response with `caller_action: "include_in_user_response_with_evidence"`.

The recommendation display uses a fixed labelled format for each matched
profile:

```text
## Recommended librarian help:

Status: matched
1. Name: [Accounting Librarian](https://library.smu.edu.sg/example-profile)
   Title: Business Research Librarian
   Contact: accounting@example.edu
   Best for: Consult for accounting datasets, WRDS, and Compustat.
   Evidence: matched terms: accounting; evidence fields: query
Recommendations are limited to configured librarian profiles; do not invent or substitute names.
```

The `Name` value is always emitted as a Markdown link. The profile `url` is
used first; if it is missing, the formatter falls back to a `mailto:` link
when an email address is configured.

When no recommendation clears the confidence threshold, the `no_match`
output still shows the closest below-threshold profiles WITH their matching
evidence, explicitly labelled as not validated -- so any librarian a caller
passes on to the user always carries evidence, and a weak candidate can
never be silently presented as a confident match. When nothing matched even
weakly, the output directs callers to `primo_list_librarians`, which
returns the complete configured directory (name, title, contact, schools,
best-for areas, and a sample of subjects) so a caller can still route the
user to a real contact without inventing one.

Librarian recommendations require an external JSON file. No real profiles are
bundled. The minimum shape is:

```json
{
  "librarians": [
    {
      "id": "accounting",
      "name": "Accounting Librarian",
      "title": "Business Research Librarian",
      "email": "accounting@example.edu",
      "url": "https://library.smu.edu.sg/example-profile",
      "subjects": ["accounting", "audit fees"],
      "keywords": ["corporate governance"],
      "aliases": ["financial reporting"],
      "best_for": ["accounting datasets", "WRDS", "Compustat"],
      "schools": ["School of Accountancy"],
      "resource_types": ["databases"],
      "notes": "Consult for accounting and audit research."
    }
  ]
}
```

### Maintaining the profile directory

The `primo-profiles` CLI keeps the JSON directory reproducible from a CSV
source and reports curation problems that weaken matching:

```bash
# Build the JSON directory from a CSV source (semicolon- or comma-separated
# multi-value cells; accepts singular or plural column headers)
python -m primo_mcp_server.profile_tools convert librarian-profile.csv librarian-profile.json

# Check the configured directory (or an explicit path) for problems:
# filler-only terms, term variants that normalise identically, terms listed
# by nearly every profile, unmatchable profiles, missing contact details,
# and deny-list terms broad enough to always fire
python -m primo_mcp_server.profile_tools lint
```

`lint` exits 0 when clean, 1 with findings, and 2 when the directory cannot
be read, so it can gate a profile-update workflow.

### Measuring recommendation accuracy

The `primo-eval` CLI benchmarks the recommendation pipeline against a golden
set of labelled queries, so tuning changes to weights, thresholds, or the
semantic path are judged by a measured delta instead of anecdote:

```bash
python -m primo_mcp_server.evaluate_recommendations librarian-eval.json --keyword-only
```

The eval file lists cases of the form
`{"query": "...", "expect": ["librarian-id"]}`; an empty `expect` means the
correct outcome is no recommendation (these cases measure false positives).
Cases can pin `records` metadata for deterministic corroboration evidence.
The report gives top-1 accuracy, hit rate within the returned list, and the
correct-rejection rate. `--keyword-only` forces the deterministic path;
without it the semantic fallback runs exactly when the server would run it.
`--min-pass-rate 0.9` turns the run into a regression gate (exit 1 below the
threshold). The eval runs the same pipeline module the server uses, so its
numbers are statements about real server behaviour. The report also counts
cases with record evidence: cases without `records` never exercise the
matcher's metadata path.

To judge a change case by case rather than by one pass rate, save a run and
compare a later one against it:

```bash
python -m primo_mcp_server.evaluate_recommendations librarian-eval.json --keyword-only --save-results baseline.json
# ... change weights, thresholds or profiles ...
python -m primo_mcp_server.evaluate_recommendations librarian-eval.json --keyword-only --compare baseline.json --fail-on-regression
```

The comparison lists cases that newly fail, newly pass, or pass or fail with
a different top librarian; `--fail-on-regression` exits 1 if any case newly
fails.

#### Growing the eval set from real queries

With `PRIMO_RECOMMEND_LOG_FILE` set, `primo-triage` walks new logged queries
one at a time, shows what the server picked (scores, matched terms, near
misses) and asks for the correct label: Enter accepts the server's answer,
librarian ids override it, `-` means no librarian, `s` skips, `q` saves and
quits. Every answer is saved immediately, and the search records logged with
each query are stored in the case, so it replays the same evidence:

```bash
python -m primo_mcp_server.triage_recommendations recommend-outcomes.jsonl librarian-eval.json
```

Log lines written before records were logged carry none; add
`--fetch-records` to run one live Primo search per such query and freeze its
results into the case. `--since YYYY-MM-DD` limits the session to recent
traffic.

## Usage Examples

From a Claude Code conversation:

- "Search Towson's catalogue for books by Frederick Douglass"
- "Search OneSearch for peer-reviewed articles on Piezo1 gating and membrane tension"
- "Does Towson have full-text access to Saotome et al. 2018 in Nature?"
- "Search the USMAI network catalogue for books on Chesapeake Bay ecology"
- "Get the full details for record alma991234567890"
- "Recommend a librarian for this accounting search"
- "Generate APA7 citations for these records"
- "Export these records as BibTeX"

## Licence

MIT
