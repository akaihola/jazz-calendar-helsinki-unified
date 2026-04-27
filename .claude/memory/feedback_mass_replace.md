---
name: Use sd for mass replacement
description: For project-wide rename/replace operations, use rg to verify the match set, then sd for the actual replacement, instead of many Edit calls
type: feedback
originSessionId: bc5c4c27-acbf-4683-a986-efa44615b124
---
For mass string replacements across many files (e.g. project rename, identifier rename, URL change), use `sd` (find-and-replace CLI) for the actual substitution. First run `rg <pattern>` to verify exactly what would be replaced; then run `sd <pattern> <replacement> <files>` to apply.

**Why:** Doing many individual Read/Edit cycles for a single mass-rename is slow and repetitive. The user explicitly directed this workflow during a Helsinki→Finland project rename.

**How to apply:** When the same string needs to change in 5+ places across multiple files, prefer `rg` (verify) then `sd` (replace). Reserve the Edit tool for surgical, file-specific changes.
