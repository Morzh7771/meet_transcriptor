// js/meet_stream.js
const puppeteer = require("puppeteer-extra");
const StealthPlugin = require("puppeteer-extra-plugin-stealth");
const { launch, getStream, wss } = require("puppeteer-stream");
const fs = require("fs");
const { executablePath } = require("puppeteer");

puppeteer.use(StealthPlugin());
const sleep = ms => new Promise(res => setTimeout(res, ms));

const [,, EMAIL, PASSWORD, MEET_CODE, OUTPUT_PATH = "output_audio.webm", DURATION_SEC = "10"] = process.argv;

(async () => {
  const browser = await launch({
    headless: false,
    executablePath: executablePath(),
    ignoreDefaultArgs: ['--mute-audio'],
    args: [
      "--disable-notifications",
      "--window-size=1280,800",
      "--autoplay-policy=no-user-gesture-required",
    ],
    closeDelay: 2000,
  });

  const page = await browser.newPage();
  await page.goto("https://accounts.google.com/", { waitUntil: "networkidle2" });
  await browser.defaultBrowserContext().overridePermissions(
    "https://meet.google.com/",
    ["microphone", "camera", "notifications"]
  );

  // Логин
  await page.waitForSelector('input[type="email"]');
  await page.click('input[type="email"]');
  await page.keyboard.type(EMAIL, { delay: 150 });
  await sleep(500);
  await page.click("#identifierNext");

  await page.waitForSelector('input[type="password"]', { visible: true });
  await sleep(700);
  await page.keyboard.type(PASSWORD, { delay: 120 });
  await sleep(500);
  await page.click("#passwordNext");
  await page.waitForNavigation({ waitUntil: "networkidle2" });

  // Вход на Meet
  await page.goto("https://meet.google.com/", { waitUntil: "networkidle2" });
  await page.waitForSelector('input[type="text"]');
  await page.click('input[type="text"]');
  await page.keyboard.type(MEET_CODE, { delay: 120 });
  await sleep(400);
  await page.keyboard.press('Enter');
  await page.waitForNavigation({ waitUntil: "networkidle2" });
  await sleep(10000);

  // Навигация для входа
  await page.keyboard.press('Tab'); await sleep(500);
  for (let i = 0; i < 4; i++) { await page.keyboard.press('Tab'); await sleep(500); }
  await page.keyboard.press('Enter'); await sleep(500);
  await page.keyboard.press('Tab'); await sleep(500);
  await page.keyboard.press('Enter'); await sleep(500);
  for (let i = 0; i < 2; i++) { await page.keyboard.press('Tab'); await sleep(500); }
  await page.keyboard.press('Enter'); await sleep(3500);
  await sleep(4000);

  // Запись только аудио
  const file = fs.createWriteStream(OUTPUT_PATH);
  const stream = await getStream(page, {
    audio: true,
    video: false,
    mimeType: "audio/webm; codecs=opus",
    audioBitsPerSecond: 128000
  });

  stream.on('error', err => console.error('Stream error:', err));
  console.log(`▶️ Recording audio for ${DURATION_SEC}s to ${OUTPUT_PATH} ...`);
  stream.pipe(file);
  await sleep(Number(DURATION_SEC) * 1000);

  await stream.destroy();
  file.close();
  console.log("⏹️ Recording finished.");

  await browser.close();
  (await wss).close();
  process.exit(0);
})();
