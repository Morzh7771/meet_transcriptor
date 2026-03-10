/** Meet DOM helpers: mic button, participant name, speaking state. Used by content script. */
function isSpeaking(element) {
  const classes = element.className || "";
  return !classes.includes("HX2H7") && (classes.includes("sxlEM") || classes.includes("wEsLMd"));
}

function findParticipantName(audioIndicator) {
  let current = audioIndicator;
  for (let i = 0; i < 15; i++) {
    current = current?.parentElement;
    if (!current) break;
    const nameSpan = current.querySelector("span.notranslate");
    if (nameSpan?.textContent?.trim()) {
      const name = nameSpan.textContent.trim();
      if (name && !name.includes("Pin") && !name.includes("More")) return name;
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

window.isSpeaking = isSpeaking;
window.findParticipantName = findParticipantName;
window.findMicButton = findMicButton;
window.getMicMuted = getMicMuted;
