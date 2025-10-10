import json
import asyncio
from datetime import datetime
from src.backend.db.dbFacade import DBFacade
from src.backend.models.db_models import MeetUpdate

async def update_meetings_from_json():
    """Update SQL database meetings with data from processed_meetings.json"""
    
    # Load processed meetings data
    print("Loading processed meetings data...")
    with open('processed_meetings.json', 'r', encoding='utf-8') as file:
        processed_meetings = json.load(file)
    
    print(f"Loaded {len(processed_meetings)} meetings from JSON")
    
    # Initialize database facade
    db = DBFacade()
    
    # Track statistics
    stats = {
        'total': len(processed_meetings),
        'updated': 0,
        'not_found': 0,
        'errors': 0
    }
    
    # Process each meeting
    for meeting in processed_meetings:
        meeting_id = meeting['id']
        print(f"\nProcessing meeting {meeting_id}...")
        
        try:
            # Check if meeting exists
            existing_meeting = await db.get_meet_by_id(meeting_id)
            
            if not existing_meeting:
                print(f"  ⚠️  Meeting {meeting_id} not found in database")
                stats['not_found'] += 1
                continue
            
            # Parse and format date to YYYY-MM-DD HH:MM:SS
            date_value = None
            if meeting.get('date'):
                try:
                    # Parse ISO format date
                    dt = datetime.fromisoformat(meeting['date'].replace('Z', '+00:00'))
                    # Format as YYYY-MM-DD HH:MM:SS
                    date_value = dt.strftime('%Y-%m-%d %H:%M:%S')
                except Exception as e:
                    print(f"  ⚠️  Error parsing date: {e}")
                    date_value = None
            
            # Parse participants from string to list
            participants_list = None
            if meeting.get('participants'):
                participants_value = meeting.get('participants')
                if isinstance(participants_value, str):
                    # Split by comma and strip whitespace
                    participants_list = [p.strip() for p in participants_value.split(',') if p.strip()]
                elif isinstance(participants_value, list):
                    participants_list = participants_value
            
            # Prepare update data
            update_data = MeetUpdate(
                client_id=meeting.get('client_id'),
                consultant_id=meeting.get('consultant_id'),
                title=meeting.get('title'),
                summary=meeting.get('summary'),
                date=date_value,
                duration=meeting.get('duration'),
                overview=meeting.get('overview'),
                notes=meeting.get('notes'),
                action_items=meeting.get('action_items'),
                trascription=meeting.get('trascription'),  # Note: using 'trascription' as in your schema
                language=meeting.get('language'),
                tags=meeting.get('tags'),
                participants=participants_list
            )
            
            # Update the meeting
            await db.update_meet(meeting_id, update_data)
            
            print(f"  ✅ Successfully updated meeting {meeting_id}")
            print(f"     Title: {meeting.get('title', 'N/A')[:50]}...")
            stats['updated'] += 1
            
        except Exception as e:
            print(f"  ❌ Error updating meeting {meeting_id}: {str(e)}")
            stats['errors'] += 1
            import traceback
            traceback.print_exc()
    
    # Print final statistics
    print("\n" + "="*60)
    print("UPDATE SUMMARY")
    print("="*60)
    print(f"Total meetings in JSON:    {stats['total']}")
    print(f"Successfully updated:      {stats['updated']}")
    print(f"Not found in database:     {stats['not_found']}")
    print(f"Errors:                    {stats['errors']}")
    print("="*60)
    
    if stats['updated'] > 0:
        print(f"\n✅ Successfully updated {stats['updated']} meetings!")
    
    if stats['not_found'] > 0:
        print(f"\n⚠️  {stats['not_found']} meetings were not found in the database")
    
    if stats['errors'] > 0:
        print(f"\n❌ {stats['errors']} meetings had errors during update")

async def verify_updates():
    """Verify that updates were applied correctly"""
    
    print("\n" + "="*60)
    print("VERIFICATION")
    print("="*60)
    
    with open('processed_meetings.json', 'r', encoding='utf-8') as file:
        processed_meetings = json.load(file)
    
    db = DBFacade()
    
    # Check first 3 meetings as sample
    sample_size = min(3, len(processed_meetings))
    print(f"\nVerifying {sample_size} sample meetings...")
    
    for i, meeting in enumerate(processed_meetings[:sample_size]):
        meeting_id = meeting['id']
        
        try:
            db_meeting = await db.get_meet_by_id(meeting_id)
            
            if db_meeting:
                print(f"\n✓ Meeting {i+1}/{sample_size}: {meeting_id}")
                print(f"  Title:        {db_meeting.title[:50] if db_meeting.title else 'N/A'}...")
                print(f"  Duration:     {db_meeting.duration}s")
                print(f"  Language:     {db_meeting.language}")
                print(f"  Tags:         {db_meeting.tags[:50] if db_meeting.tags else 'N/A'}...")
                print(f"  Participants: {db_meeting.participants[:50] if db_meeting.participants else 'N/A'}...")
            else:
                print(f"\n✗ Meeting {i+1}/{sample_size}: {meeting_id} - Not found")
                
        except Exception as e:
            print(f"\n✗ Meeting {i+1}/{sample_size}: {meeting_id} - Error: {str(e)}")

async def main():
    """Main execution function"""
    
    print("="*60)
    print("MEETING DATA UPDATE SCRIPT")
    print("="*60)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Perform updates
        await update_meetings_from_json()
        
        # Verify updates
        await verify_updates()
        
        print(f"\n{'='*60}")
        print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
    except Exception as e:
        print(f"\n❌ Fatal error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)