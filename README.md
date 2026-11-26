# WPI BS/MS Planner

An unofficial Streamlit app for planning a WPI combined B.S./M.S. degree. Pick your majors, add courses by year, assign them to requirements, and see your credit progress. The database checks the plan against the program rules as you go.

**[Access the live app here](https://wpi-bs-ms-planner.streamlit.app/)**

## Screenshots

![Credit progress cards and My courses](docs/screenshots/credits_courses.png)
*Credit progress toward each degree, plus every course in the plan, split into unassigned and assigned.*

![Requirement sections with the course dropdown open](docs/screenshots/dropdowns.png)
*Each requirement's dropdown ranks eligible courses and tags them as taken, double-countable, or how often other students chose them.*

## Features

- **Course search** across undergraduate and graduate courses, with descriptions
- **My courses**: add courses to your plan before assigning them to a requirement
- **Requirement assignment** with ranked course choices for each requirement
- **Credit progress cards** that change color as you approach each requirement's minimum
- **Double-count checks**, including the 40% limit
- **HUA rules** (depth, breadth, seminar, elective)
- **ISU extra credit** handling

## Database

All rules live in the Postgres database (hosted on Neon). `app.py` only reads and writes rows. Rule violations are raised by database triggers, and the app shows their messages as-is.

![ER diagram (version 6)](docs/er-diagram.png)

- A **Student** is enrolled in a **Program** (a B.S./M.S. pairing) in a **School**, and makes a **Plan**.
- A program has a tree of **Requirements** (`parent_id`, `min_credits`, `min_courses`, and so on), filled by **Courses**.
- A **Plan** row is a course the student plans to take. It may fill a requirement, or have no requirement yet ("My courses").
- A **double count** is one plan row whose `doublecount_for` and `doublecount_req` say which equivalent course it also stands in for, and where, in the other degree. The **Double Counts** table pairs graduate and undergraduate courses.
- Courses are disjoint graduate or undergraduate, and each is offered by a **Department**.

What the app reads and enforces:

- `get_requirement_options()` returns ranked course choices for each requirement
- `student_credit_totals` feeds the progress cards
- `fullcourselist` backs course search and "My courses"
- `plan_placements` lists each requirement a planned course fills, with its credits there
- Plan triggers enforce the HUA rules, the double-count check and 40% limit, and the course list check

## Project structure

```text
app.py               Streamlit UI
build_tables.ipynb   Scrapes WPI course listings and builds the tables
program_data/
  wpi.yaml           WPI-wide B.S. requirements, added to every major
  bs/                One YAML per B.S. major
  ms/                One YAML per M.S. program (lists its eligible bs_majors)
tables/              CSVs written by the notebook
.devcontainer/       Dev container / Codespaces config
```

## Data pipeline

`build_tables.ipynb` scrapes the WPI course listings, then builds the program and requirement tables from `program_data/`. Each M.S. YAML becomes one program per B.S. major in its `bs_majors`. That program combines the B.S. from `bs/`, the WPI-wide requirements in `wpi.yaml`, and the M.S. Everything is written to `tables/`.

## Setup and running

The app is public at https://wpi-bs-ms-planner.streamlit.app/. To run it locally, follow these steps.

Requires Python 3.11+ and a Postgres database loaded with the schema and tables.

```bash
pip install -r requirements.txt
```

Add your connection string to `.streamlit/secrets.toml`, which is not committed:

```toml
NEON_CONNECTION = "postgresql://user:password@host/dbname?sslmode=require"
```

Then start the app:

```bash
streamlit run app.py
```

The repo also includes a dev container, so you can open it in VS Code or GitHub Codespaces instead.

## Limitations

- Not official advising. Confirm your plan with your advisor.
- Only covers the class of 2028 tracking sheets.
- May not have the latest course listings.
- Course planner only, no timed scheduling.

## Team

Built for CS 542 (Database Management Systems) by Neel Awsare, Tobey Appenzeller, Karen Bonilla, and Thomas Solley.

## AI disclosure

- The UI in `app.py` was generated with Claude Opus 5.5 (Anthropic), based on the team's Figma mockup.
- The YAML files in `program_data/` were scraped by Claude Opus 5.5 (Anthropic).
