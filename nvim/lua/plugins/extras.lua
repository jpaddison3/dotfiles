return {
  -- vim-visual-multi: multiple cursors (Command-D equivalent)
  -- Default keybindings:
  --   Ctrl-n    : select word under cursor, then next occurrence (like Cmd-D)
  --   Ctrl-Down : add cursor below
  --   Ctrl-Up   : add cursor above
  --   n/N       : get next/previous occurrence (while in multi-cursor mode)
  --   q         : skip current and go to next
  --   Tab       : switch between cursor mode and extend mode
  {
    "mg979/vim-visual-multi",
    branch = "master",
    event = "VeryLazy", -- Load lazily for fast startup
  },
}
