const puppeteer = require("puppeteer-extra");
const StealthPlugin = require("puppeteer-extra-plugin-stealth");
const { launch, getStream, wss } = require("puppeteer-stream");
const fs = require("fs");
const { executablePath } = require("puppeteer");
const readline = require("readline");
const WebSocket = require("ws");

puppeteer.use(StealthPlugin());

const TARGET_CLASS_LIST = [
  "UywwFc-LgbsSe",
  "UywwFc-LgbsSe-OWXEXe-SfQLQb-suEOdc",
  "UywwFc-LgbsSe-OWXEXe-dgl2Hf",
  "UywwFc-StrnGf-YYd4I-VtOx3e",
  "tusd3",
  "IyLmn",
  "QJgqC"
];

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

    const { classList } = activeInfo;
    const hasAllClasses = TARGET_CLASS_LIST.every(cls =>
      classList.includes(cls)
    );

    console.log(`🔁 Tab ${i + 1}:`, classList.join(" "), "|", activeInfo.text);

    if (hasAllClasses) {
      console.log("✅ Found");
      return true;
    }
  }

  return false;
}

async function trackAndSendSpeakerVectors(page, durationSec, ws) {
  const endTime = Date.now() + durationSec * 1000;

  while (Date.now() < endTime) {
    const vector = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('div.cxdMu.KV1GEc[aria-label]'));
      const speakers = {};
      cards.forEach(card => {
        const name = card.getAttribute('aria-label');
        const indicator = card.querySelector('div[jsname="QgSmzd"]');
        let isSpeaking = false;
        if (indicator) {
          isSpeaking = !indicator.classList.contains('gjg47c');
        }
        speakers[name] = isSpeaking;
      });
      return {
        time: Date.now(),
        speakers
      };
    });

    console.log(vector);
    if (ws && ws.readyState === ws.OPEN) {
      ws.send(JSON.stringify(vector));
    }
    await new Promise(res => setTimeout(res, 50));
  }
}

const sleep = ms => new Promise(res => setTimeout(res, ms));

let stepCounter = 1;
async function logStep(page, message) {
  const filename = `js/screenshots/step_${String(stepCounter++).padStart(2, "0")}_${message.replace(/\s+/g, "_")}.png`;
  await page.screenshot({ path: filename, fullPage: true });
  console.log(`📸 ${message} — скриншот сохранён: ${filename}`);
}

async function main(email,password,meet_code,duration,port) {
  console.log(port)
  if (!fs.existsSync("js/screenshots")) fs.mkdirSync("js/screenshots");

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
    ],
    closeDelay: 2000,
  });

  const page = await browser.newPage();
  await page.goto("https://accounts.google.com/", { waitUntil: "networkidle2" });
  await browser.defaultBrowserContext().overridePermissions(
    "https://meet.google.com/",
    ["microphone", "camera", "notifications"]
  );
  await logStep(page, "Login page is open");

  // login
  await page.waitForSelector('input[type="email"]');
  await page.click('input[type="email"]');
  await page.keyboard.type(email, { delay: 150 });
  await sleep(500);
  await logStep(page, "Email entered");
  await page.click("#identifierNext");

  await page.waitForSelector('input[type="password"]', { visible: true });
  await sleep(700);
  await page.keyboard.type(password, { delay: 120 });
  await sleep(500);
  await logStep(page, "Password entered");
  await page.click("#passwordNext");
  await page.waitForNavigation({ waitUntil: "networkidle2" });
  await sleep(2000);

  // Join to Meet
  await page.goto("https://meet.google.com/", { waitUntil: "networkidle2" });
  await logStep(page, "Open Google Meet");
  await page.waitForSelector('input[type="text"]');
  await page.click('input[type="text"]');
  await page.keyboard.type(meet_code, { delay: 120 });
  await logStep(page, "Meeting code entered");
  await sleep(400);
  await page.keyboard.press('Enter');
  await page.waitForNavigation({ waitUntil: "networkidle2" });
  await logStep(page, "Meeting page loaded");

  // Enter navigation
  await tabUntilAllClassesMatch(page);
  await page.keyboard.press("Enter");
  await logStep(page, "Enter на нужном элементе со всеми классами");
  await sleep(1000);
  await logStep(page, "Logged in to the conference");
  await sleep(1000);
  await page.keyboard.press('Enter');

  let buttons = await page.$$('[jsname="A5il2e"]');
  if (buttons.length === 0) {
    console.log("🔍 button [jsname='A5il2e'] no find...");
    const opener = await page.$('[class="VYBDae-Bz112c-LgbsSe VYBDae-Bz112c-LgbsSe-OWXEXe-SfQLQb-suEOdc hk9qKe S5GDme Ld74n"]');
    if (opener) {
      await opener.click();
      await sleep(1000);
    } else {
      console.warn("⚠️ menu open button not found!");
    }
    buttons = await page.$$('[jsname="A5il2e"]');
  }
  if (buttons.length > 0) {
    for (const btn of buttons) {
      const hasPeopleIcon = await btn.$eval('i', i => i.textContent.includes('people')).catch(() => false);
      if (hasPeopleIcon) {
        await btn.click();
        console.log("✅ 'People' done");
        break;
      }
    }
  } else {
    console.warn("❌ button [jsname='A5il2e'] not found after open menu");
  }
  await logStep(page, "user_list");
  await sleep(1000);
  const ws = new WebSocket(`ws://localhost:${port}`);
  let currentStream = null;

  ws.on("open", async () => {
    console.log("🔌 WebSocket connected, waiting for 'restart-stream' commands...");
    if (!currentStream) {
      console.log("🟢 Starting initial stream...");
      currentStream = await getStream(page, {
        audio: true,
        video: false,
        mimeType: "audio/webm; codecs=opus",
        audioBitsPerSecond: 128000
      });
  
      currentStream.on("data", chunk => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(chunk);
        }
      });
      
      console.log("🎙️ Initial stream started.");
    }
    setTimeout(async () => {
      console.log(`⏰ Duration (${duration} sec) elapsed. Cleaning up...`);
  
      if (currentStream) {
        try {
          currentStream.destroy();
        } catch (err) {
          console.warn("⚠️ Error destroying stream:", err);
        }
      }
  
      if (ws.readyState === WebSocket.OPEN) {
        ws.close(); // вызовет ws.on("close")
      }
    }, duration * 1000);
    
    trackAndSendSpeakerVectors(page, Number(duration), ws)
      .catch(e => console.error("Ошибка в trackAndSendSpeakerVectors:", e));
  });

  ws.on("message", async (msg) => {
    const command = msg.toString().trim();
    if (command === "restart-stream") {
      console.log("🔁 Restart command received from Python.");

      if (currentStream) {
        try {
          currentStream.destroy();
        } catch (err) {
          console.warn("⚠️ Error while destroying stream:", err);
        }
      }

      currentStream = await getStream(page, {
        audio: true,
        video: false,
        mimeType: "audio/webm; codecs=opus",
        audioBitsPerSecond: 128000
      });

      currentStream.on("data", chunk => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(chunk);
        }
      });

      console.log("🎙️ New stream started.");
    }
  });

  ws.on("close", async () => {
    if (currentStream) {
      try {
        currentStream.destroy();
      } catch (err) {
        console.warn("⚠️ Error while destroying stream:", err);
      }
    }
    await browser.close();
    (await wss).close();
    console.log("⏹️ WebSocket closed. Browser and stream cleaned up.");
  });
}

module.exports = { main };