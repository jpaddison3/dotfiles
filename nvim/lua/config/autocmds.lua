-- Disable auto-wrap-while-typing in every buffer; preserve textwidth so `gq` still rewraps.
vim.api.nvim_create_autocmd("FileType", {
  pattern = "*",
  callback = function()
    vim.opt_local.formatoptions:remove("t")
  end,
})

-- Switch theme to match macOS appearance when nvim regains focus.
vim.api.nvim_create_autocmd("FocusGained", {
  callback = function()
    local dark = vim.fn.system("defaults read -g AppleInterfaceStyle 2>/dev/null"):find("Dark") ~= nil
    local target = dark and "tokyonight-night" or "tokyonight-day"
    if vim.g.colors_name ~= target then
      vim.cmd.colorscheme(target)
    end
  end,
})
