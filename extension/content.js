/**
 * Meet transcript: Start/Stop — record full meeting, then full transcript (no real-time window).
 */
(() => {
  if (window.top !== window.self) return;

  const meetCodeRegex = /^\/([a-z]{3}-[a-z]{4}-[a-z]{3})$/i;
  if (!meetCodeRegex.test(window.location.pathname)) return;

  const meetCodeMatch = window.location.pathname.match(meetCodeRegex);
  const MEET_CODE = meetCodeMatch ? meetCodeMatch[1] : null;
  if (!MEET_CODE) return;

  const ROOM = MEET_CODE;
  let panel, startStopBtn, statusEl;
  let isRecording = false;
  let speakerMonitorInterval = null;
  let inMeeting = false;
  let lastMuted = null;
  let currentSpeakerStates = {};
  const SPEAKING_CONSECUTIVE_TO_START = 2;
  const SPEAKING_CONSECUTIVE_TO_STOP = 5;
  const speakerStability = {};

  const setStatus = (text) => (statusEl && (statusEl.textContent = text));
  const setRecording = (rec) => {
    isRecording = !!rec;
    if (startStopBtn) startStopBtn.textContent = rec ? "Stop" : "Start";
    setStatus(rec ? "Recording…" : "Idle");
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
      width: "200px",
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

    panel.append(title, startStopBtn, statusEl);
    document.body.appendChild(panel);
    startStopBtn.onclick = () => (isRecording ? handleStop() : handleStart());
    setRecording(false);
  };

  const destroyPanel = () => {
    if (!panel) return;
    if (isRecording) handleStop().catch(() => {});
    panel.remove();
    panel = startStopBtn = statusEl = null;
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
    setRecording(false);
    // Waits only for restart handshake (~1-3s), then backend finishes in background
    await sendExtMessage({ type: "stop" }).catch(() => {});
    setStatus("Processing… Results in Slack");
    startStopBtn.disabled = false;
  };

  const areStatesEqual = (a, b) => {
    const ka = Object.keys(a), kb = Object.keys(b);
    if (ka.length !== kb.length) return false;
    return ka.every((k) => a[k] === b[k]);
  };

  const stabilizedSpeaking = (name, rawSpeaking) => {
    let s = speakerStability[name];
    if (!s) {
      s = speakerStability[name] = { reported: rawSpeaking, consecutive: 0 };
      return rawSpeaking;
    }
    if (rawSpeaking === s.reported) {
      s.consecutive = 0;
      return s.reported;
    }
    s.consecutive += 1;
    if (rawSpeaking && s.consecutive >= SPEAKING_CONSECUTIVE_TO_START) {
      s.reported = true;
      s.consecutive = 0;
      return true;
    }
    if (!rawSpeaking && s.consecutive >= SPEAKING_CONSECUTIVE_TO_STOP) {
      s.reported = false;
      s.consecutive = 0;
      return false;
    }
    return s.reported;
  };

  const scanAndUpdateSpeakers = () => {
    const indicators = document.querySelectorAll('[jscontroller="YQvg8b"].DYfzY');
    const newStates = {};
    indicators.forEach((ind) => {
      const name = findParticipantName(ind);
      newStates[name] = stabilizedSpeaking(name, isSpeaking(ind));
    });
    Object.keys(speakerStability).forEach((name) => {
      if (!(name in newStates)) delete speakerStability[name];
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
      Object.keys(speakerStability).forEach((k) => delete speakerStability[k]);
    }
  };

  chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
    if (msg?.type === "transcript-ready") {
      const hasBoth = msg.transcript_url && msg.audio_url;
      const hasTranscript = !!msg.transcript_url;
      if (hasBoth) {
        setStatus("Done. Transcript and audio uploaded.");
      } else if (hasTranscript) {
        setStatus("Done. Transcript uploaded.");
      } else {
        setStatus("Done. Check Slack for results.");
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
