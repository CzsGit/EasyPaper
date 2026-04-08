# Agent PDF Translation Tooling Design

## Summary

This project currently delivers paper translation through a user-facing Web application. The next product shape is different: the same translation capability must become a reusable tool that any external agent can call, while the Web UI continues to work on top of the same execution path.

Phase 1 focuses on a single end-to-end workflow:

- Input: PDF file or PDF URL
- Capability: English paper -> Chinese PDF translation
- Optional parameter: AI highlight on/off
- Output: task status plus downloadable translated PDF
- Missing parameters: returned as structured follow-up questions, not handled through an internal chat loop

The result is a dual-access backend:

- Existing Web UI remains functional
- New HTTP agent API is added
- New MCP server is added
- All three entry points reuse the same translation execution core

## Goals

- Convert the translation workflow into a stable, agent-callable capability layer.
- Support both HTTP and MCP in the first release.
- Preserve the current Web flow and avoid a ground-up rewrite.
- Let external agents own user conversation and channel delivery.
- Return structured `needs_input` responses when required parameters are missing.

## Non-Goals

- No direct integration with Feishu, WeChat, Slack, or any other messaging client.
- No internal conversational engine that decides what to ask next from arbitrary user text.
- No expansion to summary, flashcards, or knowledge extraction in Phase 1.
- No replacement of the existing Web front end.

## Why This Scope

The highest-risk product assumption is not "can we translate a PDF?" because the project already does that. The real unknown is whether an external agent can reliably:

1. send a source document,
2. receive a structured prompt for missing options,
3. submit the completed request,
4. poll progress, and
5. fetch the resulting PDF artifact.

That is the critical chain to validate first.

## Existing Assets To Reuse

The current codebase already contains the pieces needed for execution:

- `backend/app/services/document_processor.py` runs pdf2zh translation and optional highlight.
- `backend/app/services/task_manager.py` creates, tracks, stores, and expires translation tasks.
- `backend/app/api/routes.py` already supports upload, URL download, status polling, and result download for Web users.
- `backend/app/main.py` initializes the shared processor and task manager.

Phase 1 should wrap these assets rather than replacing them.

## Architecture

### 1. Translation Draft Layer

Add a new persistent object, `TranslationDraft`, to represent a request that has received a source document but is still collecting required parameters.

This is necessary because the current `Task` model only represents work that is already executing. Agent workflows need an intermediate state where the file is stored once, then reused across one or more follow-up turns.

Suggested fields:

- `draft_id`
- `source_type` (`upload` or `url`)
- `source_path`
- `source_url`
- `filename`
- `target_lang`
- `highlight`
- `status` (`collecting_input`, `ready`, `submitted`, `expired`)
- `created_at`

### 2. Translation Draft Service

Add a service responsible for:

- ingesting `pdf_url` or `pdf_base64`
- downloading or decoding and storing the source PDF
- creating or updating a draft
- validating required parameters
- returning structured `needs_input` responses
- promoting a ready draft into a real translation task

This service owns the agent-facing request lifecycle. It does not run translation itself.

### 3. Translation Execution Service

Add a thin execution service that converts a completed draft into the existing task system.

Responsibilities:

- create a `Task` through `TaskManager`
- persist the original source path into the task
- schedule the existing `DocumentProcessor.process(...)` background execution
- return task metadata suitable for HTTP and MCP

This keeps the translation engine in one place and avoids divergence between Web and agent paths.

### 4. Artifact Service

Add a small service that reads completed task output and returns:

- artifact metadata
- filename
- content type
- download path or file bytes when requested

This prevents route handlers and MCP tools from reading disk paths directly.

### 5. Agent HTTP Adapter

Add a dedicated route group under `/api/agent/v1`.

This adapter is only responsible for:

- parsing HTTP requests
- enforcing agent API key auth
- calling the draft/execution/artifact services
- formatting HTTP responses

It must not contain translation business logic.

### 6. MCP Adapter

Add an MCP server that exposes the same capability through tools. The MCP layer must call the same underlying services used by the HTTP adapter.

Phase 1 tools:

- `translate_pdf`
- `get_translation_task`
- `get_translation_artifact`

The MCP transport should be mounted into the existing ASGI app rather than run as a separate standalone service. The official MCP Python SDK documents `FastMCP` plus `streamable_http_app()` mounting for existing ASGI apps, and it explicitly recommends streamable HTTP over SSE for current usage. Sources:

- https://github.com/modelcontextprotocol/python-sdk
- https://modelcontextprotocol.io/docs/sdk

## Request / Response Model

### Unified Behavior

Every translation request follows the same state model:

1. Agent submits source document plus any known parameters.
2. If required parameters are missing, service returns `needs_input`.
3. Agent asks the user the returned question.
4. Agent resubmits with `draft_id` plus missing values.
5. Service creates a task and returns `accepted`.
6. Agent polls task status.
7. Agent fetches the translated PDF artifact.

### Required Inputs In Phase 1

- one source:
  - `pdf_url`, or
  - `pdf_base64`
- `target_lang`
  - fixed to `zh` in Phase 1, even if omitted by callers
- `highlight`
  - if omitted, return `needs_input`

### HTTP API

#### `POST /api/agent/v1/translate`

Input:

- `draft_id` optional
- `pdf_url` optional
- `pdf_base64` optional
- `highlight` optional

Responses:

`needs_input`

```json
{
  "status": "needs_input",
  "draft_id": "dr_123",
  "missing_fields": ["highlight"],
  "question": "Do you want key sentences highlighted in the translated PDF?",
  "options": [
    {"label": "Yes", "value": true},
    {"label": "No", "value": false}
  ]
}
```

`accepted`

```json
{
  "status": "accepted",
  "draft_id": "dr_123",
  "task_id": "tsk_456",
  "status_url": "/api/agent/v1/tasks/tsk_456"
}
```

#### `GET /api/agent/v1/tasks/{task_id}`

Returns:

- `status`
- `percent`
- `message`
- `error`
- `artifact_ready`

#### `GET /api/agent/v1/tasks/{task_id}/artifact`

Returns either:

- the PDF file directly, or
- artifact metadata plus a binary/file response mode

Phase 1 should prefer direct PDF download from this endpoint.

### MCP Tools

#### `translate_pdf`

Input:

- `draft_id` optional
- `pdf_url` optional
- `pdf_base64` optional
- `highlight` optional

Output:

- same logical shape as HTTP:
  - `needs_input`, or
  - `accepted`

#### `get_translation_task`

Input:

- `task_id`

Output:

- task status payload matching the HTTP status endpoint

#### `get_translation_artifact`

Input:

- `task_id`

Output:

- artifact metadata
- optionally file bytes or a fetchable URL, depending on MCP client support

## Structured Follow-Up Strategy

Phase 1 deliberately avoids embedding a dialogue engine. Instead, the backend returns a structured follow-up contract:

- `missing_fields`
- `question`
- `options`

The external agent remains responsible for:

- deciding how to phrase the question to the user
- collecting the user answer
- calling the tool again with the completed parameters

This keeps the backend generic and reusable across different agent frameworks and messaging environments.

## Authentication

Agent access should use a separate API key mechanism, not the existing Web JWT flow.

Add an `agent` config section with fields such as:

- `api_keys`
- `draft_ttl_minutes`
- `mcp_mount_path`

HTTP should validate `X-Agent-Api-Key`.

The MCP server can read the same configured key list if access control is required at the mounted endpoint. Phase 1 may also allow MCP to run inside a trusted network boundary if that matches deployment expectations, but the authentication story must be explicit in configuration and docs.

## Error Handling

Use separate response types for separate failure classes.

### Input collection

- `needs_input`: parameters missing, not an error

### Validation failures

- invalid PDF URL
- invalid base64
- missing source
- file too large
- unsupported content type

### Processing failures

- pdf2zh error
- LLM provider failure
- temporary file write/read failure

### Retrieval failures

- task not found
- artifact not ready
- artifact expired

These failures should not be collapsed into one generic `"failed"` state.

## Data Lifecycle

Drafts and tasks should have separate TTL-based cleanup.

- Existing task cleanup remains in `TaskManager`.
- Add parallel cleanup for `TranslationDraft`.
- Draft cleanup must remove stored source files that were never submitted or have expired.
- Submitted drafts should be marked `submitted` and can be cleaned independently after a shorter retention period if desired.

## Backward Compatibility

The current Web flow stays intact.

Implementation rule:

- Web upload endpoints continue to work as-is.
- Web routes may gradually reuse the new execution service, but this is optional in Phase 1.
- Agent routes and MCP tools are additive, not replacements.

This minimizes regression risk while the new tooling layer is introduced.

## Testing Strategy

Phase 1 is complete only if all of the following are covered:

- unit tests for draft validation and `needs_input` behavior
- unit tests for source ingestion from URL and base64
- HTTP integration tests for:
  - `needs_input`
  - successful task acceptance after follow-up
  - task polling
  - artifact download
- auth tests for missing or invalid `X-Agent-Api-Key`
- MCP integration tests for the same logical flow
- regression coverage proving the current Web translation endpoints still work

## Rollout Sequence

1. Add configuration and draft persistence.
2. Add draft, execution, and artifact services.
3. Add HTTP agent routes.
4. Refactor app startup only as much as needed to mount MCP cleanly.
5. Add MCP tools on top of the same service layer.
6. Document the API and include example agent call flows.

## Future Phases

Once the translation workflow is stable, the same architecture can be extended to:

- paper summary
- flashcard generation
- flashcard review sessions
- knowledge extraction

Those should follow the same pattern:

- draft if parameters may be incomplete
- execution service for background work
- artifact or structured result service
- HTTP + MCP adapters over the same core
