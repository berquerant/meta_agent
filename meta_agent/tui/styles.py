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

/* Generate screen (2-pane layout) */
#gen-screen-layout {
    height: 1fr;
}
#gen-sidebar {
    width: 32;
    background: $surface;
    border: solid $primary;
    padding: 1;
}
#gen-sidebar-title {
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}
.gen-sidebar-item {
    margin-bottom: 1;
    color: $text;
}
#gen-sidebar-actions {
    margin-top: 1;
}
#gen-sidebar-actions Button {
    margin-bottom: 1;
    width: 100%;
}
#gen-main-pane {
    width: 1fr;
    padding: 0 1;
}
#gen-preview-scroll {
    height: 1fr;
    border: solid $primary;
    padding: 1 2;
    margin-bottom: 1;
    overflow-y: auto;
}
#gen-log-pane {
    height: 8;
    border: solid $warning;
    padding: 0 1;
    margin-bottom: 1;
    background: $surface;
}
#gen-log-title {
    text-style: bold;
    color: $warning;
}
#gen-rich-log {
    height: 1fr;
}
#gen-status-bar {
    height: 1;
    margin-bottom: 1;
    color: $accent;
}
#gen-input-bar {
    height: 3;
}
#gen-input {
    width: 1fr;
}
#gen-submit-btn {
    width: 14;
    margin-left: 1;
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
.chat-opts-row {
    margin: 0 2;
    height: 3;
}
.chat-opts-row Select {
    width: 28;
    margin-right: 1;
}
.chat-opts-row Input {
    width: 1fr;
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

#recipes-actions {
    margin-top: 1;
    height: 3;
}
#recipes-chat-btn {
    margin-right: 1;
}
#recipes-edit-btn {
    margin-right: 1;
}

/* Help screen modal */
#help-modal-container {
    width: 80%;
    height: 80%;
    background: $surface;
    border: solid $accent;
    padding: 1 2;
    align: center middle;
}
#help-markdown-container {
    height: 1fr;
    margin-bottom: 1;
}
#help-close-btn {
    width: 24;
    align-horizontal: center;
}

/* Delete confirmation modal */
#delete-modal-container {
    width: 75%;
    height: 75%;
    background: $surface;
    border: solid $error;
    padding: 1 2;
    align: center middle;
}
#delete-modal-title {
    text-style: bold;
    color: $error;
    margin-bottom: 1;
}
#delete-modal-subtitle {
    margin-bottom: 1;
    color: $text;
}
#delete-file-path {
    margin-bottom: 1;
    color: $accent;
}
#delete-multi-body {
    height: 1fr;
    margin-bottom: 1;
}
#delete-file-list-pane {
    width: 35%;
    border-right: solid $primary;
    padding-right: 1;
}
#delete-list-title {
    text-style: bold;
    margin-bottom: 1;
}
#delete-file-list {
    height: 1fr;
}
#delete-preview-box {
    height: 1fr;
    padding: 1;
    border: solid $primary;
    margin-left: 1;
    background: $background;
    overflow-y: auto;
}
#delete-modal-buttons {
    height: 3;
    margin-top: 1;
    align-horizontal: right;
}
#delete-modal-buttons Button {
    margin-left: 1;
}

/* Edit recipe modal */
#edit-modal-container {
    width: 85%;
    height: 85%;
    background: $surface;
    border: solid $primary;
    padding: 1 2;
    align: center middle;
}
#edit-modal-title {
    text-style: bold;
    color: $primary;
    margin-bottom: 1;
}
#edit-modal-subtitle {
    margin-bottom: 1;
    color: $text;
}
#edit-file-path {
    margin-bottom: 1;
    color: $accent;
}
#edit-multi-body {
    height: 1fr;
    margin-bottom: 1;
}
#edit-file-list-pane {
    width: 30%;
    border-right: solid $primary;
    padding-right: 1;
}
#edit-list-title {
    text-style: bold;
    margin-bottom: 1;
}
#edit-file-list {
    height: 1fr;
}
#edit-editor-pane {
    width: 70%;
    margin-left: 1;
    height: 1fr;
}
#edit-text-area {
    height: 1fr;
    border: solid $secondary;
}
#edit-status-bar {
    height: 1;
    margin-top: 1;
    color: $error;
}
#edit-modal-buttons {
    height: 3;
    margin-top: 1;
    align-horizontal: right;
}
#edit-modal-buttons Button {
    margin-left: 1;
}
"""
