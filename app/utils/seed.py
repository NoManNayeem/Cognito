"""Database seeding script for initial admin user and database pruning."""
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine, Base
from app.models import User
from app.security.auth import get_password_hash, verify_password
from app.config import settings
import logging

logger = logging.getLogger(__name__)


def prune_database(db: Session):
    """Clean up database - remove duplicate admin users, ensure data integrity."""
    try:
        # Find all users with admin username
        admin_users = db.query(User).filter(User.username == settings.admin_username).all()
        
        if len(admin_users) > 1:
            logger.warning(f"Found {len(admin_users)} admin users, keeping only the first one")
            # Keep the first one, delete duplicates
            for admin_user in admin_users[1:]:
                db.delete(admin_user)
            db.commit()
            logger.info("Removed duplicate admin users")
        
        # Ensure all admin users have correct scopes
        admin_users = db.query(User).filter(User.username == settings.admin_username).all()
        for admin_user in admin_users:
            if "admin" not in admin_user.scopes:
                admin_user.scopes = ["admin"]
                admin_user.is_active = True
                db.commit()
                logger.info(f"Updated admin user '{admin_user.username}' scopes to ['admin']")
        
        logger.info("Database pruning completed")
    except Exception as e:
        db.rollback()
        logger.error(f"Error during database pruning: {str(e)}")
        raise


def ensure_admin_user():
    """Ensure admin user exists and matches .env configuration (upsert logic)."""
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    
    db: Session = SessionLocal()
    try:
        # Prune database first
        prune_database(db)
        
        # Check if admin user exists
        admin_user = db.query(User).filter(User.username == settings.admin_username).first()
        
        # Hash password from settings
        hashed_password = get_password_hash(settings.admin_password)
        
        if admin_user:
            # Admin exists - check if password changed or settings don't match
            password_changed = False
            try:
                # Try to verify current password against .env password
                password_changed = not verify_password(settings.admin_password, admin_user.hashed_password)
            except Exception as e:
                # If verification fails (e.g., hash format issue), assume password needs update
                logger.warning(f"Password verification failed, will update: {str(e)}")
                password_changed = True
            
            needs_update = (
                password_changed or
                admin_user.scopes != ["admin"] or
                not admin_user.is_active
            )
            
            if needs_update:
                if password_changed:
                    admin_user.hashed_password = hashed_password
                    logger.info(f"Updated admin user '{settings.admin_username}' password")
                
                if admin_user.scopes != ["admin"]:
                    admin_user.scopes = ["admin"]
                    logger.info(f"Updated admin user '{settings.admin_username}' scopes to ['admin']")
                
                if not admin_user.is_active:
                    admin_user.is_active = True
                    logger.info(f"Activated admin user '{settings.admin_username}'")
                
                db.commit()
                db.refresh(admin_user)
                logger.info(f"Admin user '{settings.admin_username}' updated successfully")
            else:
                logger.info(f"Admin user '{settings.admin_username}' already exists and is up to date")
        else:
            # Create new admin user
            admin_user = User(
                username=settings.admin_username,
                hashed_password=hashed_password,
                is_active=True,  # Admin is active by default
                scopes=["admin"]  # Admin scope
            )
            
            db.add(admin_user)
            db.commit()
            db.refresh(admin_user)
            
            logger.info(f"Admin user '{settings.admin_username}' created successfully")
        
        # Log admin user details (without password)
        logger.info(f"Admin user details: username='{admin_user.username}', active={admin_user.is_active}, scopes={admin_user.scopes}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error ensuring admin user: {str(e)}")
        raise
    finally:
        db.close()


def seed_admin_user():
    """Legacy function name - calls ensure_admin_user for backward compatibility."""
    ensure_admin_user()


if __name__ == "__main__":
    ensure_admin_user()
