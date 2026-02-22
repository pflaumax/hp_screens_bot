"""APScheduler 30-minute interval setup for the screengrab bot.

Provides clean start/stop lifecycle and handles missed jobs gracefully.
"""

import logging
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger("hp_bot.scheduler")


class BotScheduler:
    """Manages the periodic posting schedule."""

    def __init__(
        self,
        post_func: Callable[[], None],
        interval_minutes: int = 30,
    ) -> None:
        """Initialise the scheduler.

        Args:
            post_func: The function to call each interval.
            interval_minutes: Minutes between posts.
        """
        self._scheduler = BackgroundScheduler(timezone="UTC")
        self._scheduler.add_job(
            func=post_func,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id="screengrab_post",
            name=f"Post HP screengrab every {interval_minutes} minutes",
            coalesce=True,
            max_instances=1,
            misfire_grace_time=300,
        )

    def start(self) -> None:
        """Start the scheduler."""
        self._scheduler.start()
        logger.info("Scheduler started.")

    def stop(self) -> None:
        """Gracefully shut down the scheduler."""
        self._scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
