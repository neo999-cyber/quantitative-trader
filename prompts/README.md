# Prompt library

These are the four "prompts that actually print", written so they can be pasted
into Claude (or any LLM) as-is, plus the evening screen prompt used in the daily
workflow.  Each one ends with an output contract so the answer drops straight
into a candidate file for `centaur gauntlet`.

Every prompt asks the model to state what it could **not** verify.  An AI that
sounds confident about data it never saw is the fastest way to lose money.

| File | Role |
|---|---|
| `01_pattern_matcher.md` | Historical Pattern Matcher |
| `02_catalyst_synthesizer.md` | Catalyst Synthesizer |
| `03_options_flow_vulture.md` | Options Flow Vulture |
| `04_regime_checker.md` | Regime Checker |
| `05_evening_screen.md` | The nightly "find me 5 stocks" prompt (Centaur step 1) |
| `system_quant_screener.md` | System prompt: the AI's role and its output rules |
