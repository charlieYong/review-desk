# Working on Review Desk

## Read by task

- Feature changes: read [Review workflow](README.md#review-workflow), [Use and deployment boundaries](README.md#use-and-deployment-boundaries), and [Project structure](README.md#project-structure). Update the documented behavior when it changes.
- Installation, startup, or deployment: follow [INSTALL.md](INSTALL.md) for environment checks and verify the running service.
- Agent review links or revisions to a shared document: use [Give your agent review links](README.md#give-your-agent-review-links). For user-level configuration, follow [Configure agent review links](INSTALL.md#5-configure-agent-review-links).

## Development

- Keep Python serving HTML, CSS, and JavaScript directly. Keep runtime assets local and use Node.js for browser testing.
- Changes to note storage, document URLs, or review rounds must preserve existing notes and history and verify migration from browser-local data. Follow the round and revision behavior described in [Review workflow](README.md#review-workflow).

## Verification

- Run the full [browser test suite](README.md#browser-tests) after changing server or frontend behavior. Check existing coverage in `tests/browser.cjs` and add a case when the changed behavior is missing.
- Use isolated temporary content and state directories and synthetic fixtures.
- For deployments, use [Verify the running service](INSTALL.md#4-verify-the-running-service). Report any interaction checks still pending. HTTP 200 confirms reachability.

## Public documentation

- Write the primary documentation in English and update the corresponding Chinese guide for user-facing changes.
- Use placeholders such as `<username>` and `<server-ip>` in sample paths, commands, and URLs. Keep addresses with a generic technical purpose such as `127.0.0.1`, `::1`, `0.0.0.0`, and `::`.
- Review the final documentation diff for real machine names, usernames, and network addresses.
