---
name: doc-sync
description: Use when code changes may require documentation updates, and you need a fast mapping from change type to required docs in this repo.
---

# Documentation sync

Read `.github/instructions/documentation.instructions.md` for the authoritative
change-to-doc mapping and DRY conventions.

1. Identify changed behavior and developer workflows from the full task diff.
2. Update the owning reference document and any affected overview or translation.
3. Check claims against the implementation, including fallback behavior and
   missing-data cases. Do not document proposed behavior as already implemented.
4. Verify relative links and remove stale duplicate guidance.
