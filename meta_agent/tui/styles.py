"""CSS styles for meta_agent TUI."""

APP_CSS = """
/* Toast Notification Positioning (Top-Right) */
ToastRack {
    dock: top;
    align: right top;
    margin-top: 1;
    margin-right: 1;
    margin-bottom: 0;
}

/* Toolbar */
#recipes-toolbar, #agents-toolbar, #tools-toolbar, #engines-toolbar, #models-toolbar {
    height: 3;
    padding: 0 1;
    align-vertical: middle;
}
#recipes-search, #agents-search, #tools-search, #engines-search, #models-search {
    width: 1fr;
    height: 3;
}
#recipes-llm-btn, #agents-llm-btn, #tools-llm-btn, #engines-llm-btn, #models-llm-btn {
    width: 16;
    height: 3;
}

/* Body */
#recipes-body, #agents-body, #tools-body, #engines-body, #models-body {
    height: 1fr;
}

/* Sidebar */
#recipes-sidebar, #agents-sidebar, #tools-sidebar, #engines-sidebar, #models-sidebar {
    width: 30;
    border-right: solid $primary;
    overflow-y: auto;
}

/* Main & Detail pane */
#recipes-main-pane, #agents-main-pane, #tools-main-pane, #engines-main-pane, #models-main-pane {
    width: 1fr;
    height: 1fr;
}
#recipes-detail, #agents-detail, #tools-detail, #engines-detail, #models-detail {
    height: 1fr;
    padding: 1 2;
    overflow-y: auto;
    overflow-x: auto;
}
#recipes-log-pane, #agents-log-pane, #tools-log-pane, #engines-log-pane, #models-log-pane {
    height: 8;
    border-top: solid $primary;
    background: $surface;
    padding: 0 1;
}
.resource-log-title {
    text-style: bold;
    color: $accent;
}

/* Pane Headers & Maximize Button */
.pane-header {
    height: 1;
    margin-bottom: 0;
    align-vertical: middle;
}
.pane-title {
    width: 1fr;
    text-style: bold;
    color: $accent;
}
.pane-max-btn {
    min-width: 3;
    height: 1;
    border: none;
    padding: 0 1;
    background: $primary;
    color: $text;
}
.pane-max-btn:hover {
    background: $accent;
}
.pane-hidden {
    display: none;
}

/* Fullscreen / Maximized state rules for ResourceTab */
.maximized-detail #recipes-sidebar,
.maximized-detail #agents-sidebar,
.maximized-detail #tools-sidebar,
.maximized-detail #engines-sidebar,
.maximized-detail #models-sidebar {
    display: none;
}
.maximized-detail #recipes-log-pane,
.maximized-detail #agents-log-pane,
.maximized-detail #tools-log-pane,
.maximized-detail #engines-log-pane,
.maximized-detail #models-log-pane {
    display: none;
}
.maximized-detail #recipes-detail,
.maximized-detail #agents-detail,
.maximized-detail #tools-detail,
.maximized-detail #engines-detail,
.maximized-detail #models-detail {
    height: 1fr;
    border: none;
    padding: 0 1;
}

.maximized-log #recipes-sidebar,
.maximized-log #agents-sidebar,
.maximized-log #tools-sidebar,
.maximized-log #engines-sidebar,
.maximized-log #models-sidebar {
    display: none;
}
.maximized-log #recipes-detail,
.maximized-log #agents-detail,
.maximized-log #tools-detail,
.maximized-log #engines-detail,
.maximized-log #models-detail {
    display: none;
}
.maximized-log #recipes-log-pane,
.maximized-log #agents-log-pane,
.maximized-log #tools-log-pane,
.maximized-log #engines-log-pane,
.maximized-log #models-log-pane {
    height: 1fr;
    border: none;
    border-top: none;
    padding: 0 1;
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
    height: 4;
    align-vertical: middle;
}
#gen-input {
    width: 1fr;
    height: 4;
}
#gen-submit-btn {
    width: 20;
    margin-left: 1;
    height: 4;
}

/* Fullscreen / Maximized state rules for GenerateTab */
.maximized-preview #gen-sidebar,
.maximized-preview #gen-log-pane,
.maximized-preview #gen-status-bar,
.maximized-preview #gen-input-bar {
    display: none;
}
.maximized-preview #gen-main-pane {
    padding: 0;
}
.maximized-preview #gen-preview-scroll {
    height: 1fr;
    border: none;
    padding: 0 1;
    margin-bottom: 0;
}

.maximized-log #gen-sidebar,
.maximized-log #gen-preview-scroll,
.maximized-log #gen-status-bar,
.maximized-log #gen-input-bar {
    display: none;
}
.maximized-log #gen-main-pane {
    padding: 0;
}
.maximized-log #gen-log-pane {
    height: 1fr;
    border: none;
    padding: 0 1;
    margin-bottom: 0;
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
    height: 4;
    align-vertical: middle;
}
#chat-input {
    width: 1fr;
    height: 4;
}
#chat-send-btn {
    width: 16;
    margin-left: 1;
    height: 4;
}

/* Fullscreen / Maximized state rules for ChatScreen */
.maximized-messages #chat-info-sidebar,
.maximized-messages #chat-log-pane {
    display: none;
}
.maximized-messages #chat-main-pane {
    padding: 0;
}
.maximized-messages #chat-messages {
    height: 1fr;
    border: none;
    padding: 0 1;
    margin-bottom: 0;
}

.maximized-log #chat-info-sidebar,
.maximized-log #chat-messages,
.maximized-log #chat-status-bar,
.maximized-log #chat-input-bar {
    display: none;
}
.maximized-log #chat-main-pane {
    padding: 0;
}
.maximized-log #chat-log-pane {
    height: 1fr;
    border: none;
    padding: 0 1;
    margin-bottom: 0;
}

.maximized-prompt #chat-main-pane {
    display: none;
}
.maximized-prompt #chat-info-sidebar {
    width: 1fr;
    border-right: none;
    padding: 0 1;
}
.maximized-prompt #chat-sidebar-title,
.maximized-prompt .chat-sidebar-item,
.maximized-prompt #chat-sidebar-actions {
    display: none;
}
.maximized-prompt #chat-sidebar-prompt {
    height: 1fr;
    border: none;
    padding: 0 1;
    margin-bottom: 0;
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

/* App-level Log Tab */
#app-log-toolbar {
    height: 3;
    margin: 1 2 0 2;
    align-vertical: middle;
}
#app-log-title {
    width: 1fr;
    text-style: bold;
    color: $accent;
}
#app-log-clear-btn {
    margin-right: 1;
}
#app-log-container {
    height: 1fr;
    margin: 1 2;
    padding: 1;
    border: solid $warning;
    background: $surface;
}
#app-rich-log {
    height: 1fr;
}

/* Fullscreen / Maximized state rules for LogTab */
.maximized-log #app-log-toolbar {
    display: none;
}
.maximized-log #app-log-container {
    margin: 0;
    border: none;
    padding: 0 1;
    height: 1fr;
}

/* Resume Chat Modal */
#resume-modal-container {
    width: 80%;
    height: 80%;
    background: $surface;
    border: solid $accent;
    padding: 1 2;
    align: center middle;
}
#resume-modal-title {
    text-style: bold;
    color: $accent;
    margin-bottom: 1;
}
#resume-modal-subtitle {
    margin-bottom: 1;
    color: $text;
}
#resume-manual-bar {
    height: 3;
    margin-bottom: 1;
}
#resume-path-input {
    width: 1fr;
}
#resume-load-btn {
    margin-left: 1;
}
#resume-main-body {
    height: 1fr;
    margin-bottom: 1;
}
#resume-file-list-pane {
    width: 35%;
    border-right: solid $primary;
    padding-right: 1;
}
#resume-list-title {
    text-style: bold;
    margin-bottom: 1;
}
#resume-filter-input {
    margin-bottom: 1;
}
#resume-file-list {
    height: 1fr;
}
#resume-preview-box {
    height: 1fr;
    padding: 1;
    border: solid $primary;
    margin-left: 1;
    background: $background;
    overflow-y: auto;
}
#resume-status-bar {
    height: 1;
    color: $error;
}
#resume-modal-buttons {
    height: 3;
    margin-top: 1;
    align-horizontal: right;
}
#resume-modal-buttons Button {
    margin-left: 1;
}
"""
