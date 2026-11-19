# SkillForge

### Forge your skills. Unlock your potential.

**SkillForge** is a full-stack adaptive Data Structures and Algorithms (DSA) learning platform that helps students identify knowledge gaps, understand concept dependencies, and practice according to their current understanding.

The platform combines **Bayesian Knowledge Tracing (BKT)** with a graph-based prerequisite system to estimate concept mastery, recommend learning topics, and personalize question selection.

**Status:** Functional MVP | Active Development

---

## Overview

Traditional DSA practice platforms often focus on solving questions without identifying the underlying concepts a student may be struggling with.

SkillForge takes a concept-oriented approach by connecting practice performance with mastery estimation and prerequisite-aware learning recommendations.

The platform provides an interactive skill tree, diagnostic assessments, adaptive practice sessions, learning resources, and progress visualization.

## Key Features

### Interactive Skill Tree
- Visualizes DSA concepts and their prerequisite relationships.
- Displays concept-level mastery and learning status.
- Helps students understand topic dependencies and identify suitable learning paths.

### Diagnostic Assessment
- Evaluates initial understanding through a structured assessment.
- Updates mastery estimates based on student responses.
- Maintains assessment progress across sessions.

### Adaptive Practice
- Selects questions using concept mastery, prerequisite eligibility, and practice history.
- Updates recommendations as students answer questions.
- Provides answer feedback and explanations.
- Maintains persistent practice sessions.

### Bayesian Knowledge Tracing
- Estimates student understanding at the concept level.
- Updates mastery probabilities after question attempts.
- Uses probabilistic learner modeling to support personalized practice.

### Personalized Dashboard
- Displays concept progress and learning recommendations.
- Highlights concepts that may require additional attention.
- Provides access to relevant practice activities.

### Learning History and Analytics
- Records question attempts and mastery updates.
- Visualizes changes in estimated mastery over time.
- Helps learners review their progress.

### Concept Learning Resources
- Provides concept-specific learning resources.
- Connects learning material with practice and progress tracking.

---

## Technology Stack

| Component | Technologies |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Database Migrations | Alembic |
| Graph Processing | NetworkX |
| Adaptive Learning | Bayesian Knowledge Tracing (BKT) |
| Version Control | Git, GitHub |

---

## System Architecture

```text
                   Student
                      |
                      v
             React + TypeScript
                      |
                      v
                 FastAPI
                      |
          +-----------+-----------+
          |           |           |
          v           v           v
     Diagnostic    Adaptive    Progress
     Assessment    Practice    Tracking
          |           |           |
          +-----------+-----------+
                      |
                      v
               Learning Engine
                      |
          +-----------+-----------+
          |                       |
          v                       v
    Bayesian Knowledge     Prerequisite Graph
       Tracing (BKT)           (NetworkX)
          |                       |
          +-----------+-----------+
                      |
                      v
                 PostgreSQL
```

The React frontend communicates with the FastAPI backend through REST APIs. The backend processes assessment responses, updates learner mastery, evaluates prerequisite relationships, and stores learning progress in PostgreSQL.

---

## Adaptive Learning Workflow

SkillForge uses a structured learning workflow to connect student performance with personalized practice.

```text
       Student Opens SkillForge
                  |
                  v
          Diagnostic Assessment
                  |
                  v
         Concept Mastery Update
                  |
                  v
       Personalized Recommendations
                  |
                  v
            Adaptive Practice
                  |
                  v
           Question Submission
                  |
                  v
         Bayesian Knowledge Tracing
                  |
                  v
          Updated Mastery Estimate
                  |
                  v
           Progress Tracking
                  |
                  v
          Next Question Selection
```

### Bayesian Knowledge Tracing

Bayesian Knowledge Tracing is a probabilistic method for estimating whether a learner has mastered a particular skill.

SkillForge updates mastery estimates based on question responses using four parameters:

- **Initial mastery:** Estimated knowledge before practice.
- **Learning probability:** Probability of acquiring knowledge between opportunities.
- **Guess probability:** Probability of answering correctly without mastery.
- **Slip probability:** Probability of answering incorrectly despite mastery.

The implementation uses predefined BKT parameters and updates mastery estimates after question submissions.

### Prerequisite-Based Recommendations

DSA concepts are represented as nodes in a directed graph, with edges representing prerequisite relationships.

NetworkX is used to manage these dependencies.

The recommendation system considers concept mastery and prerequisite eligibility to identify suitable learning topics.

### Adaptive Question Selection

The adaptive practice engine selects questions based on:

1. Prerequisite eligibility.
2. Estimated concept mastery.
3. Previous practice activity.
4. Question availability within the current session.

This enables question selection to respond to changes in learner performance rather than following a fixed question order.

---

## Current Implementation

The MVP contains:

- 8 DSA concepts.
- 8 directed prerequisite relationships.
- 25 multiple-choice questions.
- Concept-specific mastery tracking.
- Six-question diagnostic assessments.
- Five-question adaptive practice sessions.
- Interactive prerequisite visualization.
- Learning history and mastery charts.
- Persistent assessment and practice sessions.

---

## Database and Backend

SkillForge uses PostgreSQL with SQLAlchemy for persistent data management.

The backend handles:

- DSA concepts and question records.
- Student question attempts.
- Concept-level mastery estimates.
- Diagnostic assessment sessions.
- Adaptive practice sessions.
- Learning history.
- Personalized recommendations.

Alembic manages database schema migrations.

The application also includes submission validation, idempotency handling, and transactional database operations to maintain consistent learning records.

---

## Testing and Validation

SkillForge includes automated tests covering its core backend and frontend functionality.

**MVP verification results:**

- 250 backend tests passed, plus 11 subtests.
- 134 frontend tests passed.
- TypeScript validation passed.
- ESLint checks passed.
- Frontend production build passed.
- Database migration verification completed.

Automated testing covers question submissions, learning workflows, session persistence, API behavior, and database operations.

---

## Getting Started

### Prerequisites

- Python
- Node.js and npm
- PostgreSQL
- Git

### Clone the Repository

```bash
git clone https://github.com/Aarohi-06/skillforge-knowledge-tracing.git
cd skillforge-knowledge-tracing
```

### Backend Setup

Navigate to the backend directory:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment.

**Windows PowerShell:**

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the backend dependencies and configure the PostgreSQL connection according to the repository's backend configuration.

Apply database migrations:

```bash
alembic upgrade head
```

Start the FastAPI server:

```bash
uvicorn app.main:app --reload --port 8000
```

API documentation is available at:

`http://localhost:8000/docs`

### Frontend Setup

Open another terminal and navigate to the frontend directory:

```bash
cd frontend
npm install
npm run dev
```

Open the local development URL provided by Vite, typically:

`http://localhost:5173`

**Note:** The backend requires database configuration and initial question-bank data before the complete learning workflows can be used.

---

## Project Status

SkillForge is an actively developed functional MVP demonstrating adaptive DSA learning through knowledge tracing, prerequisite-based recommendations, and personalized practice.

The repository contains the implementation of the current learning workflows, supporting backend services, database migrations, and automated tests.

---

## Author

**Aarohi Nagdeote**


GitHub: [Aarohi-06](https://github.com/Aarohi-06)

---

*SkillForge — Forge your skills. Unlock your potential.*
