"""Backward-compatible extension name for the unified event Cog.

New deployments should load ``gitRely.event_cog``. Keeping this tiny module
means existing ``--ext gitRely.event`` commands do not load the old behavior.
"""

from .event_cog import EventCog

event = EventCog


async def setup(bot):
    await bot.add_cog(EventCog(bot))
