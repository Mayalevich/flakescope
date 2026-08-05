# Baseline vs LLM — accuracy on hand-labeled ground truth

| Backend | is_flake acc | category acc | (n labeled) |
|---|---|---|---|
| `heuristic` | 83% | 67% | 6 |
| `qwen2.5:3b` | 50% | 0% | 6 |
| `qwen2.5:3b (raw)` | 50% | 0% | 6 |
| `qwen2.5:7b` | 50% | 0% | 6 |

## Per-case

| Job | heuristic | qwen2.5:3b | qwen2.5:3b (raw) | qwen2.5:7b | truth |
|---|---|---|---|---|---|
| windows machine hyperv | `real_test_bug` | `unknown` | `unknown` | `unknown` | — |
| macos machine applehv | `real_test_bug` | `unknown` | `unknown` | `unknown` | — |
| sys remote root fedora-raw | `unknown` | `unknown` | `unknown` | `unknown` | infra_permission |
| build fedora-current / lim | `unknown` | `unknown` | `unknown` | `unknown` | — |
| macos machine applehv | `real_test_bug` | `unknown` | `unknown` | `real_test_bug` | — |
| sys local root fedora-prio | `real_test_bug` | `unknown` | `unknown` | `unknown` | real_test_bug |
| compose_v2  root fedora-cu | `unknown` | `unknown` | `unknown` | `timeout` | — |
| unit  root fedora-current  | `flaky_dependency` | `unknown` | `unknown` | `unknown` | flaky_dependency |
| int remote root fedora-raw | `network_timeout` | `unknown` | `unknown` | `unknown` | flaky_dependency |
| macos machine applehv | `real_test_bug` | `unknown` | `unknown` | `infra_permission` | — |
| int local root fedora-rawh | `real_test_bug` | `unknown` | `unknown` | `unknown` | real_test_bug |
| Validate source code chang | `lint_format` | `unknown` | `unknown` | `unknown` | lint_format |