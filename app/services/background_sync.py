"""Background Gmail mailbox synchronization worker with dynamic active-mailbox switching.

Features:
- Runs as an asynchronous worker task started during FastAPI lifespan.
- Automatically resolves the current active Mailbox from the database.
- Checks active Gmail inbox incrementally every SYNC_INTERVAL_SECONDS (default 30s).
- Concurrency control: asyncio.Lock prevents simultaneous sync operations.
- Non-blocking: executes blocking IMAP operations in threadpool (asyncio.to_thread).
- Supports seamless mailbox switching: cancels current loop safely and restarts for new mailbox.
- Bounded exponential backoff on consecutive network/IMAP failures.
- Updates worker and sync states with detailed diagnostic status.
- Clean shutdown on application exit.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import SessionLocal
from app.models.mailbox_model import Mailbox
from app.models.sync_model import SyncState
from app.services.mailbox_service import MailboxService
from app.services.sync_service import EmailSyncService, SyncResult

logger = logging.getLogger("gmail_fastapi.background_sync")


class BackgroundSyncWorker:
    """Manages periodic asynchronous background synchronization of Gmail emails."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._lock: Optional[asyncio.Lock] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self._consecutive_errors: int = 0
        self._last_sync_result: Optional[SyncResult] = None
        self._last_error: Optional[str] = None
        self._last_sync_time: Optional[datetime] = None

    @property
    def lock(self) -> asyncio.Lock:
        """Lazily initialize asyncio.Lock inside active event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @property
    def stop_event(self) -> asyncio.Event:
        """Lazily initialize asyncio.Event inside active event loop."""
        if self._stop_event is None:
            self._stop_event = asyncio.Event()
        return self._stop_event

    @property
    def is_running(self) -> bool:
        """Whether the background worker loop is active."""
        return self._is_running

    @property
    def is_syncing(self) -> bool:
        """Whether a synchronization operation is currently actively running."""
        return self._lock.locked() if self._lock is not None else False

    @property
    def worker_status(self) -> str:
        """Current operational status string."""
        if not self._is_running:
            return "stopped"
        if self.is_syncing:
            return "syncing"
        if self._consecutive_errors > 0:
            return "error"
        return "idle"

    async def start(self) -> None:
        """Start the background synchronization worker loop."""
        if self._is_running:
            logger.warning("Background sync worker is already running.")
            return

        self.stop_event.clear()
        self._is_running = True
        self._consecutive_errors = 0
        self._task = asyncio.create_task(self._run_loop(), name="gmail-background-sync")
        logger.info(
            "Background Gmail sync worker started (Interval: %ds)",
            self.settings.SYNC_INTERVAL_SECONDS,
        )

    async def stop(self, db: Optional[Session] = None) -> None:
        """Stop the background sync worker cleanly."""
        if not self._is_running:
            return

        logger.info("Stopping background Gmail sync worker...")
        self._is_running = False
        self.stop_event.set()

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                current_loop = asyncio.get_running_loop()
                if self._task.get_loop() is current_loop:
                    await asyncio.wait_for(self._task, timeout=2.0)
            except Exception:
                pass

        self._task = None

        # Update database state
        try:
            if db:
                active_mb = MailboxService(db=db, settings=self.settings).get_active_mailbox()
                if active_mb:
                    state = (
                        db.query(SyncState)
                        .filter(SyncState.mailbox_id == active_mb.id)
                        .first()
                    )
                    if state:
                        state.worker_status = "stopped"
                        db.commit()
            else:
                with SessionLocal() as local_db:
                    active_mb = MailboxService(db=local_db, settings=self.settings).get_active_mailbox()
                    if active_mb:
                        state = (
                            local_db.query(SyncState)
                            .filter(SyncState.mailbox_id == active_mb.id)
                            .first()
                        )
                        if state:
                            state.worker_status = "stopped"
                            local_db.commit()
        except Exception:
            pass

        logger.info("Background Gmail sync worker stopped cleanly.")

    async def restart_for_active_mailbox(self) -> None:
        """Wait for any active sync to finish safely, then restart loop for the newly active mailbox."""
        logger.info("Restarting background sync worker for newly active mailbox...")
        async with self.lock:
            # Stop existing loop task
            if self._is_running:
                self._is_running = False
                self.stop_event.set()
                if self._task and not self._task.done():
                    self._task.cancel()
                    try:
                        await asyncio.wait_for(self._task, timeout=3.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass
                self._task = None

            # Reset error counts and launch fresh loop
            self.stop_event.clear()
            self._is_running = True
            self._consecutive_errors = 0
            self._task = asyncio.create_task(self._run_loop(), name="gmail-background-sync")
            logger.info("Background sync worker restarted successfully.")

    async def sync_now(self, batch_size: int = 50) -> SyncResult:
        """Execute a synchronization run with concurrency protection.

        Can be called manually from API endpoints or periodically by the loop.
        """
        async with self.lock:
            return await asyncio.to_thread(self._execute_sync_in_thread, batch_size)

    def _execute_sync_in_thread(self, batch_size: int) -> SyncResult:
        """Run EmailSyncService within a dedicated database session in a thread."""
        with SessionLocal() as db:
            mailbox_service = MailboxService(db=db, settings=self.settings)
            active_mb = mailbox_service.get_active_mailbox()

            if not active_mb and not self.settings.is_configured:
                raise RuntimeError("No Gmail account is configured or active.")

            sync_service = EmailSyncService(db=db, settings=self.settings, mailbox=active_mb)
            state = sync_service.get_or_create_sync_state()
            state.worker_status = "syncing"
            db.commit()

            try:
                result = sync_service.sync_inbox(batch_size=batch_size)
                self._last_sync_result = result
                self._last_sync_time = datetime.now(timezone.utc)
                self._last_error = None
                self._consecutive_errors = 0

                state.worker_status = "idle"
                db.commit()
                return result
            except Exception as err:
                self._last_error = str(err)
                self._consecutive_errors += 1
                state.worker_status = "error"
                db.commit()
                raise

    async def _run_loop(self) -> None:
        """Periodic background execution loop."""
        interval = max(5, self.settings.SYNC_INTERVAL_SECONDS)

        # Small startup delay
        try:
            await asyncio.sleep(2)
        except asyncio.CancelledError:
            return

        while not self.stop_event.is_set():
            # Check if active mailbox exists
            has_active_mb = False
            try:
                with SessionLocal() as db:
                    mb = MailboxService(db=db, settings=self.settings).get_active_mailbox()
                    has_active_mb = mb is not None or self.settings.is_configured
            except Exception:
                has_active_mb = False

            if not has_active_mb:
                logger.debug("Background sync idle: No active mailbox configured.")
                try:
                    await asyncio.wait_for(self.stop_event.wait(), timeout=interval)
                except asyncio.TimeoutError:
                    pass
                except asyncio.CancelledError:
                    break
                continue

            try:
                logger.debug("Background sync worker starting scheduled inbox check...")
                result = await self.sync_now(batch_size=50)
                if result.new_emails_synced > 0:
                    logger.info(
                        "Background sync retrieved %d new email(s) for active mailbox %s (Total in DB: %d).",
                        result.new_emails_synced,
                        result.message,
                        result.total_synced_in_db,
                    )
                else:
                    logger.debug("Background sync completed: no new emails.")
            except Exception as err:
                logger.warning(
                    "Background sync attempt failed (consecutive errors: %d): %s",
                    self._consecutive_errors,
                    str(err),
                )

            # Compute backoff if consecutive errors occur
            if self._consecutive_errors > 0:
                backoff_multiplier = min(2 ** min(self._consecutive_errors, 4), 10)
                current_wait = min(interval * backoff_multiplier, 300)
                logger.info("Applying retry backoff of %d seconds before next sync attempt.", current_wait)
            else:
                current_wait = interval

            try:
                await asyncio.wait_for(self.stop_event.wait(), timeout=current_wait)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break


# Global singleton worker instance
_global_worker: Optional[BackgroundSyncWorker] = None


def get_sync_worker(settings: Optional[Settings] = None) -> BackgroundSyncWorker:
    """Retrieve or initialize the global BackgroundSyncWorker instance."""
    global _global_worker
    if _global_worker is None:
        _global_worker = BackgroundSyncWorker(settings=settings)
    return _global_worker
