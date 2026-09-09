{"type":"thread.started","thread_id":"01a07fb5-afcc-7250-9030-2ca69492d406"}
{"type":"item.completed","item":{"id":"item_0","type":"error","message":"Model metadata for `gpt-6-astra` not found. Defaulting to fallback metadata; this can degrade performance and cause issues."}}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_1","type":"error","message":"Skill descriptions were shortened to fit the skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest."}}
{"type":"error","message":"{\"type\":\"error\",\"status\":400,\"error\":{\"type\":\"invalid_request_error\",\"message\":\"The 'gpt-6-astra' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again.\"}}"}
{"type":"turn.failed","error":{"message":"{\"type\":\"error\",\"status\":400,\"error\":{\"type\":\"invalid_request_error\",\"message\":\"The 'gpt-6-astra' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again.\"}}"}}

2026-09-08T06:30:08.588557Z  WARN codex_models_manager::model_info: Unknown model gpt-6-astra is used. This will use fallback model metadata.
2026-09-08T06:30:08.690657Z  WARN codex_skills::interface: ignoring interface.icon_small: icon path with '..' must resolve under plugin assets/
2026-09-08T06:30:08.690700Z  WARN codex_skills::interface: ignoring interface.icon_large: icon path with '..' must resolve under plugin assets/
2026-09-08T06:30:08.853416Z  WARN codex_core::shell_snapshot: Failed to create shell snapshot for powershell: Shell snapshot not supported yet for PowerShell
2026-09-08T06:30:09.238260Z  WARN codex_models_manager::model_info: Unknown model gpt-6-astra is used. This will use fallback model metadata.
2026-09-08T06:30:09.246546Z  WARN codex_models_manager::model_info: Unknown model gpt-6-astra is used. This will use fallback model metadata.
2026-09-08T06:30:10.166180Z  WARN codex_skills::interface: ignoring interface.icon_small: icon path with '..' must resolve under plugin assets/
2026-09-08T06:30:10.166228Z  WARN codex_skills::interface: ignoring interface.icon_large: icon path with '..' must resolve under plugin assets/
2026-09-08T06:30:11.346798Z  WARN codex_core::session_startup_prewarm: startup websocket prewarm setup failed: {"type":"error","status":400,"error":{"type":"invalid_request_error","message":"The 'gpt-6-astra' model requires a newer version of Codex. Please upgrade to the latest app or CLI and try again."}}
2026-09-08T06:30:14.581433Z  WARN codex_core::tasks: failed to flush rollout after emitting terminal turn event: thread 01a07fb5-afcc-7250-9030-2ca69492d406 not found