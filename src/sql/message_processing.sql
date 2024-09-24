CREATE TABLE podcast_metadata.message_processing (
    episode_hash TEXT PRIMARY KEY,           -- Unique identifier for each message
    message_id TEXT,                         -- Unique identifier for each message
    status TEXT NOT NULL,                    -- Current status of the message (e.g., 'Sent', 'Processing', 'Completed', 'Failed')
    created_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- Timestamp when the record was first created
    updated_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- Timestamp when the record was last updated
    processing_node TEXT,                    -- Optional: Identifier of the processing node or worker
    error_details TEXT,                      -- Optional: Details in case of a processing failure
    result_data JSONB,                       -- The output/result of the processing (can be NULL initially)
    completed_timestamp TIMESTAMPTZ,         -- Timestamp when processing was completed (can be NULL initially)
    retry_count INT NOT NULL DEFAULT 0,      -- Number of times the message has been retried
    priority INT DEFAULT 0,                  -- Priority of the message, higher values mean higher priority
    aws_request_id TEXT,                             -- Source or origin of the message
    is_archived BOOLEAN DEFAULT FALSE,       -- Flag to indicate if the record is archived
    processing_duration INTERVAL            -- Duration of processing
);
