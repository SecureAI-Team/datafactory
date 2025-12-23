from ..db import SessionLocal
from ..models import ScenarioPrompt


def get_prompt(name):
    db = SessionLocal()
    return db.query(ScenarioPrompt).filter(ScenarioPrompt.name == name, ScenarioPrompt.enabled == True).order_by(ScenarioPrompt.version.desc()).first()
