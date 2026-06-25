# SAP-Consulting-Change-Advisor

An agent kit using context engineering, hooks, and project memory.

## Quick start

1. Prepare input JSON (use `examples/sample-input.json`).
2. Run:
   ```powershell
   .\run-agent.ps1 -InputPath .\examples\sample-input.json -AgentRoot . -MemoryRoot .\memory -BundleOutPath .\artifacts\context-bundle.txt
   ```
3. Copy `artifacts/context-bundle.txt` into Copilot Desktop.
4. Ask for JSON output matching `schemas/output.schema.json`.
5. Save model output to a file and run:
   ```powershell
   .\hooks\post-validate-output.ps1 -OutputPath .\artifacts\model-output.json
   ```

## What this kit gives you

- Deterministic input and output contracts
- Pre-hooks for input and PII guards
- Post-hook for output completeness checks
- Ordered memory folders for reusable project knowledge
