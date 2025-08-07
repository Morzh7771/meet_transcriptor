// first_login.js
const puppeteer = require("puppeteer-extra");
const StealthPlugin = require("puppeteer-extra-plugin-stealth");
const { launch } = require("puppeteer-stream");
const fs = require("fs");
const { executablePath } = require("puppeteer");
const { start } = require("repl");

puppeteer.use(StealthPlugin());

let browser, page;

const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

let stepCounter = 1;
async function logStep(page, message) {
  const filename = `js/screenshots/login/step_${String(stepCounter++).padStart(
    2,
    "0"
  )}_${message.replace(/\s+/g, "_")}.png`;
  await page.screenshot({ path: filename, fullPage: true });
  console.log(`📸 ${message} — screenshot saved: ${filename}`);
}

async function startLogin(email, password, phone) {
  if (!fs.existsSync("js/screenshots/login"))
    fs.mkdirSync("js/screenshots/login");

  browser = await launch({
    headless: false,
    executablePath: executablePath(),
    ignoreDefaultArgs: ["--mute-audio"],
    args: [
      "--disable-notifications",
      "--window-size=1280,1200",
      "--autoplay-policy=no-user-gesture-required",
      "--no-sandbox",
    ],
    closeDelay: 2000,
  });

  page = await browser.newPage();
  await page.goto("https://accounts.google.com/", {
    waitUntil: "networkidle2",
  });
  await browser
    .defaultBrowserContext()
    .overridePermissions("https://meet.google.com/", [
      "microphone",
      "camera",
      "notifications",
    ]);
  await logStep(page, "Login page is open");

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

  if (phone) {
    await page.keyboard.type(phone, { delay: 120 });
    await page.keyboard.press("Enter");
    await sleep(4000);
  }

  await logStep(page, "Waiting for 2FA code");
}

async function submit2FACode(code) {
  if (!page) throw new Error("Login session not started");

  await page.keyboard.type(code, { delay: 120 });
  await page.keyboard.press("Enter");
  await page.waitForNavigation({ waitUntil: "networkidle2" });
  await logStep(page, "2FA code submitted and login complete");

  return true;
}

module.exports = { startLogin, submit2FACode };
// startLogin("quantexttestmeeat@gmail.com","Quantextisthebest","+380956069731")