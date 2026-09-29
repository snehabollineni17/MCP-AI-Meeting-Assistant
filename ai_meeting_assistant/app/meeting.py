import shutil
import os

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.services.meeting_processing import process_meeting
from app.security import get_current_user
from app.models import User, Meeting
from app.database import get_db

router = APIRouter(prefix="/meetings", tags=["meetings"])

@router.post("/upload")
def create_meeting(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_dir = os.path.join(base_dir, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    new_meeting = Meeting(
        title=title,
        audio_path=file_path,
        transcript=None,
        summary=None,
        action_items=None,
        user_id=current_user.id
    )

    db.add(new_meeting)
    db.commit()
    db.refresh(new_meeting)

    background_tasks.add_task(process_meeting, new_meeting.id)

    return {
        "message": "Meeting uploaded successfully",
        "meeting_id": new_meeting.id,
    }

@router.get("/meetings")
def get_meeting(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meetings = db.query(Meeting).filter(Meeting.user_id == current_user.id).all()
    return meetings

@router.get("/meetings/{meeting_id}")
def get_meeting_by_id(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meetings = db.query(Meeting).filter(Meeting.user_id == current_user.id, Meeting.id == meeting_id).first()

    if meetings is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return meetings

@router.delete("/meetings/{meeting_id}")
def delete_meeting(
    meeting_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.user_id == current_user.id).first()

    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    db.delete(meeting)
    db.commit()

    return {
        "message": "Meeting deleted successfully"
    }
