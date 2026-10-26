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

    # Display dataframe in streamlit
    st.title("Double Counts Table")
    st.dataframe(df, use_container_width=True)