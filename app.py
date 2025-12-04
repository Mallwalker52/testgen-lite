import json
from pathlib import Path

import streamlit as st

# ---------- Load question bank ----------
def load_questions(path: Path):
    if not path.exists():
        st.error(f"questions.json not found at: {path}")
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                st.error("questions.json must contain a list of questions.")
                return []
            return data
    except Exception as e:
        st.error(f"Error loading questions.json: {e}")
        return []


QUESTIONS = load_questions(Path("questions.json"))
Q_BY_ID = {q["id"]: q for q in QUESTIONS}

# ---------- Session state setup ----------
if "selected_ids" not in st.session_state:
    st.session_state["selected_ids"] = []

selected_ids = st.session_state["selected_ids"]

# ---------- Sidebar filters ----------
st.sidebar.title("TestGen Lite (Web)")

if not QUESTIONS:
    st.sidebar.write("Add a questions.json file and refresh.")
else:
    topics = sorted({q.get("topic", "Untitled") for q in QUESTIONS})
    topic_filter = st.sidebar.multiselect(
        "Filter by topic", options=topics, default=topics
    )
    search_text = st.sidebar.text_input("Search in question text", value="")


# ---------- Helper functions ----------
def filtered_questions():
    if not QUESTIONS:
        return []
    qs = [
        q
        for q in QUESTIONS
        if q.get("topic", "Untitled") in topic_filter
    ]
    if search_text.strip():
        s = search_text.lower()
        qs = [q for q in qs if s in q.get("text", "").lower()]
    return qs


def add_to_test(ids_to_add):
    for qid in ids_to_add:
        if qid not in st.session_state["selected_ids"]:
            st.session_state["selected_ids"].append(qid)


def move_up(index):
    if index <= 0 or index >= len(st.session_state["selected_ids"]):
        return
    ids = st.session_state["selected_ids"]
    ids[index - 1], ids[index] = ids[index], ids[index - 1]


def move_down(index):
    if index < 0 or index >= len(st.session_state["selected_ids"]) - 1:
        return
    ids = st.session_state["selected_ids"]
    ids[index + 1], ids[index] = ids[index], ids[index + 1]


def remove_from_test(index):
    ids = st.session_state["selected_ids"]
    if 0 <= index < len(ids):
        ids.pop(index)


def make_test_markdown():
    lines = ["# Test", ""]
    for i, qid in enumerate(st.session_state["selected_ids"], start=1):
        q = Q_BY_ID.get(qid)
        if not q:
            continue
        pts = q.get("points", 0)
        lines.append(f"{i}. ({pts} pts) {q.get('text', '')}")
        lines.append("")
    return "\n".join(lines)


def make_key_markdown():
    lines = ["# Answer Key", ""]
    for i, qid in enumerate(st.session_state["selected_ids"], start=1):
        q = Q_BY_ID.get(qid)
        if not q:
            continue
        pts = q.get("points", 0)
        lines.append(f"{i}. ({pts} pts) {q.get('text', '')}")
        lines.append("")
        lines.append(f"**Solution:** {q.get('solution', '')}")
        lines.append("")
    return "\n".join(lines)


# ---------- Layout ----------
st.title("TestGen Lite – Question Picker + Answer Key")

if not QUESTIONS:
    st.stop()

col_bank, col_test = st.columns(2)

# ----- Left column: question bank -----
with col_bank:
    st.subheader("Question Bank")

    bank_qs = filtered_questions()
    if not bank_qs:
        st.write("No questions match the current filter.")
    else:
        options = [
            f"{q['id']} – {q.get('topic', 'Untitled')}" for q in bank_qs
        ]
        id_by_label = {
            f"{q['id']} – {q.get('topic', 'Untitled')}": q["id"]
            for q in bank_qs
        }

        selected_labels = st.multiselect(
            "Select questions to add",
            options=options,
            key="bank_multiselect",
        )

        if st.button("Add selected to test"):
            ids_to_add = [id_by_label[label] for label in selected_labels]
            add_to_test(ids_to_add)

        with st.expander("Preview from bank"):
            preview_label = st.selectbox(
                "Choose a question to preview",
                options=["(none)"] + options,
                key="bank_preview_select",
            )
            if preview_label != "(none)":
                qid = id_by_label[preview_label]
                q = Q_BY_ID.get(qid)
                if q:
                    st.markdown(f"**ID:** {q['id']}")
                    st.markdown(f"**Topic:** {q.get('topic', 'Untitled')}")
                    st.markdown("**Question:**")
                    st.write(q.get("text", ""))
                    st.markdown("**Solution:**")
                    st.write(q.get("solution", ""))

# ----- Right column: current test -----
with col_test:
    st.subheader("Current Test")

    if not selected_ids:
        st.write("No questions selected yet.")
    else:
        for idx, qid in enumerate(selected_ids):
            q = Q_BY_ID.get(qid)
            if not q:
                continue
            with st.container():
                st.markdown(
                    f"**{idx + 1}. {qid} – {q.get('topic', 'Untitled')} "
                    f"({q.get('points', 0)} pts)**"
                )
                st.write(q.get("text", ""))

                bcol1, bcol2, bcol3 = st.columns(3)
                with bcol1:
                    if st.button("⬆️ Up", key=f"up_{idx}"):
                        move_up(idx)
                        st.experimental_rerun()
                with bcol2:
                    if st.button("⬇️ Down", key=f"down_{idx}"):
                        move_down(idx)
                        st.experimental_rerun()
                with bcol3:
                    if st.button("🗑 Remove", key=f"remove_{idx}"):
                        remove_from_test(idx)
                        st.experimental_rerun()

    st.markdown("---")
    st.subheader("Export")

    test_md = make_test_markdown()
    key_md = make_key_markdown()

    st.download_button(
        "Download Test (.md)",
        data=test_md,
        file_name="test.md",
        mime="text/markdown",
    )

    st.download_button(
        "Download Answer Key (.md)",
        data=key_md,
        file_name="answer_key.md",
        mime="text/markdown",
    )
