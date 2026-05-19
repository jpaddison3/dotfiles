-- Options are set by LazyVim with sensible defaults.
-- Override or add your own here. See :help vim.opt

-- Leader key: Space (LazyVim default, but explicit is good)
vim.g.mapleader = " "
vim.g.maplocalleader = "\\"

-- Line numbers
vim.opt.number = true
vim.opt.relativenumber = true

-- Tabs: 2 spaces (matches your JS/TS background)
vim.opt.tabstop = 2
vim.opt.shiftwidth = 2
vim.opt.expandtab = true

-- System clipboard integration (yank/paste works with Cmd-C/Cmd-V)
vim.opt.clipboard = "unnamedplus"

-- Rewrap width for gq / <leader>cw
vim.opt.textwidth = 100

-- Don't auto-insert newlines in normal text; use gq / <leader>cw for deliberate rewraps.
vim.opt.formatoptions:remove({ "t", "a" })
vim.api.nvim_create_autocmd("FileType", {
  group = vim.api.nvim_create_augroup("jp_no_auto_hard_wrap", { clear = true }),
  pattern = "*",
  callback = function()
    vim.opt_local.formatoptions:remove({ "t", "a" })
  end,
})

-- Visually wrap long lines by default.
vim.opt.wrap = true

-- Highlight the cursor line
vim.opt.cursorline = true

-- Keep markdown formatting characters visible (like VS Code)
vim.opt.conceallevel = 0
