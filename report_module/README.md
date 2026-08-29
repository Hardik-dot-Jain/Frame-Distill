# Frame-Distill Report Module (Role 3)

The **Frame-Distill Report Module** is a standalone, isolated visual report generator. It reads distilled frame analysis JSON data produced by upstream ingestion/AI modules and renders an interactive, presentation-ready HTML report.

> **Role Isolation Rule**: This module belongs to **Role 3**. It operates strictly within `report_module/` and adheres to an agreed JSON contract, with zero dependencies on backend, CLI, or database layers.

---

## 📁 Directory Structure

```text
report_module/
├── report_gen.py          # Main generator script: reads JSON, renders Jinja2 template
├── templates/
│   └── report.html        # Jinja2 HTML report template
├── static/
│   ├── css/
│   │   └── style.css      # Modern dark-mode styling & responsive layout
│   └── js/
│       └── script.js      # Client-side search, category filters, and lightbox preview
├── mock_data/
│   └── fake_frames.json   # Mock frame data adhering to the contract
├── output/
│   └── .gitkeep           # Target directory for generated report.html
└── README.md              # Instructions and documentation
```

---

## 🚀 Quick Start

### 1. Requirements
Install the Jinja2 template engine:
```bash
pip install jinja2
```

### 2. Run Standalone (Default Mock Data)
From within `report_module/` or the repository root:
```bash
python report_module/report_gen.py
```
This generates the report at `report_module/output/report.html`.

### 3. Custom Input / Output
```bash
python report_module/report_gen.py --input path/to/frames.json --output report_module/output/my_report.html
```

### 4. Standalone Single-File Report (Inlined CSS/JS)
```bash
python report_module/report_gen.py --inline --output report_module/output/standalone_report.html
```

---

## 📋 JSON Data Contract

Input JSON files must conform to the following schema:

```json
{
  "project_name": "String",
  "source_video": "String",
  "generated_at": "ISO-8601 Timestamp",
  "total_frames_extracted": 1420,
  "distilled_key_frames_count": 5,
  "summary": "High-level summary text",
  "topics": ["Architecture", "Performance", "Conclusion"],
  "frames": [
    {
      "id": "frame_001",
      "timestamp": "00:01:15",
      "timestamp_seconds": 75,
      "image_path": "path/to/frame.png",
      "title": "Opening & Agenda",
      "importance_score": 0.88,
      "tags": ["Introduction", "Agenda"],
      "summary": "Summary of the frame visual and content.",
      "ocr_text": "Extracted OCR text if applicable",
      "key_points": [
        "Key takeaway point 1",
        "Key takeaway point 2"
      ]
    }
  ]
}
```
