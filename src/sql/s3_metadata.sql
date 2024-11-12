-- podcast_metadata.s3_metadata definition

-- Drop table

-- DROP TABLE podcast_metadata.s3_metadata;

CREATE TABLE podcast_metadata.s3_metadata (
	id text NOT NULL,
	podcast_name text NOT NULL,
	episode_uuid text NOT NULL,
	episode_name text NOT NULL,
	episode_hash_name text NOT NULL,
	episode_url text NOT NULL,
	cdn_url text NOT NULL,
	image_url text NOT NULL,
	api_data json NOT NULL,
	api_episode_hash text NULL,
	local_filename text NULL,
	s3_location text NOT NULL,
	podcast_length_seconds int8 NULL,
	original_duration int8 NULL,
	ad_time_removed int8 NULL,
	total_processing_time int8 NULL,
	file_size int8 NULL,
	mime_type text NULL,
	upload_dt timestamp NULL,
	episode_guid varchar NULL
);