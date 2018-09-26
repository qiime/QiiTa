-- August 6, 2018

SELECT 42;

-- August 22, 2018
-- add specimen_id_column to study table (needed to plate samples in labman)

ALTER TABLE qiita.study ADD specimen_id_column varchar(256);

COMMENT ON COLUMN qiita.study.specimen_id_column IS 'The name of the column that describes the specimen identifiers (such as what is written on the tubes).';

-- September 12, 2018
-- add deprecated to software table

ALTER TABLE qiita.software ADD deprecated bool default False;
