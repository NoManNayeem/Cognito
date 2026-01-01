"""Script to recreate admin user - deletes existing and creates new one."""
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import User
from app.security.auth import get_password_hash
from app.config import settings


def recreate_admin_user():
    """Delete existing admin user and create a new one from environment variables."""
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    
    db: Session = SessionLocal()
    try:
        # Find and delete existing admin user
        admin_user = db.query(User).filter(User.username == settings.admin_username).first()
        
        if admin_user:
            print(f"Deleting existing admin user '{settings.admin_username}'...")
            db.delete(admin_user)
            db.commit()
            print(f"Deleted existing admin user")
        
        # Create new admin user
        hashed_password = get_password_hash(settings.admin_password)
        new_admin_user = User(
            username=settings.admin_username,
            hashed_password=hashed_password,
            is_active=True,  # Admin is active by default
            scopes=["admin"]  # Admin scope
        )
        
        db.add(new_admin_user)
        db.commit()
        db.refresh(new_admin_user)
        
        print(f"Admin user '{settings.admin_username}' recreated successfully")
        print(f"Username: {settings.admin_username}")
        print(f"Password: {settings.admin_password}")
        print(f"Active: {new_admin_user.is_active}")
        print(f"Scopes: {new_admin_user.scopes}")
    except Exception as e:
        db.rollback()
        print(f"Error recreating admin user: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    recreate_admin_user()
