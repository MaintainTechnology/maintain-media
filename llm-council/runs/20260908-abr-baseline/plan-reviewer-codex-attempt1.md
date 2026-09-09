{"type":"thread.started","thread_id":"01a07fb4-dccd-7603-869a-ddaf3c25a999"}
{"type":"item.completed","item":{"id":"item_0","type":"error","message":"Model metadata for `gpt-6-astra` not found. Defaulting to fallback metadata; this can degrade performance and cause issues."}}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_1","type":"error","message":"Exceeded skills context budget. All skill descriptions were removed and 93 additional skills were not included in the model-visible skills list."}}
{"type":"error","message":"{\"type\":\"error\",\"status\":400,\"error\":{\"type\":\"invalid_request_error\",\"message\":\"The 'gpt-6-astra' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again.\"}}"}
{"type":"turn.failed","error":{"message":"{\"type\":\"error\",\"status\":400,\"error\":{\"type\":\"invalid_request_error\",\"message\":\"The 'gpt-6-astra' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again.\"}}"}}

2026-09-08T06:29:14.563985Z  WARN codex_models_manager::model_info: Unknown model gpt-6-astra is used. This will use fallback model metadata.
2026-09-08T06:29:16.774005Z  WARN codex_skills::interface: ignoring interface.icon_small: icon path with '..' must resolve under plugin assets/
2026-09-08T06:29:16.774063Z  WARN codex_skills::interface: ignoring interface.icon_large: icon path with '..' must resolve under plugin assets/
2026-09-08T06:29:17.945444Z  WARN codex_core::shell_snapshot: Failed to create shell snapshot for powershell: Shell snapshot not supported yet for PowerShell
2026-09-08T06:29:18.709727Z  WARN codex_models_manager::model_info: Unknown model gpt-6-astra is used. This will use fallback model metadata.
2026-09-08T06:29:18.723359Z  WARN codex_models_manager::model_info: Unknown model gpt-6-astra is used. This will use fallback model metadata.
2026-09-08T06:29:21.682736Z  WARN codex_core::session_startup_prewarm: startup websocket prewarm setup failed: {"type":"error","status":400,"error":{"type":"invalid_request_error","message":"The 'gpt-6-astra' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again."}}
2026-09-08T06:29:25.209995Z  WARN codex_core::tasks: failed to flush rollout after emitting terminal turn event: thread 01a07fb4-dccd-7603-869a-ddaf3c25a999 not found