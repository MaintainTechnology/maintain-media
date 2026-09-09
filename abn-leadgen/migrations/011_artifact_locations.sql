ALTER TABLE artifact_manifest ADD COLUMN local_path text;
ALTER TABLE artifact_manifest ADD COLUMN artifact_class text CHECK(artifact_class IN ('raw','snapshot','event','page','backup'));
