# Baseline (heuristic) vs LLM

Model: `qwen2.5:3b` · agreement with baseline: **4/11 (36%)**


| Job | Heuristic | LLM | Agree? |
|---|---|---|---|
| macos machine applehv | `real_test_bug` | `real_test_bug` | ✅ |
| sys local root fedora-prior  | `real_test_bug` | `timeout` | ⚠️ |
| compose_v2  root fedora-curr | `unknown` | `lint_format` | ⚠️ |
| unit  root fedora-current /  | `flaky_dependency` | `network_timeout` | ⚠️ |
| int remote root fedora-rawhi | `network_timeout` | `real_test_bug` | ⚠️ |
| macos machine applehv | `real_test_bug` | `infra_permission` | ⚠️ |
| int local root fedora-rawhid | `real_test_bug` | `real_test_bug` | ✅ |
| Validate source code changes | `lint_format` | `lint_format` | ✅ |
| windows machine hyperv | `real_test_bug` | `real_test_bug` | ✅ |
| sys local root fedora-rawhid | `unknown` | `flaky_dependency` | ⚠️ |
| upgrade v5.6.2 root fedora-c | `unknown` | `lint_format` | ⚠️ |