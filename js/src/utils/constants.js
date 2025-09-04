// Google Meet element class names for join button detection
const TARGET_CLASS_LIST = [
    "UywwFc-LgbsSe",
    "UywwFc-LgbsSe-OWXEXe-SfQLQb-suEOdc",
    "UywwFc-LgbsSe-OWXEXe-dgl2Hf",
    "UywwFc-StrnGf-YYd4I-VtOx3e",
    "tusd3",
    "IyLmn",
    "QJgqC"
  ];
  
  // Common selectors used in Google Meet
  const SELECTORS = {
    EMAIL_INPUT: 'input[type="email"]',
    PASSWORD_INPUT: 'input[type="password"]',
    MEETING_CODE_INPUT: 'input[type="text"]',
    CHAT_CONTAINER: 'div.Ge9Kpc.z38b6',
    CHAT_INPUT: 'textarea[jsname="YPqjbf"]',
    SPEAKER_CARDS: 'div.cxdMu.KV1GEc[aria-label]',
    DROPDOWN_BUTTONS: '[jsname="A5il2e"]',
    PARTICIPANTS_OPENER: '.VYBDae-Bz112c-LgbsSe.VYBDae-Bz112c-LgbsSe-OWXEXe-SfQLQb-suEOdc.hk9qKe.S5GDme.Ld74n'
  };
  
  // Timing constants
  const TIMING = {
    SHORT_DELAY: 500,
    MEDIUM_DELAY: 1000,
    LONG_DELAY: 2000,
    TYPING_DELAY: 120,
    EMAIL_TYPING_DELAY: 150,
    MINUTE_INTERVAL: 60000,
    TRACKING_INTERVAL: 50
  };
  
  module.exports = {
    TARGET_CLASS_LIST,
    SELECTORS,
    TIMING
  };