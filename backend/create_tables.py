
from app.database import Base, engine
from app import models

print("Creating SkillForge database tables...")

Base.metadata.create_all(bind=engine)

print("Tables created successfully!")
print("Tables:", list(Base.metadata.tables.keys()))
