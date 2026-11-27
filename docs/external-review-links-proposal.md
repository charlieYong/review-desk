# Short links for external reviews

**Implemented design.** See the [review workflow](../README.md#review-workflow) for current user instructions. External reviews use addresses such as `/_review/订单玩法/9vMm1PGyLTV7DoEf`. The short name identifies the document to readers, and the stable ID locates it on the server. The catalog and review state store the server's absolute path.

## What reviewers see

| Surface | Behavior |
| --- | --- |
| Address bar and copied review link | `/_review/订单玩法/9vMm1PGyLTV7DoEf`, with a short document name and a fixed-length ID |
| Review document selector | `PRODUCT.md`. When names repeat, append the shortest project or directory label that distinguishes them. |
| Review breadcrumb, library, and directory browser | A project label and project-relative path, such as `orders / docs / 产品方案 / PRODUCT.md`. For a standalone document, use the file name and paths relative to its containing directory. |
| Directory browser address | `/_browse/orders/R8p6Jx2VbW5zQ3mL/docs`, with the project label, scope ID, and current directory relative to that scope |
| Copied review summary | Use the short review link as the source reference. |

The existing `/_fs` URL puts the server path in the address bar, and the review toolbar derives its label from that URL. The library and shared review API also return the absolute path. Shortening the address alone would leave those other disclosures in place. Generate the display label on the server and use it for library search and review metadata. The browser-facing review response can omit the internal `documentId` field once consumers use the public ID or canonical page.

## Choose the short name

- Use the first level-one Markdown heading or the HTML title, with spaces rendered as hyphens. Fall back to the file name without its extension when a title is missing, unusable, or looks like a filesystem path. A dated file such as `latency-report-20261125.md` with the heading `最近 30 天耗时调查` has a link such as `/_review/最近-30-天耗时调查/kQ7m2Cw9FuA4nJ5p`.
- If documents have the same short name, add a distinguishing project label or project-relative directory name, with the file name as a fallback. Limit the name to one URL segment with a bound on its encoded length. Preserve readable Chinese characters and use ordinary percent-encoding in the actual URL.
- Resolve the review by ID. After the title changes, newly shared links use the current name, and links with an earlier name or with the ID alone open the same review and resolve to the current address.

## Directory browser addresses

Use `/_browse/<project-label>/<scope-id>/<relative-directory>` for external directories. Reuse the source resource scope ID. The project label is the public display name, and a standalone directory uses `standalone` as its label. For example, a document in `docs` opens `/_browse/orders/R8p6Jx2VbW5zQ3mL/docs` from its parent-directory action. From there, the parent opens `/_browse/orders/R8p6Jx2VbW5zQ3mL/`, and a child named `reports` opens `/_browse/orders/R8p6Jx2VbW5zQ3mL/docs/reports`.

The directory URL identifies the same folder regardless of which document opened it. Stop upward navigation at the Git worktree root or, for a standalone scope, the directory that created the scope. The review action opens the document's named review link. Preserve the scope as browsing context when opening a child document whose default scope differs, and copy the canonical review URL for sharing.

## Resolve links on the server

1. Allocate a random, URL-safe document ID on first registration of an external document. Persist it with the real source path in `catalog.json` under the existing lock and atomic write. Use the same ID for repeated locates, symlink aliases, and edits at the same path. Files with the same name in different directories get separate IDs. Ordinary links for files under the content directory keep their current form.
2. Let `/_preview/locate` accept the server path as it does today. Return the canonical review route in a new `review` field, alongside the existing `page` field for opening the source. Existing callers can still build `/_review?page=…` from `page`. New callers can share `review` directly.
3. Serve external source documents and their relative resources under a scoped URL such as `/_d/<scope-id>/docs/plan.md`. Map that scope to the Git worktree root or, for a standalone document, its containing directory. The preview frame and the review frame use the scoped source URL as their base, so `./` and `../` resolve within the scope. This lets the public review link stay short while Markdown links, images, HTML styles, and directory navigation still use their normal relative paths. Resolve targets within the scope after following symlinks.

The new links remove server path components from generated URLs and interface data. Review Desk's existing network access model still applies. Previously shared URLs already contain their paths, and authored document content can itself contain identifying information.

## Upgrade behavior

- Resolve old `/_review?page=/_fs/…` bookmarks and the old `page` parameter form to the canonical short review link once registration succeeds. Continue accepting old `/_fs` source URLs and the absolute-path locate input.
- Resolve old external `/_browse?page=…&dir=…` bookmarks to the scoped directory address.
- Keep the existing real source path as the internal storage identity. Backfill catalog IDs from existing catalog and review records without rewriting review files. Match browser-local notes from legacy URLs to the same canonical document and retain the existing import deduplication. Updating the source in place keeps the link, review rounds, and notes. Moving it follows the existing rule that a new path creates a new document identity.
- The state directory backup also preserves short links. If a source disappears, keep its registration and review history so the same link works when the file returns. If registration cannot write, locate reports the existing error and a usable legacy review can still load and save notes. A short link whose mapping cannot be read needs a clear error.

## Acceptance checks

- Locate and open external documents with long parent paths, duplicate file names, and Chinese titles. Verify their shared URLs show meaningful short names and the host path prefix is absent from the address, selector, breadcrumb, directory browser, library payload, review response, and copied summary.
- Verify that duplicate titles get useful context, long titles and reserved characters stay within one bounded URL segment, and changing a title updates the shared address while an earlier name and the bare ID still reach the same review.
- Open the same source through its old bookmark, its new link, and a symlink. Verify they share existing notes and history. Verify browser-local import on the original site, two different files with the same name, and stable links after a server restart or a temporary missing file.
- Open HTML and Markdown through the short link and standalone preview. Follow a sibling document, view a parent-relative resource within the worktree, and use the directory actions. Run the existing browser, shared review, and library suites with isolated fixtures.
- Reach the same directory from two documents and from an old bookmark. Verify the same scoped address, nested paths, the upper navigation limit, and the review action's canonical share address.
