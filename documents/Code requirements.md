# LifeBox Digital Legacy System - Code Requirements

## Application Purpose
Secure family digital legacy storage with web interface for managing and accessing important information.

## Data Types to Store
- Personal documents and files
- Contact information 
- Important passwords/accounts
- Family photos and videos
- Instructions and messages
- Financial information
- Medical records

## Web Interface Features

### Main Dashboard
- Upload and organize files
- Create/edit text entries
- Categorize information
- Search functionality
- Password-protected access

### Family View
- Read-only access to all data
- Simple navigation by category
- Contact information display
- Emergency instructions
- File download capability

## Data Organization
- Categories: Documents, Photos, Contacts, Instructions, Medical, Financial
- Tags for cross-referencing
- Date/timestamp tracking
- File metadata (size, type, upload date)

## User Workflows

### Adding Information
1. Login with password
2. Select category
3. Upload file or create text entry
4. Add tags and description
5. Save to database

### Family Access
1. Enter family password
2. Browse by category
3. View/download content
4. Access emergency contact info

## Database Schema Needs
- Users table (minimal - just admin)
- Categories table
- Files/entries table
- Tags table
- Access logs

## File Storage Structure
```
/data/
├── documents/
├── photos/
├── medical/
├── financial/
└── instructions/
```

## Security Requirements
- Single admin password for editing
- Family password for viewing
- File encryption for sensitive data
- Session management

## Framework Decision
Need to choose: Flask (lightweight) vs Django (full-featured) for Python web app with SQLite database.