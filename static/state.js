export const state = {
  apiKey: localStorage.getItem("onyx_key") || "",
  currentSessionId: null,
  activeTab: "preview",
  lastResponse: null,
  lastRequest: null,
  sessions: [],
  crawls: [],
  previewDark: true
};

export const API_BASE = "";
export const TABS = ["preview", "screenshot", "markdown", "code", "json"];
export const MAX_HISTORY = 20;

// State Persistence logic for Request Builder
export function saveBuilderState() {
  if (state.lastRequest) {
    localStorage.setItem("onyx_builder_state", JSON.stringify(state.lastRequest));
  }
}

export function loadBuilderState() {
  try {
    const data = localStorage.getItem("onyx_builder_state");
    if (data) {
      return JSON.parse(data);
    }
  } catch (e) {
    console.error("Error parsing builder state", e);
  }
  return null;
}
