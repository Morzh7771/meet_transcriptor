
function isSpeaking(element) {
  const classes = element.className;
  return !classes.includes("HX2H7") && (classes.includes("sxlEM") || classes.includes("wEsLMd"));
}

function findParticipantName(ringElement) {
  let current = ringElement;
  for (let i = 0; i < 10; i++) {
    current = current?.parentElement;
    if (!current) break;
    const nameSpan = current.querySelector("span.notranslate");
    if (nameSpan?.textContent?.trim()) {
      return nameSpan.textContent.trim();
    }
  }
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

window.isSpeaking = isSpeaking;
window.findParticipantName = findParticipantName;
window.findMicButton = findMicButton;
window.getMicMuted = getMicMuted;
window.buildSpeakerSegments = buildSpeakerSegments;
