/**
 * Minimal: зашёл на мит → кнопка Start → транскрипт в реальном времени в мини-окне.
 * Без доп. полей (Client ID, Consultant ID и т.д.).
 */
(() => {
  if (window.top !== window.self) return;

  const meetCodeRegex = /^\/([a-z]{3}-[a-z]{4}-[a-z]{3})$/i;
  if (!meetCodeRegex.test(window.location.pathname)) return;

  const meetCodeMatch = window.location.pathname.match(meetCodeRegex);
  const MEET_CODE = meetCodeMatch ? meetCodeMatch[1] : null;
  if (!MEET_CODE) return;

  const ROOM = MEET_CODE;
  let panel, startStopBtn, statusEl, transcriptEl;
  let isRecording = false;
  let speakerMonitorInterval = null;
  let inMeeting = false;
  let lastMuted = null;
  let currentSpeakerStates = {};

  const pad = (n) => String(Math.floor(n)).padStart(2, "0");
  const formatSegment = (s) => {
    const sh = Math.floor(s.start_sec / 3600), sm = Math.floor((s.start_sec % 3600) / 60), ss = Math.floor(s.start_sec % 60);
    const eh = Math.floor(s.end_sec / 3600), em = Math.floor((s.end_sec % 3600) / 60), es = Math.floor(s.end_sec % 60);
    return `(${pad(sh)}:${pad(sm)}:${pad(ss)}-${pad(eh)}:${pad(em)}:${pad(es)}) ${s.speaker || "Unknown"}: ${(s.text || "").trim()}`;
  };

  const addTranscript = (textOrSegments) => {
    if (!transcriptEl) return;
    let text = "";
    if (Array.isArray(textOrSegments) && textOrSegments.length > 0) {
      text = textOrSegments.map((s) => formatSegment(s)).join("\n");
    } else if (typeof textOrSegments === "string" && (text = textOrSegments.trim())) {
      // already formatted
    }
    if (!text) return;
    const cur = transcriptEl.value || "";
    // Chronological order: first chunk on top, latest at bottom (append new below)
    transcriptEl.value = cur ? `${cur}\n\n${text}` : text;
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  };

  const setStatus = (text) => (statusEl && (statusEl.textContent = text));
  const setRecording = (rec) => {
    isRecording = !!rec;
    if (startStopBtn) startStopBtn.textContent = rec ? "Stop" : "Start";
    setStatus(rec ? "Transcribing…" : "Idle");
  };

  const createPanel = () => {
    if (panel) return;
    panel = el("div", {}, {
      position: "fixed",
      bottom: "80px",
      left: "16px",
      zIndex: 999999,
      background: "rgba(28,28,28,0.95)",
      color: "#fff",
      padding: "12px",
      borderRadius: "12px",
      width: "320px",
      maxHeight: "40vh",
      boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
      fontFamily: "system-ui, Arial, sans-serif",
      display: "flex",
      flexDirection: "column",
    });

    const title = el("div", { textContent: "Transcript" }, { fontWeight: "600", marginBottom: "8px", fontSize: "14px" });
    startStopBtn = el("button", { textContent: "Start" }, {
      width: "100%",
      padding: "10px",
      borderRadius: "8px",
      border: "1px solid #4a90e2",
      background: "#2d6cdf",
      color: "#fff",
      cursor: "pointer",
      fontSize: "14px",
    });
    statusEl = el("div", { textContent: "Idle" }, { marginTop: "6px", opacity: 0.85, fontSize: "12px" });
    transcriptEl = el("textarea", { readOnly: true, rows: 8, placeholder: "Transcript will appear here…" }, {
      width: "100%",
      marginTop: "8px",
      padding: "8px",
      borderRadius: "8px",
      border: "1px solid #444",
      background: "#111",
      color: "#e6ffe6",
      fontFamily: "monospace",
      fontSize: "12px",
      resize: "vertical",
      flex: "1",
      minHeight: "80px",
    });

    panel.append(title, startStopBtn, statusEl, transcriptEl);
    document.body.appendChild(panel);
    startStopBtn.onclick = () => (isRecording ? handleStop() : handleStart());
    setRecording(false);
  };

  const destroyPanel = () => {
    if (!panel) return;
    if (isRecording) handleStop().catch(() => {});
    panel.remove();
    panel = startStopBtn = statusEl = transcriptEl = null;
  };

  const handleStart = async () => {
    startStopBtn.disabled = true;
    setStatus("Starting…");
    const ack = await sendExtMessage({
      type: "start",
      opts: { apiBase: API_BASE, room: ROOM },
    });
    if (ack?.ok) {
      setRecording(true);
      const micBtn = findMicButton();
      const muted = getMicMuted(micBtn);
      if (muted !== null) sendExtMessage({ type: "meet-mic-state", muted });
      scanAndUpdateSpeakers();
      speakerMonitorInterval = setInterval(scanAndUpdateSpeakers, 100);
    } else {
      setStatus("Error: " + (ack?.error || "Failed to start"));
    }
    startStopBtn.disabled = false;
  };

  const handleStop = async () => {
    startStopBtn.disabled = true;
    setStatus("Stopping…");
    if (speakerMonitorInterval) {
      clearInterval(speakerMonitorInterval);
      speakerMonitorInterval = null;
    }
    await sendExtMessage({ type: "stop" });
    setRecording(false);
    startStopBtn.disabled = false;
  };

  const areStatesEqual = (a, b) => {
    const ka = Object.keys(a), kb = Object.keys(b);
    if (ka.length !== kb.length) return false;
    return ka.every((k) => a[k] === b[k]);
  };

  const scanAndUpdateSpeakers = () => {
    const indicators = document.querySelectorAll('[jscontroller="YQvg8b"].DYfzY');
    const newStates = {};
    indicators.forEach((ind) => {
      newStates[findParticipantName(ind)] = isSpeaking(ind);
    });
    if (!areStatesEqual(currentSpeakerStates, newStates)) {
      currentSpeakerStates = { ...newStates };
      if (isRecording) sendExtMessage({ type: "update-speakers", speakerStates: currentSpeakerStates, time: Date.now() });
    }
  };

  const reportMicState = (muted) => {
    if (!inMeeting || typeof muted !== "boolean" || muted === lastMuted) return;
    lastMuted = muted;
    sendExtMessage({ type: "meet-mic-state", muted });
  };

  const isInMeeting = () => !!document.querySelector('[jsname="BOHaEe"], [data-participant-id]');
  const checkMeetingState = () => {
    const cur = isInMeeting();
    if (cur === inMeeting) return;
    inMeeting = cur;
    if (inMeeting) {
      createPanel();
      reportMicState(getMicMuted(findMicButton()));
    } else {
      destroyPanel();
      currentSpeakerStates = {};
    }
  };

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === "chunk-transcript" && msg.data) {
      const d = msg.data;
      if (d.segments && Array.isArray(d.segments) && d.segments.length > 0) {
        addTranscript(d.segments);
      } else if (d.processed_text && String(d.processed_text).trim()) {
        addTranscript(String(d.processed_text).trim());
      }
    }
    sendResponse({ ok: true });
    return true;
  });

  setTimeout(checkMeetingState, 1000);
  setInterval(() => {
    checkMeetingState();
    if (inMeeting) reportMicState(getMicMuted(findMicButton()));
  }, 2000);
  new MutationObserver(checkMeetingState).observe(document.body, { childList: true, subtree: true });
})();
