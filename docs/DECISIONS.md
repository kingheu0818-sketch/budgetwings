# Decision Records

Each entry captures a significant design choice, the alternatives considered,
and why this path was taken. These are informal ADRs, optimized for being
skimmable.

---

## ADR-001: Use intermediate `ExtractedDeal` schema instead of exposing `Deal` to the LLM

**Context:** When introducing structured output for `price_parser`, we had to
choose what schema to expose to the LLM.

**Options considered:**
1. Expose `Deal` directly — minimal boilerplate
2. Create a simpler intermediate `ExtractedDeal` — more code but cleaner boundary
3. Flatten to plain dict — no validation

**Decision:** Option 2 (`ExtractedDeal`).

**Reasoning:**
- `Deal` has fields like `price_cny_fen` and fallback URL behavior that do not
  belong in an LLM-facing contract
- separating the LLM protocol from the domain model creates an anti-corruption
  layer between unstable model behavior and stable business code
- the conversion step becomes a single chokepoint for yuan -> fen conversion,
  booking URL fallback, and date correction

**Trade-off:** One more schema to maintain.

**Related:** `tools/price_parser.py`, T2 benchmark.

---

## ADR-002: Evidence must be a contiguous substring, not fuzzy match

**Context:** Once `evidence_text` was introduced, we needed to decide how strict
the grounding contract should be.

**Options considered:**
1. Accept fuzzy semantic similarity
2. Accept token-overlap or partial quote matching
3. Require a normalized contiguous substring of the source text

**Decision:** Option 3.

**Reasoning:**
- fuzzy matching makes the validator harder to reason about and easier to game
- a contiguous substring can be explained to humans, tested deterministically,
  and benchmarked without judgment calls
- strictness keeps the failure boundary sharp: either the evidence exists in the
  source text or it does not

**Trade-off:** Some real deals may be rejected if the model paraphrases instead
of quoting exactly.

**Related:** `tools/evidence_validator.py`, T3 benchmark.

---

## ADR-003: Keep legacy Scout alongside agentic mode

**Context:** After proving that function calling was available through the
OpenAI-compatible proxy, we had to decide whether to replace the old Scout or
let both modes coexist.

**Options considered:**
1. Replace legacy Scout entirely with agentic Scout
2. Keep both modes and choose via configuration
3. Freeze Scout and avoid agentic work for now

**Decision:** Option 2.

**Reasoning:**
- legacy mode is still cheaper and more predictable for batch jobs and CI smoke
  checks
- agentic mode is better for open-ended exploration and interactive use
- coexistence lets the benchmark tell us which path is better for a workload,
  instead of forcing a single architecture everywhere

**Trade-off:** More code paths to maintain and document.

**Related:** `agents/scout.py`, `config.py`, T4-B benchmark.

---

## ADR-004: Benchmark in mock mode by default, not real API

**Context:** Every major change in this repo needs a reproducible before/after
report, but real API runs introduce rate limits, cost, and provider variance.

**Options considered:**
1. Benchmark only against real APIs
2. Benchmark only against static fixtures
3. Default to deterministic mock mode, allow real API as an opt-in

**Decision:** Option 3.

**Reasoning:**
- mock mode gives stable deltas in CI and local review
- real API mode remains available when we want to inspect live behavior
- separating correctness from provider variance keeps the benchmark useful as an
  engineering artifact, not just a demo

**Trade-off:** Mock results cannot be over-interpreted as production latency or
provider-quality numbers.

**Related:** `scripts/bench_price_parser.py`, `scripts/bench_scout_modes.py`.

---

## ADR-005: Use three independent evidence checks instead of one fuzzy validator

**Context:** Evidence validation could have been implemented as one broad
"grounded enough" heuristic, but that would blur failure modes together.

**Options considered:**
1. One composite relevance score
2. One fuzzy textual comparison
3. Three explicit checks: evidence exists, price exists, destination exists

**Decision:** Option 3.

**Reasoning:**
- each check blocks a different class of hallucination
- independent checks produce cleaner metrics and clearer rejection reasons
- debugging is dramatically easier when the system can say *why* a deal was
  rejected instead of just saying "grounding failed"

**Trade-off:** More explicit code and slightly more verbose logging.

**Related:** `tools/evidence_validator.py`, T3 rejection breakdown.

---

## ADR-006: Use OpenAI-compatible function calling via IkunCode proxy

**Context:** T4-Probe was run against the endpoints that were actually available
in the development environment. We needed to choose a tool-calling protocol for
the first real agentic loop.

**Options considered:**
1. Native Anthropic tool use
2. OpenAI-compatible function calling through the proxy
3. Pure ReAct text prompting without native tool calls

**Decision:** Option 2.

**Reasoning:**
- the probe showed `gpt-5.4` and `gpt-5.4-mini` both passing connectivity,
  structured JSON, and tool-use checks
- building on top of a confirmed protocol is safer than designing around an
  endpoint we did not verify in practice
- OpenAI-style function calling also maps cleanly onto our `submit_deal` /
  `finish` loop design

**Trade-off:** The architecture is presently more coupled to the available
proxy path than to provider-neutral theory.

**Related:** `data/probe/T4_probe_report.md`, `llm/openai_adapter.py`.

---

## ADR-007: Allow exact-string destination fallback outside the alias table

**Context:** `EvidenceValidator` primarily relies on a hardcoded alias table,
but agentic Scout can sometimes surface a destination that is not explicitly in
that table.

**Options considered:**
1. Reject every destination not present in aliases
2. Fallback to exact-string match on the destination itself
3. Disable destination validation until aliases become data-driven

**Decision:** Option 2.

**Reasoning:**
- rejecting everything outside the alias list would artificially cap the
  usefulness of agentic exploration
- exact-string fallback is still conservative because the destination must
  appear in the quoted evidence text
- this keeps the validator useful without pretending the alias layer is already
  complete

**Trade-off:** The boundary between "inside whitelist" and "outside whitelist"
needs to be explained carefully in benchmarks and docs.

**Related:** `tools/evidence_validator.py`, `tools/destinations.py`, T4-B report.

---

## ADR-008: Every major change should ship as implementation + benchmark evidence

**Context:** This repo is meant to function both as software and as a portfolio
artifact. Claims without measurements age poorly.

**Options considered:**
1. Ship feature-only commits and explain results in PR text
2. Put all changes in one big commit
3. Pair implementation with explicit benchmark/report commits

**Decision:** Option 3.

**Reasoning:**
- it keeps the git history readable as a sequence of hypotheses and outcomes
- reviewers can inspect the code change and the evidence separately
- it forces discipline: if a change is meaningful enough to brag about, it is
  meaningful enough to benchmark

**Trade-off:** Slightly noisier history, but much stronger narrative value for
future maintainers and interview discussions.

**Related:** T2, T3, and T4-B commit structure.
