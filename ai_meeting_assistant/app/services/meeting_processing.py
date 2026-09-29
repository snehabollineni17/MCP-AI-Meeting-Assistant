import traceback
from app.services.transcript import transcribe_audio
from app.models import Meeting 
from app.database import SessionLocal
from app.services.summarizer import generate_summary 
from app.services.action_items import generate_action_items

def process_meeting(meeting_id:int):

    db = SessionLocal()
    meeting = None
    stage = "loading meeting"
    
    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()

        if not meeting:
            return 
        
        stage = "marking meeting as processing"
        meeting.status = "PROCESSING"
        db.commit()

        stage = "transcribing audio"
        print(f"[Meeting {meeting_id}] Starting transcription...")
        meeting.transcript = transcribe_audio(meeting.audio_path)
        db.commit()
        print(f"[Meeting {meeting_id}] Transcription complete.")

        stage = "generating summary"
        print(f"[Meeting {meeting_id}] Generating summary...")
        meeting.summary = generate_summary(meeting.transcript)
        db.commit()
        print(f"[Meeting {meeting_id}] Summary complete.")

        stage = "generating action items"
        print(f"[Meeting {meeting_id}] Generating action items...")
        meeting.action_items = generate_action_items(meeting.transcript)
        db.commit()
        print(f"[Meeting {meeting_id}] Action items complete.")

        stage = "marking meeting as completed"
        meeting.status = "COMPLETED"
        db.commit()
        print(f"[Meeting {meeting_id}] Processing completed successfully!")
    
    except Exception as e:
        print(f"[Meeting {meeting_id}] ERROR during {stage}: {str(e)}")
        traceback.print_exc()
        if meeting is not None:
            try:
                meeting.status = "FAILED"
                db.commit()
            except Exception:
                print(f"[Meeting {meeting_id}] Unable to persist FAILED status.")
                traceback.print_exc()
        
    finally:
        db.close()
