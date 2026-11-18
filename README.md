
# SkillForge

### Level up, one concept at a time.

**SkillForge** is a full-stack adaptive Data Structures and Algorithms (DSA) learning platform designed to help students identify knowledge gaps, understand concept dependencies, and practice more effectively.

Instead of following a fixed sequence of questions, SkillForge uses **Bayesian Knowledge Tracing (BKT)** and a **graph-based prerequisite system** to estimate concept mastery and personalize practice recommendations.

> **Project Status:** Functional MVP | Active Development  
> **Deployment:** Planned

---

## The Problem

Traditional DSA practice platforms often focus on solving more questions rather than understanding which concepts a student needs to improve.

Students may struggle with:
- Identifying weak concepts.
- Understanding prerequisite relationships between topics.
- Choosing what to practice next.
- Measuring conceptual progress over time.
- Following a structured learning path.

SkillForge addresses these challenges by combining knowledge tracing, prerequisite graphs, and adaptive question selection.

---

## Key Features

### 1. Interactive Skill Tree
- Visualizes DSA concepts and their prerequisite relationships.
- Helps learners understand how topics are connected.
- Provides concept-level mastery information.
- Supports structured learning recommendations.

### 2. Diagnostic Assessment
- Offers an initial assessment to evaluate a learner's understanding.
- Uses six questions covering Arrays, Time Complexity, and Recursion.
- Updates concept mastery estimates based on responses.
- Supports persistent assessment sessions and progress recovery.

### 3. Bayesian Knowledge Tracing
- Maintains an estimated mastery probability for each practiced concept.
- Updates mastery after question submissions.
- Accounts for correct and incorrect responses using BKT.
- Provides the foundation for personalized recommendations.

The current implementation uses predefined BKT parameters. Parameter estimation from real learning data is planned for future development.

### 4. Adaptive Practice
- Selects questions based on estimated mastery, prerequisite eligibility, and practice history.
- Presents one question at a time.
- Updates the learner's progress after each answer.
- Provides feedback and explanations.
- Supports persistent five-question adaptive sessions.
- Avoids repeating questions within a session.

### 5. Personalized Dashboard
- Displays concept-level progress.
- Highlights learning recommendations.
- Helps students identify areas requiring additional practice.

### 6. Progress Tracking
- Records question attempts and learning history.
- Displays changes in mastery estimates.
- Provides visual progress representations.

### 7. Concept Learning Resources
- Provides concept-specific learning material and resources.
- Connects learning content with practice and progress tracking.

---

## Technology Stack

| Layer | Technologies |
|-------|-------------|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Database Migrations | Alembic |
| Graph Processing | NetworkX |
| Knowledge Tracing | Bayesian Knowledge Tracing (BKT) |
| Testing | Automated frontend and backend tests |
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
          +------------+------------+
          |            |            |
          v            v            v
     Diagnostic     Adaptive     Progress
     Assessment     Practice     Tracking
          |            |            |
          +------------+------------+
                       |
                       v
             Learning Logic
                       |
          +------------+------------+
          |                         |
          v                         v
    Bayesian Knowledge       Prerequisite Graph
       Tracing (BKT)             (NetworkX)
          |                         |
          +------------+------------+
                       |
                       v
                  PostgreSQL
```

The frontend communicates with the FastAPI backend through REST APIs. The backend manages questions, assessments, learning progress, prerequisite relationships, and mastery updates.

---

## How Adaptive Learning Works

SkillForge combines two complementary approaches:

**Bayesian Knowledge Tracing** estimates how well a student understands a concept.

**Graph-based prerequisite analysis** identifies which concepts depend on previously learned topics.

### Learning Workflow

```text
Student Opens SkillForge
           |
           v
    Diagnostic Assessment
           |
           v
   Initial Mastery Estimates
           |
           v
    Interactive Skill Tree
           |
           v
  Personalized Recommendations
           |
           v
      Adaptive Practice
           |
           v
      Student Answers
           |
           v
      BKT Mastery Update
           |
           v
    Progress Saved to DB
           |
           v
     Next Question Selected
```

### Bayesian Knowledge Tracing

BKT is a probabilistic approach for estimating a learner's mastery of a skill based on observed responses.

SkillForge currently uses the following parameters:

| Parameter | Value | Meaning |
|-----------|-------|---------|
| Initial mastery | 0.20 | Starting probability of knowing a concept |
| Learning probability | 0.10 | Probability of learning between opportunities |
| Guess probability | 0.20 | Probability of answering correctly without mastery |
| Slip probability | 0.10 | Probability of answering incorrectly despite mastery |

After each response, the learner's estimated mastery is updated.

These parameters are currently predefined rather than trained on a dataset.

### Adaptive Question Selection

The adaptive practice engine considers:

1. Concepts eligible under prerequisite rules.
2. Estimated concept mastery.
3. Whether concepts have been practiced previously.
4. How recently they were attempted.
5. Available questions not already used in the current session.

The system prioritizes eligible concepts with lower estimated mastery and uses deterministic tie-breaking rules for question selection.

This approach is currently rule-based and does not claim to be a trained recommendation model.

---

## Current Dataset

The MVP currently includes:

- **8 DSA concepts**
- **8 prerequisite relationships**
- **25 curated multiple-choice questions**
- Question explanations and concept associations

The question bank is maintained through a structured import process.

The dataset is intentionally limited in the MVP and will be expanded to cover a broader DSA curriculum.

---

## Database and Backend

SkillForge uses PostgreSQL to persist learning information across sessions.

The backend supports:

- Question and concept management.
- Student progress and mastery records.
- Question attempt history.
- Diagnostic assessment sessions.
- Adaptive practice sessions.
- Persistent session recovery.
- Idempotent question submissions.
- Transactional updates and concurrency protection.
- Version-controlled database migrations using Alembic.

The current MVP uses a demonstration student identity. Individual user authentication is planned.

---

## Testing

The application includes automated tests for frontend and backend functionality.

At the current MVP milestone:

- **134 frontend tests**
- **250 backend tests, plus 11 subtests**
- TypeScript validation
- ESLint checks
- Frontend production build verification
- Database migration verification

Testing covers core learning workflows, API behavior, assessment persistence, question submissions, and related functionality.

Full manual end-to-end browser verification remains part of the next development milestone.

---

## Getting Started

### Prerequisites

Install:

- Python
- Node.js and npm
- PostgreSQL
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/Aarohi-06/skillforge-knowledge-tracing.git
cd skillforge-knowledge-tracing
```

### 2. Backend Setup

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install backend dependencies using the dependency file provided in the backend directory.

Configure your local PostgreSQL connection using the project's backend configuration.

Create the development database and apply Alembic migrations:

```bash
alembic upgrade head
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

Backend API:

```text
http://localhost:8000
```

Interactive API documentation:

```text
http://localhost:8000/docs
```

### 3. Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL displayed by Vite, typically:

```text
http://localhost:5173
```

**Note:** Database credentials, dependency installation, and initial data setup must follow the repository's backend configuration and import instructions. The application is currently intended for local development rather than production hosting.

---

## Project Roadmap

SkillForge is an actively evolving project.

### Phase 1: Functional MVP
- [x] Full-stack application architecture
- [x] Interactive prerequisite-based skill tree
- [x] Bayesian Knowledge Tracing
- [x] Personalized learning recommendations
- [x] Diagnostic assessment workflow
- [x] Adaptive practice sessions
- [x] Progress tracking and history
- [x] Persistent PostgreSQL storage
- [x] Automated frontend and backend tests

### Phase 2: Product Expansion
- [ ] Google OAuth and individual student accounts
- [ ] Interactive application tour and onboarding
- [ ] Expanded DSA curriculum
- [ ] Larger and better-reviewed question bank
- [ ] Improved question explanations
- [ ] More comprehensive diagnostic assessments
- [ ] Improved question difficulty calibration
- [ ] Production deployment
- [ ] End-to-end browser testing

### Phase 3: Advanced Adaptive Learning
- [ ] Data-driven estimation of BKT parameters
- [ ] Evaluation against baseline learning strategies
- [ ] Improved personalization and learning analytics
- [ ] Spaced repetition and revision scheduling
- [ ] User testing and learning-outcome evaluation

The roadmap is subject to change as the project develops.

---

## Current Limitations

The current version is an MVP and has several known limitations:

- Limited DSA concept and question coverage.
- BKT parameters are predefined rather than learned from student data.
- Diagnostic assessments cover only a subset of concepts.
- Question explanations and learning resources require further review and expansion.
- Authentication and multi-user account management are not yet implemented.
- The application is not yet publicly deployed.
- Real-world learning effectiveness has not yet been evaluated.

These limitations are part of the planned development roadmap.

---

## Project Goals

SkillForge aims to evolve into a learning platform that helps students:

- Understand what they know.
- Identify what they need to improve.
- Learn concepts in a meaningful order.
- Practice questions suited to their current understanding.
- Track progress through an adaptive learning journey.

The long-term objective is to explore how knowledge tracing and prerequisite-aware recommendations can support more effective DSA learning.

---

## Author

**Aarohi Nagdeote**

B.Tech in Computer Science and Engineering (AI & Data Science)  
Ramdeobaba University, Nagpur

GitHub: [Aarohi-06](https://github.com/Aarohi-06)

---

*SkillForge — Level up, one concept at a time.*
