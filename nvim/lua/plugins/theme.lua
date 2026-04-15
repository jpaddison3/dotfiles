-- Auto dark/light theme based on macOS system appearance.
-- Checks on startup via `defaults read`. No live switching in terminal nvim
-- (that would require a GUI frontend like Neovide).
local function is_dark_mode()
  return vim.fn.system("defaults read -g AppleInterfaceStyle 2>/dev/null"):find("Dark") ~= nil
end

return {
  {
    "folke/tokyonight.nvim",
    opts = {
      style = "night",
    },
  },
  {
    "LazyVim/LazyVim",
    opts = function(_, opts)
      if is_dark_mode() then
        opts.colorscheme = "tokyonight-night"
      else
        opts.colorscheme = "tokyonight-day"
      end
    end,
  },
}
