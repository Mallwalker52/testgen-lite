import json
import random
from pathlib import Path

import streamlit as st

# =========================================================
# Load question bank
# =========================================================

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

# =========================================================
# Session state
# =========================================================
# Each element of "instances" is a dict:
#   {"qid": <question id>, "variant": <int or None>}
# so the same question can appear multiple times with different variants.
if "instances" not in st.session_state:
    st.session_state["instances"] = []

instances = st.session_state["instances"]

# =========================================================
# Helper functions for metadata / topics
# =========================================================

def get_question_topics(q):
    """Return list of topics for a question."""
    if "topics" in q and isinstance(q["topics"], list):
        return q["topics"]
    t = q.get("topic")
    return [t] if t else []


def get_label_topic(q):
    """Single label for display (first topic or 'Untitled')."""
    if "topic" in q and q["topic"]:
        return q["topic"]
    topics = get_question_topics(q)
    return topics[0] if topics else "Untitled"


# =========================================================
# Sidebar filters
# =========================================================

st.sidebar.title("TestGen Lite (Web)")

if not QUESTIONS:
    st.sidebar.write("Add a questions.json file and refresh.")
else:
    # Courses
    all_courses = sorted(
        {c for q in QUESTIONS for c in q.get("courses", [])}
    )
    course_filter = st.sidebar.multiselect(
        "Course",
        options=all_courses,
        default=all_courses if all_courses else [],
    )

    # Static / Non-static
    static_options = ["Static", "Non-static"]
    static_filter = st.sidebar.multiselect(
        "Static / Non-static",
        options=static_options,
        default=static_options,
    )

    # Question types
    all_qtypes = sorted(
        {qt for q in QUESTIONS for qt in q.get("qtypes", [])}
    )
    qtype_filter = st.sidebar.multiselect(
        "Question type",
        options=all_qtypes,
        default=all_qtypes if all_qtypes else [],
    )

    # Topics – unselected by default, but if empty we don't filter by topic
    all_topics = sorted(
        {t for q in QUESTIONS for t in get_question_topics(q)}
    )
    topic_filter = st.sidebar.multiselect(
        "Topics",
        options=all_topics,
        default=[],   # nothing selected initially
    )

    # Text search
    search_text = st.sidebar.text_input("Search in question text", value="")

# =========================================================
# Filtering logic
# =========================================================

def question_matches_filters(q):
    # Courses
    q_courses = q.get("courses", [])
    if course_filter and not any(c in course_filter for c in q_courses):
        return False

    # Static / Non-static
    is_static = q.get("static", True)
    if "Static" not in static_filter and is_static:
        return False
    if "Non-static" not in static_filter and not is_static:
        return False

    # Question types
    q_qtypes = q.get("qtypes", [])
    if qtype_filter and not any(t in qtype_filter for t in q_qtypes):
        return False

    # Topics
    q_topics = get_question_topics(q)
    # If topic_filter is empty, don't restrict by topic
    if topic_filter and not any(t in topic_filter for t in q_topics):
        return False

    # Text search
    if search_text.strip():
        s = search_text.lower()
        if s not in q.get("text", "").lower():
            return False

    return True


def filtered_questions():
    if not QUESTIONS:
        return []
    return [q for q in QUESTIONS if question_matches_filters(q)]

# =========================================================
# Manipulating instances (questions in the current test)
# =========================================================

def add_to_test(ids_to_add):
    """Add one instance per qid (allowing duplicates).

    For non-static questions with variants, choose a variant index
    each time the question is added.
    """
    for qid in ids_to_add:
        q = Q_BY_ID.get(qid)
        if not q:
            continue

        variant_idx = None
        if not q.get("static", True) and "variants" in q:
            variants = q.get("variants", [])
            if isinstance(variants, list) and variants:
                variant_idx = random.randrange(len(variants))

        instances.append({"qid": qid, "variant": variant_idx})


def move_up(index):
    if index <= 0 or index >= len(instances):
        return
    instances[index - 1], instances[index] = instances[index], instances[index - 1]


def move_down(index):
    if index < 0 or index >= len(instances) - 1:
        return
    instances[index + 1], instances[index] = instances[index], instances[index + 1]


def remove_from_test(index):
    if 0 <= index < len(instances):
        instances.pop(index)


def get_instance_question(inst_obj):
    """Return the concrete question (with variant applied if needed)."""
    qid = inst_obj["qid"]
    base = Q_BY_ID.get(qid)
    if not base:
        return None

    variant_idx = inst_obj.get("variant", None)
    variants = base.get("variants", [])

    if variant_idx is None or base.get("static", True) or not variants:
        # Static or no variants: just use base
        return base

    # Non-static with variants: override text/solution with chosen variant
    variant = variants[variant_idx]
    q = dict(base)  # shallow copy metadata
    q["text"] = variant.get("text", base.get("text", ""))
    q["solution"] = variant.get("solution", base.get("solution", ""))
    return q

# =========================================================
# Markdown export
# =========================================================

def make_test_markdown():
    lines = ["# Test", ""]
    for i, inst_obj in enumerate(instances, start=1):
        inst_q = get_instance_question(inst_obj)
        if not inst_q:
            continue
        lines.append(f"{i}. {inst_q.get('text', '')}")
        lines.append("")
    return "\n".join(lines)


def make_key_markdown():
    lines = ["# Answer Key", ""]
    for i, inst_obj in enumerate(instances, start=1):
        inst_q = get_instance_question(inst_obj)
        if not inst_q:
            continue
        lines.append(f"{i}. {inst_q.get('text', '')}")
        lines.append("")
        lines.append(f"**Solution:** {inst_q.get('solution', '')}")
        lines.append("")
    return "\n".join(lines)

# =========================================================
# Layout
# =========================================================

st.title("TestGen Lite – Question Picker + Answer Key")

if not QUESTIONS:
    st.stop()

col_bank, col_test = st.columns(2)

# ---------------------------------------------------------
# Left column: Question bank + preview
# ---------------------------------------------------------
with col_bank:
    st.subheader("Question Bank")

    bank_qs = filtered_questions()
    if not bank_qs:
        st.write("No questions match the current filter.")
    else:
        options = [
            f"{q['id']} – {get_label_topic(q)}"
            for q in bank_qs
        ]
        id_by_label = {
            f"{q['id']} – {get_label_topic(q)}": q["id"]
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

        # Preview block stays right here in the left column
        with st.expander("Preview from bank"):
            preview_label = st.selectbox(
                "Choose a question to preview",
                options=["(none)"] + options,
                key="bank_preview_select",
            )
            if preview_label != "(none)":
                qid = id_by_label[preview_label]
                base = Q_BY_ID.get(qid)
                if base:
                    is_static = base.get("static", True)
                    variants = base.get("variants", [])

                    st.markdown(f"**ID:** {base['id']}")
                    st.markdown(
                        f"**Courses:** "
                        f"{', '.join(base.get('courses', [])) or '—'}"
                    )
                    st.markdown(
                        f"**Types:** "
                        f"{', '.join(base.get('qtypes', [])) or '—'}"
                    )
                    st.markdown(
                        f"**Topics:** "
                        f"{', '.join(get_question_topics(base)) or '—'}"
                    )
                    st.markdown(
                        f"**Static / Non-static:** "
                        f"{'Static' if is_static else 'Non-static (algorithmic)'}"
                    )

                    # Show an example question + solution:
                    #   - static: use top-level text/solution
                    #   - non-static with no top-level text: show the first variant
                    if is_static or base.get("text"):
                        st.markdown("**Question:**")
                        st.markdown(base.get("text", ""))
                        st.markdown("**Solution:**")
                        st.markdown(base.get("solution", ""))
                    else:
                        if variants:
                            example = variants[0]
                            st.markdown("**Question (example variant):**")
                            st.markdown(example.get("text", ""))
                            st.markdown("**Solution (one possible):**")
                            st.markdown(example.get("solution", ""))
                        else:
                            st.write("No text or variants defined for this question.")

# ---------------------------------------------------------
# Right column: Current test + export
# ---------------------------------------------------------
with col_test:
    st.subheader("Current Test")

    if not instances:
        st.write("No questions selected yet.")
    else:
        for idx, inst_obj in enumerate(instances, start=0):
            inst_q = get_instance_question(inst_obj)
            if not inst_q:
                continue
            with st.container():
                label_topic = get_label_topic(inst_q)
                # Number by position in test: 1., 2., 3., ...
                st.markdown(f"**{idx + 1}. {label_topic}**")
                st.markdown(inst_q.get("text", ""))

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
