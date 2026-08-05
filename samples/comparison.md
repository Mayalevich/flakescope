# Baseline vs LLM — accuracy on hand-labeled ground truth

| Backend | is_flake acc | category acc | (n labeled) |
|---|---|---|---|
| `heuristic` | 88% | 75% | 8 |
| `qwen2.5:7b` | 62% | 12% | 8 |
| `qwen2.5:7b (raw)` | 62% | 12% | 8 |

## Per-case

| Job | heuristic | qwen2.5:7b | qwen2.5:7b (raw) | truth |
|---|---|---|---|---|
| sys remote rootless fedora | `network_timeout` | `unknown` | `unknown` | — |
| windows machine hyperv | `real_test_bug` | `unknown` | `unknown` | real_test_bug |
| apiv2  rootless fedora-cur | `unknown` | `unknown` | `unknown` | — |
| windows machine hyperv | `real_test_bug` | `unknown` | `unknown` | real_test_bug |
| macos machine applehv | `real_test_bug` | `unknown` | `unknown` | real_test_bug |
| sys remote root fedora-raw | `unknown` | `unknown` | `unknown` | infra_permission |
| build fedora-current / lim | `unknown` | `unknown` | `unknown` | — |
| macos machine applehv | `real_test_bug` | `real_test_bug` | `real_test_bug` | real_test_bug |
| sys local root fedora-prio | `real_test_bug` | `unknown` | `unknown` | real_test_bug |
| compose_v2  root fedora-cu | `unknown` | `timeout` | `timeout` | — |
| unit  root fedora-current  | `flaky_dependency` | `unknown` | `unknown` | flaky_dependency |
| int remote root fedora-raw | `network_timeout` | `unknown` | `unknown` | flaky_dependency |