"""File handling utilities for uploads and previews."""
import os
import aiofiles
from fastapi import UploadFile
from typing import Optional
from pathlib import Path


# Allowed file extensions
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

# Upload directory
UPLOADS_DIR = "app/static/uploads"


def validate_file(filename: str) -> bool:
    """Validate file type."""
    if not filename:
        return False
    
    file_ext = Path(filename).suffix.lower()
    return file_ext in ALLOWED_EXTENSIONS


async def save_uploaded_file(file: UploadFile) -> str:
    """Save uploaded file to uploads directory."""
    # Ensure uploads directory exists
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    
    # Generate unique filename
    file_ext = Path(file.filename).suffix.lower()
    unique_filename = f"{os.urandom(16).hex()}{file_ext}"
    file_path = os.path.join(UPLOADS_DIR, unique_filename)
    
    # Save file
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    return file_path


def get_file_preview(file_path: str) -> str:
    """Get preview of file content."""
    file_ext = Path(file_path).suffix.lower()
    
    if file_ext == ".txt" or file_ext == ".md":
        # Read text file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Return first 1000 characters
                return content[:1000] + ("..." if len(content) > 1000 else "")
        except Exception as e:
            return f"Error reading file: {str(e)}"
    
    elif file_ext == ".pdf":
        # PDF preview - return message indicating PDF viewer needed
        return "PDF file - use browser PDF viewer"
    
    elif file_ext == ".docx":
        # DOCX preview - would need python-docx library
        try:
            from docx import Document
            doc = Document(file_path)
            # Extract text from first few paragraphs
            text = "\n".join([para.text for para in doc.paragraphs[:10]])
            return text[:1000] + ("..." if len(text) > 1000 else "")
        except Exception as e:
            return f"Error reading DOCX: {str(e)}"
    
    else:
        return "Preview not available for this file type"


def extract_metadata(file_path: str) -> dict:
    """Extract metadata from file."""
    file_stat = os.stat(file_path)
    return {
        "filename": os.path.basename(file_path),
        "size": file_stat.st_size,
        "extension": Path(file_path).suffix.lower(),
        "modified": file_stat.st_mtime
    }
