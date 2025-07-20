"""
Signal Handler - Manages graceful shutdown signals and coordination
"""

import signal
import asyncio
import logging
from datetime import datetime
from typing import Callable, List, Optional
from dataclasses import dataclass
from rich.console import Console
from rich.prompt import Confirm

# Configure logging - only show warnings and errors
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

console = Console()

@dataclass
class ShutdownContext:
    """Context information for shutdown process"""
    signal_type: str
    timestamp: datetime
    force_shutdown: bool = False
    timeout_seconds: int = 10  # Reduced timeout for simpler shutdown

@dataclass
class CleanupHandler:
    """Cleanup handler registration"""
    name: str
    handler: Callable[[], None]
    priority: int = 0
    timeout: float = 5.0

class ShutdownCoordinator:
    """Coordinates the graceful shutdown process"""
    
    def __init__(self, console: Console):
        self.console = console
        self._shutdown_requested = False
        self._shutdown_event = asyncio.Event()
        self._cleanup_handlers: List[CleanupHandler] = []
        self._current_operation = "idle"
        
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested"""
        return self._shutdown_requested
    
    def get_shutdown_event(self) -> asyncio.Event:
        """Get the shutdown event for async waiting"""
        return self._shutdown_event
    
    def set_current_operation(self, operation: str):
        """Set the current operation state"""
        self._current_operation = operation
        logger.info(f"Operation state changed: {operation}")
    
    def register_cleanup_handler(self, name: str, handler: Callable[[], None], priority: int = 0):
        """Register a cleanup handler"""
        cleanup_handler = CleanupHandler(name, handler, priority)
        self._cleanup_handlers.append(cleanup_handler)
        # Sort by priority (higher priority first)
        self._cleanup_handlers.sort(key=lambda x: x.priority, reverse=True)
        logger.info(f"Registered cleanup handler: {name} (priority: {priority})")
    
    async def initiate_shutdown(self, signal_type: str, force: bool = False) -> None:
        """Initiate the shutdown process"""
        if self._shutdown_requested and not force:
            return
        
        context = ShutdownContext(
            signal_type=signal_type,
            timestamp=datetime.now(),
            force_shutdown=force
        )
        
        logger.info(f"Shutdown initiated: signal={signal_type}, force={force}, operation={self._current_operation}")
        
        # Show shutdown message
        if force:
            self.console.print("\n[red]Force shutdown initiated...[/red]")
        else:
            self.console.print(f"\n[yellow]Graceful shutdown requested ({signal_type})...[/yellow]")
        
        self._shutdown_requested = True
        self._shutdown_event.set()
        
        # Perform cleanup
        await self._cleanup_resources(context)
    
    async def _cleanup_resources(self, context: ShutdownContext) -> None:
        """Perform resource cleanup"""
        start_time = datetime.now()
        self.console.print("[blue]Cleaning up resources...[/blue]")
        
        cleanup_tasks = []
        for handler in self._cleanup_handlers:
            try:
                logger.info(f"Starting cleanup: {handler.name}")
                
                # Create cleanup task with timeout
                if asyncio.iscoroutinefunction(handler.handler):
                    task = asyncio.create_task(handler.handler())
                else:
                    # Wrap sync function in async
                    task = asyncio.create_task(asyncio.to_thread(handler.handler))
                
                cleanup_tasks.append((handler.name, task))
                
            except Exception as e:
                logger.error(f"Error starting cleanup for {handler.name}: {e}")
        
        # Wait for all cleanup tasks with timeout
        if cleanup_tasks:
            try:
                # Wait for all tasks with overall timeout
                await asyncio.wait_for(
                    asyncio.gather(*[task for _, task in cleanup_tasks], return_exceptions=True),
                    timeout=context.timeout_seconds
                )
                
                for name, task in cleanup_tasks:
                    if task.done():
                        if task.exception():
                            logger.error(f"Cleanup failed for {name}: {task.exception()}")
                        else:
                            logger.info(f"Cleanup completed for {name}")
                    else:
                        logger.warning(f"Cleanup timeout for {name}")
                        task.cancel()
                        
            except asyncio.TimeoutError:
                logger.warning(f"Cleanup timeout after {context.timeout_seconds} seconds")
                # Cancel remaining tasks
                for _, task in cleanup_tasks:
                    if not task.done():
                        task.cancel()
        
        cleanup_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Cleanup completed in {cleanup_time:.2f} seconds")
        
        self.console.print(f"[green]Shutdown complete. Goodbye![/green]")

class SignalHandler:
    """Handles system signals for graceful shutdown"""
    
    def __init__(self, shutdown_coordinator: ShutdownCoordinator):
        self.shutdown_coordinator = shutdown_coordinator
        self._signal_count = 0
        self._last_signal_time = None
        self._force_threshold = 2  # Force shutdown after 2 rapid signals
        self._rapid_signal_window = 2.0  # 2 seconds window
        
    def setup_handlers(self) -> None:
        """Setup signal handlers"""
        try:
            # Handle SIGINT (Ctrl+C)
            signal.signal(signal.SIGINT, self._handle_sigint)
            
            # Handle SIGTERM (termination request)
            signal.signal(signal.SIGTERM, self._handle_sigterm)
            
            logger.info("Signal handlers registered successfully")
            
        except Exception as e:
            logger.error(f"Failed to register signal handlers: {e}")
            # Fallback to basic KeyboardInterrupt handling
    
    def _handle_sigint(self, signum: int, frame) -> None:
        """Handle SIGINT (Ctrl+C) signal"""
        current_time = datetime.now()
        
        # Check for rapid successive signals
        if self._last_signal_time:
            time_diff = (current_time - self._last_signal_time).total_seconds()
            if time_diff < self._rapid_signal_window:
                self._signal_count += 1
            else:
                self._signal_count = 1
        else:
            self._signal_count = 1
        
        self._last_signal_time = current_time
        
        # Determine if force shutdown is needed
        force_shutdown = self._signal_count >= self._force_threshold
        
        if force_shutdown:
            logger.warning(f"Multiple SIGINT signals received ({self._signal_count}), forcing shutdown")
        
        # Create task to handle shutdown asynchronously
        asyncio.create_task(
            self.shutdown_coordinator.initiate_shutdown("SIGINT", force=force_shutdown)
        )
    
    def _handle_sigterm(self, signum: int, frame) -> None:
        """Handle SIGTERM signal"""
        logger.info("SIGTERM received, initiating graceful shutdown")
        
        # SIGTERM always forces shutdown without confirmation
        asyncio.create_task(
            self.shutdown_coordinator.initiate_shutdown("SIGTERM", force=True)
        )