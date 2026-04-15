-- Custom keymaps on top of LazyVim defaults.
-- This file runs on VeryLazy, after all plugins have loaded,
-- so these bindings override any plugin defaults.

local map = vim.keymap.set

-- == File (<leader>f) ==
map("n", "<leader>fs", "<cmd>w<cr>", { desc = "Save file" })
map("n", "<leader>fn", "<cmd>enew<cr>", { desc = "New file" })
map("n", "<leader>fg", function()
  local path = vim.fn.fnamemodify(vim.api.nvim_buf_get_name(0), ":~:.")
  vim.fn.setreg("+", path)
  vim.notify("Copied: " .. path)
end, { desc = "Copy relative path" })
map("n", "<leader>fo", function() Snacks.picker.recent() end, { desc = "Recent files" })
map("n", "<leader>fr", function()
  vim.ui.input({ prompt = "New name: ", default = vim.fn.expand("%:t") }, function(name)
    if not name or name == "" then return end
    local old = vim.api.nvim_buf_get_name(0)
    local new = vim.fn.fnamemodify(old, ":h") .. "/" .. name
    os.rename(old, new)
    vim.cmd("edit " .. vim.fn.fnameescape(new))
    vim.cmd("bdelete #")
    vim.notify("Renamed to: " .. name)
  end)
end, { desc = "Rename file" })

-- == macOS muscle memory ==
map("i", "<M-BS>", "<C-w>", { desc = "Delete word backwards" })
map("c", "<M-BS>", "<C-w>", { desc = "Delete word backwards" })

-- == Code (<leader>c) ==
map("n", "<leader>cl", "gcc", { desc = "Toggle comment", remap = true })
map("v", "<leader>cl", "gc", { desc = "Toggle comment", remap = true })
map({ "n", "v" }, "<leader>cw", "gq", { desc = "Rewrap text", remap = true })
