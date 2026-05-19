-- The built-in markdown ftplugin adds `t`, which hard-wraps text while typing.
-- Keep `textwidth` available for manual `gq` rewraps without inserting newlines.
vim.opt_local.formatoptions:remove({ "t", "c", "a" })

-- Keep markdown visually wrapped even when opened before LazyVim's autocmds load.
vim.opt_local.wrap = true
