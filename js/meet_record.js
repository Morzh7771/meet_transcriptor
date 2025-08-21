const puppeteer = require("puppeteer-extra");
const StealthPlugin = require("puppeteer-extra-plugin-stealth");
const { launch, getStream } = require("puppeteer-stream");
const fs = require("fs");
const { executablePath } = require("puppeteer");
const WebSocket = require("ws");

puppeteer.use(StealthPlugin());
async function keepAudioAlive(page) {
  await page.evaluate(() => {
    try {
      if (window.__silence_ctx) return;
      const AC = window.AudioContext || window.webkitAudioContext;
      const ctx = new AC();
      const src = ctx.createBufferSource();
      const buf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
      src.buffer = buf;
      src.loop = true;
      src.connect(ctx.destination);
      src.start();
      window.__silence_ctx = ctx;
      window.__silence_src = src;
      console.log("🔊 Silent audio keepalive started");
    } catch (e) {
      console.error("keepAudioAlive error:", e);
    }
  });
}
const TARGET_CLASS_LIST = [
  "UywwFc-LgbsSe",
  "UywwFc-LgbsSe-OWXEXe-SfQLQb-suEOdc",
  "UywwFc-LgbsSe-OWXEXe-dgl2Hf",
  "UywwFc-StrnGf-YYd4I-VtOx3e",
  "tusd3",
  "IyLmn",
  "QJgqC"
];

function startMinuteScreenshotAndKeypress(page, sessionState, label = "minute_tick", intervalMs = 60_000) {
  if (!sessionState) sessionState = {};
  if (sessionState.minuteInterval) clearInterval(sessionState.minuteInterval);

  let running = false;

  const minuteInterval = setInterval(async () => {
    if (running) return;
    if (sessionState.terminateRequested || !page || page.isClosed()) return;

    running = true;
    try {
      // Ensure the Meet tab has focus before keypress.
      await page.bringToFront();

      // Press "b" (use code for layout safety).
      await page.keyboard.press("Shift")

      // Take a labeled screenshot (increments global step counter).
      await logStep(page, label);
    } catch (e) {
      console.error("❌ minute task error:", e);
    } finally {
      running = false;
    }
  }, intervalMs);

  sessionState.minuteInterval = minuteInterval;
  return minuteInterval;
}

const sleep = ms => new Promise(res => setTimeout(res, ms));

let stepCounter = 1;
async function logStep(page, message) {
  const filename = `js/screenshots/step_${String(stepCounter++).padStart(2, "0")}_${message.replace(/\s+/g, "_")}.png`;
  await page.screenshot({ path: filename, fullPage: true });
}
async function open_dropdown(page){
  let buttons = await page.$$('[jsname="A5il2e"]');
  if (buttons.length === 0) {
    await sleep(2000);                    
    const opener = await page.$(
      '.VYBDae-Bz112c-LgbsSe.VYBDae-Bz112c-LgbsSe-OWXEXe-SfQLQb-suEOdc.hk9qKe.S5GDme.Ld74n'
    );
    if (opener) {
      await opener.click();
      await sleep(1000);
    }
    buttons = await page.$$('[jsname="A5il2e"]');
  }
  await find_people(buttons)
  await sleep(1500);
  await find_chat(buttons)
}
async function find_people(buttons) {
  if (buttons.length > 0) {
    for (const btn of buttons) {
      const hasPeopleIcon = await btn
        .$eval('i', i => i.textContent.includes('people'))
        .catch(() => false);
      if (hasPeopleIcon) {
        await btn.click();
        break;
      }
    }
  }
  return true;
}
async function find_chat(buttons) {
  if (buttons.length > 0) {
    for (const btn of buttons) {
      const hasPeopleIcon = await btn
        .$eval('i', i => i.textContent.includes('chat'))
        .catch(() => false);
      if (hasPeopleIcon) {
        await btn.click();
        break;
      }
    }
  }
  return true;
}

async function wait_meet_join(page) {
  const selectors = [
    'div.XDoBEd-JGcpL-MkD1Ye.bXvFAe.plQnQb',
    'div.U0e0y',
  ];

  await page.waitForFunction(
    (selArray) =>
      selArray.every((selector) => {
        const el = document.querySelector(selector);
        return (
          !el ||
          el.hidden ||
          el.style.display === 'none' ||
          el.offsetParent === null
        );
      }),
    { polling: 'mutation', timeout: 0 },
    selectors
  );
}

async function tabUntilAllClassesMatch(page, maxSteps = 30) {
  await page.keyboard.press('Enter');
  for (let i = 0; i < maxSteps; i++) {
    await page.keyboard.press("Tab");
    await sleep(500);

    const activeInfo = await page.evaluate(() => {
      const el = document.activeElement;
      return {
        tag: el?.tagName || "",
        classList: Array.from(el?.classList || []),
        text: el?.innerText?.trim()?.slice(0, 100) || "",
      };
    });

    const hasAllClasses = TARGET_CLASS_LIST.every(cls =>
      activeInfo.classList.includes(cls)
    );

    if (hasAllClasses) return true;
  }

  return false;
}

async function trackAndSendSpeakerVectors(page, ws, chatWS, sessionState, time_start) {
  while (!sessionState.terminateRequested) {
    // Abort if the Meet page is closed.
    if (!page || page.isClosed()) {
      sessionState.terminateRequested = true;
      break;
    }

    try {
      const data = await page.evaluate((startTime) => {
        /* ---------------------- SPEAKER CARDS ---------------------- */
        const cards = Array.from(
          document.querySelectorAll('div.cxdMu.KV1GEc[aria-label]')
        );
        const speakers = {};
        cards.forEach((card) => {
          const name = card.getAttribute('aria-label');
          const indicator = card.querySelector('div[jsname="QgSmzd"]');
          const isSpeaking =
            indicator ? !indicator.classList.contains('gjg47c') : false;
          speakers[name] = isSpeaking;
        });

        /* ------------------------- CHAT --------------------------- */
        const chatContainer = document.querySelector('div.Ge9Kpc.z38b6');
        const chat = [];

        if (chatContainer) {
          // Each Ss4fHf element may contain one or many RLrADb message nodes.
          const blocks = Array.from(chatContainer.querySelectorAll('div.Ss4fHf'));

          blocks.forEach((block) => {
            // Static sender name and timestamp for all messages within this block.
            const senderName =
              block.querySelector('.poVWob')?.innerText.trim() || '';
            const timestamp =
              block.querySelector('.MuzmKe')?.innerText.trim() || '';

            // Grab every individual message inside the block.
            const messages = Array.from(block.querySelectorAll('div.RLrADb'));
            messages.forEach((msgNode) => {
              const text =
                msgNode.querySelector('[jsname="dTKtvb"]')?.innerText.trim() ||
                '';
              chat.push({
                name: senderName,
                time: timestamp,
                raw_time: Date.now(),
                massage: text, // field name requested by user
              });
            });
          });
        }

        // return { time: Date.now() - startTime, speakers, chat };
        return { time: Date.now(), speakers, chat };
      }, time_start);

      console.log(
        '🕒',
        data.time,
        'ms | 🎙',
        JSON.stringify(data.speakers),
        '| 💬 messages:',
        data.chat
      );

      // Expand the participants fly-out if no speaker cards are detected.
      if (Object.keys(data.speakers).length === 0) {
        await open_dropdown(page);
      }

      // Stream the snapshot via WebSocket.
      if (ws && ws.readyState === ws.OPEN) {
        ws.send(JSON.stringify({ time: data.time, speakers: data.speakers }));
      }
      if (data.chat.length && chatWS && chatWS.readyState === WebSocket.OPEN && chatWS.bufferedAmount < 1_000_000) {
        chatWS.send(JSON.stringify({ chat: data.chat }));
      }
    } catch (err) {
      console.error('❌ trackAndSendSpeakerVectors error:', err);
      break;
    }

    await sleep(50);
  }
}

async function launchBrowser() {
  const browser = await launch({
    headless: false,
    executablePath: executablePath(),
    ignoreDefaultArgs: ['--mute-audio'],
    args: [
      "--disable-notifications",
      "--window-size=1920,1080",
      "--autoplay-policy=no-user-gesture-required",
      "--no-sandbox",
      "--no-first-run",
      "--no-default-browser-check",
      "--disable-features=TranslateUI",
      "--disable-extensions",
      "--disable-background-timer-throttling",
      "--disable-renderer-backgrounding",
      "--disable-backgrounding-occluded-windows",
      "--disable-features=AudioServiceOutOfProcess",
      "--autoplay-policy=no-user-gesture-required",
      "--disable-features=CalculateNativeWinOcclusion",
    ],
    closeDelay: 2000,
  });

  const page = await browser.newPage();
  return { browser, page };
}

async function joinMeetAndRecord(email, password, sessionState, page, meetCode, port, chatPort) {
  await main(email, password, meetCode, port, sessionState, page, chatPort);
}

async function sendMessageToChat(page, message) {
  console.log("Inside sendMessageToChat sending: ", message);

  const chatContainer = await page.$('div.Ge9Kpc.z38b6');
  if (!chatContainer) {
    console.log("Chat container not found. Opening chat...");
    await open_dropdown(page);
    await sleep(1500);
  }

 const inputField = await page.$('textarea[jsname="YPqjbf"]');

  if (inputField) {
    await inputField.type(message);
    await inputField.press('Enter');
    console.log("Message sent: " + message);

  } else {
    console.error("Message input field not found.");
  }
}

async function main(email, password, meetCode, port, sessionState, page, chatPort) {
  if (!fs.existsSync("js/screenshots")) fs.mkdirSync("js/screenshots");

  await page.goto("https://accounts.google.com/", { waitUntil: "networkidle2" });
  await page.browser().defaultBrowserContext().overridePermissions("https://meet.google.com/", ["microphone", "camera", "notifications"]);
  await logStep(page, "Login page");

  await page.waitForSelector('input[type="email"]');
  await page.click('input[type="email"]');
  await page.keyboard.type(email, { delay: 150 });
  await sleep(500);
  await logStep(page, "Email typed");
  await page.click("#identifierNext");

  await page.waitForSelector('input[type="password"]', { visible: true });
  await sleep(700);
  await page.keyboard.type(password, { delay: 120 });
  await sleep(500);
  await logStep(page, "Password typed");
  await page.click("#passwordNext");
  await page.waitForNavigation({ waitUntil: "networkidle2" });
  await sleep(2000);

  await page.goto("https://meet.google.com/", { waitUntil: "networkidle2" });
  await logStep(page, "Meet homepage");
  await page.waitForSelector('input[type="text"]');
  await page.click('input[type="text"]');
  await page.keyboard.type(meetCode, { delay: 120 });
  await logStep(page, "Meeting code typed");
  await sleep(400);
  await page.keyboard.press('Enter');
  await page.waitForNavigation({ waitUntil: "networkidle2" });
  await logStep(page, "Meeting page");

  await tabUntilAllClassesMatch(page);
  await page.keyboard.press("Enter");
  await logStep(page, "Joined meeting");
  await sleep(3000);

  await wait_meet_join(page)

  await logStep(page, "Meeting entered");
  await sleep(5000);
  await page.keyboard.press('Enter');
  await sleep(2000);

  await open_dropdown(page)

  await logStep(page, "Participants panel");
  await sleep(1000);

  await keepAudioAlive(page);

  startMinuteScreenshotAndKeypress(page, sessionState);
  const time_start = Date.now();
  const ws = new WebSocket(`ws://localhost:${port}`);
  const chatWS  = new WebSocket(`ws://localhost:${chatPort}`);
  sessionState.ws = ws;
  sessionState.chatWS = chatWS;

  ws.on("open", async () => {
    const currentStream = await getStream(page, {
      audio: true,
      video: false,
      mimeType: "audio/webm; codecs=opus",
      audioBitsPerSecond: 128000
    });

    sessionState.currentStream = currentStream;

    currentStream.on("data", chunk => {
      if (ws.readyState === WebSocket.OPEN) ws.send(chunk);
    });

    sessionState.speakerTrackerTask = trackAndSendSpeakerVectors(page, ws, chatWS, sessionState, time_start);
  });

  chatWS.on("message", async (msg) => {
    const s = msg.toString().trim();
    if (s === "terminate") {
      await cleanupMeetSession(sessionState);
      return;
    }
    if (!s.startsWith("{")) return;
    const payload = JSON.parse(s);
    if (payload.type === "chat_response") {
      await sendMessageToChat(page, payload.message);
    }
  });

  ws.on("message", async (msg) => {
    const command = msg.toString().trim();
    console.log("String of the message is: ", command)
    try {
        // if (typeof command === 'string' && command.startsWith('{')) {
        //     const data = JSON.parse(command);
            
        //     if (data.type === "chat_response") {
        //       console.log("Sending in js")
        //         await sendMessageToChat(page, data.message);
        //         return;
        //     }
        // }
        if (command === "terminate") {
          await cleanupMeetSession(sessionState);
          return;
        }
        
        if (command === "restart-stream") {
            if (sessionState.currentStream) {
                try { sessionState.currentStream.destroy(); } catch {}
            }

            if (!page || page.isClosed()) return;

            try {
                const stream = await getStream(page, {
                    audio: true,
                    video: false,
                    mimeType: "audio/webm; codecs=opus",
                    audioBitsPerSecond: 128000
                });

                sessionState.currentStream = stream;
                stream.on("data", chunk => {
                    if (ws.readyState === WebSocket.OPEN) ws.send(chunk);
                });
            } catch {}
        }
    } catch (e) {
        console.error("Error handling message:", e);
    }
});
}

async function cleanupMeetSession(sessionState) {
  const { ws, chatWS, browser, currentStream, speakerTrackerTask } = sessionState;
  sessionState.terminateRequested = true;

  if (currentStream) {
    try { currentStream.destroy(); } catch {}
  }

  if (ws && ws.readyState === ws.OPEN) {
    ws.close();
  }

  if (chatWS && chatWS.readyState === WebSocket.OPEN) {
    try { chatWS.close(); } catch {}
  }

  if (speakerTrackerTask) {
    try {
      await speakerTrackerTask;
    } catch {}
  }

  if (browser) {
    try { await browser.close(); } catch {}
  }

  sessionState.browser = null;
  sessionState.ws = null;
  sessionState.chatWS = null;
  sessionState.currentStream = null;
  sessionState.terminateRequested = false;
}

module.exports = {
  launchBrowser,
  joinMeetAndRecord,
  main,
  cleanupMeetSession
};
