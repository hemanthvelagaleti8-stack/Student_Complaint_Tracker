# Campus Complaint Tracker

A lightweight, self-contained web application for managing campus maintenance complaints.

## Features
- Submit complaints and automatically generate ticket numbers.
- Suggest possible duplicates using category, location, and description similarity.
- Search complaints by location or description.
- Update ticket status: Pending, In progress, or Resolved.
- Preserve a timestamped history of ticket updates.
- View open-complaint summaries by category and oldest ticket age.
- Store data locally in `data.json`; no third-party packages or multi-user login required.

## Requirements
- Python 3.9 or newer
- No third-party Python packages required

## Run locally
1. Extract this ZIP.
2. Open a terminal in the extracted `campus-complaint-tracker` folder.
3. Run:

   **Windows**
   ```bash
   py app.py
   ```

   **macOS / Linux**
   ```bash
   python3 app.py
   ```

4. Open http://127.0.0.1:8000 in your browser.
5. Press `Ctrl+C` in the terminal to stop the server.

## Project structure
```text
campus-complaint-tracker/
├── app.py
├── data.json
├── README.md
└── .gitignore
```

## Data and scope
Complaints are stored in `data.json` beside `app.py`. Back up this file before deleting or replacing it. The ZIP starts with an empty data store.

This is a local, single-operator sample application, not a multi-user authentication system.
