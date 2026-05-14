import frappe


@frappe.whitelist()
def get_student_program_and_courses():
    """
    Returns data for the logged-in student, including:
    {
        "student": "STU-0001",
        "student_name": "Jane Doe",
        "program": "PROG-IT-DIP",
        "program_name": "Diploma in Information Technology",
        "academic_year": "2025",
        "academic_term": "Semester 1",
        "courses": [
            {"course": "IT-101", "course_name": "Intro to IT"},
            ...
        ]
    }
    """
    user = frappe.session.user
    if not user or user == "Guest":
        return {}

    # --- 1. FIND THE STUDENT RECORD LINKED TO THIS USER ---
    student = _get_student_for_user(user)
    if not student:
        return {}

    student_doc = frappe.get_doc("Student", student)

    # --- 2. FIND PROGRAM FOR THIS STUDENT ---
    program, program_name = _get_program_for_student(student_doc)

    # --- 3. GET DEFAULT ACADEMIC YEAR / TERM ---
    academic_year, academic_term = _get_default_year_and_term()

    # --- 4. GET COURSES FOR PROGRAM + TERM ---
    courses = []
    if program and academic_term:
        courses = _get_program_courses(program, academic_term)

    return {
        "student": student_doc.name,
        "student_name": (
            student_doc.student_name
            or getattr(student_doc, "title", "")
            or getattr(student_doc, "first_name", "")
        ),
        "program": program,
        "program_name": program_name,
        "academic_year": academic_year,
        "academic_term": academic_term,
        "courses": courses,
    }


def _get_student_for_user(user):
    """
    Try different ways to match logged-in user → Student.
    Adjust if your Student doctype uses slightly different fieldnames.
    """
    student_meta = frappe.get_meta("Student")
    candidate_filters = []

    # 1) match by email
    if student_meta.has_field("student_email_id"):
        candidate_filters.append({"student_email_id": user})

    # 2) match by linked user
    if student_meta.has_field("user"):
        candidate_filters.append({"user": user})
    if student_meta.has_field("user_id"):
        candidate_filters.append({"user_id": user})

    # 3) match by student_id (e.g. S12025…)
    if student_meta.has_field("student_id"):
        candidate_filters.append({"student_id": user})

    # 4) finally, name == user
    candidate_filters.append({"name": user})

    for f in candidate_filters:
        name_list = frappe.get_all("Student", filters=f, pluck="name", limit=1)
        if name_list:
            return name_list[0]

    return None


def _get_program_for_student(student_doc):
    """
    Priority:
    1) Latest Program Enrollment for this student
    2) student.program field (if exists)
    3) Student Applicant linked by email or student_id (if you used that)
    """

    # 1) latest Program Enrollment
    enrollments = frappe.get_all(
        "Program Enrollment",
        filters={"student": student_doc.name, "docstatus": ["<", 2]},
        fields=["program"],
        order_by="creation desc",
        limit=1,
    )
    if enrollments:
        prog = enrollments[0].get("program")
        prog_name = frappe.db.get_value("Program", prog, "program_name") if prog else ""
        return prog, prog_name

    # 2) student.program if exists
    if hasattr(student_doc, "program") and student_doc.program:
        prog = student_doc.program
        prog_name = frappe.db.get_value("Program", prog, "program_name") or ""
        return prog, prog_name

    # 3) Student Applicant (optional)
    student_email = getattr(student_doc, "student_email_id", None)
    student_id = getattr(student_doc, "student_id", None)

    applicant_filters = []
    if student_email:
        applicant_filters.append({"email_id": student_email})
    if student_id:
        applicant_filters.append({"student_id": student_id})

    for f in applicant_filters:
        apps = frappe.get_all(
            "Student Applicant",
            filters=f,
            fields=["name", "program"],
            order_by="creation desc",
            limit=1,
        )
        if apps:
            prog = apps[0].get("program")
            prog_name = frappe.db.get_value("Program", prog, "program_name") or ""
            return prog, prog_name

    return None, ""


def _get_default_year_and_term():
    """
    Simple default using Education Settings.
    You can change this later to a custom TTI Settings if you want.
    """
    year = (
        frappe.db.get_single_value("Education Settings", "current_academic_year") or ""
    )
    term = (
        frappe.db.get_single_value("Education Settings", "current_academic_term") or ""
    )

    return year, term


def _get_program_courses(program, academic_term=None):
    """
    INTERNAL helper: uses your Program Course child table.

    Assumptions:
    - Parent doctype: Program
    - Child doctype: Program Course
    - Child table fields:
        - course (Link → Course)
        - course_name (Data)
        - academic_term (Select or Link)
        - parent, parenttype, parentfield (standard child table fields)
    """
    if not program:
        return []

    filters = {
        "parent": program,
        "parenttype": "Program",
    }
    # if you know the parentfield name (e.g. "courses"), you can also add:
    # filters["parentfield"] = "courses"

    if academic_term:
        # because you confirmed you DO have academic_term field
        filters["academic_term"] = academic_term

    rows = frappe.get_all(
        "Program Course",
        filters=filters,
        fields=["course", "course_name"],
        order_by="idx asc",
    )

    courses = []
    for r in rows:
        courses.append(
            {
                "course": r.get("course"),
                "course_name": r.get("course_name"),
            }
        )

    return courses


@frappe.whitelist()
def get_program_courses(program, academic_term=None):
    """
    Public whitelisted wrapper to use from JS.
    """
    if not program:
        return []
    return _get_program_courses(program, academic_term)
