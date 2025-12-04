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
                st.error("questions.json must contain a list of questions.")
                return []
            return data
    except Exception as e:
        st.error(f"Error loading questions.json: {e}")
        return []


QUESTIONS = load_questions(Path("questions.json"))
Q_BY_ID = {q["id"]: q for q in QUESTIONS}

# ---------- Session state ----------
# Each selected item is an *instance* id, e.g. "M2760_TRIG_001#3"
if "selected_instances" not in st.session_state:
    st.session_state["selected_instances"] = []

# Map instance_id -> chosen variant index (for non-static questions)
if "selected_variants" not in st.session_state:
    st.session_state["selected_variants"] = {}

# Counter used to make unique instance ids
if "instance_counter" not in st.session_state:
    st.session_state["instance_counter"] = 0

selected_instances = st.session_state["selected_instances"]
selected_variants = st.session_state["selected_variants"]

# ---------- Helper: topics ----------
def get_question_topics(q):
    # Prefer list in "topics"; fall back to single "topic"
    if "topics" in q and isinstance(q["topics"], list):
        return q["topics"]
    t = q.get("topic")
    return [t] if t else []


def get_label_topic(q):
    # For display in lists
    if "topic" in q and q["topic"]:
        return q["topic"]
    topics = get_question_topics(q)
    return topics[0] if topics else "Untitled"


# ---------- Filters in sidebar ----------
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
        default=all_courses if all_courses else []
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
        default=all_qtypes if all_qtypes else []
    )

    # Topics – **unselected by default** (means “no topic filter”)
    all_topics = sorted(
        {t for q in QUESTIONS for t in get_question_topics(q)}
    )
    topic_filter = st.sidebar.multiselect(
        "Topics",
        options=all_topics,
        default=[],   # <- nothing selected by default
    )

    # Text search
    search_text = st.sidebar.text_input("Search in question text", value="")


# ---------- Helper functions ----------
def question_matches_filters(q):
    # Courses
    q_courses = q.get("courses", [])
    if course_filter and not any(c in course_filter for c in q_courses):
        return False

    # Static / non-static
    is_static = q.get("static", True)
    if "Static" not in static_filter and is_static:
        return False
    if "Non-static" not in static_filter and not is_static:
        return False

    # Question types
    q_qtypes = q.get("qtypes", [])
    if qtype_filter and not any(t in qtype_filter for t in q_qtypes):
        return False

    # Topics – only filter if user picked something
    q_topics = get_question_topics(q)
    if topic_filter and not any(t in topic_filter for t in q_topics):
        return False

    # Search text
    if search_text.strip():
        s = search_text.lower()
        if s not in q.get("text", "").lower():
            return False

    return True


def filtered_questions():
    if not QUESTIONS:
        return []
    return [q for q in QUESTIONS if question_matches_filters(q)]


def add_to_test(ids_to_add):
    """Add one *instance* per qid. Duplicates are allowed."""
    for qid in ids_to_add:
        if qid not in Q_BY_ID:
            continue
        # Create unique instance id
        inst_id_num = st.session_state["instance_counter"]
        instance_id = f"{qid}#{inst_id_num}"
        st.session_state["instance_counter"] += 1

        st.session_state["selected_instances"].append(instance_id)

        # If question is non-static with variants, choose one variant index
        q = Q_BY_ID[qid]
        if not q.get("static", True) and "variants" in q:
            variants = q["variants"]
            if isinstance(variants, list) and variants:
                idx = random.randrange(len(variants))
                st.session_state["selected_variants"][instance_id] = idx


def move_up(index):
    if index <= 0 or index >= len(st.session_state["selected_instances"]):
        return
    instances = st.session_state["selected_instances"]
    instances[index - 1], instances[index] = instances[index], instances[index - 1]


def move_down(index):
    if index < 0 or index >= len(st.session_state["selected_instances"]) - 1:
        return
    instances = st.session_state["selected_instances"]
    instances[index + 1], instances[index] = instances[index], instances[index + 1]


def remove_from_test(index):
    instances = st.session_state["selected_instances"]
    if 0 <= index < len(instances):
        instance_id = instances[index]
        instances.pop(index)
        # Remove any stored variant choice
        if instance_id in st.session_state["selected_variants"]:
            del st.session_state["selected_variants"][instance_id]


def get_instance(instance_id):
    """Return the 'instance' of a question (with variant applied if needed)."""
    # instance_id looks like "QID#3"
    qid = instance_id.split("#", 1)[0]
    q = Q_BY_ID.get(qid)
    if not q:
        return None

    is_static = q.get("static", True)
    if is_static or "variants" not in q:
        return q

    variants = q.get("variants", [])
    if not variants:
        return q

    idx = st.session_state["selected_variants"].get(instance_id, 0)
    idx = max(0, min(idx, len(variants) - 1))
    variant = variants[idx]

    # Shallow copy base metadata but override text/solution
    inst = dict(q)
    inst["text"] = variant.get("text", q.get("text", ""))
    inst["solution"] = variant.get("solution", q.get("solution", ""))
    return inst


def make_test_markdown():
    lines = ["# Test", ""]
    for i, instance_id in enumerate(st.session_state["selected_instances"], start=1):
        inst = get_instance(instance_id)
        if not inst:
            continue
        lines.append(f"{i}. {inst.get('text', '')}")
        lines.append("")
    return "\n".join(lines)


def make_key_markdown():
    lines = ["# Answer Key", ""]
    for i, instance_id in enumerate(st.session_state["selected_instances"], start=1):
        inst = get_instance(instance_id)
        if not inst:
            continue
        lines.append(f"{i}. {inst.get('text', '')}")
        lines.append("")
        lines.append(f"**Solution:** {inst.get('solution', '')}")
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
                    f\"{'Static' if is_static else 'Non-static (algorithmic)'}\"
                )

                # Show an example question/solution
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

                # Optional: list all variant prompts for instructors
                if not is_static and variants:
                    st.markdown("**All variants (questions only):**")
                    for v in variants:
                        st.markdown("- " + v.get("text", ""))

# ----- Right column: current test -----
with col_test:
    st.subheader("Current Test")

    if not selected_instances:
        st.write("No questions selected yet.")
    else:
        for idx, instance_id in enumerate(selected_instances):
            inst = get_instance(instance_id)
            if not inst:
                continue
            with st.container():
                label_topic = get_label_topic(inst)
                # Numbering is just 1., 2., 3., ...; no points shown
                st.markdown(
                    f"**{idx + 1}. {label_topic}**"
                )
                st.markdown(inst.get("text", ""))

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
