# bb-wide instructions (symlinked to ~/.bb/AGENTS.md)

- bb expands `$BB_THREAD_STORAGE` only inside ui blocks (`Load()`, `Image()`, `Snippet()`). Anywhere else you show me a path under it, such as a Markdown link or a path in prose, expand the variable yourself and write the absolute path; a link to `$BB_THREAD_STORAGE/brief.md` shows "File not found."
