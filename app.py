# -----------------------------------------------------------------------------
"""
# Assignment	: Term (Group) Project
# Author	: Neel Awsare, Tobey Appenzeller, Karen Bonilla, Thomas Solley
# Class	: CS 542 - Database Management
# File:	: app.py
# Purpose	: UI mockup of the WPI BS/MS Planner (layout only, not wired to the DB).
#
# AI NOTICE: UI elements in this file were generated with Claude Opus 5.5 (Anthropic),
#            based on the team's Figma mockup (v3 - grad and undergrad).
# -----------------------------------------------------------------------------
"""
from pathlib import Path

import streamlit as st
import yaml

PLACEHOLDER = "Value"


def program_names(level):
    """Program names from program_data/<level>/*.yaml, for the Program dropdowns."""
    files = sorted(Path("program_data", level).glob("*.yaml"))
    return [yaml.safe_load(f.read_text())["name"] for f in files]


def select_grid(labels, key, ncols=2):
    """Lay out empty placeholder dropdowns in a grid, one per label."""
    cols = st.columns(ncols)
    for i, label in enumerate(labels):
        with cols[i % ncols]:
            st.selectbox(label, [], index=None, placeholder=PLACEHOLDER, key=f"{key}-{i}")


def classes(n, start=1):
    return [f"Class {i}" for i in range(start, start + n)]


def header():
    _, sign_in, register = st.columns([9, 1, 1])
    sign_in.button("Sign in")
    register.button("Register", type="primary")

    title, search = st.columns([3, 1], vertical_alignment="bottom")
    title.title("WPI BS/MS Planner")
    title.subheader("Easier BS/MS Planning")
    search.text_input("Class Search", placeholder="Class Search", label_visibility="collapsed")


def student_info():
    year, taken, double = st.columns([1, 2, 2])
    year.selectbox("Graduation Year", range(2026, 2033), index=3)
    taken.text_area("Classes Taken", placeholder="AE 6435, MA 501")
    double.text_area("Double-Counted Classes", placeholder="AE 6435, MA 501")


def undergraduate():
    st.header("Undergraduate")
    prog, depth = st.columns(2)
    prog.selectbox("Program", program_names("bs"), key="bs-program")
    depth.selectbox("Depth", ["History", "Art", "Music", "Philosophy", "Literature"])

    with st.expander("Humanities and Arts"):
        st.markdown("**Depth Component**")
        select_grid(classes(4), "hua-depth")
        st.markdown("**Breadth Component**")
        select_grid(classes(1, start=5), "hua-breadth")
        st.markdown("**Humanities Elective**")
        select_grid(classes(1, start=6), "hua-elective")

    sections = [
        ("Wellness and Physical Education", 4),
        ("Social Science", 2),
        ("The Interactive Qualifying Project", 1),
        ("Free Electives", 3),
        ("Computer Science", 18),
        ("Math", 7),
        ("Basic Science and/or Engineering Science", 5),
    ]
    for name, n in sections:
        with st.expander(name):
            select_grid(classes(n), f"bs-{name}")


def graduate():
    st.header("Graduate")
    st.selectbox("Program", program_names("ms"), key="ms-program")

    with st.expander("Breadth"):
        select_grid(["Theory", "Algorithms", "Design", "Compilers and Languages",
                     "Databases", "Cybersecurity"], "ms-breadth")
        systems, or_, networks = st.columns([5, 1, 5], vertical_alignment="center")
        systems.selectbox("Systems", [], index=None, placeholder=PLACEHOLDER)
        or_.markdown("**or**")
        networks.selectbox("Networks", [], index=None, placeholder=PLACEHOLDER)
        select_grid(["Graphics and Imaging", "Artificial Intelligence",
                     "Applications of CS"], "ms-breadth-2")

    with st.expander("Computer Science Electives"):
        select_grid([f"Elective {i}" for i in range(1, 7)], "ms-electives")


def main():
    st.set_page_config(page_title="WPI BS/MS Planner", layout="wide")
    header()
    student_info()
    left, right = st.columns(2, gap="large")
    with left:
        undergraduate()
    with right:
        graduate()


if __name__ == "__main__":
    main()
