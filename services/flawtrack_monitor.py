"""
FlawTrack API Health Monitoring Service
Provides real-time health monitoring and status tracking for FlawTrack API
"""
import os
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from utils.flawtrack_config import get_flawtrack_api
import logging

logger = logging.getLogger(__name__)

@dataclass
class HealthStatus:
    """Health status data structure"""
    timestamp: datetime
    healthy: bool
    status: str
    message: str
    response_time_ms: int
    api_version: str
    service_info: Optional[dict] = None

class FlawTrackMonitor:
    """
    FlawTrack API health monitoring service

    Provides real-time health checks, status history, and alerting
    """

    def __init__(self):
        self.current_status: Optional[HealthStatus] = None
        self.status_history: List[HealthStatus] = []
        self.max_history_size = 100  # Keep last 100 health checks
        self.monitoring_enabled = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.check_interval = int(os.getenv('FLAWTRACK_HEALTH_CHECK_INTERVAL', '300'))  # 5 minutes
        self._stop_monitoring = threading.Event()

    def start_monitoring(self) -> bool:
        """
        Start background health monitoring

        Returns:
            True if monitoring started successfully, False otherwise
        """
        if self.monitoring_enabled:
            logger.info("FlawTrack monitoring is already running")
            return True

        try:
            self.monitoring_enabled = True
            self._stop_monitoring.clear()

            self.monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="FlawTrackMonitor"
            )
            self.monitor_thread.start()

            logger.info(f"FlawTrack health monitoring started (interval: {self.check_interval}s)")
            return True

        except Exception as e:
            logger.error(f"Failed to start FlawTrack monitoring: {str(e)}")
            self.monitoring_enabled = False
            return False

    def stop_monitoring(self):
        """Stop background health monitoring"""
        if not self.monitoring_enabled:
            return

        self.monitoring_enabled = False
        self._stop_monitoring.set()

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)

        logger.info("FlawTrack health monitoring stopped")

    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring_enabled and not self._stop_monitoring.is_set():
            try:
                self.check_health()
                # Wait for next check or stop signal
                self._stop_monitoring.wait(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(30)  # Wait before retrying

    def check_health(self) -> HealthStatus:
        """
        Perform a health check on the FlawTrack API

        Returns:
            HealthStatus object with current status
        """
        try:
            api = get_flawtrack_api()

            if not api:
                status = HealthStatus(
                    timestamp=datetime.utcnow(),
                    healthy=False,
                    status='error',
                    message='FlawTrack API not configured',
                    response_time_ms=0,
                    api_version='unknown'
                )
            else:
                # Perform actual health check
                health_result = api.health_check()

                status = HealthStatus(
                    timestamp=datetime.utcnow(),
                    healthy=health_result.get('healthy', False),
                    status=health_result.get('status', 'unknown'),
                    message=health_result.get('message', ''),
                    response_time_ms=health_result.get('response_time_ms', 0),
                    api_version=health_result.get('api_version', 'unknown'),
                    service_info=health_result.get('service_info')
                )

            # Update current status
            self.current_status = status

            # Add to history
            self._add_to_history(status)

            # Log status changes
            if self._is_status_change(status):
                if status.healthy:
                    logger.info(f"FlawTrack API is healthy - {status.message} ({status.response_time_ms}ms)")
                else:
                    logger.warning(f"FlawTrack API is unhealthy - {status.message}")

            return status

        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")

            status = HealthStatus(
                timestamp=datetime.utcnow(),
                healthy=False,
                status='error',
                message=f'Health check failed: {str(e)}',
                response_time_ms=0,
                api_version='unknown'
            )

            self.current_status = status
            self._add_to_history(status)

            return status

    def get_current_status(self) -> Optional[HealthStatus]:
        """Get the current health status"""
        return self.current_status

    def get_status_history(self, hours: int = 24) -> List[HealthStatus]:
        """
        Get health status history for the specified time period

        Args:
            hours: Number of hours to look back (default: 24)

        Returns:
            List of HealthStatus objects
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [
            status for status in self.status_history
            if status.timestamp >= cutoff_time
        ]

    def get_availability_stats(self, hours: int = 24) -> Dict:
        """
        Get availability statistics for the specified time period

        Args:
            hours: Number of hours to analyze (default: 24)

        Returns:
            Dictionary with availability statistics
        """
        history = self.get_status_history(hours)

        if not history:
            return {
                'availability_percentage': 0.0,
                'total_checks': 0,
                'healthy_checks': 0,
                'unhealthy_checks': 0,
                'average_response_time_ms': 0,
                'last_healthy': None,
                'last_unhealthy': None
            }

        total_checks = len(history)
        healthy_checks = sum(1 for status in history if status.healthy)
        unhealthy_checks = total_checks - healthy_checks

        # Calculate availability percentage
        availability = (healthy_checks / total_checks) * 100 if total_checks > 0 else 0

        # Calculate average response time for healthy checks
        healthy_response_times = [
            status.response_time_ms for status in history
            if status.healthy and status.response_time_ms > 0
        ]
        avg_response_time = sum(healthy_response_times) / len(healthy_response_times) if healthy_response_times else 0

        # Find last healthy and unhealthy timestamps
        last_healthy = None
        last_unhealthy = None

        for status in reversed(history):  # Most recent first
            if status.healthy and last_healthy is None:
                last_healthy = status.timestamp
            elif not status.healthy and last_unhealthy is None:
                last_unhealthy = status.timestamp

            if last_healthy and last_unhealthy:
                break

        return {
            'availability_percentage': round(availability, 2),
            'total_checks': total_checks,
            'healthy_checks': healthy_checks,
            'unhealthy_checks': unhealthy_checks,
            'average_response_time_ms': round(avg_response_time, 0),
            'last_healthy': last_healthy,
            'last_unhealthy': last_unhealthy
        }

    def _add_to_history(self, status: HealthStatus):
        """Add status to history and maintain size limit"""
        self.status_history.append(status)

        # Remove old entries if we exceed the maximum size
        if len(self.status_history) > self.max_history_size:
            self.status_history = self.status_history[-self.max_history_size:]

    def _is_status_change(self, new_status: HealthStatus) -> bool:
        """Check if the status has changed from the previous check"""
        if not self.status_history or len(self.status_history) < 2:
            return True

        previous_status = self.status_history[-2]  # Second to last (before current one)
        return previous_status.healthy != new_status.healthy

    def is_monitoring_enabled(self) -> bool:
        """Check if monitoring is currently enabled"""
        return self.monitoring_enabled

    def get_monitoring_info(self) -> Dict:
        """Get information about the monitoring service"""
        return {
            'monitoring_enabled': self.monitoring_enabled,
            'check_interval_seconds': self.check_interval,
            'history_size': len(self.status_history),
            'max_history_size': self.max_history_size,
            'thread_alive': self.monitor_thread.is_alive() if self.monitor_thread else False,
            'last_check': self.current_status.timestamp if self.current_status else None
        }

# Global monitor instance
_monitor_instance: Optional[FlawTrackMonitor] = None

def get_monitor() -> FlawTrackMonitor:
    """Get the global FlawTrack monitor instance"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = FlawTrackMonitor()
    return _monitor_instance

def start_monitoring() -> bool:
    """Start FlawTrack API monitoring"""
    monitor = get_monitor()
    return monitor.start_monitoring()

def stop_monitoring():
    """Stop FlawTrack API monitoring"""
    monitor = get_monitor()
    monitor.stop_monitoring()

def get_health_status() -> Optional[HealthStatus]:
    """Get current FlawTrack API health status"""
    monitor = get_monitor()
    return monitor.get_current_status()

def perform_health_check() -> HealthStatus:
    """Perform an immediate health check"""
    monitor = get_monitor()
    return monitor.check_health()