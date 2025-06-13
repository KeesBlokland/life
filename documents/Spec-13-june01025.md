# LifeBox Digital Legacy System
## Updated Architecture Overview & Implementation Status

### Project Goals (Unchanged)
**Primary:** Secure, accessible digital legacy storage for family  
**Secondary:** Portable backup system with guaranteed recovery  
**Constraint:** Must be usable by non-technical family members

---

## Current Implementation Status

### ✅ COMPLETED - Primary Web Application
**Location:** Debian Proxmox Container  
**Status:** Fully functional  

**Implemented Features:**
- Flask web application with responsive design
- Password-based authentication (view/admin levels)
- File upload with HEIC conversion and image processing
- File categorization and metadata management
- Search functionality across content and tags
- Calendar system with events and refuse bin reminders
- Shopping list management
- Admin dashboard with system statistics
- SQLite database with full CRUD operations
- Compact iPad-friendly UI design

**Current File Management:**
- Individual file uploads
- Automatic categorization (documents/images/videos)
- Tag-based organization
- Duplicate detection via checksums
- Soft delete with admin recovery

---

## 🚧 IN PROGRESS - Core Legacy Features

### Document Grouping System
**Goal:** Group related files into logical documents (e.g., passport = front + back pages)

**Database Changes Required:**
```sql
-- New documents table
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMP
);

-- Add document_id to files table
ALTER TABLE files ADD COLUMN document_id INTEGER REFERENCES documents(id);
```

### 🔐 Essential: Contacts & Credentials System
**Goal:** Secure storage of vital login information and contacts for family access

**Database Schema Required:**
```sql
-- Contacts/Organizations table
CREATE TABLE contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL, -- 'person', 'company', 'government', 'utility', 'financial'
    contact_type TEXT, -- 'family', 'friend', 'service', 'account'
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_date TIMESTAMP
);

-- Contact details (phone, email, address)
CREATE TABLE contact_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    detail_type TEXT NOT NULL, -- 'phone', 'email', 'address', 'website'
    label TEXT, -- 'home', 'work', 'mobile', 'billing'
    value TEXT NOT NULL,
    is_primary BOOLEAN DEFAULT 0,
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);

-- Credentials (encrypted storage)
CREATE TABLE credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER NOT NULL,
    service_name TEXT NOT NULL, -- 'Online Banking', 'Tax Portal', 'Electric Company'
    website_url TEXT,
    username TEXT,
    password_encrypted TEXT, -- Encrypted with family recovery key
    password_hint TEXT,
    notes TEXT,
    last_used DATE,
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE
);
```

**Essential Categories:**
- **Government:** Tax portals, social security, DMV, voter registration
- **Financial:** Banks, credit cards, investment accounts, retirement
- **Utilities:** Electric, gas, water, internet, phone, trash
- **Insurance:** Health, car, home, life insurance portals
- **Family/Friends:** Emergency contacts, important relationships
- **Services:** Doctors, lawyers, accountants, repair services

**Key Routes to Add:**
- `/contacts/browse` - List contacts by category
- `/contacts/view/<id>` - Contact details with credentials
- `/contacts/add` - Add new contact/organization
- `/contacts/edit/<id>` - Update contact information
- `/credentials/add/<contact_id>` - Add login credentials
- `/credentials/view/<id>` - Secure credential display

---

## ❌ NOT IMPLEMENTED - Raspberry Pi Mirror System

**Original Plan:** Portable backup device  
**Current Status:** Deferred  

**Missing Components:**
- Raspberry Pi setup and configuration
- Hourly rsync synchronization from Proxmox
- Pi web server for emergency access
- Self-imaging automation
- Dropbox upload integration
- Family recovery procedures

**Recommendation:** Complete document grouping first, then implement Pi system

---

## 📋 Updated System Architecture

### Current Architecture
```
┌─────────────────┐
│ Proxmox CT      │ 
│ (Primary Only)  │ ── Web Interface ── Family Access
│ - Flask App     │
│ - SQLite DB     │
│ - File Storage  │
└─────────────────┘
```

### Target Architecture (Phase 2)
```
┌─────────────────┐ rsync ┌─────────────────┐
│ Proxmox CT      │ ────► │ Raspberry Pi    │
│ (Primary)       │ hourly│ (Mirror)        │
└─────────────────┘       └─────────────────┘
         │                         │
         ▼                         ▼
   ┌──────────┐              ┌──────────────┐
   │ Backups  │              │ Self-Image   │
   │(Proxmox) │              │ → Dropbox    │
   └──────────┘              └──────────────┘
```

---

## 🚨 IMMEDIATE FIXES REQUIRED

### 1. Bin Display Improvements (MINOR - DO FIRST)
**Problem:** Calendar shows generic "Bin" text, requiring clicks to identify bin type

**Required Changes:**
- Update event titles to show "Blue Bin", "Yellow Bin", etc.
- Add bin-specific background colors in calendar (blue events for blue bins)
- Modify `temp_add_event.html` bin selection to auto-update title
- Update calendar CSS with bin color classes
- One glance shows all bin types without clicking

**Files to Modify:**
- `temp_add_event.html` - Update bin type selection JavaScript
- `temp_calendar.html` - Add bin color classes to events
- `styles.css` - Add bin-specific event colors
- `bp_main.py` - Ensure bin type stored in event description/title

### 2. Calendar Overcomplification - CRITICAL REALIZATION
Problem: Spent entire day trying to fix complex calendar widgets when user wanted simple event list
Root Issue: Engineer asked for "show events in chronological order" - I built calendar grids, month boundaries, 4-week periods
Simple Solution Needed:

Events = rows in table with dates
Query: SELECT * FROM events WHERE date >= today ORDER BY date LIMIT 20
Display: Simple chronological list (like homepage "Upcoming" section but longer)
Navigation: "Show More" / "Show Previous" buttons
Format: Jun 17: Brown Bin, Green Bin | Aug 25 2026: Birthday

User's Valid Engineering Logic:

Walk through the table
Display what you find
Don't overthink it
Events are just data, not calendar widgets

What NOT to build:

Complex calendar grids
Month boundary logic
4-week period calculations
Navigation that breaks when crossing months

Tomorrow: Build simple chronological event list, not calendar widgets
Files to Create/Modify:

Simple events list template (chronological, not calendar grid)
Backend: Basic date-ordered query with pagination
Remove broken calendar navigation complexity

Key Lesson: User asked for bicycle, I built broken rocket ship. Keep it simple.



### 2. Calendar Recurring Events Issues
**Problem:** Recurring bin entries appearing on unwanted days, not editable, invisible until day selected

**Required Fixes:**
- **Recurring Events Management Page**
  - List all recurring events with ability to edit/delete
  - Route: `/calendar/recurring` 
  - Show frequency, next occurrence, created date
  - Bulk delete option for problematic entries

- **Calendar Event Type Distinction**
  - Differentiate between one-time and recurring events in UI
  - Recurring events show different color/icon
  - Edit recurring: "This occurrence only" vs "All occurrences"
  - Better recurring event creation form

- **Refuse Bin Logic Fix**
  - Review automatic bin event creation
  - Ensure settings-based bins don't create database entries
  - Clear separation between settings-based and user-created events

### 3. Shopping Lists CRUD Missing
**Problem:** Can add items but cannot edit, delete, or manage existing entries

**Required Fixes:**
1. **Full CRUD Operations**
   - Edit item names and quantities
   - Delete individual items
   - Mark/unmark as "common items" for quick re-adding
   - Bulk operations (clear completed, delete all)

2. **Enhanced List Management**
   - Multiple shopping lists (grocery, hardware, etc.)
   - List templates for common shopping trips
   - Print-friendly view for shopping

**Routes to Add:**
- `/lists/edit/<item_id>` - Edit shopping item
- `/lists/delete/<item_id>` - Delete shopping item  
- `/calendar/recurring` - Manage recurring events

---

## 🎯 Implementation Priorities

### Phase 0: Critical Fixes (IMMEDIATE)
**Goal:** Fix existing broken functionality  
**Timeline:** Before any new features  

**Tasks:**
1. Calendar recurring events management
2. Shopping lists full CRUD operations
3. Debug and fix bin event creation logic

### Phase 1A: Contacts & Credentials System (CRITICAL)
**Goal:** Essential legacy information access for family  
**Timeline:** Immediate priority  

**Why Critical:** Family needs access to accounts, services, and contacts when someone becomes incapacitated or passes away. This is often **impossible to recover** if lost.

**Essential Use Cases:**
- Government portals (taxes, social security, DMV)
- Banking and financial accounts  
- Utility company logins
- Insurance portals
- Emergency family contacts
- Important service providers

**Tasks:**
1. Database schema for contacts and encrypted credentials
2. Contact management interface with categories
3. Secure credential storage with family recovery key
4. Browse interface organized by contact type
5. Admin tools for credential management

### Phase 1B: Document Grouping System
**Goal:** Complete family-friendly document management  
**Timeline:** After contacts system  

**Tasks:**
1. Database schema changes with migration
2. Upload interface for document creation
3. Document browser interface
4. File navigation within documents
5. Admin CRUD for document management

### Phase 2: Raspberry Pi Integration
**Goal:** Portable backup and recovery system  
**Timeline:** After document grouping complete  

**Tasks:**
1. Pi setup with identical web interface
2. Sync scripts (rsync over SSH)
3. Self-imaging automation
4. Dropbox integration
5. Family recovery instructions

### Phase 3: Advanced Features
**Goal:** Enhanced digital legacy features  
**Timeline:** Future  

**Possible Features:**
- Time-delayed message delivery
- Family access schedules
- Encrypted legacy content
- Multiple backup locations
- Mobile app for uploads

---

## 📊 Current vs. Planned Features

| Feature | Specified | Implemented | Priority |
|---------|-----------|-------------|----------|
| Web Interface | ✓ | ✓ | Complete |
| File Management | ✓ | ✓ | Complete |
| **Contacts & Credentials** | ✓ | ❌ | **CRITICAL** |
| Document Grouping | - | 🚧 | High |
| Authentication | ✓ | ✓ | Complete |
| Search System | ✓ | ✓ | Complete |
| Calendar/Lists | - | ✓ | Bonus |
| Pi Mirror System | ✓ | ❌ | Medium |
| Auto Backup | ✓ | ❌ | Medium |
| Recovery System | ✓ | ❌ | Medium |
| Family Instructions | ✓ | ❌ | Low |

---

## 🔄 Decision Log

**Immediate Fixes Identified:**
- **Reason:** Calendar recurring events are broken (unwanted bin entries, not editable)
- **Impact:** System unusable for calendar management
- **Status:** BLOCKING - must fix before new features

**Shopping Lists CRUD Missing:**
- **Reason:** Basic list management functionality incomplete
- **Impact:** Users can add but can't manage existing items
- **Status:** High priority fix

**Document Grouping Addition:**
- **Reason:** Family legacy documents naturally group (passport pages, insurance sets)
- **Impact:** Improves usability for target audience (elderly family members)
- **Status:** Approved for implementation (after fixes)

**Contacts/Credentials Addition:**
- **Reason:** Critical legacy information missing (logins, contacts)
- **Impact:** Essential for family digital legacy access
- **Status:** Approved as highest priority (after fixes)

---

## 📝 Next Steps

1. **Fix Critical Issues** (IMMEDIATE - BLOCKING)
   - Debug recurring events system (unwanted bin entries)
   - Implement recurring events management page
   - Add full CRUD operations to shopping lists
   - Test calendar functionality thoroughly

2. **Implement Contacts & Credentials System** (CRITICAL)
   - Database schema for contacts and encrypted credentials
   - Contact management interface
   - Secure credential storage system
   - Family-friendly browsing by category

3. **Complete Document Grouping System**
   - Database migration script
   - Upload interface modifications
   - Document viewer implementation

4. **Test with Family Members**
   - Usability validation for all systems
   - Interface refinements
   - Documentation updates

5. **Plan Pi Integration**
   - Hardware requirements
   - Sync strategy including encrypted credentials
   - Recovery procedures

**BLOCKING ISSUES:** Calendar and lists functionality must be fixed before implementing new features. A broken calendar system undermines user confidence in the entire application.

---

## 🔒 Security Considerations for Credentials

**Encryption Strategy:**
- Passwords encrypted with family recovery key (separate from admin password)
- Recovery key stored in multiple secure locations
- Option for time-delayed access (emergency situations)

**Access Levels:**
- **View Only:** Family can see usernames and hints
- **Emergency Access:** Full credentials with recovery key
- **Admin Access:** Full CRUD operations

**Backup Strategy:**
- Encrypted credential export for external storage
- Family recovery instructions with key location
- Multiple backup locations (Dropbox, USB drives, printed guides)

This updated specification reflects the current state and maintains the original vision while acknowledging practical implementation evolution.