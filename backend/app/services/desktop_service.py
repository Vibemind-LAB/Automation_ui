"""Live Desktop Service for TRAE Backend

Provides desktop streaming, screenshot capture, and automation capabilities
for the Live Desktop System integration.
"""

import asyncio
import base64
import json
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from ..logger_config import get_logger

logger = get_logger("desktop_service")


class LiveDesktopService:
    """Service for managing live desktop streaming and automation"""

    def __init__(self):
        self.initialized = False
        self.streaming_active = False
        self.connected_clients: Dict[str, Dict[str, Any]] = {}
        self.stream_config = {
            "quality": "medium",
            "frame_rate": 30,
            "compression": "jpeg",
            "scale_factor": 1.0,
        }
        self.screenshot_cache: Optional[bytes] = None
        self.last_screenshot_time = 0
        # The app polls about five times a second. A longer cache made the picture
        # lag a full second behind what happens on the screen.
        self.screenshot_cache_duration = 0.2
        # monitor index (1 = primary, as mss counts) -> (time, jpeg bytes)
        self._monitor_cache: Dict[int, tuple] = {}

        # Stream callbacks for WebSocket connections
        self.frame_callbacks: List[Callable[[bytes], None]] = []

    async def initialize(self):
        """Initialize the desktop service"""
        if self.initialized:
            logger.warning("⚠️ LiveDesktopService already initialized")
            return

        try:
            logger.info("🖥️ Initializing LiveDesktopService...")

            # Initialize desktop capture capabilities
            await self._initialize_desktop_capture()

            # Test screenshot capability
            test_screenshot = await self.take_screenshot()
            if test_screenshot:
                logger.info("✅ Desktop screenshot capability verified")
            else:
                logger.warning(
                    "⚠️ Desktop screenshot test failed, but service will continue"
                )

            self.initialized = True
            logger.info("✅ LiveDesktopService initialized successfully")

        except Exception as e:
            logger.error(f"❌ LiveDesktopService initialization failed: {e}")
            raise

    async def _initialize_desktop_capture(self):
        """Initialize desktop capture system"""
        try:
            # Try to import required libraries for desktop capture
            # Note: This is a placeholder - actual implementation would depend on
            # the specific desktop capture library being used (e.g., PIL, opencv, etc.)

            # For now, we'll use a mock implementation
            logger.info("🔧 Desktop capture system initialized (mock implementation)")

        except ImportError as e:
            logger.warning(f"⚠️ Desktop capture library not available: {e}")
            logger.info("ℹ️ Service will run in mock mode")

    def get_status(self) -> Dict[str, Any]:
        """Get current service status"""
        return {
            "initialized": self.initialized,
            "streaming_active": self.streaming_active,
            "connected_clients": len(self.connected_clients),
            "client_list": list(self.connected_clients.keys()),
            "stream_config": self.stream_config.copy(),
            "last_screenshot_time": self.last_screenshot_time,
            "frame_callbacks_count": len(self.frame_callbacks),
        }

    async def configure_streaming(self, config: Dict[str, Any]) -> bool:
        """Configure streaming parameters"""
        try:
            logger.info(f"🔧 Configuring streaming with: {config}")

            # Validate and update configuration
            if "quality" in config and config["quality"] in ["low", "medium", "high"]:
                self.stream_config["quality"] = config["quality"]

            if "frame_rate" in config and 1 <= config["frame_rate"] <= 60:
                self.stream_config["frame_rate"] = config["frame_rate"]

            if "compression" in config and config["compression"] in [
                "jpeg",
                "png",
                "webp",
            ]:
                self.stream_config["compression"] = config["compression"]

            if "scale_factor" in config and 0.1 <= config["scale_factor"] <= 2.0:
                self.stream_config["scale_factor"] = config["scale_factor"]

            logger.info(f"✅ Streaming configuration updated: {self.stream_config}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to configure streaming: {e}")
            return False

    async def take_screenshot(
        self, encode_base64: bool = False, monitor: int = 1
    ) -> Optional[str | bytes]:
        """Take a JPEG screenshot of one monitor (1 = primary, as mss counts)."""
        try:
            current_time = time.time()

            cached = self._monitor_cache.get(monitor)
            if cached and current_time - cached[0] < self.screenshot_cache_duration:
                screenshot_data = cached[1]
            else:
                screenshot_data = await self._capture_desktop(monitor)
                if not screenshot_data:
                    logger.warning("⚠️ Screenshot capture returned no data")
                    return None
                self._monitor_cache[monitor] = (current_time, screenshot_data)
                if monitor == 1:
                    self.screenshot_cache = screenshot_data
                    self.last_screenshot_time = current_time

            if encode_base64:
                return base64.b64encode(screenshot_data).decode("utf-8")
            return screenshot_data

        except Exception as e:
            logger.error(f"❌ Screenshot capture failed: {e}")
            return None

    @staticmethod
    def _list_monitors() -> List[Dict[str, Any]]:
        """The real monitors, in the order mss numbers them (1-based)."""
        import mss

        with mss.mss() as sct:
            real = sct.monitors[1:]
        return [
            {
                "index": position,
                "primary": position == 1,
                "geometry": {
                    "left": int(mon["left"]),
                    "top": int(mon["top"]),
                    "width": int(mon["width"]),
                    "height": int(mon["height"]),
                },
            }
            for position, mon in enumerate(real, start=1)
        ]

    async def list_monitors(self) -> List[Dict[str, Any]]:
        """Monitor list with geometry; empty when the screen cannot be read."""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._list_monitors)
        except Exception as e:
            logger.error(f"❌ Failed to list monitors: {e}")
            return []

    async def _capture_desktop(self, monitor: int = 1) -> Optional[bytes]:
        """Capture one monitor with mss and return JPEG bytes."""
        try:
            import io

            import mss
            from PIL import Image

            loop = asyncio.get_event_loop()

            def _grab():
                with mss.mss() as sct:
                    # Index 0 is "all monitors combined"; real monitors start at 1.
                    if monitor < 1 or monitor >= len(sct.monitors):
                        return None
                    sct_img = sct.grab(sct.monitors[monitor])
                    img = Image.frombytes("RGB", sct_img.size, sct_img.rgb)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=70)
                    return buf.getvalue()

            return await loop.run_in_executor(None, _grab)

        except Exception as e:
            logger.error(f"❌ Desktop capture failed: {e}", exc_info=True)
            return None

    async def start_streaming(
        self, client_id: str, client_info: Dict[str, Any], monitor_id: str = "monitor_0"
    ) -> bool:
        """Start desktop streaming for a client on a specific monitor

        Args:
            client_id: Unique identifier for the client
            client_info: Arbitrary info about the client
            monitor_id: Target monitor identifier (e.g., 'monitor_0')
        """
        try:
            logger.info(
                f"🎬 Starting desktop streaming for client: {client_id} on monitor: {monitor_id}"
            )

            # Register or update client
            self.connected_clients[client_id] = {
                "client_info": client_info,
                "connected_at": datetime.now().isoformat(),
                "stream_active": True,
                "monitor_id": monitor_id,
            }

            # Start streaming if not already active
            if not self.streaming_active:
                await self._start_stream_loop()

            logger.info(
                f"✅ Desktop streaming started for client: {client_id} on {monitor_id}"
            )
            return True

        except Exception as e:
            logger.error(
                f"❌ Failed to start streaming for client {client_id} on {monitor_id}: {e}"
            )
            return False

    async def stop_streaming(
        self, client_id: str, monitor_id: Optional[str] = None
    ) -> bool:
        """Stop desktop streaming for a client

        Args:
            client_id: Unique client identifier
            monitor_id: Optional monitor identifier (ignored for now, kept for API compatibility)
        """
        try:
            logger.info(
                f"🛑 Stopping desktop streaming for client: {client_id}{' on ' + monitor_id if monitor_id else ''}"
            )

            # Remove client if exists
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]

            # Stop streaming loop if there are no clients left
            if not self.connected_clients:
                await self._stop_stream_loop()

            logger.info(
                f"✅ Desktop streaming stopped for client: {client_id}{' on ' + monitor_id if monitor_id else ''}"
            )
            return True

        except Exception as e:
            logger.error(
                f"❌ Failed to stop streaming for client {client_id}{' on ' + monitor_id if monitor_id else ''}: {e}"
            )
            return False

    async def _start_stream_loop(self):
        """Start the streaming loop"""
        if self.streaming_active:
            return

        self.streaming_active = True
        logger.info("🎬 Starting desktop stream loop")

        # Start streaming task
        asyncio.create_task(self._stream_loop())

    async def _stop_stream_loop(self):
        """Stop the streaming loop"""
        self.streaming_active = False
        logger.info("🛑 Desktop stream loop stopped")

    async def _stream_loop(self):
        """Main streaming loop"""
        frame_interval = 1.0 / self.stream_config["frame_rate"]

        while self.streaming_active and self.connected_clients:
            try:
                # Capture frame
                frame_data = await self.take_screenshot()

                if frame_data and self.frame_callbacks:
                    # Send frame to all registered callbacks
                    for callback in self.frame_callbacks:
                        try:
                            callback(frame_data)
                        except Exception as e:
                            logger.error(f"❌ Frame callback error: {e}")

                # Wait for next frame
                await asyncio.sleep(frame_interval)

            except Exception as e:
                logger.error(f"❌ Stream loop error: {e}")
                await asyncio.sleep(1.0)  # Error recovery delay

        self.streaming_active = False
        logger.info("🏁 Stream loop ended")

    def add_frame_callback(self, callback: Callable[[bytes], None]):
        """Add a callback for frame data"""
        self.frame_callbacks.append(callback)
        logger.debug(f"📡 Frame callback added, total: {len(self.frame_callbacks)}")

    def remove_frame_callback(self, callback: Callable[[bytes], None]):
        """Remove a frame callback"""
        if callback in self.frame_callbacks:
            self.frame_callbacks.remove(callback)
            logger.debug(
                f"📡 Frame callback removed, total: {len(self.frame_callbacks)}"
            )

    async def get_screen_info(self) -> Dict[str, Any]:
        """Screen information read from the real monitors."""
        monitors = await self.list_monitors()
        if not monitors:
            return {"screens": [], "monitors": [], "capture_available": False}
        geometries = [m["geometry"] for m in monitors]
        left = min(g["left"] for g in geometries)
        top = min(g["top"] for g in geometries)
        right = max(g["left"] + g["width"] for g in geometries)
        bottom = max(g["top"] + g["height"] for g in geometries)
        primary = geometries[0]
        return {
            "screens": [
                {
                    "id": m["index"],
                    "primary": m["primary"],
                    "width": m["geometry"]["width"],
                    "height": m["geometry"]["height"],
                    "x": m["geometry"]["left"],
                    "y": m["geometry"]["top"],
                    "scale_factor": 1.0,
                }
                for m in monitors
            ],
            "monitors": monitors,
            "resolution": {"width": primary["width"], "height": primary["height"]},
            "total_width": right - left,
            "total_height": bottom - top,
            "capture_available": True,
        }

    async def get_available_monitors(self) -> List[Dict[str, Any]]:
        """Get list of available desktop monitors/clients for streaming

        Returns:
            List of available monitors with their metadata
        """
        try:
            logger.debug("🖥️ Getting available monitors for desktop streaming...")

            # In a real implementation, this would query actual monitor information
            # For now, we'll return mock data based on common multi-monitor setups
            monitors = [
                {
                    "id": "monitor_0",
                    "name": "Primary Monitor",
                    "status": "available",
                    "resolution": {"width": 1920, "height": 1080},
                    "isPrimary": True,
                    "x": 0,
                    "y": 0,
                    "scale_factor": 1.0,
                    "streaming": False,
                },
                {
                    "id": "monitor_1",
                    "name": "Secondary Monitor",
                    "status": "available",
                    "resolution": {"width": 1920, "height": 1080},
                    "isPrimary": False,
                    "x": 1920,
                    "y": 0,
                    "scale_factor": 1.0,
                    "streaming": False,
                },
            ]

            # Update streaming status based on connected clients
            for monitor in monitors:
                monitor_id = monitor["id"]
                # Check if any client is streaming from this monitor
                monitor["streaming"] = any(
                    client_info.get("stream_active", False)
                    and client_info.get("monitor_id") == monitor_id
                    for client_info in self.connected_clients.values()
                )

            logger.info(f"✅ Found {len(monitors)} available monitors")
            return monitors

        except Exception as e:
            logger.error(f"❌ Failed to get available monitors: {e}")
            # Return empty list on error to avoid breaking the WebSocket handler
            return []

    async def cleanup(self):
        """Cleanup the desktop service"""
        logger.info("🧹 Cleaning up LiveDesktopService...")

        try:
            # Stop streaming
            self.streaming_active = False

            # Clear connected clients
            self.connected_clients.clear()

            # Clear callbacks
            self.frame_callbacks.clear()

            # Clear cache
            self.screenshot_cache = None

            self.initialized = False
            logger.info("✅ LiveDesktopService cleanup completed")

        except Exception as e:
            logger.error(f"❌ LiveDesktopService cleanup error: {e}")
            raise


# Global service instance
_desktop_service_instance = None


def get_desktop_service() -> LiveDesktopService:
    """Get desktop service instance (singleton pattern)."""
    global _desktop_service_instance
    if _desktop_service_instance is None:
        _desktop_service_instance = LiveDesktopService()
    return _desktop_service_instance
