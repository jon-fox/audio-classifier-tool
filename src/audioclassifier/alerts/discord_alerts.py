import os

import requests
import traceback
from datetime import datetime
from audioclassifier.config.constants import DISCORD_ALERTS_ENABLED
from audioclassifier.logger.logger_setup import logger


class DiscordAlerter:
    def __init__(self):
        self.webhook_url = None

        if not DISCORD_ALERTS_ENABLED:
            logger.info("Discord alerts disabled (set DISCORD_ALERTS=true to enable)")
            return

        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
        if not self.webhook_url:
            logger.warning(
                "DISCORD_ALERTS is enabled but DISCORD_WEBHOOK_URL is not set, alerts disabled"
            )

    def send_error_alert(
        self, error, context="", name="", source="", additional_info=None
    ):
        """
        Send a detailed error alert to Discord

        Args:
            error: The exception object or error message
            context: Additional context about where the error occurred
            name: Name of the audio being processed when error occurred
            source: Source the audio belongs to
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
            ]

            if source:
                message_parts.append(f"**Source:** {source}")

            if name:
                message_parts.append(f"**Audio:** {name}")

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
        source="",
        name="",
        additional_info=None,
        alert_title="PROCESSING",
    ):
        """
        Send processing status alerts (success, start, etc.)

        Args:
            message_type: Type of message (success, started, warning, etc.)
            source: Source the audio belongs to
            name: Name of the audio
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
            ]

            if source:
                message_parts.append(f"**Source:** {source}")

            if name:
                message_parts.append(f"**Audio:** {name}")

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


def send_error_alert(error, context="", name="", source="", additional_info=None):
    """
    Convenience function to send error alerts
    """
    return discord_alerter.send_error_alert(
        error, context, name, source, additional_info
    )


def send_processing_alert(message_type, source="", name="", additional_info=None):
    """
    Convenience function to send processing alerts
    """
    return discord_alerter.send_processing_alert(
        message_type, source, name, additional_info
    )
