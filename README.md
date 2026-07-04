# TrafficWatch — AI-Powered Vehicle Offence Detection System

TrafficWatch is a full-stack traffic violation management platform that combines 
computer vision-based offence detection with an end-to-end case management 
workflow — from automatic detection and fine issuance to citizen disputes and 
admin review.

Built as a simulation of a digital traffic enforcement system for Sri Lanka's 
Department of Motor Traffic (DMT), it demonstrates how AI-powered image 
recognition can be integrated into a real-world regulatory workflow, complete 
with citizen-facing services and administrative oversight.

## Features

- **AI-Powered Detection**: Uploaded roadside images are analyzed using a 
  computer vision model (via Roboflow's inference API) to detect helmet 
  non-compliance, with confidence-based violation validation.
- **Automated Violation Logging**: Detected violations are automatically 
  recorded with a simulated vehicle plate, location, timestamp, fine amount, 
  and model confidence score.
- **Citizen Dashboard**: Users log in with their license plate to view their 
  violation history, outstanding fines, and a compliance score.
- **Rewards & Compliance Tracking**: Clean driving records unlock simulated 
  incentives — insurance discounts, revenue license discounts, and toll fee 
  reductions — based on days since the last violation.
- **Dispute Resolution Workflow**: Citizens can formally dispute a violation 
  with an explanation; admins review, approve, or reject disputes with a 
  documented decision.
- **Admin Dashboard**: Real-time statistics on total violations, pending 
  cases, disputes, and revenue collected, broken down by offence type.
- **Notification Logging**: Simulated SMS/email alerts for violations and 
  dispute outcomes.
- **Regulatory Grounding**: Violation types are mapped to real Sri Lankan 
  Motor Traffic Act provisions, including the specific legal rule and 
  penalty for each offence.

## Tech Stack

- **Backend**: Python, Flask
- **Database**: SQLAlchemy ORM, SQLite
- **Computer Vision**: Roboflow Inference API (helmet detection model)
- **Frontend**: HTML/Jinja2 templates

## Current Scope

The system's data model and rules engine support three offence types — 
helmet non-compliance, red light violations, and stop line violations — with 
penalties and legal references defined for all three. At present, the live 
detection pipeline is wired up for **helmet violations only**; red light and 
stop line detection are planned extensions.

## Setup

1. Clone the repository and create a virtual environment
2. Install dependencies:
```bash
   pip install -r requirements.txt
```
3. Create a `.env` file in the project root with:

```bash
   ROBOFLOW_API_KEY=your_api_key_here
   SECRET_KEY=your_secret_key_here
```

4. Run the app:
```bash
   python app.py
```
5. Visit `http://localhost:5000`

## Demo Credentials

- **Admin login**: `admin` / `admin123` *(for demo purposes only — not for production use)*
- **Sample license plates** are seeded automatically on first run for testing 
  the citizen dashboard.

## Disclaimer

This is a personal project built as a technical demonstration. It is 
not affiliated with or endorsed by Sri Lanka's actual Department of Motor 
Traffic, and all data, users, and violations are simulated.