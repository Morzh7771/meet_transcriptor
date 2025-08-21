import asyncio
from src.backend.modules.meetingAnalizer import MeetingAnalizer

transcript = [
    "Anne: Hi everyone, thanks for joining today’s weekly sync.",
    "Bob: Hi Anne, hi Claire.",
    "Claire: Hi all, good to see you both.",
    "Anne: Let’s start with project Alpha. Bob, could you share your update?",
    "Bob: Sure. I finished integrating the authentication module with the backend.",
    "Bob: The only thing pending is adding unit tests for the edge cases.",
    "Claire: That’s great progress. Any blockers?",
    "Bob: Yes, I still need access to the staging server. I requested it last week, but IT hasn’t responded yet.",
    "Anne: Okay, I’ll follow up with IT and make sure you get the credentials by tomorrow.",
    "Bob: Thanks, that would help.",
    "Anne: Claire, how’s the design work going?",
    "Claire: I finalized the mobile dashboard screens. They are ready for review.",
    "Claire: Next, I’ll start working on the reporting section, which should take about four days.",
    "Bob: Nice, once those are ready I can integrate them directly.",
    "Anne: Perfect. Please upload the designs to Figma and share the link in Slack by the end of the day.",
    "Claire: Will do.",
    "Anne: Regarding next sprint, we need to align on priorities.",
    "Bob: I suggest we finish the reporting feature first, since the client asked about it.",
    "Claire: Agreed. After that, I think we should focus on improving performance for the dashboard.",
    "Anne: That makes sense. I’ll update the sprint backlog accordingly.",
    "Anne: Quick reminder—our client demo is scheduled for next Friday.",
    "Bob: Got it, I’ll make sure the backend endpoints are stable by then.",
    "Claire: I’ll polish the UI and make sure all screens are consistent before the demo.",
    "Anne: Excellent. To summarize: Bob will complete unit tests and wait for IT access, Claire will upload the designs today and start the reporting section, and I’ll handle the IT follow-up and update the sprint backlog.",
    "Bob: Sounds good to me.",
    "Claire: Same here, thanks Anne.",
    "Anne: Great teamwork. Let’s wrap up for today."
]

async def main():
    # summarizer = Summarizer()
    # result = await summarizer.summarize(transcript)
    # print(f"The result is: {result}")
    # print(f"The summary is: {result.summary}")
    # print(f"The tags are: {result.tags}")
    analizer = MeetingAnalizer()
    # overview = await analizer.generate_overview(transcript)
    # overview = overview.overview
    # summary_and_tags = await analizer.summarize(transcript)
    # summary = summary_and_tags.summary
    # tags = summary_and_tags.tags
    # notes = await analizer.generate_notes(transcript)
    # notes = notes.notes
    action_items = await analizer.generate_action_items(transcript)
    action_items = action_items.action_items
    # The summary is: {summary}\nThe overview is: {overview}\nThe tags are: {tags}\nThe notes are: {notes}\n
    print(f"The summary is: {summary}\nThe overview is: {overview}\nThe tags are: {tags}\nThe notes are: {notes}\nThe action_items are: {action_items}")
    return


if __name__ == "__main__":
    asyncio.run(main())

