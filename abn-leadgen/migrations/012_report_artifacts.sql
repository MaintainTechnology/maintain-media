ALTER TABLE artifact_manifest DROP CONSTRAINT artifact_manifest_artifact_class_check;
ALTER TABLE artifact_manifest ADD CONSTRAINT artifact_manifest_artifact_class_check CHECK(
 artifact_class IN ('raw','snapshot','event','page','backup','report','manifest')
);
