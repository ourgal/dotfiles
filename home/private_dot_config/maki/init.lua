maki.setup({
  plugins = {
    completion = { enabled = true },
  },
  net = {
    allowed_private_hosts = {
      "28.0.0.0/8",
      "fc00::/16",
    },
  },
  ui = {
    -- The shared notifier below replaces maki's built-in turn-end notice.
    notifications = "off",
  },
})

-- Delegate task-end notification to the shared agent notifier so every agent
-- uses one implementation. A shell string runs via bash on Unix and via
-- agent.shell (Git Bash) on Windows, so the same script works on both.
local home = (maki.uv.os_homedir() or ""):gsub("\\", "/")
local notifier = string.format("%q", home .. "/.local/bin/notify-agent-done")
maki.api.create_autocmd("TurnEnd", {
  callback = function(ev)
    maki.fn.jobstart(notifier .. " Maki \"Answer complete\"", {
      -- Jobs die with the autocmd dispatch unless scoped to a session.
      scope = { session = ev.data.session_id },
      stdout = false,
      stderr = false,
    })
  end,
})
