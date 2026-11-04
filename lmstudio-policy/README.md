# LM Studio idle policy

Use LM Studio's native idle timer with a 30-minute default. The native timer
counts inactivity after work finishes; a long-running generation is allowed to
finish. The next inference request loads the model again through JIT.

Install or reapply after downloading another model:

```sh
bash lmstudio-policy/install.sh
```

The installer copies its small helpers to `~/.local/share/lmstudio-policy`, so
they keep working if the checkout or worktree is removed. `newcomputer.bash`
runs the installer when LM Studio is present.

## Load methods

- **API/JIT:** `developer.jitModelTTL` is enabled at 1800 seconds in
  `~/.lmstudio/settings.json`. JIT loading must remain enabled in the local
  server. Existing explicit request TTLs take precedence.
- **GUI model picker:** every currently downloaded model receives a saved
  `uiTTL` of 1800 seconds in LM Studio's model data. The loading dialog shows
  this as **Auto Unload If Idle (TTL)**. Reapply after adding models.
- **CLI:** `~/.local/bin/lms` forwards to `~/.lmstudio/bin/lms`, adding
  `--ttl 1800` to `lms load` when no explicit `--ttl` was supplied. Other
  commands and all other arguments pass through unchanged.
- **Explicit native REST loads:** on the installed build, use
  `ttl_seconds: 1800` in `POST /api/v1/models/load` for an LLM. This is a
  different field from the `ttl: 1800` used for JIT inference requests.
- **SDK loads:** pass `{ ttl: 1800 }` to `client.llm.load(...)`.

The JIT default does not retrofit a timer onto an already-loaded model.
Migrate an old instance only when it has finished its work, retaining its
identifier and load configuration. Do not stop or restart LM Studio while a
model is generating merely to apply this policy.

## Reload compatibility

The configurator saves the currently loaded LLMs' existing context length and
parallelism as native per-model defaults. This preserves those settings when
JIT reloads them, instead of falling back to the global 8192-token context.
Other model parameters, including the chosen model and quantization, are not
changed. Existing additional per-model settings are retained.

API clients should use the downloaded model key, such as `qwen3.8-27b-mlx`
or `qwen3-coder-next`. A name assigned only to a loaded instance may not be
resolvable once that instance expires. Clients must allow enough time for
loading weights and processing an uncached prompt.

## Scope and bypasses

This configures native defaults; it does not patch LM Studio or run a custom
process-killing watchdog. Calling the native CLI by its absolute path bypasses
the CLI shim, so pass `--ttl 1800` explicitly in that case. A program that calls
the explicit load API/SDK without a timer can still create an untimed instance.
**The installed app's tray `Load Model` quick-load bypasses saved `uiTTL`**:
a live tray load on November 4 produced `ttlMs: null`. Use the main loading
dialog with **Auto Unload If Idle (TTL)** enabled, or the ordinary `lms load`
command instead. A missing `ttlMs` in `lms ps --json` means no timer was applied.
There is no public API in this build for retrofitting a TTL onto a loaded
instance; its next load must specify the timer. A tray-loaded instance is
therefore an explicit gap in native default coverage, not a timed instance.

The saved GUI/default configuration file formats were checked against the
installed LM Studio build on November 4, 2026. Rerun verification after an app
upgrade if these formats change. The installer keeps prior JSON files under
`~/.cache/agent-tmp/lmstudio-idle-policy/backups`.

## Check the policy

```sh
lms ps --json
```

Ordinary loaded instances should show `ttlMs: 1800000`. While an instance is
working, its `lastUsedTime` is null; after completion, native TTL starts from
its latest idle time. Do not use the age of a log file to infer activity.

References:

- https://lmstudio.ai/docs/developer/core/ttl-and-auto-evict
- https://lmstudio.ai/docs/cli/local-models/load
