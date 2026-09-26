# VS Code / Copilot Extension Feasibility Spike

## Objective
To investigate the feasibility of building a VS Code extension or adapting GitHub Copilot public APIs to extract agent telemetry (context length, tool usage, conversation history) for DriftGuard.

## Current State of APIs

### 1. VS Code Extension API
The VS Code Extension API is highly extensible but largely disconnected from the private runtime of GitHub Copilot.
- **What is possible:**
  - We can track file changes, cursor positions, and basic editor usage.
  - We can create our own Chat Participant (e.g. `@driftguard`) using the VS Code Chat API to intercept user messages and model responses.
  - We can contribute our own tools/commands that the user can execute.
- **What is NOT possible:**
  - We cannot silently intercept or read the private token stream or conversation history between the user and `@workspace` or GitHub Copilot.
  - We cannot directly hook into Copilot's internal tool loop unless Copilot exposes it via a public API.

### 2. GitHub Copilot API
GitHub Copilot currently maintains a closed ecosystem for its core chat and autocomplete features.
- While you can create Copilot Extensions (Chat participants), these extensions only receive requests when explicitly invoked by the user (e.g., `@my-extension`).
- Copilot does not currently provide a generic "telemetry hook" or "tool interception hook" for third-party extensions to observe its internal chain-of-thought or retry loops.

## Conclusion and Recommendations
**Feasibility:** Low for passive interception of GitHub Copilot. High for building a custom Chat Participant or wrapping standard MCP tools.

**Recommended Path Forward:**
1. **Model Context Protocol (MCP):** Focus heavily on the MCP gateway middleware. As more tools adopt MCP, inserting DriftGuard between the agent (Copilot, Claude, etc.) and the MCP server becomes the most robust way to capture tool-loop failures without needing proprietary API access.
2. **Custom Chat Participant:** If we build a VS Code extension, it should act as an active chat participant (`@driftguard`) that developers can use to analyze their workspace, or we can build an extension that reads MCP logs locally.
3. **Agent Wrappers:** Continue supporting standard Python agent wrappers (like LangChain or custom loops) as they provide full control over the runtime context.
