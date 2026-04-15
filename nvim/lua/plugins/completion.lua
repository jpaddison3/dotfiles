return {
  {
    "saghen/blink.cmp",
    opts = function(_, opts)
      -- Remove copilot from completion menu (using native ghost text instead)
      opts.sources = opts.sources or {}
      opts.sources.default = vim.tbl_filter(function(source)
        return source ~= "copilot"
      end, opts.sources.default or {})

      -- Only show completion menu on Ctrl+Space, not automatically
      opts.completion = opts.completion or {}
      opts.completion.list = opts.completion.list or {}
      opts.completion.list.selection = { preselect = false, auto_insert = false }
      opts.completion.menu = opts.completion.menu or {}
      opts.completion.menu.auto_show = false
    end,
  },
  {
    "zbirenbaum/copilot.lua",
    opts = {
      suggestion = {
        enabled = true,
        auto_trigger = true,
        hide_during_completion = false,
        keymap = {
          accept = "<Tab>",
          next = "<M-]>",
          prev = "<M-[>",
        },
      },
    },
  },
}
