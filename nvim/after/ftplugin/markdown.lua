-- The built-in markdown ftplugin adds `t`, which hard-wraps text while typing.
-- Keep `textwidth` available for manual `gq` rewraps without inserting newlines.
vim.opt_local.formatoptions:remove({ "t", "c", "a" })

-- LazyVim sets `formatexpr` to its conform/LSP formatter. When `formatexpr` is
-- set, `gq` (and our <leader>cw) routes through it instead of the built-in
-- paragraph reflow — and since no markdown formatter line-wraps, gq silently
-- does nothing. Clear it so gq falls back to the built-in reflow at textwidth.
vim.opt_local.formatexpr = ""

-- Keep markdown visually wrapped even when opened before LazyVim's autocmds load.
vim.opt_local.wrap = true
