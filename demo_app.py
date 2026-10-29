# ----------------------------------------------------------------------------- 
"""
# Assignment	: Term (Group) Project
# Author	: Neel Awsare, Tobey Appenzeller, Karen Bonilla, Thomas Solley 
# Class	: CS 542 – Database Management
# Due Date  : 12/01/2026
# Purpose	: Demonstrate the ability to connect-to our DBMS, perform a Query, 
#               return a result
# File:	: demo_app.py
# ------------------------------------------------------------------------------
# Procedure: demo_app()
# Purpose/Spec: Esseentially, act-as "main"; "Do the thing".
# Parameters: None.
# Input: None.
# Assumptions: The user has already created a local virtual environment (if 
#               using Microsoft VSC w/ Python extensions, for example), 
#               installed Python to their computer, modified their system PATH 
#               variable appropriately, has access-to and has run the 
#               operations described-in README.txt (from Github repo) to get 
#               all required libraries and their dependencies installed (such 
#               as streamlit, psycopg, pandas, etc.), created their local 
#               instance of ".env"-file with their personal Connection-String 
#               provided-by Neon. User has (stable) Internet access, and the 
#               ability to access and use a Web-browser. User is assumed to be 
#               one of the 4 authors listed above; user is expected to have 
#               some familiarity with Python syntax, debugging, and 
#               troubleshooting, or be able to look things up on the Internet. 
#               User may or may not have Github enabled on their machine to 
#               manage (remote) code repository. 
# Output: A call-to a local instance of streamlit web-application; link will 
#               open in user's default browser according-to their default tab/
#               window settings.
# System Calls: pandas, streamlit, psycopg, os, load_dotenv()
# ------------------------------------------------------------------------------
# Procedure: 
# Purpose/Spec: 
# Parameters: 
# Input: 
# Assumptions: 
# Output: 
# System Calls: 
# ------------------------------------------------------------------------------
#
# RESOURCES USED will be at the END of the file (for brevity's sake)
#
# Note that use of AI to replace learning of Course Material is strictly 
#               frowned-upon. Any use of AI in this project must be noted and 
#               declared. Use of AI to generate UI-elements is deemed 
#               acceptable, as long as it is marked.
#
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# CHANGE LOG: (managed by Github)
#
# Date			Name			Purpose
# ------------------------------------------------------------------------------
# 10/26/2026		   Neel Awsare     	    Inception
# 10/27/2026           Thomas Solley        Attempted to add code that would 
#                                           demonstrate functionality of one of 
#                                           our Triggers; attempt an Insert 
#                                           operation on Table "plan", using a 
#                                           course_code that does not exist (in 
#                                           either Tables "courses_grad" or 
#                                           "courses_undergrad", therefore not 
#                                           in the View "fullCourseList", 
#                                           thereby violating the FK-IC on 
#                                           course_code in Table "plan", 
#                                           enforced-by Trigger 
#                                           tr_checkCourseList). Upon 
#                                           activating this Trigger (required 
#                                           because we cannot add a FK that 
#                                           references a View; since we removed 
#                                           parent Table "courses" to match our 
#                                           ERD-5.0, we have no other 
#                                           cumulative list of all available/
#                                           supported classes in the DB; rather 
#                                           than add Table "courses" back-in to 
#                                           Neon, which would complicate the 
#                                           ERD, I simulated this list with the 
#                                           View fullCourseList) -- the 
#                                           attempted Insert should fail, and 
#                                           the hard-coded RAISE EXCEPTION 
#                                           message in Neon should be 
#                                           displayed-by streamlit.
#                                           Both the Trigger and 
#                                           Insert-statement (logic) were 
#                                           tested-in Neon using the SQL Editor 
#                                           beforehand.
#                                           This code was pushed and 
#                                           committed-to the Repo without 
#                                           verifying integrity or 
#                                           functionality; I could not get the 
#                                           file to run on my machine due-to 
#                                           ENV and Module errors.
# 10/28/2026           Thomas Solley        Fixed the Try-Catch statement, 
#                                           verified that the proper RAISE 
#                                           EXCEPTION text from Trigger 
#                                           tr_checkCourseList is being 
#                                           displayed in streamlit upon 
#                                           attempted execution of the 
#                                           .to_sql() block.
#                                           Added this Header, including 
#                                           Assignment definition, Procedure 
#                                           definitions (future), Revision 
#                                           History, and Resources Used.
"""
# ----------------------------------------------------------------------------- 
# Imports
import psycopg
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Global Variables

# Constants

# Class/Function definition (remember that, by default, Python executes code in the order it is written; it does not use function prototypes)
def demo_app():
    # Load environment variables; ".env", includes Neon connection-string (per-user)
    load_dotenv()

    # Connect to neon
    with psycopg.connect(os.environ.get('NEON_CONNECTION')) as conn:
        # Query and store to dataframe
        query = "SELECT * FROM doublecounts"
        df = pd.read_sql_query(query, conn)

        # Additionally, try to insert-to the Plan table, a Course which does not exist in the View (combined table), 'fullCourseList'
        """
        trigger_test_data = {
            'student_id' : [1234567],
            'program_id' : ['cs-bsms'],
            'course_code' : ['CS 1000'],
            'requirement_id' : ['cs-bsms/cs-breadth/other-breadth/applications-of-cs'],
            'doublecount_for' : [None]
        }
        tt = pd.DataFrame(trigger_test_data)
        """
        # Note that 'to_sql()' returns None. It does NOT return the result of the function.
        try:
            """ Fails to run as-intended.
            tt.to_sql(
                name = 'plan',
                con = conn,
                if_exists = 'append',
                index = False
            )
            """
            student_id = 1234567
            program_id = 'cs-bsms'
            course_code = 'CS 1000'
            requirement_id = 'cs-bsms/cs-breadth/other-breadth/applications-of-cs'
            doublecount_for = None
            sql = """
                INSERT INTO plan (student_id, program_id, course_code, requirement_id, doublecount_for) VALUES (%s, %s, %s, %s, %s)"""
            data = (student_id, program_id, course_code, requirement_id, doublecount_for)

            with conn.cursor() as cur:
                cur.execute(sql, data)
                # Note we are not calling con.commit() here, since we both expect this to fail AND we don't want to actually save this entry.
            # End with-statement
        except (psycopg.errors.RaiseException, psycopg.errors.UniqueViolation, psycopg.errors.ForeignKeyViolation) as f:
            conn.rollback() # not sure if this will undo the Pre-Try transaction as well (it shouldn't)
            #st.error("Error1 performing INSERT: %s", (f))
            error_message = f.diag.message_primary
            st.error(f"Database Trigger blocked INSERT action: {error_message}")
        except psycopg.errors.OperationalError as g:
            conn.rollback()
            st.error(f"Connection/Operational error: {g}")
        except psycopg.Error as h:
            conn.rollback()
            st.error(f"Generic Database error: {h}")
        except Exception as e:
            # It is apparently important to include this here, though, because of how PGS handles aborted transactions vs. persistent connections...
            # In the base Demo, this was not required because commits and rollbacks were implicitly handled with the With-statement.
            conn.rollback()
            #st.error("Error2 performing INSERT: %s", (e))
            st.error(f"Unhandled error: {e}")
        # End try-catch

        # Display dataframe in streamlit
        st.title("Double Counts Table")
        st.dataframe(df, use_container_width=True)
    # End With-statement

    # Safety; should not be needed, based-on syntax.
    conn.close()
# End fn. demo_app()

# Tests, to be run in this specific file (if focused)
if __name__ == '__main__':
    demo_app()
# End if-statement
# ------------------------------------------------------------------------------
# RESOURCES USED 
# --> <SearchEngineWebSiteName.extension>, "the base search query used", <full_url_string>, Accessed-Date-full-string.
# AND
# <ActualSourceSupportingWebsiteName.extension>, "title of webpage", <full_url_string>, Accessed-Date-full-string.
# --> (Snow, Sylvan. CS-513-F01, "HW1.docx", <https://canvas.wpi.edu/courses/88998/assignments/491256?module_item_id=1556650>. 08/25/2026). [used-for Header and Footer template].
# --> <Github.com>, "wpi-bs-ms-planner", <https://github.com/awsare/wpi-bs-ms-planner/tree/main>, September 21 2026.
# --> <Google.com>, "python neon streamlit postgresql, try to perform SQL INSERT operation, catch RAISE EXCEPTION trigger in Python psycopg3", <https://www.google.com/search?q=python+neon+streamlit+postgresql%2C+try+to+perform+SQL+INSERT+operation%2C+catch+RAISE+EXCEPTION+trigger+in+Python+psycopg3&sca_esv=bd43364d62e50cb8&rlz=1C1HKFL_enUS1208US1208&sxsrf=AKL5yDj84q0sWujvxPB-NncW2jVTxlnivA%3A1793229843083&ei=E4TiarTUBKiEw8cPrZzRmA0&biw=1707&bih=945&ved=2ahUKEwj0qbDe7d2XAxUowvACHS1OFNMQ4dUDegQIBhAM&uact=5&oq=python+neon+streamlit+postgresql%2C+try+to+perform+SQL+INSERT+operation%2C+catch+RAISE+EXCEPTION+trigger+in+Python+psycopg3&gs_lp=Egxnd3Mtd2l6LXNlcnAid3B5dGhvbiBuZW9uIHN0cmVhbWxpdCBwb3N0Z3Jlc3FsLCB0cnkgdG8gcGVyZm9ybSBTUUwgSU5TRVJUIG9wZXJhdGlvbiwgY2F0Y2ggUkFJU0UgRVhDRVBUSU9OIHRyaWdnZXIgaW4gUHl0aG9uIHBzeWNvcGczSABQAFgAcAB4AZABAJgBAKABAKoBALABALgBA8gBAPgBAZgCAKACAJgDAOIDBBgAIF3iAwQYACBe4gMEGAAgX-IDBBgAIGDiAwQYACBh4gMEGAAgYpIHAKAHALIHALgHAMIHAMgHAIAIAQ&sclient=gws-wiz-serp>, October 28 2026.
# AND
# <PGTutorial.com>, "PostgreSQL Python: Insert Data into a table with psycopg3", <https://www.pgtutorial.com/postgresql-python/insert/>, October 28 2026.
# --> 
# ------------------------------------------------------------------------------
# EOL