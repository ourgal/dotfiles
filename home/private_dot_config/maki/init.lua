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
})
