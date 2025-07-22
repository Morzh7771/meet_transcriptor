const puppeteer = require("puppeteer-extra");
const StealthPlugin = require("puppeteer-extra-plugin-stealth");
const { launch, getStream, wss } = require("puppeteer-stream");
const fs = require("fs");
const { executablePath } = require("puppeteer");
const readline = require("readline");
const WebSocket = require("ws");

puppeteer.use(StealthPlugin());

const sleep = ms => new Promise(res => setTimeout(res, ms));
function askQuestion(query) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });
  return new Promise(resolve => rl.question(query, ans => {
    rl.close();
    resolve(ans);
  }));
}

let stepCounter = 1;
async function logStep(page, message) {
  const filename = `js/screenshots/step_${String(stepCounter++).padStart(2, "0")}_${message.replace(/\s+/g, "_")}.png`;
  await page.screenshot({ path: filename, fullPage: true });
  console.log(`📸 ${message} — скриншот сохранён: ${filename}`);
}

const [,, EMAIL, PASSWORD, MEET_CODE, DURATION_SEC = "10"] = process.argv;

(async () => {
  if (!fs.existsSync("js/screenshots")) fs.mkdirSync("js/screenshots");

  const browser = await launch({
    headless: false,
    executablePath: executablePath(),
    ignoreDefaultArgs: ['--mute-audio'],
    args: [
      "--disable-notifications",
      "--window-size=1280,800",
      "--autoplay-policy=no-user-gesture-required",
      "--no-sandbox",
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
  await page.keyboard.type(EMAIL, { delay: 150 });
  await sleep(500);
  await logStep(page, "Email entered");
  await page.click("#identifierNext");

  await page.waitForSelector('input[type="password"]', { visible: true });
  await sleep(700);
  await page.keyboard.type(PASSWORD, { delay: 120 });
  await sleep(500);
  await logStep(page, "Password entered");
  await page.click("#passwordNext");
  await page.waitForNavigation({ waitUntil: "networkidle2" });
  await sleep(2000);

  // 2FA
  //await page.keyboard.type("+380956069731", { delay: 120 });
  //await logStep(page, "Enter phone number for 2FA");
  //await sleep(500);
  //await page.keyboard.press('Enter');
  //await sleep(4000);
  //await logStep(page, "2FA code");
  //const twoFactorCode = await askQuestion("Enter 2FA code and press Enter: ");
  //await page.keyboard.type(twoFactorCode, { delay: 120 });
  //await page.keyboard.press('Enter');
  //await page.waitForNavigation({ waitUntil: "networkidle2" });
  //await logStep(page, "2FA entered");

  // Join to Meet
  await page.goto("https://meet.google.com/", { waitUntil: "networkidle2" });
  await logStep(page, "Open Google Meet");
  await page.waitForSelector('input[type="text"]');
  await page.click('input[type="text"]');
  await page.keyboard.type(MEET_CODE, { delay: 120 });
  await logStep(page, "Meeting code entered");
  await sleep(400);
  await page.keyboard.press('Enter');
  await page.waitForNavigation({ waitUntil: "networkidle2" });
  await sleep(10000);
  await logStep(page, "Meeting page loaded");

  // Enter navigation
  await page.keyboard.press('Tab'); await sleep(500);
  await logStep(page, "tab step");
  for (let i = 0; i < 9; i++) { await logStep(page, "tab step"); await page.keyboard.press('Tab'); await sleep(1000); }
  await page.keyboard.press('Enter'); await logStep(page, "tab step"); await sleep(500);
  await page.keyboard.press('Enter'); await logStep(page, "tab step"); await sleep(500);
  await sleep(2000);
  await logStep(page, "Logged in to the conference");
  
  const ws = new WebSocket("ws://localhost:8765");

  ws.on("open", async () => {
    console.log("🔌 WebSocket connected, starting transmission...");

    const stream = await getStream(page, {
      audio: true,
      video: false,
      mimeType: "audio/webm; codecs=opus",
      audioBitsPerSecond: 128000
    });

    stream.on("data", chunk => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(chunk);
      }
    });

    console.log(`▶️ Record audio ${DURATION_SEC} seconds.`);
    await sleep(Number(DURATION_SEC) * 1000);

    await stream.destroy();
    ws.close();
    console.log("⏹️ Record end, WebSocket closed.");

    await browser.close();
    (await wss).close();
    process.exit(0);
  });

  ws.on("error", err => {
    console.error("❌ WebSocket error :", err);
    browser.close();
    process.exit(1);
  });
})();
