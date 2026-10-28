import psycopg
import os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Connect to neon
with psycopg.connect(os.environ.get('NEON_CONNECTION')) as conn:
    # Query and store to dataframe
    query = "SELECT * FROM doublecounts"
    df = pd.read_sql_query(query, conn)

    # Additionally, try to insert-to the Plan table, a Course which does not exist in the View (combined table), 'fullCourseList'
    trigger_test_data = {
        'student_id' : [1234567],
        'program_id' : ['cs-bsms'],
        'course_code' : ['CS 1000'],
        'requirement_id' : ['cs-bsms/cs-breadth/other-breadth/applications-of-cs'],
        'doublecount_for' : [None]
    }
    tt = pd.DataFrame(trigger_test_data)

    # Note that 'to_sql()' returns None. It does NOT return the result of the function.
    try:
        tt.to_sql(
            name = 'plan',
            con = conn,
            if_exists = 'append',
            index = False
        )
    except Exception as e:
        st.error(f"Error performing INSERT: {e.diag.message_primary}")
    # End try-catch

    # Display dataframe in streamlit
    st.title("Double Counts Table")
    st.dataframe(df, use_container_width=True)