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
#   - plan_placements            : each requirement a planned course fills, with its credits there
#   - plan triggers              : HUA rules, double-count check and 40% limit, course
#                                  list check. Their RAISE EXCEPTION messages
#                                  are shown to the user as-is.
#
# Plan rows with requirement_id NULL are courses the student entered but has not
# assigned yet ("My courses"). Assigning one UPDATEs that row; unassigning sets
# requirement_id back to NULL. A double count is one row (the course taken) whose
# doublecount_for/doublecount_req say which equivalent course it also stands in for,
# and where, in the other degree.
#
# AI NOTICE: UI elements in this file were generated with Claude Opus 5.5 (Anthropic),
#            based on the team's Figma mockup (v3 - grad and undergrad).
# -----------------------------------------------------------------------------
"""
from collections import defaultdict

import pandas as pd
import psycopg
import streamlit as st
from course_picker import course_picker
from psycopg.rows import dict_row

YEARS = list(range(2026, 2033))
ss = st.session_state


# ----------------------------------------------------------------------------- database
def conn():
    """One connection per browser session, reopened if Neon dropped it."""
    c = ss.get("conn")
    if c is None or c.closed:
        c = ss.conn = psycopg.connect(st.secrets["NEON_CONNECTION"], autocommit=True, row_factory=dict_row,
                                      keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=5)
    return c


def retry(fn):
    """Run fn(conn); if Neon dropped the idle connection, reconnect and run it once more."""
    try:
        return fn(conn())
    except psycopg.OperationalError:
        ss.pop("conn", None)
        return fn(conn())


def q(sql, params=None):
    return retry(lambda c: c.execute(sql, params).fetchall())


def ver():
    """Bumped after every write so per-write widgets (add boxes) start fresh from the DB."""
    return ss.get("v", 0)


def write(*stmts, done=None):
    """Run (sql, params) pairs in one transaction. On a trigger error, show it and roll back.
    `done` is shown as a toast after the rerun."""
    try:
        def run(c):
            with c.transaction():
                for sql, params in stmts:
                    c.execute(sql, params)
        retry(run)
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
                WHERE f.requirement_id LIKE %s ORDER BY 1""", ("%/bs/humanities-and-arts/depth",))
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
    rows = q("SELECT * FROM get_requirement_options(%s, %s, %s)", (sid, pid, req))
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
        st.title("WPI BS/MS planner", anchor=False)
        st.caption("Track the courses you've taken, fill each B.S. and M.S. requirement, "
                   "and choose which courses to double count.")
        with st.form("sign-in"):
            raw = st.text_input("Student ID", placeholder="e.g. 901234567", max_chars=9,
                                validate=(r"^\d+$", "Use digits only."))
            if st.form_submit_button("Sign in", type="primary", icon=":material/login:", width="stretch") and raw:
                ss.lookup = int(raw)  # student.student_id is BIGINT
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
            # HUA depth topic is set later from the sidebar.
            if st.form_submit_button("Create profile", type="primary", width="stretch") and write(
                    ("INSERT INTO student (student_id, grad_year, student_email) VALUES (%s, %s, %s)",
                     (sid, year, email or None)), done="Profile created"):
                sign_in(sid)
                st.rerun()


def save_profile():
    write(("UPDATE student SET grad_year = %s, hua_depth = %s WHERE student_id = %s",
           (ss.grad_year, ss.hua_depth, ss.sid)), done="Profile saved")


def sidebar():
    # Program names are "B.S. in X / M.S. in Y": pick the B.S. major, then an M.S. paired with it.
    split = {pid: [part.split(" in ", 1)[1] for part in name.split(" / ")] for pid, name in programs().items()}
    with st.sidebar:
        st.header(f"Student {ss.sid:.0f}", icon=":material/account_circle:", anchor=False)
        if ss.email:
            st.caption(ss.email)
        bs, ms = split[ss.program]
        majors = sorted({b for b, _ in split.values()})
        bs = st.selectbox("B.S. major", majors, index=majors.index(bs),
                          help="Each B.S./M.S. pairing has its own plan. Switching shows that pairing's courses and "
                               "requirements; your other plans are kept.")
        pairs = {m: pid for pid, (b, m) in split.items() if b == bs}
        ms = st.selectbox("M.S. program", list(pairs), index=list(pairs).index(ms) if ms in pairs else 0)
        ss.program = pairs[ms]
        st.selectbox("Humanities & Arts depth topic", hua_topics(), index=None, key="hua_depth",
                     on_change=save_profile,
                     help="Humanities & Arts depth is 3 courses in one topic (at least one at the 2000 level or above); "
                          "breadth is 1 course outside that topic's area. Pick a topic here before adding depth "
                          "courses — until then they can't be added. Changing it later doesn't remove courses "
                          "you've already placed.")
        st.selectbox("Graduation year", YEARS, index=None, key="grad_year", on_change=save_profile)
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
    st.caption(f"{len(hits):,} matches. Select a row to read its description or add it to My courses.")
    sel = st.dataframe(hits, hide_index=True, alt="Course search results", on_select="rerun",
                       selection_mode="single-row", key="search-hits",
                       column_config={"course_code": "Course", "title": "Title", "subject": "Subject",
                                      "credits_raw": st.column_config.NumberColumn("Credits", format="%g"),
                                      "academic_level": "Level"}).selection.rows
    if not sel:
        return
    c = hits[sel[0]]
    code = c["course_code"]
    desc = q("SELECT description FROM fullcourselist WHERE course_code = %s LIMIT 1", (code,))
    st.subheader(f"{code} — {c['title']}", anchor=False)
    st.caption(f"{c['credits_raw']:g} credits · {c['academic_level']} · {c['subject']}")
    st.write((desc and desc[0]["description"]) or "No description in the catalog.")
    have = q("SELECT 1 FROM plan WHERE student_id = %s AND program_id = %s AND course_code = %s",
             (ss.sid, ss.program, code))
    # Unassigned rows are "My courses"; assign them to a requirement from the sections below.
    if st.button("Already in your plan" if have else "Add to My courses", icon=":material/add:",
                 type="primary", disabled=bool(have)) and write((
            "INSERT INTO plan (student_id, program_id, course_code) VALUES (%s, %s, %s)",
            (ss.sid, ss.program, code)), done=f"Added {code} to My courses"):
        st.rerun()


# ----------------------------------------------------------------------------- overview
def overview(plan):
    rows = q("SELECT * FROM student_credit_totals WHERE student_id = %s AND program_id = %s", (ss.sid, ss.program))
    totals = {r["path"]: r["min_credits"] for r in requirements(ss.program) if r["path"] in ("bs", "ms")}
    t = rows[0] if rows else {"ug_credits": 0, "ug_required": totals["bs"], "gr_credits": 0, "gr_required": totals["ms"],
                              "total_credits": 0, "total_required": totals["bs"] + totals["ms"]}
    cols = st.columns(4)
    tips = {"ug": "B.S. credits. A grad course counts 1.5× here (a 2-credit grad course = 3 undergrad credits).",
            "gr": "M.S. credits. An undergrad course counts 2/3 here (3 undergrad credits = 2 grad credits), "
                  "or 3 with the ISU add-on.",
            "total": "B.S. + M.S. credits. A double-counted course adds to both degrees."}
    for col, (name, k) in zip(cols, [("Undergraduate", "ug"), ("Graduate", "gr"), ("Total", "total")]):
        have, need = float(t[f"{k}_credits"]), t[f"{k}_required"]
        with col.container(border=True, height="stretch"):
            st.metric(f"{name} credits", f"{have:g} / {need}", help=tips[k])
            # st.progress can't be recolored: green when filled, orange in progress, gray when empty (as the badges)
            color = "#21c354" if have >= need else "#ff8700" if have > 0 else "#808495"
            st.markdown(f'<div role="progressbar" aria-valuenow="{have:g}" aria-valuemax="{need}" '
                        f'style="background:rgba(128,128,128,.25);border-radius:4px;height:8px">'
                        f'<div style="width:{min(have / need, 1) * 100:.0f}%;background:{color};'
                        f'border-radius:4px;height:100%"></div></div>', unsafe_allow_html=True)
    # WPI: at most 40% of the M.S. credits count toward both degrees; a double count uses its M.S.-side credits
    cap = 0.4 * totals["ms"]
    used = sum(float(p["credits"]) for p in plan if p["doublecount_for"] and p["degree"] == "ms")
    with cols[3].container(border=True, height="stretch"):
        st.metric("Double-counted credits", f"{used:g} / {cap:g}",
                  help="Double counting: one undergrad course also fills its equivalent grad course in the M.S. "
                       "(paired courses are listed per program). It counts 3 credits toward the B.S. and 2 toward "
                       "the M.S.; completing the ISU extra credit bumps the M.S. side to 3. WPI allows at most 40% "
                       "of the M.S. credits to count toward both degrees.")
        st.caption(", ".join(f"{p['course_code']} (as {p['doublecount_for']})" for p in plan if p["is_doublecount"])
                   or "Pick “also count as …” when adding a double-countable course.")


def my_courses(plan):
    unassigned = [p["course_code"] for p in plan if p["requirement_id"] is None]
    in_plan = {p["course_code"] for p in plan}
    with st.container(border=True):
        st.subheader("My courses", icon=":material/inventory_2:", anchor=False)
        st.caption("Every course you've taken or plan to take. Assign unassigned ones from the requirement "
                   "sections below, where they're marked ✓ taken.")
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
        credits_col = {"Credits": st.column_config.NumberColumn(format="%g")}
        # Tables size to their rows (default auto height); an empty one still shows its header and one blank row.
        st.markdown(f"**Unassigned** :gray-badge[{len(unassigned)}]")
        table = pd.DataFrame([{"Course": c, "Title": courses().get(c, {}).get("title"), "Credits": credits_of(c)}
                              for c in unassigned], columns=["Course", "Title", "Credits"])
        picked = st.dataframe(table, hide_index=True, on_select="rerun", selection_mode="multi-row",
                              key=f"bank-{ss.program}-{ver()}", alt="Unassigned courses", column_config=credits_col)
        gone = [unassigned[i] for i in picked.selection.rows]
        if gone and st.button(f"Remove selected ({len(gone)})", icon=":material/delete:",
                              key=f"bank-rm-{ver()}") and write(
                *[("DELETE FROM plan WHERE student_id = %s AND program_id = %s AND course_code = %s "
                   "AND requirement_id IS NULL", (ss.sid, ss.program, c)) for c in gone],
                done=f"Removed {len(gone)} course{'s' * (len(gone) > 1)}"):
            st.rerun()

        assigned = [p for p in plan if p["requirement_id"]]
        names = {r["id"]: r["name"] for r in requirements(ss.program)}
        st.markdown(f"**Assigned** :gray-badge[{len(assigned)}]")
        st.dataframe(pd.DataFrame([{"Course": p["course_code"], "Title": courses().get(p["course_code"], {}).get("title"),
                                    "Credits": float(p["credits"]), "Requirement": names.get(p["requirement_id"]),
                                    "Degree": "M.S." if p["degree"] == "ms" else "B.S."}
                                   for p in assigned], columns=["Course", "Title", "Credits", "Requirement", "Degree"]),
                     hide_index=True, alt="Assigned courses", column_config=credits_col)
        st.caption("Unassign a course with ✕ in its requirement below.")


# ----------------------------------------------------------------------------- requirements
def stats(node, kids, plan):
    """(done, summary) for a requirement and everything under it."""
    nid = node["id"]
    rows = [p for p in plan if p["requirement_id"] and
            (p["requirement_id"] == nid or p["requirement_id"].startswith(nid + "/"))]
    cr = sum(float(p["credits"]) for p in rows)
    children = kids.get(nid, [])
    kids_done = sum(stats(ch, kids, plan)[0] for ch in children) if node["min_children"] else 0
    done = (bool(rows) and cr >= node["min_credits"] and len(rows) >= node["min_courses"]
            and kids_done >= node["min_children"])
    parts = [f"{cr:g}/{node['min_credits']} cr" if node["min_credits"] else f"{cr:g} cr"]
    # A catch-all (Free Electives, M.S. Electives) has no minimum of its own: it is done when the degree total is met.
    root = next((r for r in kids[None] if r["id"] == node["parent_id"]), None)
    if root and not (node["min_credits"] or node["min_courses"] or node["max_credits"] or children):
        left = root["min_credits"] - sum(float(p["credits"]) for p in plan
                                         if p["requirement_id"] and p["requirement_id"].startswith(root["id"] + "/"))
        done = left <= 0
        if left > 0:
            parts.append(f"{left:g} more for the {root['min_credits']}-credit total")
    if node["min_courses"]:
        parts.append(f"{len(rows)}/{node['min_courses']} courses")
    if node["min_children"] and children:
        parts.append(f"{kids_done}/{node['min_children']} sections")
    return done, " · ".join(parts), bool(rows)


def badge(done, text, started):
    color = "green" if done else "orange" if started else "gray"
    return f":{color}-badge[{':material/check: ' if done else ''}{text}]"


def option_tags(o):
    """Chips under each option in the course picker: (style, text)."""
    return ([("taken", "✓ Taken")] if o["is_taken"] else []) + \
        ([("double", "⇄ Double-countable")] if o["is_double_countable"] else []) + \
        ([("popular", f"★ Popular · {o['pct_chosen'] or 0:g}% chose")] if o["tier"] <= 4 else []) + \
        ([("", o["hua_role"])] if o["hua_role"] else [])


def credits_in(code, degree, isu=False):
    """What a course is worth toward a degree: its own credits at its own level; grad -> B.S. x1.5
    (1 grad credit = 1/6 unit), undergrad -> M.S. x2/3."""
    grad = courses().get(code, {}).get("academic_level") == "Graduate"
    if grad == (degree == "ms"):
        return credits_of(code)
    return credits_of(code) * (1.5 if grad else 2 / 3) + (isu and not grad)  # ISU: +1 grad credit


@st.cache_data(ttl="1h")
def slots(pid, code):
    """Requirements in this program that list `code`, most specific (shortest course list) first."""
    return [r["requirement_id"] for r in q(
        """SELECT f.requirement_id FROM filledby f JOIN requirements r ON r.id = f.requirement_id
           WHERE r.program_id = %s AND f.course_code = %s
           ORDER BY (SELECT count(*) FROM filledby g WHERE g.requirement_id = r.id), r.path""", (pid, code))]


def picker(node, kids, plan):
    """Assigned courses (with unassign buttons) + an add box fed by get_requirement_options()."""
    req, v = node["id"], ver()
    for p in plan:
        if p["requirement_id"] != req:
            continue
        code, dc = p["course_code"], p["doublecount_for"]
        note = (f" :violet-badge[:material/sync_alt: as {dc}]" if p["is_doublecount"]
                else f" :violet-badge[:material/sync_alt: also counts as {dc}]" if dc else "")
        # wrap=False keeps ✕ on the right; a long title wraps inside the text instead.
        with st.container(horizontal=True, vertical_alignment="center", wrap=False):
            # Indent arrow marks it as a course inside the requirement above, not another requirement.
            st.markdown(f":gray[:material/subdirectory_arrow_right:] {code} · {courses().get(code, {}).get('title', '')} "
                        f":gray-badge[{float(p['credits']):g} cr]" + note, width="stretch")
            unassign = st.button(":material/close:", type="tertiary", key=f"rm-{req}-{code}",
                                 help="Stop double counting it" if p["is_doublecount"]
                                 else "Unassign (moves it back to My courses)")
        # The double-count side only drops the double count; the course's own side unassigns it entirely.
        sql = ("UPDATE plan SET doublecount_for = NULL, doublecount_req = NULL" if p["is_doublecount"] else
               "UPDATE plan SET requirement_id = NULL, doublecount_for = NULL, doublecount_req = NULL")
        if unassign and write((sql + " WHERE student_id = %s AND program_id = %s AND course_code = %s",
                               (ss.sid, ss.program, code)),
                              done=f"{code} no longer double counts" if p["is_doublecount"]
                              else f"Moved {code} back to My courses"):
            st.rerun()

    # Complete (this requirement plus its sub-requirements): no add box.
    if stats(node, kids, plan)[0]:
        return
    opts = options(ss.sid, ss.program, req)
    if not opts:
        st.caption("No more eligible courses.")
        return
    # A double count is the one course taken, also filling its equivalent's slot in the other degree.
    other = "ms" if req.split("/")[1] == "bs" else "bs"
    names = {r["id"]: r["name"] for r in requirements(ss.program)}
    used = {p["course_code"] for p in plan} | {p["doublecount_for"] for p in plan if p["doublecount_for"]}
    # Top alignment: the picker's option list opens inline and grows the row downward.
    with st.container(horizontal=True, vertical_alignment="top"):
        code = course_picker([{"code": c, "title": o["title"], "tags": option_tags(o)} for c, o in opts.items()],
                             key=f"add-{req}-{v}")
        # (equivalent course, other-degree requirement listing it); the first is the default
        choices = [(eq, r) for eq in partners(ss.program).get(code, []) if eq not in used
                   for r in slots(ss.program, eq) if r.split("/")[1] == other]
        pick, isu = None, False
        if code and choices:
            pick = st.selectbox("Double count", choices + [None], key=f"pair-{req}-{v}",
                                label_visibility="collapsed", width=320,
                                help="Also count this course as its equivalent in the other degree. "
                                     "Uses part of your 40% double-count limit.",
                                format_func=lambda o: "Don't double count" if o is None else
                                f"Also count as {o[0]} in {names[o[1]]} ({credits_in(code, other):g} cr)")
            if pick and other == "ms":
                isu = st.checkbox("ISU credit (+1 grad cr)", key=f"isu-{req}-{v}",
                                  help="Check if you complete the ISU extra credit for this course. "
                                       "It raises the M.S. credit from 2 to 3 and counts toward the 40% limit.")
        go = st.button("Add", icon=":material/add:", type="primary", disabled=not code, key=f"go-{req}-{v}")
    d, dreq = pick or (None, None)
    # Already in My courses -> UPDATE that row; otherwise INSERT a new one.
    if go and write((
            """WITH upd AS (
                 UPDATE plan SET requirement_id = %(r)s, doublecount_for = %(d)s, doublecount_req = %(dr)s, isu = %(i)s
                 WHERE student_id = %(s)s AND program_id = %(p)s AND course_code = %(c)s
                   AND requirement_id IS NULL RETURNING 1)
               INSERT INTO plan (student_id, program_id, course_code, requirement_id, doublecount_for, doublecount_req, isu)
               SELECT %(s)s, %(p)s, %(c)s, %(r)s, %(d)s, %(dr)s, %(i)s WHERE NOT EXISTS (SELECT 1 FROM upd)""",
            {"s": ss.sid, "p": ss.program, "c": code, "r": req, "d": d, "dr": dreq, "i": isu}),
            done=f"Added {code} to {node['name']}" + (f", also counting as {d}" if d else "")):
        st.rerun()


def render(node, kids, plan):
    children = kids.get(node["id"], [])
    if node["fillable"]:
        picker(node, kids, plan)
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
            st.header("Undergraduate" if bs else "Graduate", anchor=False)
            st.caption(root["name"])
            for top in kids[root["id"]]:
                done, text, started = stats(top, kids, plan)
                # The label is part of the expander's identity, so a changed credit count would make a
                # new, closed expander. Remember open/closed ourselves and pass it back in.
                label = f"{top['name']} {badge(done, text, started)}"
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
        st.title("WPI BS/MS planner", anchor=False, width="stretch")
        if st.button("Course search", icon=":material/search:"):
            course_search()

    # One row per requirement a course fills (a double count fills two), with what it's worth there.
    plan = q("SELECT * FROM plan_placements WHERE student_id = %s AND program_id = %s ORDER BY course_code",
             (ss.sid, ss.program))
    overview(plan)
    my_courses(plan)
    requirement_tree(plan)


if __name__ == "__main__":
    main()
