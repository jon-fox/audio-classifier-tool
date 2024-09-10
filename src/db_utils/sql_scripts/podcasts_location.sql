-- podcast_metadata.s3_metadata definition

-- Drop table

DROP TABLE podcast_metadata.s3_metadata;

CREATE TABLE podcast_metadata.s3_metadata (
	id serial4 NOT NULL,
	podcast_name varchar(255) NOT NULL,
	episode_uuid varchar(255) NOT NULL, 
	episode_name varchar(255) NOT NULL,
	episode_url varchar(1000) NOT NULL,
	cdn_url varchar(1000) NOT NULL,
    episode_number varchar(255) NULL,
	episode_description varchar NULL,
	local_filename varchar(255) NULL,
	s3_location text NOT NULL,
	podcast_length_seconds int8 NULL,
    original_duration int8 NULL,
    ad_time_removed int8 NULL,
    total_processing_time int8 NULL,
	description text NULL,
    file_size int8 NULL,
	mime_type varchar(50) NULL,
	upload_dt timestamp NULL,
	tags _text NULL,
	CONSTRAINT s3_metadata_pkey PRIMARY KEY (id)
);