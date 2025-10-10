import json
import asyncio
from datetime import datetime
from src.backend.modules.meetingAnalizer import MeetingAnalizer

async def process_meetings_data():
    # Load JSON data
    with open('json/meet_profiles_v4.json', 'r', encoding='utf-8') as file:
        meetings_data = json.load(file)
    
    # Initialize the meeting analyzer
    analyzer = MeetingAnalizer()
    
    processed_meetings = []
    
    for meeting in meetings_data:
        print(f"Processing meeting {meeting['id']}")
        
        # Use full transcript as string (not split into lines)
        full_transcript = meeting['trascription']
        
        # Extract participant names from transcript
        participants = extract_participants(full_transcript)
        
        # Step 1: Generate summary and tags
        print(f"  - Generating summary and tags...")
        summary_response = await analyzer.summarize(full_transcript, meeting['id'])
        
        # Step 2: Generate notes
        print(f"  - Generating notes...")
        notes_response = await analyzer.generate_notes(full_transcript)
        
        # Step 3: Generate overview and title
        print(f"  - Generating overview...")
        overview_response = await analyzer.generate_overview(full_transcript)
        
        # Step 4: Generate action items (uses summary, not transcript)
        print(f"  - Generating action items...")
        action_items = await analyzer.generate_action_items(summary_response.summary, meeting['id'])
    
        title = overview_response.title
 
        
        # Build complete meeting object
        complete_meeting = {
            'id': meeting['id'],
            'client_id': meeting['client_id'],
            'consultant_id': meeting['consultant_id'],
            'title': title,
            'summary': summary_response.summary,
            'date': datetime.fromisoformat(meeting['date'].replace('Z', '+00:00')),
            'duration': meeting['duration'],
            'overview': '\n'.join(overview_response.overview) if hasattr(overview_response, 'overview') else '',
            'notes': notes_response.notes if hasattr(notes_response, 'notes') else notes_response,
            'action_items': action_items if isinstance(action_items, str) else action_items,
            'trascription': meeting['trascription'],
            'language': meeting['language'],
            'tags': ', '.join(summary_response.tags),
            'participants': ', '.join(participants)
        }
        
        processed_meetings.append(complete_meeting)
        print(f"✅ Completed processing meeting {meeting['id']}\n")
    
    return processed_meetings

def extract_participants(transcript):
    # Extract unique speaker names from transcript
    participants = set()
    lines = transcript.split('\n')
    
    for line in lines:
        if ':' in line:
            speaker = line.split(':', 1)[0].strip()
            # Filter out prefixes like "client (Name)" and keep clean names
            if speaker:
                # Handle "client (Name)" format
                if speaker.lower().startswith('client (') and speaker.endswith(')'):
                    clean_name = speaker[8:-1]  # Extract name from "client (Name)"
                    participants.add(clean_name)
                elif not speaker.lower().startswith('client'):
                    participants.add(speaker)
    
    return list(participants)

def generate_meeting_title(summary):
    # Generate a concise title from the summary
    words = summary.split()[:8]  # Take first 8 words
    title = ' '.join(words)
    
    # Remove trailing punctuation and add ellipsis if truncated
    title = title.rstrip('.,!?')
    if len(summary.split()) > 8:
        title += '...'
    
    return title

async def main():
    try:
        # Process all meetings
        processed_meetings = await process_meetings_data()
        
        # Save processed data
        # Convert datetime objects to ISO strings for JSON serialization
        for meeting in processed_meetings:
            meeting['date'] = meeting['date'].isoformat()
        
        with open('processed_meetings.json', 'w', encoding='utf-8') as file:
            json.dump(processed_meetings, file, indent=2, ensure_ascii=False)
        
        print(f"\nSuccessfully processed {len(processed_meetings)} meetings")
        print(f"Output saved to: processed_meetings.json")
        
    except Exception as e:
        print(f"Error during processing: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())