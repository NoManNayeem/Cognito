"""Database utility scripts for manual operations."""
import sys
import os
import logging
from app.utils.seed import ensure_admin_user, prune_database
from app.database import SessionLocal
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """CLI entry point for database utilities."""
    if len(sys.argv) < 2:
        print("Usage: python -m app.utils.db_utils <command>")
        print("Commands:")
        print("  ensure-admin  - Ensure admin user exists and matches .env settings")
        print("  prune         - Prune database (remove duplicates, fix data integrity)")
        print("  full          - Run both prune and ensure-admin")
        print("\nEnvironment Variables:")
        print("  DB_URL        - Database connection string (default: postgresql://cognito:cognito_password@localhost:5432/cognito)")
        print("  ADMIN_USERNAME - Admin username (default: admin)")
        print("  ADMIN_PASSWORD - Admin password (default: change-this-password)")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    # Show current configuration
    logger.info(f"Database URL: {settings.db_url.split('@')[0]}@***")
    logger.info(f"Admin username: {settings.admin_username}")
    
    # Check if running in Docker or locally
    if os.getenv("DB_URL"):
        logger.info("Using DB_URL from environment variable")
    else:
        logger.info("Using default database configuration")
        logger.info("To use a different database, set DB_URL environment variable")
        logger.info("Example: DB_URL=postgresql://user:pass@host:port/db python -m app.utils.db_utils prune")
    
    try:
        if command == "ensure-admin":
            logger.info("Ensuring admin user exists...")
            ensure_admin_user()
            logger.info("Admin user ensured successfully")
        
        elif command == "prune":
            logger.info("Pruning database...")
            db = SessionLocal()
            try:
                prune_database(db)
                logger.info("Database pruned successfully")
            finally:
                db.close()
        
        elif command == "full":
            logger.info("Running full database maintenance...")
            db = SessionLocal()
            try:
                prune_database(db)
                logger.info("Database pruned successfully")
            finally:
                db.close()
            ensure_admin_user()
            logger.info("Full database maintenance completed successfully")
        
        else:
            logger.error(f"Unknown command: {command}")
            sys.exit(1)
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error executing command '{command}': {error_msg}")
        
        # Provide helpful error messages for common issues
        if "password authentication failed" in error_msg or "OperationalError" in error_msg:
            logger.error("\n" + "="*60)
            logger.error("Database connection failed!")
            logger.error("="*60)
            logger.error("Possible solutions:")
            logger.error("1. Make sure Docker containers are running:")
            logger.error("   docker compose up -d")
            logger.error("2. Set the correct DB_URL environment variable:")
            logger.error("   $env:DB_URL='postgresql://cognito:cognito_password@localhost:5432/cognito'")
            logger.error("   python -m app.utils.db_utils prune")
            logger.error("3. Or run the command inside the Docker container:")
            logger.error("   docker exec cognito-app python -m app.utils.db_utils prune")
            logger.error("="*60)
        
        sys.exit(1)


if __name__ == "__main__":
    main()
