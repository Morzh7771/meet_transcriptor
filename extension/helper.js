function isSpeaking(element) {
  // New method: check for audio indicator classes
  // Active speaking has: "DYfzY cYKTje gjg47c sxlEM" or "DYfzY cYKTje gjg47c wEsLMd"
  // Silent has: "DYfzY cYKTje gjg47c" (no sxlEM or wEsLMd)
  const classes = element.className;
  
  // Check if the element has the speaking indicator classes
  // sxlEM or wEsLMd indicate active speaking
  // HX2H7 indicates muted/silent
  return !classes.includes("HX2H7") && (classes.includes("sxlEM") || classes.includes("wEsLMd"));
}

function findParticipantName(audioIndicator) {
  // The audio indicator is nested deep in the participant card
  // We need to traverse up to find the name span
  let current = audioIndicator;
  
  // Go up the DOM tree to find the participant card container
  for (let i = 0; i < 15; i++) {
    current = current?.parentElement;
    if (!current) break;
    
    // Look for the name span with class "notranslate" 
    // It's usually in a container with class "LqxiJe vLRPrf iPFm3e"
    const nameSpan = current.querySelector("span.notranslate");
    if (nameSpan?.textContent?.trim()) {
      const name = nameSpan.textContent.trim();
      // Avoid generic names like button labels
      if (name && name.length > 0 && !name.includes("Закрепить") && !name.includes("Ещё")) {
        return name;
      }
    }
  }
  
  // Fallback: generate unique ID based on timestamp
  return `User_${Date.now() % 10000}`;
}

function findMicButton() {
  return document.querySelector('button[data-is-muted]');
}

function getMicMuted(btn) {
  if (!btn) return null;
  return btn.getAttribute("data-is-muted") === "true";
}

function buildSpeakerSegments(events, durationMs) {
  if (!events || events.length === 0) return [];
  const segments = [];
  const open = new Map();
  const t0 = events[0].t;

  const closeSeg = (user, startMs, endMs) => {
    if (endMs > startMs) {
      segments.push({
        user,
        start: +(startMs / 1000).toFixed(1),
        end: +(endMs / 1000).toFixed(1),
      });
    }
  };

  for (const u of events[0].s) open.set(u, 0);

  for (let i = 1; i < events.length; i++) {
    const rel = Math.max(0, events[i].t - t0);
    const nextSet = new Set(events[i].s);

    for (const [u, startMs] of Array.from(open.entries())) {
      if (!nextSet.has(u)) {
        closeSeg(u, startMs, rel);
        open.delete(u);
      }
    }
    for (const u of nextSet) {
      if (!open.has(u)) open.set(u, rel);
    }
  }

  const endRel = typeof durationMs === "number" ? durationMs : 0;
  for (const [u, startMs] of open.entries()) {
    closeSeg(u, startMs, endRel);
  }
  return segments;
}

// Expose to global scope for content/offscreen scripts
window.isSpeaking = isSpeaking;
window.findParticipantName = findParticipantName;
window.findMicButton = findMicButton;
window.getMicMuted = getMicMuted;
window.buildSpeakerSegments = buildSpeakerSegments;