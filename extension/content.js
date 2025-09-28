(() => {
  if (window.top !== window.self) return;

  const meetCodeRegex = /^\/([a-z]{3}-[a-z]{4}-[a-z]{3})$/i;
  if (!meetCodeRegex.test(window.location.pathname)) return;

  // Extract meet code from URL
  const meetCodeMatch = window.location.pathname.match(meetCodeRegex);
  const MEET_CODE = meetCodeMatch ? meetCodeMatch[1] : null;
  
  console.log("[content] URL pathname:", window.location.pathname);
  console.log("[content] Meet code match:", meetCodeMatch);
  console.log("[content] Extracted MEET_CODE:", MEET_CODE);
  
  if (!MEET_CODE) {
    console.error("Could not extract meet code from URL");
    return;
  }
  
  const ROOM = MEET_CODE; // Use meet code as room ID
  console.log("[content] Using ROOM:", ROOM);

  let panel, startStopBtn, statusEl, transcriptEl;
  let isRecording = false;
  let speakerMonitorInterval = null;
  let inMeeting = false;
  let lastMuted = null;

  // Simple state: participant -> true/false (speaking/silent)
  let currentSpeakerStates = {}; // {"User1": true, "User2": false, ...}

  const addTranscript = (text) => {
    if (transcriptEl && text) {
      const currentContent = transcriptEl.value || "";
      transcriptEl.value = currentContent ? `${text}\n\n${currentContent}` : text;
    }
  };

  // SIMPLE function: scan all participants and their speaking state
  const scanAndUpdateSpeakers = () => {
    const rings = document.querySelectorAll('[jscontroller="YQvg8b"]');
    const newSpeakerStates = {};
    
    // Go through all participants
    Array.from(rings).forEach((ring) => {
      const participantName = findParticipantName(ring);
      const isSpeakingNow = isSpeaking(ring);
      
      // Remember current state of participant
      newSpeakerStates[participantName] = isSpeakingNow;
    });

    // Check if anything changed
    const statesChanged = !areStatesEqual(currentSpeakerStates, newSpeakerStates);
    
    if (statesChanged) {
      // Log changes
      logSpeakerChanges(currentSpeakerStates, newSpeakerStates);
      
      // Update state
      currentSpeakerStates = { ...newSpeakerStates };
      
      // Send new state if recording
      if (isRecording) {
        sendSpeakerStates();
      }
    }
  };

  // Function to compare states
  const areStatesEqual = (oldStates, newStates) => {
    const oldKeys = Object.keys(oldStates);
    const newKeys = Object.keys(newStates);
    
    if (oldKeys.length !== newKeys.length) return false;
    
    for (const participant of newKeys) {
      if (oldStates[participant] !== newStates[participant]) {
        return false;
      }
    }
    return true;
  };

  // Log changes for debugging
  const logSpeakerChanges = (oldStates, newStates) => {
    const time = new Date().toLocaleTimeString();
    
    for (const [participant, isNowSpeaking] of Object.entries(newStates)) {
      const wasSpeaking = oldStates[participant] || false;
      
      if (wasSpeaking !== isNowSpeaking) {
        if (isNowSpeaking) {
          console.log(`[${time}] 🎤 ${participant} started speaking`);
        } else {
          console.log(`[${time}] 🔇 ${participant} stopped speaking`);
        }
      }
    }
    
    // Show current state of all speakers
    const currentSpeakers = Object.entries(newStates)
      .filter(([name, speaking]) => speaking)
      .map(([name]) => name);
      
    if (currentSpeakers.length > 0) {
      console.log(`[${time}] Currently speaking: ${currentSpeakers.join(", ")}`);
    }
  };

  // Send current state of all participants - FIXED field names for backend
  const sendSpeakerStates = () => {
    console.log("[content] Sending speaker states:", currentSpeakerStates);
    
    sendExtMessage({ 
      type: "update-speakers", 
      speakerStates: currentSpeakerStates, // simple object {participant: true/false}
      time: Date.now() // Changed from timestamp to time to match backend expectation
    });
  };

  const reportMicState = (muted) => {
    if (!inMeeting || typeof muted !== "boolean" || muted === lastMuted) return;
    console.log(`[content] Mic state: ${muted ? "MUTED" : "UNMUTED"}`);
    lastMuted = muted;
    sendExtMessage({ type: "meet-mic-state", muted });
  };

  const setStatus = (text) => (statusEl && (statusEl.textContent = text));
  const setRecording = (rec) => {
    isRecording = !!rec;
    if (startStopBtn) startStopBtn.textContent = rec ? "Stop" : "Start";
    setStatus(rec ? "PCM Streaming..." : "Idle");
  };

  const createPanel = () => {
    if (panel) return;
    panel = el("div", {}, {
      position: "fixed",
      bottom: "85px",
      left: "16px",
      zIndex: 999999,
      background: "rgba(28,28,28,0.95)",
      color: "#fff",
      padding: "12px",
      borderRadius: "12px",
      width: "420px",
      boxShadow: "0 8px 24px rgba(0,0,0,0.35)",
      fontFamily: "system-ui,Arial,sans-serif",
    });

    const title = el("div", { textContent: "Qontext Audio Transcriptor (PCM Stream)" }, { fontWeight: "600", marginBottom: "6px" });
    startStopBtn = el("button", { textContent: "Start" }, {
      marginTop: "4px",
      width: "100%",
      padding: "10px",
      borderRadius: "8px",
      border: "1px solid #4a90e2",
      background: "#2d6cdf",
      color: "#fff",
      cursor: "pointer",
    });
    statusEl = el("div", { textContent: "Idle" }, { marginTop: "6px", opacity: "0.85", fontSize: "12px" });
    transcriptEl = el("textarea", { readOnly: true, rows: 10 }, {
      width: "100%",
      marginTop: "8px",
      padding: "8px",
      borderRadius: "8px",
      border: "1px solid #444",
      background: "#111",
      color: "#e6ffe6",
      fontFamily: "monospace",
      resize: "vertical",
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
    console.log("[content] Start PCM streaming button clicked");
    startStopBtn.disabled = true;
    setStatus("Starting PCM session...");

    const startMessage = {
      type: "start",
      opts: { apiBase: API_BASE, room: ROOM},
    };

    const ack = await sendExtMessage(startMessage);
    console.log("[content] Received PCM start response:", ack);

    setRecording(true);

    const micBtn = findMicButton();
    const currentMuted = getMicMuted(micBtn);
    if (currentMuted !== null) {
      sendExtMessage({ type: "meet-mic-state", muted: currentMuted });
    }

    // Immediately send current state
    scanAndUpdateSpeakers();

    // Start constant scanning every 100ms
    speakerMonitorInterval = setInterval(scanAndUpdateSpeakers, 100);
    startStopBtn.disabled = false;
  };

  const handleStop = async () => {
    startStopBtn.disabled = true;
    setStatus("Stopping PCM streaming...");
    
    if (speakerMonitorInterval) {
      clearInterval(speakerMonitorInterval);
      speakerMonitorInterval = null;
    }
     
    await sendExtMessage({ type: "stop" });
    setRecording(false);
    startStopBtn.disabled = false;
  };

  const isInMeeting = () => !!document.querySelector('[jsname="BOHaEe"], [data-participant-id]');
  const checkMeetingState = () => {
    const current = isInMeeting();
    if (current === inMeeting) return;
    inMeeting = current;
    if (inMeeting) {
      console.log("[content] Entered meeting, creating panel");
      createPanel();
      const micBtn = findMicButton();
      const currentMuted = getMicMuted(micBtn);
      reportMicState(currentMuted);
    } else {
      console.log("[content] Left meeting, destroying panel");
      destroyPanel();
      // Reset state
      currentSpeakerStates = {};
    }
  };

  // Listen for transcript messages
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg?.type === "chunk-transcript" && msg.data?.processed_text) {
      const textToShow = msg.data.processed_text.trim();
      if (textToShow && !transcriptEl?.value?.includes(textToShow)) {
        addTranscript(textToShow);
      }
    }
    sendResponse({ ok: true });
  });

  setTimeout(checkMeetingState, 1000);
  setInterval(() => {
    checkMeetingState();
    if (inMeeting) {
      const micBtn = findMicButton();
      const currentMuted = getMicMuted(micBtn);
      reportMicState(currentMuted);
    }
  }, 2000);
  
  new MutationObserver(checkMeetingState).observe(document.body, { childList: true, subtree: true });
})();