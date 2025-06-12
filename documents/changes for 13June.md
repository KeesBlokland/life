**Implementation Instructions for Document Grouping System**

**Current State:** Life app has individual file uploads. Need to group multiple files into logical documents (passport = front + back pages).

**Required Changes:**

**Database Schema:**
1. Create `documents` table: id, title, description, tags, category, created_date
2. Add `document_id` to `files` table (nullable for backwards compatibility)
3. Move metadata from file-level to document-level
4. Migration script to convert existing files to single-file documents

**Core Files to Modify:**
- `util_db.py` - Add schema changes
- `bp_files.py` - Document CRUD routes  
- `temp_upload.html` - Group files before upload
- `temp_files.html` - Show documents not files
- New: `temp_document_viewer.html` - Navigate between files in document

**Upload Flow:**
- Select multiple files → assign shared document title/tags → creates one document record
- Files link to document_id
- Preserve individual filenames for navigation

**Browse Interface:**
- Display documents (with file count indicator)
- View button opens document viewer
- Edit allows adding/removing files from document

**Document Viewer:**
- Show current file with Previous/Next navigation
- Display "File 2 of 4" 
- Admin edit: add files, remove files, rename document

**Key Routes:**
- `/documents/browse` - List documents
- `/documents/view/<id>` - Document viewer with file navigation
- `/documents/edit/<id>` - CRUD for document grouping
- `/documents/upload` - Multi-file document creation

**Backwards Compatibility:**
- Existing files become single-file documents
- Preserve all current functionality

Start with database changes, then upload interface, then viewer.