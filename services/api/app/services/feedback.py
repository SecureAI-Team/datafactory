from ..db import SessionLocal
from ..models import Feedback


def create_feedback(data):
    db = SessionLocal()
    fb = Feedback(**data)
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb
