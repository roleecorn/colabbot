"""Unified event-system package."""

from .event_cog import EventCog


async def setup(bot):
    await bot.add_cog(EventCog(bot))
