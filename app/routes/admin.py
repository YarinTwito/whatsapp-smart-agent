from fastapi import APIRouter, Depends, HTTPException
from app.models import Feedback, BugReport
from sqlmodel import Session, select
from app.core.database import get_db
import os

router = APIRouter(prefix="/admin", tags=["admin"])

# Simple API key auth
def verify_api_key(api_key: str):
    if api_key != os.getenv("ADMIN_API_KEY", "admin_secret_key"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True

@router.get("/feedback", dependencies=[Depends(verify_api_key)])
def get_all_feedback(session: Session = Depends(get_db)):
    """Get all user feedback"""
    feedback = session.exec(select(Feedback).order_by(Feedback.submitted_at.desc())).all()
    return feedback

@router.get("/reports", dependencies=[Depends(verify_api_key)])
def get_all_reports(session: Session = Depends(get_db)):
    """Get all bug reports"""
    reports = session.exec(select(BugReport).order_by(BugReport.submitted_at.desc())).all()
    return reports

@router.put("/reports/{report_id}/status", dependencies=[Depends(verify_api_key)])
def update_report_status(report_id: int, status: str, session: Session = Depends(get_db)):
    """Update bug report status"""
    report = session.get(BugReport, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    report.status = status
    session.add(report)
    session.commit()
    return {"status": "updated"} 