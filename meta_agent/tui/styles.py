"""CSS styles for meta_agent TUI."""

APP_CSS = """
/* Toolbar */
#recipes-toolbar, #agents-toolbar, #tools-toolbar {
    height: 3;
    padding: 0 1;
}
#recipes-search, #agents-search, #tools-search {
    width: 1fr;
}
#recipes-llm-btn, #agents-llm-btn, #tools-llm-btn {
    width: 14;
}
#recipes-sort, #agents-sort, #tools-sort {
    width: 18;
}

/* Body */
#recipes-body, #agents-body, #tools-body {
    height: 1fr;
}

/* Sidebar */
#recipes-sidebar, #agents-sidebar, #tools-sidebar {
    width: 30;
    border-right: solid $primary;
    overflow-y: auto;
}

/* Detail pane */
#recipes-detail, #agents-detail, #tools-detail {
    width: 1fr;
    padding: 1 2;
    overflow-y: auto;
    overflow-x: hidden;
}

Markdown {
    height: auto;
}

LoadingIndicator {
    height: 1;
}

/* Chat button */
#recipes-chat-btn {
    margin-top: 1;
    display: none;
}

/* Generate screen */
#gen-title {
    margin: 1 2;
    text-style: bold;
    color: $accent;
}
#gen-label {
    margin: 0 2;
}
#gen-input {
    margin: 0 2 1 2;
}
#gen-btn {
    margin: 0 2;
}
#gen-status {
    margin: 1 2;
}

/* Chat options screen */
#chat-opts-title {
    margin: 1 2;
    text-style: bold;
    color: $accent;
}
.chat-opts-label {
    margin: 1 2 0 2;
}
#chat-opts-engine, #chat-opts-model, #chat-opts-agent, #chat-opts-tools {
    margin: 0 2;
}
#chat-opts-system {
    margin: 0 2;
    height: 8;
}
#chat-opts-cmd {
    margin: 0 2 1 2;
    padding: 1 2;
    background: $surface;
    border: solid $primary;
    overflow-x: auto;
    height: auto;
}
#chat-opts-buttons {
    margin: 0 2 1 2;
    height: 3;
}
#chat-opts-start {
    margin-right: 1;
}

/* Chat screen */
#chat-screen-layout {
    height: 1fr;
}
#chat-info-sidebar {
    width: 32;
    border-right: solid $primary;
    padding: 1 2;
    overflow-y: auto;
}
#chat-sidebar-title {
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}
.chat-sidebar-item {
    margin-bottom: 1;
}
#chat-sidebar-prompt {
    height: 8;
    border: solid $secondary;
    padding: 0 1;
    margin-bottom: 1;
}
#chat-back-btn {
    margin-top: 1;
}
#chat-main-pane {
    width: 1fr;
    height: 1fr;
    padding: 1 2;
}
#chat-messages {
    height: 1fr;
    border: solid $primary;
    padding: 1 2;
    margin-bottom: 1;
    overflow-y: auto;
}
#chat-log-pane {
    height: 8;
    border: solid $warning;
    padding: 0 1;
    margin-bottom: 1;
    background: $surface;
}
#chat-log-title {
    text-style: bold;
    color: $warning;
}
#chat-rich-log {
    height: 1fr;
}
#chat-status-bar {
    height: 1;
    margin-bottom: 1;
    color: $accent;
}
#chat-input-bar {
    height: 3;
}
#chat-input {
    width: 1fr;
}
#chat-send-btn {
    width: 12;
    margin-left: 1;
}
"""
