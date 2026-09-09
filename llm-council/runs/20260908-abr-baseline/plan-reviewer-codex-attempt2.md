{"type":"thread.started","thread_id":"01a07fb5-1bd0-7b43-88a3-cb116ed72938"}
{"type":"item.completed","item":{"id":"item_0","type":"error","message":"Model metadata for `gpt-6-astra` not found. Defaulting to fallback metadata; this can degrade performance and cause issues."}}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_1","type":"error","message":"Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest."}}
{"type":"error","message":"{\"type\":\"error\",\"status\":400,\"error\":{\"type\":\"invalid_request_error\",\"message\":\"The 'gpt-6-astra' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again.\"}}"}
{"type":"turn.failed","error":{"message":"{\"type\":\"error\",\"status\":400,\"error\":{\"type\":\"invalid_request_error\",\"message\":\"The 'gpt-6-astra' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again.\"}}"}}

2026-09-08T06:29:30.704456Z  WARN codex_models_manager::model_info: Unknown model gpt-6-astra is used. This will use fallback model metadata.
2026-09-08T06:29:30.809991Z  WARN codex_skills::interface: ignoring interface.icon_small: icon path with '..' must resolve under plugin assets/
2026-09-08T06:29:30.810035Z  WARN codex_skills::interface: ignoring interface.icon_large: icon path with '..' must resolve under plugin assets/
2026-09-08T06:29:30.961285Z  WARN codex_core::shell_snapshot: Failed to create shell snapshot for powershell: Shell snapshot not supported yet for PowerShell
2026-09-08T06:29:31.289513Z  WARN codex_models_manager::model_info: Unknown model gpt-6-astra is used. This will use fallback model metadata.
2026-09-08T06:29:31.295513Z  WARN codex_models_manager::model_info: Unknown model gpt-6-astra is used. This will use fallback model metadata.
2026-09-08T06:29:32.481313Z  WARN codex_skills::interface: ignoring interface.icon_small: icon path with '..' must resolve under plugin assets/
2026-09-08T06:29:32.481370Z  WARN codex_skills::interface: ignoring interface.icon_large: icon path with '..' must resolve under plugin assets/
2026-09-08T06:29:33.483527Z  WARN codex_core::session_startup_prewarm: startup websocket prewarm setup failed: {"type":"error","status":400,"error":{"type":"invalid_request_error","message":"The 'gpt-6-astra' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again."}}
2026-09-08T06:29:36.700024Z  WARN codex_core::tasks: failed to flush rollout after emitting terminal turn event: thread 01a07fb5-1bd0-7b43-88a3-cb116ed72938 not found