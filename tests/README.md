# Test Suite Documentation

This directory contains unit, integration, and UI tests for `meta_agent`.

## Test Suite Overview

| File | Target Module | Description |
|---|---|---|
| [`test_tui_app.py`](test_tui_app.py) | `meta_agent.tui.app` | Verifies main TUI application lifecycle, tab navigation, shortcuts, fullscreen modes, and log management. |
| [`test_tui_screens.py`](test_tui_screens.py) | `meta_agent.tui.screens.*` | Verifies modal screens (`HelpScreen`, `ChatOptionsScreen`, `EditRecipeScreen`, `DeleteRecipeScreen`, `ResumeChatScreen`, `ChatScreen`), validation, and dismiss workflows. |
| [`test_tui_helpers.py`](test_tui_helpers.py) | `meta_agent.tui.helpers` | Table-driven tests for filtering, recipe matching, prompt construction, intent parsing, and input history. |
| [`test_tui_e2e_llm.py`](test_tui_e2e_llm.py) | `meta_agent.tui.*` / `meta_agent.llm` | E2E workflows with mock LLM client (recipe generation, chat token streaming, agent mode, Ask LLM routing). |
| [`test_recipe_ops.py`](test_recipe_ops.py) | `meta_agent.api` | Tests recipe file I/O, persistence, discovery, and file system safety. |
| [`test_utils.py`](test_utils.py) | `meta_agent.utils` | Tests shared date formatting and text utility functions. |
| [`test_meta_agent.py`](test_meta_agent.py) | `meta_agent` | Tests package initialization and top-level module imports. |

---

## TUI Test Specifications

The TUI test suite leverages Textual's asynchronous testing harness (`App.run_test()` / `pilot`) alongside pytest's table-driven parametrization (`@pytest.mark.parametrize`) to test keyboard shortcuts, mouse clicks, multi-window screen stacks, live updates, and error handling.

### 1. Main Application (`test_tui_app.py`)

| Test Function | Scenario / User Actions | Assertions & Significance |
|---|---|---|
| `test_tui_app_tabs_and_search_focus` | <ul><li>Switch active tab (`Recipes` &rarr; `Agents` &rarr; `Generate`)</li><li>Press `Ctrl+F` to focus the search `TextArea`</li><li>Invoke `action_open_generate()`</li></ul> | Ensures keyboard-driven tab switching and quick search activation seamlessly focus the correct text controls. |
| `test_tui_fullscreen_maximize_and_restore` | <ul><li>Press `Ctrl+O` to maximize and restore the detail pane</li><li>Press `Ctrl+L` or click the maximize button to maximize the log pane</li><li>Press `Esc` to restore standard layout</li><li>Switch tabs to verify auto-reset of fullscreen mode</li></ul> | Confirms that pane maximize/restore toggles function cleanly across keybindings and buttons without state corruption. |
| `test_tui_multiline_messages_and_submission` | <ul><li>Type multi-line prompt text in `GenerateTab`</li><li>Submit using `Ctrl+J`</li></ul> | Verifies separation between Enter (newline) and submission (`Ctrl+J` / `Ctrl+Enter`), ensuring inputs are cleared and saved to history. |
| `test_tui_main_keybindings_and_shortcuts` | <ul><li>With a recipe selected, trigger `Ctrl+C`, `Ctrl+E`, `Ctrl+D`, `Ctrl+R`, and `Ctrl+G` actions</li><li>Verify transition to target modal screens</li><li>Press `Esc` to dismiss modals</li></ul> | Guarantees that global keyboard navigation immediately dispatches the appropriate modal screen or tab. |
| `test_tui_shortcuts_and_escape_while_input_focused` | <ul><li>Focus `TextArea` and press `Esc` to unfocus</li><li>Press `Ctrl+G` to switch tabs while focused</li><li>Press `Ctrl+H` to open `HelpScreen` while typing in prompt</li></ul> | Verifies priority bindings execute directly without requiring manual field defocusing. |
| `test_tui_log_tab_clear_and_export` | <ul><li>Switch to `tab-logs`</li><li>Press `Ctrl+L` to maximize and `Esc` to restore</li><li>Press `Ctrl+S` to export `.log`</li><li>Press `Ctrl+K` to empty the log buffer</li></ul> | Ensures application execution logs can be reviewed in fullscreen, archived to disk via shortcut, and cleared on demand. |
| `test_tui_resource_selection_updates_detail` | <ul><li>Select items across recipes, agents, and tools lists</li><li>Verify markdown detail pane updates</li></ul> | Confirms that selecting list items correctly updates the detail pane and selected state. |
| `test_tui_ask_llm_button_trigger` | <ul><li>Enter search query in `#recipes-search`</li><li>Click Ask LLM button (`#recipes-llm-btn`)</li></ul> | Verifies natural language query submission triggers intent processing and query logging. |
| `test_tui_list_focus_auto_selects_first_item` | <ul><li>Focus `#recipes-list` via Tab navigation</li><li>Verify first item is auto-selected and details/action buttons appear</li><li>Press `Down` arrow to verify real-time selection updates</li></ul> | Verifies list views automatically select the first element on focus and sync details on navigation. |

---

### 2. Modal Screens & Sub-views (`test_tui_screens.py`)

| Test Function | Scenario / User Actions | Assertions & Significance |
|---|---|---|
| `test_tui_help_modal_open_and_dismiss` | <ul><li>Press `Ctrl+H` / `F1` to open `HelpScreen`</li><li>Press `Esc` to dismiss</li></ul> | Verifies that shortcut cheat sheets and usage instructions are always accessible and dismissible. |
| `test_tui_chat_options_screen_interaction` | <ul><li>Push `ChatOptionsScreen` for a recipe</li><li>Inspect auto-generated CLI command preview</li><li>Press `Esc` to cancel</li></ul> | Ensures pre-flight configuration accurately renders recipe defaults and live command generation. |
| `test_tui_chat_options_dropdown_search_and_sync` | <ul><li>Open searchable overlay via `Ctrl+F` on agent select</li><li>Select a preset agent option</li><li>Verify synchronized text in `#chat-opts-agent`</li><li>Click `Copy Command` button</li></ul> | Confirms bidirectional synchronization between select dropdowns and manual inputs, along with clipboard copy events. |
| `test_tui_chat_options_tool_append_and_start` | <ul><li>Select tool from `#chat-opts-tool-select` to append</li><li>Verify tool appended to `#chat-opts-tools`</li><li>Click `Start Chat` button (`#chat-opts-start`)</li></ul> | Verifies appending tools via dropdown and starting chat session transitions with configured options. |
| `test_tui_edit_recipe_screen_save` | <ul><li>Open `EditRecipeScreen` with valid TOML</li><li>Click `Save` button</li></ul> | Validates the end-to-end recipe editing, syntax verification, and persistence pipeline. |
| `test_tui_edit_recipe_validation_error` | <ul><li>Enter syntactically invalid TOML (e.g. unclosed bracket)</li><li>Click `Save` button</li><li>Verify screen remains open and `#edit-status-bar` shows error</li><li>Click `Cancel` to discard</li></ul> | **Negative Test**: Prevents file corruption by verifying invalid TOML cannot be saved and presents actionable syntax error diagnostics. |
| `test_tui_edit_recipe_multi_file_switch_and_ctrl_s` | <ul><li>Select different file in `#edit-file-list`</li><li>Verify editor loads selected file content</li><li>Edit and save via `Ctrl+S` shortcut</li></ul> | Confirms multi-file conflict resolution in editor and keyboard-driven saving. |
| `test_tui_delete_recipe_screen_dismiss` | <ul><li>Open `DeleteRecipeScreen` with matched files</li><li>Click `Cancel` button</li></ul> | Guarantees deletion confirmation safety by ensuring cancelation leaves target files untouched. |
| `test_tui_delete_recipe_multi_file_and_confirm` | <ul><li>Open `DeleteRecipeScreen` with duplicate recipe files</li><li>Click `Delete All` button (`#delete-all-btn`)</li><li>Verify all matching files are unlinked</li></ul> | Confirms complete removal of duplicate recipe files and screen dismiss. |
| `test_tui_resume_chat_screen` | <ul><li>Create exported Markdown chat session</li><li>Filter by keyword in `ResumeChatScreen`</li><li>Inspect candidate file list and cancel</li></ul> | Verifies that prior chat transcripts can be discovered, filtered, and selected for interactive resumption. |
| `test_tui_resume_chat_preview_and_confirm` | <ul><li>Select session in `#resume-file-list`</li><li>Verify session preview rendered in `#resume-preview-md`</li><li>Click `Resume Chat` button (`#resume-confirm-btn`)</li></ul> | Validates interactive chat session preview and resumption workflow. |
| `test_tui_chat_screen_fullscreen_toggle` | <ul><li>In `ChatScreen`, toggle messages (`Ctrl+O`), logs (`Ctrl+L`), and prompt (`Ctrl+P`) fullscreen</li><li>Verify `Esc` restores pane when maximized vs closes screen when normal</li></ul> | Confirms robust hierarchical Escape key handling and independent pane expansion in the complex 3-pane chat interface. |
| `test_tui_chat_screen_export_and_history_navigation` | <ul><li>Click `Export Chat` button to write session Markdown</li><li>Execute `action_export_logs` to save log output</li><li>Navigate input history with `Up` (load past query) and `Down` (restore in-progress draft)</li></ul> | Verifies chat/log persistence to file and shell-like prompt history navigation preserving unsubmitted drafts. |
| `test_tui_chat_screen_back_and_empty_submission` | <ul><li>Submit empty/whitespace-only input</li><li>Verify input is ignored</li><li>Click Back button (`#chat-back-btn`) to dismiss screen</li></ul> | Confirms empty query input guard and Back button dismissal. |

---

### 3. TUI Helpers & State Management (`test_tui_helpers.py`)

Table-driven tests using `@pytest.mark.parametrize` cover various input combinations and edge cases:

| Test Function | Parametrized Cases | Assertions & Significance |
|---|---|---|
| `test_filter_items` | <ul><li>Substring matching (`"alpha"`)</li><li>Prefix matching (`"bot"`)</li><li>Empty query (returns all items)</li><li>Non-matching query (returns empty list)</li></ul> | Validates search query filtering robustness across edge cases. |
| `test_find_matching_recipe` | <ul><li>Exact match takes precedence over substring (`"pytest"` &rarr; `pytest`)</li><li>Substring match fallback (`"bot"` &rarr; `pytest_bot`)</li><li>Case-insensitive match (`"DOC"` &rarr; `doc_writer`)</li><li>Non-matching / empty target (`None`)</li></ul> | Verifies exact-match precedence and fuzzy fallback heuristics when locating recipes from user intent. |
| `test_build_chat_command_parts` | <ul><li>Recipe defaults (no extra flags added)</li><li>Single option override (e.g. `--engine cloud`)</li><li>Combined overrides (e.g. `--model`, `--agent`)</li></ul> | Ensures CLI invocation argument construction only appends flags that differ from recipe defaults. |
| `test_parse_recipe_action_intent` | <ul><li>`generate`: Extracts generation prompt</li><li>`resume`: Extracts chat session file</li><li>`delete`: Extracts target recipe</li><li>`edit`: Extracts target recipe</li><li>`search`: Natural language ranked fallback</li></ul> | Verifies intent extraction from Ask LLM responses across structured JSON and fallback string formats. |
| `test_input_history` | <ul><li>Adding entries and trimming beyond `max_size`</li><li>`previous()` navigation backwards through history</li><li>Clamping at the oldest entry</li><li>`next()` navigation restoring the draft</li><li>New append resetting cursor and draft</li><li>`clear()` resetting state</li></ul> | Ensures prompt history navigation acts reliably without losing draft text. |

---

### 4. E2E LLM Workflows (`test_tui_e2e_llm.py`)

End-to-end integration tests using `MockLLMClient` verifying complete UI loops and asynchronous workers:

| Test Function | Workflow / User Scenario | Assertions & Significance |
|---|---|---|
| `test_e2e_tui_generate_recipe_workflow` | <ul><li>Type prompt in `GenerateTab` & submit via `Ctrl+J`</li><li>`MockLLMClient` responds with valid TOML</li><li>Click `Chat with Recipe` button</li></ul> | Verifies full recipe creation pipeline: background thread execution, disk writing (`.toml`), preview display, and direct transition to `ChatOptionsScreen`. |
| `test_e2e_tui_chat_streaming_workflow` | <ul><li>Open `ChatScreen` in direct engine mode</li><li>Submit user question</li><li>`MockLLMClient` streams tokens progressively</li></ul> | Validates real-time token streaming and assembly in `ChatScreen` markdown view and history capture without UI blocking. |
| `test_e2e_tui_chat_agent_execution_workflow` | <ul><li>Open `ChatScreen` in agent mode (`orchestrator`) with tools</li><li>Submit agent task</li><li>`MockLLMClient` responds with final output</li></ul> | Verifies multi-turn agent execution, tools invocation logging, and assistant response capturing. |
| `test_e2e_tui_ask_llm_action_workflow` | <ul><li>Type natural language query in `Recipes` tab</li><li>Click Ask LLM button</li><li>`MockLLMClient` returns JSON action intent</li></ul> | Verifies end-to-end semantic intent parsing, automatic switching to `GenerateTab`, and query pre-population. |

---

### 5. Golden Layout & Visual Snapshot Tests (`test_tui_golden.py`)

Visual snapshot tests ensuring UI layout structure, margins, header/footer placement, and pane boundaries remain consistent:

| Test Function | Screen / Tab | Assertions & Significance |
|---|---|---|
| `test_golden_main_recipes_tab` | `tab-recipes` (Main Screen) | Verifies header, tab strip, search input, recipe list, detail pane, and footer layout. |
| `test_golden_generate_tab` | `tab-generate` (Generate Tab) | Verifies preview scroll, warning log pane, compact status bar, and prompt input bar. |
| `test_golden_logs_tab` | `tab-logs` (Logs Tab) | Verifies compact title toolbar, application rich log container, and footer shortcuts (`Ctrl+K`, `Ctrl+S`). |
| `test_golden_help_screen` | `HelpScreen` Modal | Verifies shortcuts markdown tables, close button, and modal container styling. |
| `test_golden_chat_screen` | `ChatScreen` | Verifies fixed 32-column sidebar, system prompt pane, chat messages, dedicated log pane, and multiline input bar. |
