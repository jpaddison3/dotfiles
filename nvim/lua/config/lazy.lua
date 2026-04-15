-- This is the main lazy.nvim setup file.
-- It tells lazy.nvim to load LazyVim as the base config,
-- then layer your custom plugins from lua/plugins/ on top.

require("lazy").setup({
  spec = {
    -- LazyVim: the distribution. This single line pulls in ~30 plugins
    -- (telescope, treesitter, which-key, lualine, etc.) with good defaults.
    {
      "LazyVim/LazyVim",
      import = "lazyvim.plugins",
    },
    -- LazyVim "extras" — opt-in modules. Each adds a coherent feature set.
    -- Browse all available extras: https://www.lazyvim.org/extras
    { import = "lazyvim.plugins.extras.ai.copilot" },
    -- Your custom plugins (from lua/plugins/*.lua)
    { import = "plugins" },
  },
  defaults = {
    lazy = false, -- LazyVim defaults to lazy-loading; this respects that
    version = false, -- Use latest git commits, not releases (more up-to-date)
  },
  performance = {
    rtp = {
      -- Disable some built-in vim plugins we don't need (faster startup)
      disabled_plugins = {
        "gzip",
        "tarPlugin",
        "tohtml",
        "tutor",
        "zipPlugin",
      },
    },
  },
})
