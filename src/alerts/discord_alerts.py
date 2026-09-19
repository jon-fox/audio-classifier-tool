import requests
import traceback
from datetime import datetime
from src.config import settings
from src.config.constants import DISCORD_ALERTS_ENABLED
from src.config.settings import AWS_ENABLED, get_setting
from src.logger.logger_setup import logger


class DiscordAlerter:
    def __init__(self):
        self.webhook_url = None
        self.instance_id = "UNKNOWN"

        if not DISCORD_ALERTS_ENABLED:
            logger.info("Discord alerts disabled (set DISCORD_ALERTS=true to enable)")
            return

        try:
            self.webhook_url = get_setting(settings.DISCORD_WEBHOOK_URL)
            if not self.webhook_url:
                logger.warning(
                    "DISCORD_ALERTS is enabled but no webhook is configured, alerts disabled"
                )
            # Use lazy import to avoid circular dependency
            self.instance_id = self._get_instance_id() or "UNKNOWN"
        except Exception as e:
            logger.error(f"Failed to initialize Discord alerter: {e}")
            self.webhook_url = None

    def _get_instance_id(self):
        """Lazy import to avoid circular dependency"""
        if not AWS_ENABLED:
            return None
        try:
            from src.cloud.aws.ec2 import get_instance_id

            return get_instance_id()
        except ImportError as e:
            logger.warning(f"Could not import get_instance_id: {e}")
            return None

    def send_error_alert(
        self, error, context="", episode_name="", podcast_name="", additional_info=None
    ):
        """
        Send a detailed error alert to Discord

        Args:
            error: The exception object or error message
            context: Additional context about where the error occurred
            episode_name: Name of the episode being processed when error occurred
            podcast_name: Name of the podcast being processed when error occurred
            additional_info: Dictionary of additional information to include
        """
        if not self.webhook_url:
            logger.debug("Discord alerts disabled, skipping alert")
            return False

        try:
            # Build the error message
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

            # Extract error details
            if isinstance(error, Exception):
                error_type = type(error).__name__
                error_message = str(error)
                # Get traceback if available
                tb_str = (
                    traceback.format_exc()
                    if hasattr(error, "__traceback__")
                    else "No traceback available"
                )
            else:
                error_type = "Error"
                error_message = str(error)
                tb_str = "No traceback available"

            # Build the alert message
            message_parts = [
                "🚨 **AUDIOCLASSIFIER APP ERROR ALERT** 🚨",
                f"**Timestamp:** {timestamp}",
                f"**Instance ID:** {self.instance_id}",
            ]

            if podcast_name:
                message_parts.append(f"**Podcast:** {podcast_name}")

            if episode_name:
                message_parts.append(f"**Episode:** {episode_name}")

            if context:
                message_parts.append(f"**Context:** {context}")

            message_parts.extend(
                [
                    f"**Error Type:** {error_type}",
                    f"**Error Message:** {error_message}",
                ]
            )

            if additional_info:
                message_parts.append("**Additional Info:**")
                for key, value in additional_info.items():
                    message_parts.append(f"  • {key}: {value}")

            # Add truncated traceback (Discord has message limits)
            if tb_str and tb_str != "No traceback available":
                # Truncate traceback to avoid Discord message limits (2000 chars)
                tb_lines = tb_str.split("\n")
                if len(tb_str) > 1000:
                    tb_str = "\n".join(tb_lines[:10]) + "\n... (traceback truncated)"

                message_parts.append(f"**Traceback:**\n```\n{tb_str}\n```")

            final_message = "\n".join(message_parts)

            # Ensure message doesn't exceed Discord's 2000 character limit
            if len(final_message) > 1900:
                final_message = final_message[:1900] + "\n... (message truncated)"

            # Send to Discord
            payload = {"content": final_message}
            response = requests.post(self.webhook_url, json=payload, timeout=10)

            if response.status_code == 204:
                logger.info("Discord error alert sent successfully")
                return True
            else:
                logger.error(
                    f"Failed to send Discord alert. Status: {response.status_code}, Response: {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Error sending Discord alert: {e}")
            return False

    def send_processing_alert(
        self,
        message_type,
        podcast_name="",
        episode_name="",
        additional_info=None,
        alert_title="PROCESSING",
    ):
        """
        Send processing status alerts (success, start, etc.)

        Args:
            message_type: Type of message (success, started, warning, etc.)
            podcast_name: Name of the podcast
            episode_name: Name of the episode
            additional_info: Dictionary of additional information
        """
        if not self.webhook_url:
            logger.debug("Discord alerts disabled, skipping alert")
            return False

        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

            emoji_map = {
                "success": "✅",
                "started": "🚀",
                "warning": "⚠️",
                "info": "ℹ️",
            }

            emoji = emoji_map.get(message_type, "📢")

            message_parts = [
                f"{emoji} **AUDIOCLASSIFIER {alert_title} UPDATE**",
                f"**Type:** {message_type.upper()}",
                f"**Timestamp:** {timestamp}",
                f"**Instance ID:** {self.instance_id}",
            ]

            if podcast_name:
                message_parts.append(f"**Podcast:** {podcast_name}")

            if episode_name:
                message_parts.append(f"**Episode:** {episode_name}")

            if additional_info:
                for key, value in additional_info.items():
                    message_parts.append(f"**{key}:** {value}")

            final_message = "\n".join(message_parts)

            payload = {"content": final_message}
            response = requests.post(self.webhook_url, json=payload, timeout=10)

            if response.status_code == 204:
                logger.info(f"Discord {message_type} alert sent successfully")
                return True
            else:
                logger.error(
                    f"Failed to send Discord {message_type} alert. Status: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"Error sending Discord processing alert: {e}")
            return False


# Global instance for easy access
discord_alerter = DiscordAlerter()


def send_error_alert(
    error, context="", episode_name="", podcast_name="", additional_info=None
):
    """
    Convenience function to send error alerts
    """
    return discord_alerter.send_error_alert(
        error, context, episode_name, podcast_name, additional_info
    )


def send_processing_alert(
    message_type, podcast_name="", episode_name="", additional_info=None
):
    """
    Convenience function to send processing alerts
    """
    return discord_alerter.send_processing_alert(
        message_type, podcast_name, episode_name, additional_info
    )


def send_training_data_alert(
    message_type, podcast_name="", episode_name="", additional_info=None
):
    """
    Convenience function to send training data alerts
    """
    return discord_alerter.send_processing_alert(
        message_type,
        podcast_name,
        episode_name,
        additional_info,
        alert_title="TRAINING DATA",
    )
