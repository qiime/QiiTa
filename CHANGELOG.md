# Qiita changelog

Version 092018
--------------

* Study listing performance was improve and now public studies are only shown once for Admins.
* The study listing page used to show all artifacts for public studies, even the private ones, now we show based on their permissions.
* Users now can allow access from Qiita to copy (scp/sftp) their files from their own servers.
* Sample deletion from the sample information file now is done in bulk.
* The Sample-Prep Summary now can be sorted.
* Admins now have a page to check the status of the plugins.
* We now support unique tube identifies for samples, helpful for connections with LIMS systems.
* Resorted the top menus so they are clearer for new users.
* Study titles cannot have special, non UTF-8, chars.
* The password check and reset has been fixed.
* Plugin software now have a new column deprecated to highlight artifacts that were generated with outdated software.
* EBI-ENA submissions was improved by only scanning the samples in the prep information file vs. all samples in the study.
* We now check that the sample information file does not contain regular prep info file columns and that the prep does not have QIIME specific mapping file columns.
* The qtp-target-gene has been updated to support multiple SFF files
* The qp-deblur was updated to use deblur-1.1.0

Version 062018
--------------

* We haven't updated the ChangeLog for a while (since circa 2015). Anyway, we will ask developers to add an entry for any new features in Qiita.
* Now you can select or unselect all files in the upload folder.
* Added circle color explanation in the processing network.
* Fixed error in the sample info category summary (https://github.com/biocore/qiita/issues/2610).
* Qiimp has been added to the Qiita GUI.
* We added the qt-shogun plugin.
* Adding qiita_db.processing_job.ProcessingJob.validator_jobs to remove duplicated code.

Version 0.2.0-dev
-----------------

* Users can now change values and add samples and/or columns to sample and prep templates using the <kbd>Update</kbd> button (see the prep template and sample template tabs).
* The raw files of a RawData can be now updated using the `qiita db update_raw_data` CLI command.
* instrument_model is now a required prep template column for EBI submissions.
* PostgreSQL 9.3.0 is now the minimum required version because we are using the SQL type JSON, included for first time in 9.3.0.
* The objects `RawData`, `PreprocessedData` and `ProcessedData` have been removed from the system and substituted by a general `Artifact` object.
* The CLI commands `load_raw`, `load_preprocessed` and `load_processed` have been removed from the system and substituted by `load_artifact`.
* We incorporated the idea of plugins into the system. Now, all processing could be plugins.
* QIIME workflows for splitting libraries (SFF/FASTA-QUAL and FASTQ/per-sample-FASTQ) and for picking OTUs has been moved to a new target gene plugin.
* An initial RESTapi has been introduced as a result of the plugin system, in which OAuth2 authentication is required to access the data.
* The system has been ported to use HTTPS instead of HTTP.
* The website now supports Mozilla Firefox 48 and above.

Version 0.2.0 (2015-08-25)
--------------------------

* Creating an empty RawData is no longer needed in order to add a PrepTemplate.
Now, the PrepTemplate is required in order to add a RawData to a study. This is
the normal flow of a study, as the PrepTemplate information is usually
available before the RawData information is available.
* A user can upload a QIIME mapping file instead of a SampleTemplate. The
system will create a SampleTemplate and a PrepTemplate from the information
present in the QIIME mapping file. The QIIME required columns for this
functionality to work are 'BarcodeSequence', 'LinkerPrimerSequence' and
'Description'. For more information about QIIME mapping files, visit
http://qiime.org/documentation/file_formats.html#mapping-file-overview.
* The command line interface has been reorganized:
 * `qiita_env` has been renamed `qiita-env`
 * `qiita_test_install` has been renamed `qiita-test-install`
 * `qiita ebi` has been moved to `qiita ware ebi`
 * `qiita log` has been moved to `qiita maintenance log`
 * A new `qiita pet` command subgroup has been created
 * `qiita webserver` has been moved to `qiita pet webserver`
* Cluster names now use dashes instead of underscores (e.g., `qiita_general` is now `qiita-general`)
* `qiita-general` is now used as a default argument to `qiita-env start_cluster` and `qiita-env stop_cluster` if no cluster name is specified
* Qiita now now allows for processing of already demultiplexed data without any technical (barcode and primer) section of the read.
* Qiita now includes full portal support, limiting study and analysis access at below the qiita_db level. This allows one database to act as if subsets of studies/analyses are their own specific interface. Commands added for portals creation and maintenance, under `qiita db portal ...` and `qiita-env`. Portal specific web user interface support has also been added; each portal is fully CSS customizable.
* 403 errors are now not logged in the logging table
* Qiita will execute all DB interactions in transactions. The queue code was moved and improved from SQLConnectionHandler to a new Transaction object. The system implements the singleton pattern. That is, there is only a single transaction in the system, represented by the variable `TRN`, and all DB interactions go through it.

Version 0.1.0 (2015-04-30)
--------------------------

Initial alpha release.
