# Share annotations across browsers

Implemented design. See the [review workflow](../README.md#review-workflow) and [installation guide](../INSTALL.md) for current usage.

## Before the change

Notes, rounds, and history lived in browser localStorage, keyed by the full document URL. Sharing the link shared the source but each browser had its own notes. Opening one file through a content-directory URL or an absolute-path URL could also create separate local reviews.

## Shared storage

1. Resolve both kinds of page URL to the same real absolute source path. Symlink aliases share a review. Files in different directories keep separate identities, even when their names match.
2. The first shared review read persists an initial round and source revision, even for a document without notes. State is saved under the application state directory. The filename is derived from the document path and the JSON records the underlying document identity.
3. Submit each action separately under the single server process's lock. A fresh addition merges with other additions. Editing, deleting, or changing the resolution status checks the original entry and returns HTTP 409 on conflict. Save through an atomic file replacement.
4. The server checks the active round and content revision. Starting a round archives all saved notes together. A note submitted after the round changes is rejected and kept as a draft by the client.
5. Clients read shared updates on open, reload, focus, visibility changes, and a 15-second visible-page polling interval. A draft survives updates, including a round started by another visitor.

History holds notes and quotes. Use the source project's revision history for older versions of the document itself.

## Existing browser notes

The review page finds legacy entries at the current origin and resolves old content URLs and absolute-path URLs to the same document. It imports legacy arrays and round-and-history objects while retaining the local originals. A previously imported snapshot is skipped, including after a note from that snapshot was deleted. Same-round, same-revision entries merge. Older revisions go into history. Legacy notes with no recorded revision are associated with the source at import time.

Each browser with old notes must open the relevant file on its original site origin. Users with review tabs open during an upgrade should reload before saving. See [Upgrading from browser-local notes](../README.md#upgrading-from-browser-local-notes).

## Project document paths

Keep project sources in the project's documentation directory and use the locate endpoint to obtain a review URL. Updating the same file keeps the link and its history. Use the standalone content directory for drafts with no project home. The [agent template](../README.md#give-your-agent-review-links) describes the handoff.

## Verification

The [shared review regression suite](../tests/shared.cjs) uses independent browser contexts to verify concurrent additions, stale operations, polling and draft preservation, persistence after restart, in-place updates and archived rounds, path aliases, and legacy migration. These browser contexts exercise shared behavior. Deployment verification covers real client connectivity separately.
