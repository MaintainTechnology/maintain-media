{"type":"thread.started","thread_id":"01a07fb5-6259-7b83-a055-6a0590dfa472"}
{"type":"item.completed","item":{"id":"item_0","type":"error","message":"Model metadata for `gpt-6-astra` not found. Defaulting to fallback metadata; this can degrade performance and cause issues."}}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_1","type":"error","message":"Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest."}}
{"type":"error","message":"{\"type\":\"error\",\"status\":400,\"error\":{\"type\":\"invalid_request_error\",\"message\":\"The 'gpt-6-astra' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again.\"}}"}
{"type":"turn.failed","error":{"message":"{\"type\":\"error\",\"status\":400,\"error\":{\"type\":\"invalid_request_error\",\"message\":\"The 'gpt-6-astra' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again.\"}}"}}

2026-09-08T06:29:48.761357Z  WARN codex_models_manager::model_info: Unknown model gpt-6-astra is used. This will use fallback model metadata.
2026-09-08T06:29:48.856229Z  WARN codex_skills::interface: ignoring interface.icon_small: icon path with '..' must resolve under plugin assets/
2026-09-08T06:29:48.856283Z  WARN codex_skills::interface: ignoring interface.icon_large: icon path with '..' must resolve under plugin assets/
2026-09-08T06:29:48.997301Z  WARN codex_core::shell_snapshot: Failed to create shell snapshot for powershell: Shell snapshot not supported yet for PowerShell
2026-09-08T06:29:49.267594Z  WARN codex_models_manager::model_info: Unknown model gpt-6-astra is used. This will use fallback model metadata.
2026-09-08T06:29:49.273841Z  WARN codex_models_manager::model_info: Unknown model gpt-6-astra is used. This will use fallback model metadata.
2026-09-08T06:29:50.525402Z  WARN codex_skills::interface: ignoring interface.icon_small: icon path with '..' must resolve under plugin assets/
2026-09-08T06:29:50.525434Z  WARN codex_skills::interface: ignoring interface.icon_large: icon path with '..' must resolve under plugin assets/
2026-09-08T06:29:51.101062Z  WARN codex_core::session_startup_prewarm: startup websocket prewarm setup failed: {"type":"error","status":400,"error":{"type":"invalid_request_error","message":"The 'gpt-6-astra' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again."}}
2026-09-08T06:29:54.619835Z  WARN codex_core::tasks: failed to flush rollout after emitting terminal turn event: thread 01a07fb5-6259-7b83-a055-6a0590dfa472 not found