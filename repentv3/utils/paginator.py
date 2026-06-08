"""
Repent - Simple 2-button paginator for leaderboards and lists.
"""

import discord
from discord.ui import View, Button


class PaginatorView(View):
    """Simple previous/next paginator."""

    def __init__(self, pages: list, timeout: float = 120.0):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current = 0
        self.update_buttons()

    def update_buttons(self):
        for child in self.children:
            if isinstance(child, Button):
                if child.custom_id == "prev":
                    child.disabled = self.current == 0
                elif child.custom_id == "next":
                    child.disabled = self.current == len(self.pages) - 1

    async def update_message(self, interaction: discord.Interaction):
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev(self, interaction: discord.Interaction, button: Button):
        if self.current > 0:
            self.current -= 1
            await self.update_message(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next(self, interaction: discord.Interaction, button: Button):
        if self.current < len(self.pages) - 1:
            self.current += 1
            await self.update_message(interaction)


class LeaderboardPaginator(View):
    """Paginated leaderboard with rank numbers."""

    def __init__(self, entries: list, per_page: int = 10, title: str = "Leaderboard", guild=None):
        super().__init__(timeout=180.0)
        self.entries = entries
        self.per_page = per_page
        self.current = 0
        self.title = title
        self.guild = guild
        self.pages = self._build_pages()
        self.update_buttons()

    def _build_pages(self) -> list:
        pages = []
        total = len(self.entries)
        max_page = max(1, (total + self.per_page - 1) // self.per_page)
        for i in range(max_page):
            start = i * self.per_page
            end = min(start + self.per_page, total)
            embed = discord.Embed(
                title=f"🏆 {self.title}",
                color=0x4488FF,
            )
            lines = []
            for idx, entry in enumerate(self.entries[start:end], start=start + 1):
                medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(idx, f"**#{idx}**")
                member = self.guild.get_member(entry["user_id"]) if self.guild else None
                name = member.mention if member else f"<@{entry['user_id']}>"
                lines.append(f"{medal} {name} — Level **{entry['level']}** • **{entry['xp']}** XP")
            embed.description = "\n".join(lines) if lines else "No entries yet."
            embed.set_footer(text=f"Page {i + 1}/{max_page}")
            pages.append(embed)
        return pages if pages else [discord.Embed(title=f"🏆 {self.title}", description="No entries yet.", color=0x4488FF)]

    def update_buttons(self):
        for child in self.children:
            if isinstance(child, Button):
                if child.custom_id == "prev":
                    child.disabled = self.current == 0
                elif child.custom_id == "next":
                    child.disabled = self.current == len(self.pages) - 1

    async def update_message(self, interaction: discord.Interaction):
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, custom_id="prev")
    async def prev(self, interaction: discord.Interaction, button: Button):
        if self.current > 0:
            self.current -= 1
            await self.update_message(interaction)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id="next")
    async def next(self, interaction: discord.Interaction, button: Button):
        if self.current < len(self.pages) - 1:
            self.current += 1
            await self.update_message(interaction)
