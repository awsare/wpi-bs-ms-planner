# -----------------------------------------------------------------------------
"""
# Assignment	: Term (Group) Project
# Author	: Neel Awsare, Tobey Appenzeller, Karen Bonilla, Thomas Solley
# Class	: CS 542 - Database Management
# File:	: app.py
# Purpose	: WPI BS/MS Planner UI, wired to the Neon database.
#
# All rules live in the database; this file only reads and writes rows:
#   - get_requirement_options()  : ranked course choices for each requirement
#   - student_credit_totals      : credit progress cards
#   - fullcourselist             : course search and "My courses"
#   - plan triggers              : HUA rules, double-count limit/partner, course
#                                  list check. Their RAISE EXCEPTION messages
#                                  are shown to the user as-is.
#
# Plan rows with requirement_id NULL are courses the student entered but has not
# assigned yet ("My courses"). Assigning one UPDATEs that row; unassigning sets
# requirement_id back to NULL.
#
# AI NOTICE: UI elements in this file were generated with Claude Opus 5.5 (Anthropic),
#            based on the team's Figma mockup (v3 - grad and undergrad).
# -----------------------------------------------------------------------------
"""
import os
from collections import defaultdict

import psycopg
import streamlit as st
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv()
YEARS = list(range(2026, 2033))
ss = st.session_state


# ----------------------------------------------------------------------------- database
def conn():
    """One connection per browser session, reopened if Neon dropped it."""
    c = ss.get("conn")
    if c is None or c.closed:
        c = ss.conn = psycopg.connect(os.environ["NEON_CONNECTION"], autocommit=True, row_factory=dict_row)
    return c


def q(sql, params=None):
    return conn().execute(sql, params).fetchall()


def ver():
    """Bumped after every write so per-write widgets (add boxes) start fresh from the DB."""
    return ss.get("v", 0)


def write(*stmts, done=None):
    """Run (sql, params) pairs in one transaction. On a trigger error, show it and roll back.
    `done` is shown as a toast after the rerun."""
    try:
        with conn().transaction():
            for sql, params in stmts:
                conn().execute(sql, params)
    except psycopg.Error as e:
        msg = e.diag.message_primary or str(e)
        st.error(msg + (f"\n\n{e.diag.message_hint}" if e.diag.message_hint else ""), icon=":material/error:")
        return False
    options.clear()
    ss.v = ver() + 1
    if done:
        ss.toast = done
    return True


@st.cache_data(ttl="1h")
def courses():
    rows = q("SELECT DISTINCT ON (course_code) course_code, title, subject, credits_raw, academic_level "
             "FROM fullcourselist ORDER BY course_code")
    return {r["course_code"]: r for r in rows}


@st.cache_data(ttl="1h")
def programs():
    return {r["id"]: r["name"] for r in q("SELECT id, name FROM programs ORDER BY name")}


@st.cache_data(ttl="1h")
def hua_topics():
    rows = q("""SELECT DISTINCT trim(unnest(regexp_split_to_array(c.subject, ';'))) AS t
                FROM filledby f JOIN fullcourselist c USING (course_code)
                WHERE f.requirement_id LIKE %s ORDER BY 1""", ("%/bs/humanities-and-arts",))
    return [r["t"] for r in rows]


@st.cache_data(ttl="1h")
def requirements(pid):
    return q("""SELECT r.*, EXISTS (SELECT 1 FROM filledby f WHERE f.requirement_id = r.id) AS fillable
                FROM requirements r WHERE r.program_id = %s ORDER BY r.path""", (pid,))


@st.cache_data(ttl="1h")
def partners(pid):
    out = defaultdict(list)
    for d in q("SELECT * FROM doublecounts WHERE program_id = %s", (pid,)):
        out[d["undergrad_course"]].append(d["grad_course"])
        out[d["grad_course"]].append(d["undergrad_course"])
    return dict(out)


@st.cache_data(ttl="5m", max_entries=2000)
def options(sid, pid, req):
    """get_requirement_options() for one requirement: {course_code: row}, in the function's order."""
    rows = q("SELECT * FROM get_requirement_options(%s::real, %s, %s)", (sid, pid, req))
    return {r["course_code"]: r for r in rows}


def course_label(code):
    c = courses().get(code)
    return f"{code} — {c['title']}" if c else code


def credits_of(code):
    return float(courses().get(code, {}).get("credits_raw") or 0)


# ----------------------------------------------------------------------------- sign in / profile
def sign_in(sid):
    """Load the student's profile into session state (the one place it's initialized)."""
    stu = q("SELECT * FROM student WHERE student_id = %s", (sid,))[0]
    mine = q("SELECT program_id FROM plan WHERE student_id = %s GROUP BY 1 ORDER BY count(*) DESC LIMIT 1", (sid,))
    ss.sid = sid
    ss.grad_year = int(stu["grad_year"]) if stu["grad_year"] else None
    ss.hua_depth = stu["hua_depth"]
    ss.email = stu["student_email"]
    ss.program = mine[0]["program_id"] if mine else next(iter(programs()))
    ss.pop("lookup", None)
    ss.v = ver() + 1


def sign_out():
    for k in ("sid", "grad_year", "hua_depth", "email", "program", "lookup"):
        ss.pop(k, None)
    ss.v = ver() + 1


def sign_in_page():
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.title("WPI BS/MS planner", icon=":material/school:")
        st.caption("Track the courses you've taken, fill each B.S. and M.S. requirement, "
                   "and choose which courses to double count.")
        with st.form("sign-in"):
            raw = st.text_input("Student ID", placeholder="e.g. 901234567",
                                validate=(r"^\d+$", "Use digits only."))
            if st.form_submit_button("Sign in", type="primary", icon=":material/login:", width="stretch") and raw:
                ss.lookup = float(raw)  # student.student_id is REAL
        sid = ss.get("lookup")
        if sid is None:
            return
        if q("SELECT 1 FROM student WHERE student_id = %s", (sid,)):
            sign_in(sid)
            st.rerun()
        with st.form("register"):
            st.markdown(f"**No profile for ID {sid:.0f} yet. Create one:**")
            year = st.selectbox("Graduation year", YEARS)
            email = st.text_input("Email", type="email")
            depth = st.selectbox("Humanities & Arts depth topic", hua_topics(), index=None,
                                 help="The topic your 3 HUA depth courses come from. You can change it later.")
            if st.form_submit_button("Create profile", type="primary", width="stretch") and write(
                    ("INSERT INTO student (student_id, grad_year, hua_depth, student_email) VALUES (%s, %s, %s, %s)",
                     (sid, year, depth, email or None)), done="Profile created"):
                sign_in(sid)
                st.rerun()


def save_profile():
    write(("UPDATE student SET grad_year = %s, hua_depth = %s WHERE student_id = %s",
           (ss.grad_year, ss.hua_depth, ss.sid)), done="Profile saved")


def sidebar():
    progs = programs()
    with st.sidebar:
        st.header(f"Student {ss.sid:.0f}", icon=":material/account_circle:")
        if ss.email:
            st.caption(ss.email)
        st.selectbox("Program", list(progs), format_func=progs.get, key="program")
        st.selectbox("Graduation year", YEARS, index=None, key="grad_year", on_change=save_profile)
        st.selectbox("Humanities & Arts depth topic", hua_topics(), index=None, key="hua_depth",
                     on_change=save_profile,
                     help="Courses in this topic count toward HUA depth; others count as breadth.")
        st.button("Sign out", icon=":material/logout:", on_click=sign_out, width="stretch")


# ----------------------------------------------------------------------------- course search
@st.dialog("Course search", width="large", icon=":material/search:")
def course_search():
    text = st.text_input("Search", type="search", live=True, label_visibility="collapsed",
                         placeholder="Course code, title, or subject — e.g. CS 4432, databases, History")
    if not text:
        st.caption(f"{len(courses()):,} undergraduate and graduate courses.")
        return
    t = text.lower()
    hits = [c for code, c in courses().items()
            if t in code.lower() or t in (c["title"] or "").lower() or t in (c["subject"] or "").lower()]
    st.caption(f"{len(hits):,} matches")
    st.dataframe(hits, hide_index=True, alt="Course search results",
                 column_config={"course_code": "Course", "title": "Title", "subject": "Subject",
                                "credits_raw": st.column_config.NumberColumn("Credits", format="%g"),
                                "academic_level": "Level"})


# ----------------------------------------------------------------------------- overview
def overview(plan):
    rows = q("SELECT * FROM student_credit_totals WHERE student_id = %s AND program_id = %s", (ss.sid, ss.program))
    t = rows[0] if rows else {"ug_credits": 0, "ug_required": 135, "gr_credits": 0,
                              "gr_required": 30, "total_credits": 0, "total_required": 165}
    cols = st.columns(4)
    for col, (name, k) in zip(cols, [("Undergraduate", "ug"), ("Graduate", "gr"), ("Total", "total")]):
        have, need = float(t[f"{k}_credits"]), t[f"{k}_required"]
        with col.container(border=True, height="stretch"):
            st.metric(f"{name} credits", f"{have:g} / {need}")
            st.progress(min(have / need, 1.0))
    pairs = [p for p in plan if p["doublecount_for"]]
    with cols[3].container(border=True, height="stretch"):
        st.metric("Double counts", f"{len(pairs)} / 4")
        st.caption(", ".join(f"{p['course_code']} ⇄ {p['doublecount_for']}" for p in pairs)
                   or "Pick a partner course when adding a double-countable course.")


def my_courses(plan):
    unassigned = [p["course_code"] for p in plan if p["requirement_id"] is None]
    in_plan = {p["course_code"] for p in plan}
    with st.container(border=True):
        st.subheader("My courses", icon=":material/inventory_2:")
        st.caption("Courses you've taken or plan to take that aren't assigned yet. "
                   "Assign them from the requirement sections below, where they're marked *taken*.")
        with st.container(horizontal=True, vertical_alignment="bottom"):
            add = st.multiselect("Add courses", [c for c in courses() if c not in in_plan],
                                 format_func=course_label, key=f"bank-add-{ver()}",
                                 placeholder="Search for courses to add", label_visibility="collapsed")
            clicked = st.button("Add", icon=":material/add:", type="primary", disabled=not add,
                                key=f"bank-go-{ver()}")
        if clicked and write(*[("INSERT INTO plan (student_id, program_id, course_code) VALUES (%s, %s, %s) "
                                "ON CONFLICT DO NOTHING", (ss.sid, ss.program, c)) for c in add],
                             done=f"Added {len(add)} course{'s' * (len(add) > 1)}"):
            st.rerun()
        if not unassigned:
            st.caption("No unassigned courses.")
            return
        table = [{"Course": c, "Title": courses().get(c, {}).get("title"), "Credits": credits_of(c)}
                 for c in unassigned]
        picked = st.dataframe(table, hide_index=True, on_select="rerun", selection_mode="multi-row",
                              key=f"bank-{ss.program}-{ver()}", height=250, alt="Unassigned courses",
                              column_config={"Credits": st.column_config.NumberColumn(format="%g")})
        gone = [unassigned[i] for i in picked.selection.rows]
        if st.button(f"Remove selected ({len(gone)})", icon=":material/delete:", disabled=not gone,
                     key=f"bank-rm-{ver()}") and write(
                *[("DELETE FROM plan WHERE student_id = %s AND program_id = %s AND course_code = %s "
                   "AND requirement_id IS NULL", (ss.sid, ss.program, c)) for c in gone],
                done=f"Removed {len(gone)} course{'s' * (len(gone) > 1)}"):
            st.rerun()


# ----------------------------------------------------------------------------- requirements
def stats(node, kids, plan):
    """(done, summary) for a requirement and everything under it."""
    nid = node["id"]
    rows = [p for p in plan if p["requirement_id"] and
            (p["requirement_id"] == nid or p["requirement_id"].startswith(nid + "/"))]
    cr = sum(credits_of(p["course_code"]) for p in rows)
    children = kids.get(nid, [])
    kids_done = sum(stats(ch, kids, plan)[0] for ch in children) if node["min_children"] else 0
    done = (bool(rows) and cr >= node["min_credits"] and len(rows) >= node["min_courses"]
            and kids_done >= node["min_children"])
    parts = [f"{cr:g}/{node['min_credits']} cr" if node["min_credits"] else f"{cr:g} cr"]
    if node["min_courses"]:
        parts.append(f"{len(rows)}/{node['min_courses']} courses")
    if node["min_children"] and children:
        parts.append(f"{kids_done}/{node['min_children']} sections")
    return done, " · ".join(parts), bool(rows)


def badge(done, text, started):
    color = "green" if done else "orange" if started else "gray"
    return f":{color}-badge[{':material/check: ' if done else ''}{text}]"


def option_label(o, paired):
    tags = []
    if o["tier"] <= 4:
        tags.append(f"popular, {o['pct_chosen'] or 0:g}% chose")
    code = o["course_code"]
    if o["is_taken"]:
        tags.append("taken")
    if code in paired:
        tags.append(f"paired with {paired[code]}")
    elif o["is_double_countable"]:
        tags.append("double-countable")
    if o["hua_role"]:
        tags.append(o["hua_role"])
    # ✓ taken · ⇄ double-countable (can start a pair) · 🔗 already paired, just needs a requirement
    link = "🔗 " if code in paired else "⇄ " if o["is_double_countable"] else ""
    marks = ("✓ " if o["is_taken"] else "") + link
    return f"{marks}{o['course_code']} — {o['title']}" + (f"  ({', '.join(tags)})" if tags else "")


def picker(node, plan):
    """Assigned courses (with unassign buttons) + an add box fed by get_requirement_options()."""
    req, v = node["id"], ver()
    paired = {}  # course -> its partner, both directions (one relation counts both ways)
    for p in plan:
        if p["doublecount_for"]:
            paired[p["course_code"]], paired[p["doublecount_for"]] = p["doublecount_for"], p["course_code"]
    for p in plan:
        if p["requirement_id"] != req:
            continue
        code = p["course_code"]
        dc = paired.get(code)
        with st.container(horizontal=True, vertical_alignment="center"):
            # Indent arrow marks it as a course inside the requirement above, not another requirement.
            st.markdown(f":gray[:material/subdirectory_arrow_right:] {code} · {courses().get(code, {}).get('title', '')} "
                        f":gray-badge[{credits_of(code):g} cr]"
                        + (f" :violet-badge[:material/sync_alt: {dc}]" if dc else ""), width="stretch")
            # Unassign (back to My courses). Either half of a double count unassigns the pair.
            unassign = st.button(":material/close:", type="tertiary", key=f"rm-{req}-{code}",
                                 help="Unassign (moves it back to My courses)")
        if unassign and write((
                """UPDATE plan SET requirement_id = NULL, doublecount_for = NULL
                   WHERE student_id = %(s)s AND program_id = %(p)s AND requirement_id = %(r)s
                   AND (course_code = %(c)s OR doublecount_for = %(c)s OR course_code IN
                        (SELECT doublecount_for FROM plan WHERE student_id = %(s)s AND program_id = %(p)s
                         AND course_code = %(c)s))""",
                {"s": ss.sid, "p": ss.program, "r": req, "c": code}), done=f"Moved {code} back to My courses"):
            st.rerun()

    # Enough credits (this requirement plus its sub-requirements): no add box.
    cr = sum(credits_of(p["course_code"]) for p in plan if p["requirement_id"] and
             (p["requirement_id"] == req or p["requirement_id"].startswith(req + "/")))
    if node["min_credits"] and cr >= node["min_credits"]:
        return
    opts = options(ss.sid, ss.program, req)
    if not opts:
        st.caption("No more eligible courses.")
        return
    # One relation covers both directions: a course already in a pair (either side) can't start another.
    with st.container(horizontal=True, vertical_alignment="bottom"):
        code = st.selectbox("Add a course", list(opts), index=None, format_func=lambda c: option_label(opts[c], paired),
                            key=f"add-{req}-{v}", placeholder="Add a course…", label_visibility="collapsed")
        pair = None
        free = [c for c in partners(ss.program).get(code, []) if c not in paired] if code not in paired else []
        if code and free:
            pair = st.selectbox("Double-count with", free + [None],  # first partner is the default
                                key=f"pair-{req}-{v}", label_visibility="collapsed", width=230,
                                format_func=lambda c: "Don't double count" if c is None else f"Double count with {c}")
        go = st.button("Add", icon=":material/add:", type="primary", disabled=not code, key=f"go-{req}-{v}")
    # Already in My courses -> UPDATE that row; otherwise INSERT a new one.
    if go and write((
            """WITH upd AS (
                 UPDATE plan SET requirement_id = %(r)s, doublecount_for = %(d)s
                 WHERE student_id = %(s)s AND program_id = %(p)s AND course_code = %(c)s
                   AND requirement_id IS NULL RETURNING 1)
               INSERT INTO plan (student_id, program_id, course_code, requirement_id, doublecount_for)
               SELECT %(s)s, %(p)s, %(c)s, %(r)s, %(d)s WHERE NOT EXISTS (SELECT 1 FROM upd)""",
            {"s": ss.sid, "p": ss.program, "c": code, "r": req, "d": pair}), done=f"Added {code} to {node['name']}"):
        st.rerun()


def render(node, kids, plan):
    children = kids.get(node["id"], [])
    if node["fillable"]:
        picker(node, plan)
    elif not children:
        st.caption("No course list in the catalog for this requirement — it's tracked outside the planner.")
    for ch in children:
        # Each requirement is its own card, so its courses and add box sit visibly inside it.
        with st.container(border=True):
            st.markdown(f"**{ch['name']}** {badge(*stats(ch, kids, plan))}")
            render(ch, kids, plan)


def requirement_tree(plan):
    kids = defaultdict(list)
    for r in requirements(ss.program):
        kids[r["parent_id"]].append(r)
    for col, root in zip(st.columns(2, gap="large"), kids[None]):
        with col:
            bs = root["path"] == "bs"
            st.header("Undergraduate" if bs else "Graduate",
                      icon=":material/school:" if bs else ":material/workspace_premium:")
            st.caption(root["name"])
            for top in kids[root["id"]]:
                done, text, _ = stats(top, kids, plan)
                # The label is part of the expander's identity, so a changed credit count would make a
                # new, closed expander. Remember open/closed ourselves and pass it back in.
                label = f"{top['name']} · {text}"
                wkey, okey = f"exp-{top['id']}-{label}", f"open-{top['id']}"
                exp = st.expander(label, expanded=ss.get(okey, False), key=wkey,
                                  icon=":material/check_circle:" if done else ":material/radio_button_unchecked:",
                                  on_change=lambda w=wkey, o=okey: ss.update({o: ss[w]}))
                with exp:
                    if exp.open:  # closed sections skip building their widgets and option queries
                        render(top, kids, plan)


# ----------------------------------------------------------------------------- page
def main():
    st.set_page_config(page_title="WPI BS/MS planner", page_icon=":material/school:", layout="wide")
    if "toast" in ss:
        st.toast(ss.pop("toast"), icon=":material/check_circle:")
    if "sid" not in ss:
        sign_in_page()
        return

    sidebar()
    with st.container(horizontal=True, vertical_alignment="center"):
        st.title("WPI BS/MS planner", icon=":material/school:", width="stretch")
        if st.button("Course search", icon=":material/search:"):
            course_search()
    st.caption(programs()[ss.program])

    plan = q("SELECT * FROM plan WHERE student_id = %s AND program_id = %s ORDER BY course_code",
             (ss.sid, ss.program))
    overview(plan)
    my_courses(plan)
    requirement_tree(plan)


if __name__ == "__main__":
    main()
