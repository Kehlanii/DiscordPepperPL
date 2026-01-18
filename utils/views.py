from typing import Any, Dict, List

import discord

from .config import Config


class DealPaginator(discord.ui.View):
    def __init__(self, deals: List[Dict[str, Any]], author: discord.User):
        super().__init__(timeout=180)
        self.deals = deals
        self.author = author
        self.current_page = 0
        self.total_pages = len(deals)

        self.btn_prev = discord.ui.Button(label="⬅️", style=discord.ButtonStyle.secondary)
        self.btn_prev.callback = self.on_prev

        self.btn_next = discord.ui.Button(label="➡️", style=discord.ButtonStyle.primary)
        self.btn_next.callback = self.on_next

        self.btn_close = discord.ui.Button(label="🗑️", style=discord.ButtonStyle.danger)
        self.btn_close.callback = self.on_close

        self._refresh_view()

    def _create_embed(self) -> discord.Embed:
        deal = self.deals[self.current_page]

        embed = discord.Embed(
            title=deal["title"][:250],
            url=deal["link"] if deal["link"] else None,
            color=Config.COLOR_PRIMARY,
        )

        price_text = "Darmowa" if deal.get("price") == "0 zł" else (deal["price"] or "---")
        if deal["next_best_price"]:
            price_text += f"  ~~{deal['next_best_price']}~~"

        embed.add_field(name="💰 Cena", value=f"**{price_text}**", inline=True)
        embed.add_field(name="🏪 Sklep", value=deal["merchant"], inline=True)

        temp = deal["temperature"]
        if temp >= 500:
            emoji = "🌋"
        elif temp >= 100:
            emoji = "🔥"
        elif temp > 0:
            emoji = "👍"
        else:
            emoji = "❄️"

        embed.add_field(name=f"{emoji} Ocena", value=f"{temp}°", inline=True)

        if deal["voucher_code"]:
            embed.add_field(name="🎫 Kod", value=f"```\n{deal['voucher_code']}\n```", inline=False)

        if deal["image_url"]:
            embed.set_thumbnail(url=deal["image_url"])

        embed.set_footer(
            text=f"Okazja {self.current_page + 1} z {self.total_pages} • Pepper.pl",
            icon_url="https://static.pepper.pl/assets/img/favicons/favicon-32x32.png",
        )
        return embed

    def _refresh_view(self):
        """Rebuilds the view's items."""
        self.clear_items()

        self.btn_prev.disabled = self.current_page == 0
        self.btn_next.disabled = self.current_page == self.total_pages - 1

        self.add_item(self.btn_prev)
        self.add_item(self.btn_next)
        self.add_item(self.btn_close)

        current_url = self.deals[self.current_page].get("link")
        if current_url:
            btn_link = discord.ui.Button(
                label="🔗 Idź do okazji", style=discord.ButtonStyle.link, url=current_url
            )
            self.add_item(btn_link)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("🚫 To nie jest twoje menu.", ephemeral=True)
            return False
        return True

    async def on_prev(self, interaction: discord.Interaction):
        self.current_page -= 1
        self._refresh_view()
        await interaction.response.edit_message(embed=self._create_embed(), view=self)

    async def on_next(self, interaction: discord.Interaction):
        self.current_page += 1
        self._refresh_view()
        await interaction.response.edit_message(embed=self._create_embed(), view=self)

    async def on_close(self, interaction: discord.Interaction):
        await interaction.message.delete()

    def get_initial_embed(self):
        return self._create_embed()
