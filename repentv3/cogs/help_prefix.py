"""Repent - Prefix commands (removed)

This project is now slash-command only.

The original repository contained prefix commands like:
- xsetup, xconfig, xantinuke enable/status

Those were removed to ensure all usable commands are available as app_commands
(slash commands) and to avoid any confusion.
"""

# Intentionally empty; keep file so imports/cog loading won't crash if any
# tooling expects it. Main loader will still load this extension, but there
# are no commands registered.

async def setup(bot):
    return

