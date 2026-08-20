# Command Safety & Audit Model

This document describes the command validation pipeline that enforces the
safety boundary between "AI proposes" and "hardware executes".

## Principle

> AI is the *advisor*, not the *executor*. No raw model output or external string
> is ever sent directly to the serial transport. Every command passes through a
> single validation pipeline before it can be dispatched.

## Pipeline

Every proposed command batch goes through four stages:

1. **Parse** — external output (AI text, serial string, API body) is parsed into
   strongly-typed domain commands (`RelayCommand`, `CurtainCommand`, `BuzzerCommand`).
2. **Syntax validation** — malformed text is rejected with a machine-readable reason.
3. **Domain-range validation** — relay channels and values must be in range.
4. **Permission & mode validation** — reserved channels and execute-mode gating apply.

The single source of truth is `energy_system/core/command_policy.py`. The API, AI
advisor, and serial bridge must not reimplement their own command parsing.

## Allowlist

| Command | Allowed form | AI permissions |
|---|---|---|
| `RELAY` | channels 1–4, state 0/1 | AI may only control channels 3–4; 1–2 are reserved for rule control |
| `CURTAIN` | `OPEN` / `CLOSE` / `STOP` | allowed |
| `BUZZER` | state 0/1 | allowed |

## Rejection reasons (rich)

| Reason | Meaning |
|---|---|
| `commands_not_list` | input was not a list |
| `too_many_commands` | batch exceeded `max_ai_cmds_per_cycle` (rate-limited) |
| `non_string_command` | a list item was not a non-empty string |
| `unknown_command` | unrecognized command head |
| `malformed_relay_command` | relay command not `RELAY <n> <0|1>` |
| `relay_channel_out_of_range` | relay channel not in 1–4 |
| `relay1_2_reserved_for_rules` | AI attempted to control a rule-reserved relay |
| `unknown_curtain_action` | curtain action not OPEN/CLOSE/STOP |
| `malformed_curtain_command` | malformed curtain command |
| `malformed_buzzer_command` | malformed buzzer command |

> `validate_ai_commands()` remains a deprecated compatibility entry that maps the
> rich reasons back to the legacy coarse set (`command_not_allowed`, etc.). New code
> should use `validate_commands()`.

## Execute-mode gating

- `suggest` (default) — AI output is logged and shown but never dispatched.
- `execute_safe_devices` / `execute_all` — require explicit configuration, an online
  device, safe mode off, and a minimum execution interval. These are not enabled by
  default and must never be exposed on an unauthenticated public API.

## Audit events

Every decision records an `AuditEvent` with `event_type` in
`accepted | rejected | rate_limited | not_executed`, plus `run_mode`, `candidate_id`,
`timestamp`, and a sanitized command summary. Audit records must **never** contain:

- API keys / tokens / passwords
- full authentication headers
- the full prompt
- raw sensor payloads that could be privacy-sensitive

Use `sanitize_command_for_audit()` to bound command length before logging.
