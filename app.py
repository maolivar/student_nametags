"""
app.py
Streamlit web app for generating tent-card nametags.

Run with:
    streamlit run app.py

Two-tab pipeline:
    Tab 1 — Paste raw names → parse → review/edit table → (optionally download CSV)
    Tab 2 — Select which columns to print → generate PDF → download
"""

import pandas as pd
import streamlit as st

from name_parser import parse_lines
from pdf_engine import generate_pdf_bytes

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Nametag Generator", layout="wide")
st.title("Nametag Generator")

# ── shared session state ───────────────────────────────────────────────────────
if "parsed_df" not in st.session_state:
    st.session_state["parsed_df"] = None

# ── tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2 = st.tabs(["1 · Parse Names", "2 · Generate PDF"])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — Parse Names
# ═════════════════════════════════════════════════════════════════════════════
with tab1:
    col_input, col_options = st.columns([2, 1])

    with col_input:
        st.subheader("Paste names")
        st.caption("One name per line. Example: AMOR COHEN FLORENCIA")
        raw_text = st.text_area(
            label="Raw name list",
            height=350,
            placeholder="AMOR COHEN FLORENCIA\nGARCIA DE LA TORRE CARLOS\n...",
            label_visibility="collapsed",
        )

    with col_options:
        st.subheader("Format options")

        order = st.radio(
            "Name order",
            options=["last_first", "first_last"],
            format_func=lambda x: "Last name(s) first" if x == "last_first" else "First name(s) first",
        )

        num_apellido_words = st.number_input(
            "Default number of last names per student",
            min_value=1,
            max_value=3,
            value=2,
            step=1,
            help=(
                "Used for lines where no exception separator is found. "
                "The parser consumes this many last-name parts from the apellido side. "
                "Example: set to 2 when most students have two last names (AMOR COHEN FLORENCIA)."
            ),
        )

        num_nombre_words = st.number_input(
            "Default number of first names per student",
            min_value=1,
            max_value=3,
            value=2,
            step=1,
            help=(
                "Used for lines where no exception separator is found. "
                "The parser consumes this many first-name parts from the nombre side. "
                "Example: set to 2 when most students have two first names."
            ),
        )

        sep_raw = st.text_input(
            "Exception separator (for students who differ from the default)",
            value="  ",
            help=(
                "If a line contains this separator, it overrides the default word count: "
                "everything before = last name(s), everything after = first name(s). "
                "Example: students with one last name entered as 'AMOR  FLORENCIA' (two spaces). "
                "Common separators: two spaces, comma, pipe |, semicolon, tab (\\t). "
                "Leave blank to always use the default word count."
            ),
        )
        separator = sep_raw.replace("\\t", "\t").replace("\\n", "\n")
        if separator:
            st.caption(f"Exception separator active: {repr(separator)}")

        triggers_raw = st.text_input(
            "Composite last-name triggers (comma-separated)",
            value="DE, DEL, DE LA, DE LOS, DE LAS, VAN, VON",
            help=(
                "Words that signal a multi-word apellido. "
                "Example: 'DE LA' causes 'DE LA TORRE' to be treated as one last-name part."
            ),
        )
        composite_triggers = [t.strip() for t in triggers_raw.split(",") if t.strip()]

        capitalize = st.selectbox(
            "Capitalization",
            options=["UPPER", "TITLE", "AS_IS"],
            format_func=lambda x: {"UPPER": "ALL CAPS", "TITLE": "Title Case", "AS_IS": "As entered"}[x],
        )

    st.divider()

    parse_btn = st.button("Parse names", type="primary", disabled=not raw_text.strip())

    if parse_btn and raw_text.strip():
        rows = parse_lines(
            raw_text=raw_text,
            order=order,
            separator=separator,
            num_apellido_words=int(num_apellido_words),
            num_nombre_words=int(num_nombre_words),
            composite_triggers=composite_triggers,
            capitalize=capitalize,
        )
        st.session_state["parsed_df"] = pd.DataFrame(rows)

    if st.session_state["parsed_df"] is not None:
        df = st.session_state["parsed_df"]

        st.subheader(f"Parsed names — {len(df)} rows")
        st.caption("Edit any cell directly. Uncheck 'include' to skip a student in the PDF.")

        edited_df = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "last_name_1":  st.column_config.TextColumn("Last Name 1"),
                "last_name_2":  st.column_config.TextColumn("Last Name 2"),
                "first_name_1": st.column_config.TextColumn("First Name 1"),
                "first_name_2": st.column_config.TextColumn("First Name 2"),
                "include":      st.column_config.CheckboxColumn("Include", default=True),
            },
            column_order=["last_name_1", "last_name_2", "first_name_1", "first_name_2", "include"],
            key="name_editor",
        )
        st.session_state["parsed_df"] = edited_df

        csv_bytes = edited_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Download CSV (optional — for review)",
            data=csv_bytes,
            file_name="parsed_names.csv",
            mime="text/csv",
        )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — Generate PDF
# ═════════════════════════════════════════════════════════════════════════════
with tab2:
    df = st.session_state.get("parsed_df")

    # ── fallback: upload CSV if session has no data ────────────────────────
    if df is None:
        st.info("No parsed names in session. You can upload a previously saved CSV.")
        uploaded = st.file_uploader("Upload parsed_names.csv", type=["csv"])
        if uploaded is not None:
            df = pd.read_csv(uploaded)
            if "include" not in df.columns:
                df["include"] = True
            st.session_state["parsed_df"] = df

    if df is not None:
        included = df[df["include"] == True]  # noqa: E712

        # ── column selection ───────────────────────────────────────────────
        st.subheader("What to print on each nametag")

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("**First line** (large — first name)")
            fn1 = st.checkbox("First Name 1", value=True,  key="fn1")
            fn2 = st.checkbox("First Name 2", value=False, key="fn2")

        with col_b:
            st.markdown("**Second line** (smaller — last name)")
            ln1 = st.checkbox("Last Name 1", value=True,  key="ln1")
            ln2 = st.checkbox("Last Name 2", value=True,  key="ln2")

        # Build the combined strings for each student
        def build_name(row, use_fn1, use_fn2, use_ln1, use_ln2):
            first_parts = []
            if use_fn1 and str(row.get("first_name_1", "")).strip():
                first_parts.append(str(row["first_name_1"]).strip())
            if use_fn2 and str(row.get("first_name_2", "")).strip():
                first_parts.append(str(row["first_name_2"]).strip())
            last_parts = []
            if use_ln1 and str(row.get("last_name_1", "")).strip():
                last_parts.append(str(row["last_name_1"]).strip())
            if use_ln2 and str(row.get("last_name_2", "")).strip():
                last_parts.append(str(row["last_name_2"]).strip())
            return " ".join(first_parts), " ".join(last_parts)

        st.divider()
        st.subheader(f"Preview — {len(included)} student(s)")

        if len(included) == 0:
            st.warning("No students selected. Check the 'include' column in Tab 1.")
        else:
            preview_rows = [
                build_name(row, fn1, fn2, ln1, ln2)
                for _, row in included.iterrows()
            ]
            preview_df = pd.DataFrame(preview_rows, columns=["First line", "Second line"])
            st.dataframe(preview_df, use_container_width=True, hide_index=True)

            if st.button("Generate PDF", type="primary"):
                with st.spinner("Building PDF…"):
                    pdf_bytes = generate_pdf_bytes(preview_rows)

                st.success(f"PDF ready — {len(preview_rows)} page(s).")
                st.download_button(
                    label="Download nametags.pdf",
                    data=pdf_bytes,
                    file_name="nametags.pdf",
                    mime="application/pdf",
                )
    else:
        st.write("Go to **Tab 1** to parse names first.")
