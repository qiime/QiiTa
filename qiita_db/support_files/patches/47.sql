-- Jan 5, 2017
-- Move the analysis to the plugin system. This is a major rewrite of the
-- database backend that supports the analysis pipeline.
-- After exploring the data on the database, we realized that
-- there are a lot of inconsistencies in the data. Unfortunately, this
-- makes the process of trasnferring the data from the old structure
-- to the new one a bit more challenging, as we will need to handle
-- different special cases. Furthermore, all the information needed is not
-- present in the database, since it requires checking BIOM files. Due to these
-- reason, the vast majority of the data transfer is done in the python patch
-- 47.py

-- In this file we are just creating the new data structures. The old
-- datastructure will be dropped in the python patch once all data has been
-- transferred.

-- Create the new data structures

-- Table that links the analysis with the initial set of artifacts
CREATE TABLE qiita.analysis_artifact (
    analysis_id         bigint NOT NULL,
    artifact_id         bigint NOT NULL,
    CONSTRAINT idx_analysis_artifact_0 PRIMARY KEY (analysis_id, artifact_id)
);
CREATE INDEX idx_analysis_artifact_analysis ON qiita.analysis_artifact (analysis_id);
CREATE INDEX idx_analysis_artifact_artifact ON qiita.analysis_artifact (artifact_id);
ALTER TABLE qiita.analysis_artifact ADD CONSTRAINT fk_analysis_artifact_analysis FOREIGN KEY ( analysis_id ) REFERENCES qiita.analysis( analysis_id );
ALTER TABLE qiita.analysis_artifact ADD CONSTRAINT fk_analysis_artifact_artifact FOREIGN KEY ( artifact_id ) REFERENCES qiita.artifact( artifact_id );

-- We can handle some of the special cases here, so we simplify the work in the
-- python patch

-- Special case 1: there are jobs in the database that do not contain
-- any information about the options used to process those parameters.
-- However, these jobs do not have any results and all are marked either
-- as queued or error, although no error log has been saved. Since these
-- jobs are mainly useleess, we are going to remove them from the system
DELETE FROM qiita.analysis_job
    WHERE job_id IN (SELECT job_id FROM qiita.job WHERE options = '{}');
DELETE FROM qiita.job WHERE options = '{}';

-- Special case 2: there are a fair amount of jobs (719 last time I
-- checked) that are not attached to any analysis. Not sure how this
-- can happen, but these orphan jobs can't be accessed from anywhere
-- in the interface. Remove them from the system. Note that we are
-- unlinking the files but we are not removing them from the filepath
-- table. We will do that on the patch 47.py using the
-- purge_filepaths function, as it will make sure that those files are
-- not used anywhere else
DELETE FROM qiita.job_results_filepath WHERE job_id IN (
    SELECT job_id FROM qiita.job J WHERE NOT EXISTS (
        SELECT * FROM qiita.analysis_job AJ WHERE J.job_id = AJ.job_id));
DELETE FROM qiita.job J WHERE NOT EXISTS (
    SELECT * FROM qiita.analysis_job AJ WHERE J.job_id = AJ.job_id);
