import json
import random
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
                st.error("questions.json must contain a list of questions (a JSON array).")
                return []
            return data
    except Exception as e:
        st.error(f"Error loading questions.json: {e}")
        return []


QUESTIONS = load_questions(Path("questions.json"))
Q_BY_ID = {q["id"]: q for q in QUESTIONS}


# ---------- Session state ----------
# Each test entry is an "instance": {"qid": <id>, "variant": <int or None>}
if "instances" not in st.session_state:
    st.session_state["instances"] = []

instances = st.session_state["instances"]


# ---------- Helper functions ----------
def get_question_topics(q):
    """Return a list of topic strings for a question."""
    if "topics" in q and isinstance(q["topics"], list):
        return q["topics"]
    t = q.get("topic")
    return [t] if t else []


def get_label_topic(q):
    """One-line label for the topic for list displays."""
    if "topic" in q and q["topic"]:
        return q["topic"]
    topics = get_question_topics(q)
    return topics[0] if topics else "Untitled"


def question_matches_filters(q, course_filter, static_filter, qtype_filter, topic_filter, search_text):
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

    # Topics – only filter if some topics are selected
    q_topics = get_question_topics(q)
    if topic_filter and not any(t in topic_filter for t in q_topics):
        return False

    # Search text
    if search_text.strip():
        s = search_text.lower()
        if s not in q.get("text", "").lower():
            return False

    return True


def filtered_questions(course_filter, static_filter, qtype_filter, topic_filter, search_text):
    if not QUESTIONS:
        return []
    return [
        q
        for q in QUESTIONS
        if question_matches_filters(q, course_filter, static_filter, qtype_filter, topic_filter, search_text)
    ]


def add_to_test(ids_to_add):
    """
    Add one instance per qid, allowing duplicates.

    For non-static questions with variants, pick a variant each time.
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


def move_up(index: int):
    if index <= 0 or index >= len(instances):
        return
    instances[index - 1], instances[index] = instances[index], instances[index - 1]


def move_down(index: int):
    if index < 0 or index >= len(instances) - 1:
        return
    instances[index + 1], instances[index] = instances[index], instances[index + 1]


def remove_from_test(index: int):
    if 0 <= index < len(instances):
        instances.pop(index)


def regenerate_variant(index: int):
    """Pick a new variant for the given instance, if possible."""
    if index < 0 or index >= len(instances):
        return
    inst_obj = instances[index]
    base = Q_BY_ID.get(inst_obj["qid"])
    if not base or base.get("static", True):
        return
    variants = base.get("variants", [])
    if not variants:
        return
    current = inst_obj.get("variant")
    choices = [i for i in range(len(variants)) if i != current] or list(range(len(variants)))
    inst_obj["variant"] = random.choice(choices)


def get_instance_question(inst_obj):
    """Return the concrete question (with variant applied if needed)."""
    qid = inst_obj["qid"]
    base = Q_BY_ID.get(qid)
    if not base:
        return None

    variant_idx = inst_obj.get("variant", None)
    variants = base.get("variants", [])

    if variant_idx is None or base.get("static", True) or not variants:
        # Static or no variants: use base question
        return base

    # Use chosen variant, overriding text/solution
    variant = variants[variant_idx]
    q = dict(base)  # shallow copy metadata
    q["text"] = variant.get("text", base.get("text", ""))
    q["solution"] = variant.get("solution", base.get("solution", ""))
    return q


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


# ---------- UI Layout ----------
st.title("TestGen Lite – Question Picker + Answer Key")

if not QUESTIONS:
    st.stop()

# ----- Sidebar filters -----
st.sidebar.title("Filters")

# Courses
all_courses = sorted({c for q in QUESTIONS for c in q.get("courses", [])})
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
all_qtypes = sorted({qt for q in QUESTIONS for qt in q.get("qtypes", [])})
qtype_filter = st.sidebar.multiselect(
    "Question type",
    options=all_qtypes,
    default=all_qtypes if all_qtypes else [],
)

# Topics – unselected by default
all_topics = sorted({t for q in QUESTIONS for t in get_question_topics(q)})
topic_filter = st.sidebar.multiselect(
    "Topics",
    options=all_topics,
    default=[],  # no topics selected initially
)

# Text search
search_text = st.sidebar.text_input("Search in question text", value="")

# ----- Main columns -----
col_bank, col_test = st.columns(2)

# =======================
# Left column: Question Bank
# =======================
with col_bank:
    st.subheader("Question Bank")

    bank_qs = filtered_questions(
        course_filter, static_filter, qtype_filter, topic_filter, search_text
    )

    if not bank_qs:
        st.write("No questions match the current filter.")
    else:
        options = [f"{q['id']} – {get_label_topic(q)}" for q in bank_qs]
        id_by_label = {f"{q['id']} – {get_label_topic(q)}": q["id"] for q in bank_qs}

        selected_labels = st.multiselect(
            "Select questions to add",
            options=options,
            key="bank_multiselect",
        )

        if st.button("Add selected to test"):
            ids_to_add = [id_by_label[label] for label in selected_labels]
            add_to_test(ids_to_add)
            st.rerun()

        # Preview from bank
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
                    st.markdown(f"**Courses:** {', '.join(base.get('courses', [])) or '—'}")
                    st.markdown(f"**Types:** {', '.join(base.get('qtypes', [])) or '—'}")
                    st.markdown(f"**Topics:** {', '.join(get_question_topics(base)) or '—'}")
                    st.markdown(
                        f"**Static / Non-static:** "
                        f"{'Static' if is_static else 'Non-static (algorithmic)'}"
                    )

                    # Example question + solution
                    if is_static or base.get("text"):
                        st.markdown("**Question:**")
                        st.markdown(base.get("text", ""))
                        st.markdown("**Solution:**")
                        st.markdown(base.get("solution", ""))
                    else:
                        # Non-static with only variants: preview the first one
                        if variants:
                            example = variants[0]
                            st.markdown("**Question (example variant):**")
                            st.markdown(example.get("text", ""))

                            st.markdown("**Solution (one possible):**")
                            st.markdown(example.get("solution", ""))
                        else:
                            st.write("No text or variants defined for this question.")

                    # Add this single question directly from preview
                    if st.button("Add this question to test", key=f"add_single_{qid}"):
                        add_to_test([qid])
                        st.rerun()


# =======================
# Right column: Current Test
# =======================
with col_test:
    st.subheader("Current Test")

    if not instances:
        st.write("No questions selected yet.")
    else:
        for idx, inst_obj in enumerate(instances):
            inst_q = get_instance_question(inst_obj)
            if not inst_q:
                continue

            with st.container():
                label_topic = get_label_topic(inst_q)
                is_static = inst_q.get("static", True)

                # Number by position in test: 1., 2., 3., ...
                st.markdown(f"**{idx + 1}. {label_topic}**")
                st.caption("Static" if is_static else "Non-static (algorithmic)")
                st.markdown(inst_q.get("text", ""))

                # Controls
                bcol1, bcol2, bcol3, bcol4 = st.columns(4)
                with bcol1:
                    if st.button("⬆️ Up", key=f"up_{idx}"):
                        move_up(idx)
                        st.rerun()
                with bcol2:
                    if st.button("⬇️ Down", key=f"down_{idx}"):
                        move_down(idx)
                        st.rerun()
                with bcol3:
                    if st.button("🗑 Remove", key=f"remove_{idx}"):
                        remove_from_test(idx)
                        st.rerun()
                with bcol4:
                    if not is_static:
                        if st.button("♻️ Regenerate", key=f"regen_{idx}"):
                            regenerate_variant(idx)
                            st.rerun()

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
