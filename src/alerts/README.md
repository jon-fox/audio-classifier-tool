# Discord Error Alerting System for JusSkipIt App

## Overview

This document describes the Discord alerting system implemented for the JusSkipIt application to monitor and notify about errors in real-time.

## Configuration

The Discord webhook URL is stored in AWS Systems Manager Parameter Store:
- Parameter: `/application/discord/errors_webhook`
- Used for sending error notifications to Discord

## Features

### Error Alerts
- **Real-time notifications**: Immediate Discord alerts when exceptions occur
- **Detailed context**: Includes episode name, podcast name, error details, and relevant context
- **Instance tracking**: Shows which EC2 instance encountered the error
- **Traceback information**: Includes error tracebacks (truncated for Discord limits)

### Processing Alerts
- **Success notifications**: Alerts when episodes are successfully processed
- **Processing status**: Updates about processing stages
- **Performance metrics**: Processing time, file sizes, etc.

## Alert Types

### 🚨 Error Alerts
Sent when exceptions occur in critical functions:
- MP3 file processing failures
- Audio download errors
- Ad removal processing errors
- S3 upload failures
- Database operation errors
- Instance termination events

### ✅ Success Alerts
Sent when processing completes successfully:
- Episode processing completion
- File upload success
- RSS feed updates

## Implementation Details

### Core Components

1. **Discord Alerter Class** (`src/alerts/discord_alerts.py`)
   - Main alerting functionality
   - Handles message formatting and Discord API communication
   - Manages message length limits (2000 character Discord limit)

2. **Global Functions**
   - `send_error_alert()`: Convenience function for error notifications
   - `send_processing_alert()`: Convenience function for status updates

### Integration Points

The alerting system is integrated into:

- **Main Processing** (`src/main.py`)
  - SQS polling errors
  - Message processing errors
  - JSON decode errors
  - Processing completion success

- **MP3 Handler** (`src/pod_handler/mp3_handler.py`)
  - Download failures
  - Audio processing errors
  - S3 upload errors
  - Database insertion errors
  - Status update failures

- **Download Module** (`src/pod_handler/download_mp3.py`)
  - HTTP request failures
  - File write errors

- **S3 Operations** (`src/s3/write_to_s3.py`)
  - S3 client creation errors
  - File upload failures

- **Database Operations** (`src/db_utils/write_to_db.py`)
  - Metadata insertion errors
  - Message processing data errors
  - Status update errors

- **Audio Processing** (`src/pod_handler/mp3_converter_whisperx.py`)
  - Segment extraction errors
  - Transcription failures

- **Instance Management** (`src/metadata/utils.py`)
  - Critical error termination events
  - EC2 termination failures

## Alert Message Format

### Error Alert Structure
```
🚨 **JUSSKIPIT APP ERROR ALERT** 🚨
**Timestamp:** 2025-07-07 12:34:56 UTC
**Instance ID:** i-1234567890abcdef0
**Podcast:** Example Podcast
**Episode:** Example Episode Name
**Context:** Error context description
**Error Type:** Exception
**Error Message:** Detailed error message
**Additional Info:**
  • Key1: Value1
  • Key2: Value2
**Traceback:**
```
Exception traceback here
```
```

### Success Alert Structure
```
✅ **JUSSKIPIT PROCESSING UPDATE**
**Type:** SUCCESS
**Timestamp:** 2025-07-07 12:34:56 UTC
**Instance ID:** i-1234567890abcdef0
**Podcast:** Example Podcast
**Episode:** Example Episode Name
**Episode Hash:** abc123def456
**Processed Length:** 1800 seconds
**CDN URL:** https://cdn.example.com/path/file.mp3
**Added to RSS:** Yes
```

## Error Handling

The alerting system includes robust error handling:
- Graceful failure when Discord webhook is unavailable
- Timeout protection for Discord API calls
- Message truncation for Discord character limits
- Fallback logging when alerts fail

## Benefits

1. **Immediate Awareness**: Real-time notifications of processing issues
2. **Rich Context**: Detailed information for faster debugging
3. **Historical Tracking**: Discord channel serves as error log
4. **Instance Monitoring**: Track which instances are having issues
5. **Processing Visibility**: Monitor successful processing completion

## Usage

The alerting system is automatically integrated and requires no manual intervention. Alerts are sent automatically when:
- Exceptions occur in monitored functions
- Processing completes successfully
- Critical errors trigger instance termination

## Dependencies

- `requests`: For Discord webhook HTTP calls
- `boto3`: For AWS SSM parameter retrieval and instance metadata
- `traceback`: For detailed error information
- `datetime`: For timestamp formatting

## Configuration Requirements

1. AWS Systems Manager parameter `/application/discord/errors_webhook` must be set
2. EC2 instances must have appropriate IAM permissions for SSM access
3. Discord webhook must be properly configured in the target Discord channel
