const { sleep, logStep } = require('../utils/helpers');
const { TARGET_CLASS_LIST } = require('../utils/constants');
const WebSocket = require('ws');

// Global variable for scroll control
let scrollingState = {
  isScrolling: false,
  shouldStop: false,
  scrollInterval: null
};

/**
 * Starts auto-scrolling for element with jsname="edGALd"
 */
async function startAutoScroll(page) {
  if (scrollingState.isScrolling) {
    return; // Already scrolling
  }

  scrollingState.isScrolling = true;
  scrollingState.shouldStop = false;

  console.log("Starting participants auto-scroll");

  // Start scrolling in separate loop
  scrollingState.scrollInterval = setInterval(async () => {
    if (scrollingState.shouldStop) {
      stopAutoScroll();
      return;
    }

    try {
      await page.evaluate(() => {
        const scrollElement = document.querySelector('[jscontroller="edGALd"]');
        if (scrollElement) {
          scrollElement.scrollTop += 50; // Scroll down by 50px
          
          // If reached the end, start from beginning
          if (scrollElement.scrollTop >= scrollElement.scrollHeight - scrollElement.clientHeight) {
            scrollElement.scrollTop = 0;
          }
        }
      });
    } catch (err) {
      console.error('Error during scrolling:', err);
      stopAutoScroll();
    }
  }, 100); // Scroll every 100ms
}

/**
 * Stops auto-scrolling
 */
function stopAutoScroll() {
  if (scrollingState.scrollInterval) {
    clearInterval(scrollingState.scrollInterval);
    scrollingState.scrollInterval = null;
  }
  scrollingState.isScrolling = false;
  scrollingState.shouldStop = false;
  console.log("⏹️ Auto-scroll stopped");
}

/**
 * Opens dropdown panels in Google Meet
 */
async function openDropdown(page) {
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
  if(buttons){
    console.log(buttons.length)
    return buttons
  }
}

/**
 * Finds and clicks people panel button, starts auto-scroll
 */
async function findPeople(buttons, page) {
  if (buttons.length > 0) {
    for (const btn of buttons) {
      const hasPeopleIcon = await btn
        .$eval('i', i => i.textContent.includes('people'))
        .catch(() => false);
      if (hasPeopleIcon) {
        await btn.click();
        await sleep(1000);
        // Start auto-scrolling when people panel is opened
        await startAutoScroll(page);
        break;
      }
    }
  }
  return true;
}

/**
 * Finds and clicks chat panel button
 */
async function findChat(buttons) {
  if (buttons.length > 0) {
    for (const btn of buttons) {
      const hasChatIcon = await btn
        .$eval('i', i => i.textContent.includes('chat'))
        .catch(() => false);
      if (hasChatIcon) {
        await btn.click();
        break;
      }
    }
  }
  return true;
}

/**
 * Waits for meeting join to complete
 */
async function waitMeetJoin(page) {
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

/**
 * Tabs through elements until join button is found
 */
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

/**
 * Sends message to chat and stops auto-scrolling
 */
async function sendMessageToChat(page, message) {
    console.log("Sending message to chat:", message);
    
    // Stop auto-scrolling when sending message
    stopAutoScroll();
    
    let buttons = await openDropdown(page);
    await findChat(buttons);
    await sleep(1500);

    const inputField = await page.$('textarea[jsname="YPqjbf"]');

    if (inputField) {
      await inputField.type(message);
      await inputField.press('Enter');
      console.log("Message sent:", message);
    } else {
      console.error("Message input field not found.");
    }
    
    // Return to people panel and restart scrolling
    await findPeople(buttons, page);
    await sleep(1500);
}

/**
 * Tracks speaker activity and chat messages
 */
async function trackSpeakersAndChat(page, ws, chatWS, sessionState, timeStart) {
  while (!sessionState.terminateRequested) {
    if (!page || page.isClosed()) {
      sessionState.terminateRequested = true;
      break;
    }

    try {
      const data = await page.evaluate((startTime) => {
        // Speaker cards detection
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

        // Chat messages extraction
        const chatContainer = document.querySelector('div.Ge9Kpc.z38b6');
        const chat = [];

        if (chatContainer) {
          const blocks = Array.from(chatContainer.querySelectorAll('div.Ss4fHf'));

          blocks.forEach((block) => {
            const senderName =
              block.querySelector('.poVWob')?.innerText.trim() || '';
            const timestamp =
              block.querySelector('.MuzmKe')?.innerText.trim() || '';

            const messages = Array.from(block.querySelectorAll('div.RLrADb'));
            messages.forEach((msgNode) => {
              const text =
                msgNode.querySelector('[jsname="dTKtvb"]')?.innerText.trim() ||
                '';
              chat.push({
                name: senderName,
                time: timestamp,
                raw_time: Date.now(),
                massage: text,
              });
            });
          });
        }

        return { time: Date.now(), speakers, chat };
      }, timeStart);

      console.log(
        '🎤',
        data.time,
        'ms | 🔊',
        JSON.stringify(data.speakers),
        '| 💬 messages:',
        data.chat
      );

      console.log('Current URL:', await page.url());
      console.log('Page title:', await page.title());

      // Open participants panel if no speakers detected
      if (Object.keys(data.speakers).length === 0) {
        let buttons = await openDropdown(page);
        await findPeople(buttons, page);
      }

      // Send data via WebSockets
      if (ws && ws.readyState === ws.OPEN) {
        ws.send(JSON.stringify({ time: data.time, speakers: data.speakers }));
      }
      if (data.chat.length && chatWS && chatWS.readyState === WebSocket.OPEN && chatWS.bufferedAmount < 1_000_000) {
        chatWS.send(JSON.stringify({ chat: data.chat }));
      }
    } catch (err) {
      console.error('❌ trackSpeakersAndChat error:', err);
      break;
    }

    await sleep(50);
  }
}

module.exports = {
  openDropdown,
  findPeople,
  findChat,
  waitMeetJoin,
  tabUntilAllClassesMatch,
  sendMessageToChat,
  trackSpeakersAndChat,
  startAutoScroll,
  stopAutoScroll
};