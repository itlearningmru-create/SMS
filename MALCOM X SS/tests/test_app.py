import re
from io import BytesIO
from datetime import datetime

import pytest

from app import create_app, seed_sample_data
from app.grading import cbc_grade, is_lower_secondary_class
from app.school_profile import SCHOOL_PROFILE, register_school_profile


def test_cbc_grade_boundaries_and_lower_secondary_scope():
    assert cbc_grade(100) == ("A", "Exceptional")
    assert cbc_grade(80) == ("A", "Exceptional")
    assert cbc_grade(79.99) == ("B", "Outstanding")
    assert cbc_grade(70) == ("B", "Outstanding")
    assert cbc_grade(60) == ("C", "Satisfactory")
    assert cbc_grade(50) == ("D", "Basic")
    assert cbc_grade(0) == ("E", "Elementary")
    assert cbc_grade(49.99) == ("E", "Elementary")
    assert all(is_lower_secondary_class(f"S{level}") for level in range(1, 5))
    assert all(
        is_lower_secondary_class(f"Senior {level}")
        for level in range(1, 5)
    )
    assert not is_lower_secondary_class("S5")


def test_login_page_loads():
    app = create_app(test_config=True)
    client = app.test_client()
    response = client.get("/login")
    assert response.status_code == 200
    assert b"MX-SMS" in response.data
    assert b"Demo credentials" not in response.data
    assert b"admin123" not in response.data
    assert b"Malcolm X Secondary School badge" in response.data

    badge = client.get("/static/images/school-badge.png")
    assert badge.status_code == 200
    assert badge.mimetype == "image/png"


def test_dashboard_requires_login():
    app = create_app(test_config=True)
    client = app.test_client()
    response = client.get("/dashboard")
    assert response.status_code == 302


def test_admin_can_login():
    app = create_app(test_config=True)
    client = app.test_client()
    response = client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"School Overview" in response.data
    assert b"MALCOLM X SECONDARY SCHOOL KATWE" in response.data


def test_create_admin_cli():
    app = create_app(test_config=True)
    runner = app.test_cli_runner()
    result = runner.invoke(
        args=["create-admin"],
        input="secure_admin\nadmin@example.com\nAlex\nAdmin\nStrongPassword!2026\nStrongPassword!2026\n",
    )

    assert result.exit_code == 0
    with app.app_context():
        from app.models import User

        user = User.query.filter_by(username="secure_admin").one()
        assert user.email == "admin@example.com"
        assert user.check_password("StrongPassword!2026")


def test_student_must_change_temporary_password_and_cannot_view_staff_pages():
    app = create_app(test_config=True)
    with app.app_context():
        from app.extensions import db
        from app.models import Student, StudentAccount

        student = Student(
            student_no="MX-2026-020",
            first_name="Student",
            last_name="Example",
            dob=datetime(2010, 1, 1),
            entry_class="Senior 2",
            status="Applied",
        )
        account = StudentAccount(student=student)
        account.set_password("TemporaryStudentPassword")
        db.session.add(student)
        db.session.add(account)
        db.session.commit()

    client = app.test_client()
    login_page = client.get("/login")
    response = client.post(
        "/login",
        data={
            "username": "MX-2026-020",
            "password": "TemporaryStudentPassword",
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/student-portal/change-password")
    assert client.get("/students").headers["Location"].endswith("/student-portal")

    change_page = client.get("/student-portal/change-password")
    response = client.post(
        "/student-portal/change-password",
        data={
            "current_password": "TemporaryStudentPassword",
            "new_password": "NewStudentPassword!2026",
            "confirm_password": "NewStudentPassword!2026",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Welcome, Student Example" in response.data
    assert b"School administration" not in response.data

    response = client.get("/students", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/student-portal")


def test_create_student_logins_for_all_admission_statuses():
    app = create_app(test_config=True)
    with app.app_context():
        from app.extensions import db
        from app.models import Student, StudentAccount

        db.session.add_all(
            [
                Student(
                    student_no="MX-2026-021",
                    first_name="Applicant",
                    last_name="One",
                    dob=datetime(2010, 1, 1),
                    status="Applied",
                ),
                Student(
                    student_no="MX-2026-022",
                    first_name="Applicant",
                    last_name="Two",
                    dob=datetime(2010, 1, 1),
                    status="Rejected",
                ),
            ]
        )
        db.session.commit()

    result = app.test_cli_runner().invoke(args=["create-student-logins"])
    assert result.exit_code == 0
    assert "MX-2026-021" in result.output
    assert "MX-2026-022" in result.output
    with app.app_context():
        from app.models import StudentAccount

        accounts = StudentAccount.query.join(StudentAccount.student).filter(
            StudentAccount.student.has(
                Student.student_no.in_(["MX-2026-021", "MX-2026-022"])
            )
        ).all()
        assert len(accounts) == 2
        assert all(
            account.must_change_password
            for account in accounts
        )


def test_creating_student_provisions_portal_login():
    app = create_app(test_config=True)
    client = app.test_client()
    client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
    )

    response = client.post(
        "/students/new",
        data={
            "student_no": "MX-2026-023",
            "first_name": "New",
            "last_name": "Student",
            "gender": "Other",
            "dob": "2010-01-01",
            "nationality": "Ugandan",
            "class_room_id": "1",
            "status": "Applied",
            "email": "",
            "phone": "",
            "notes": "",
            "passport_photo": (
                BytesIO(b"\x89PNG\r\n\x1a\nsample image content"),
                "student.png",
            ),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Student portal username: MX-2026-023" in response.data
    match = re.search(
        rb"One-time temporary password: ([A-Za-z0-9_-]+)",
        response.data,
    )
    assert match

    from app.extensions import db
    from app.models import Student, StudentAccount

    with app.app_context():
        student = Student.query.filter_by(student_no="MX-2026-023").one()
        account = StudentAccount.query.filter_by(student_id=student.id).one()
        assert account.must_change_password
        assert account.check_password(match.group(1).decode())
        assert student.passport_photo.startswith("students/")
        student_id = student.id

    photo_response = client.get(
        f"/students/{student_id}/passport-photo"
    )
    assert photo_response.status_code == 200
    assert photo_response.data.startswith(b"\x89PNG\r\n\x1a\n")
    assert app.test_client().get(
        f"/students/{student_id}/passport-photo"
    ).status_code == 302

    student_client = app.test_client()
    response = student_client.post(
        "/login",
        data={
            "username": "MX-2026-023",
            "password": match.group(1).decode(),
        },
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/student-portal/change-password")
    assert (
        student_client.get(
            f"/students/{student_id}/passport-photo"
        ).status_code
        == 200
    )


def test_teacher_accounts_scope_marks_and_allow_dos_report_cards():
    app = create_app(test_config=True)
    admin = app.test_client()
    admin.post("/login", data={"username": "admin", "password": "admin123"})

    response = admin.post(
        "/accounts/teachers/new",
        data={
            "first_name": "Tina",
            "last_name": "Teacher",
            "department": "Science",
            "phone": "",
        },
    )
    credentials = re.search(
        rb"<code>([^<]+)</code></td><td><code>([^<]+)</code>",
        response.data,
    )
    assert credentials
    username, temporary_password = (
        value.decode() for value in credentials.groups()
    )

    from app.extensions import db
    from app.models import (
        Assessment,
        ClassRoom,
        ExamResult,
        Student,
        StudentClassPlacement,
        Subject,
        Teacher,
        TeachingAssignment,
        User,
        UserPasswordPolicy,
    )

    with app.app_context():
        teacher = Teacher.query.filter_by(full_name="Tina Teacher").one()
        assigned_room = ClassRoom.query.filter_by(
            name="S2", stream="A"
        ).one()
        other_room = ClassRoom.query.filter_by(
            name="S4", stream=""
        ).one()
        subject = Subject.query.filter_by(code="MATH").one()
        assessment = Assessment.query.first()
        formative_assessment = Assessment(
            name="Continuous Assessment",
            academic_year_id=assessment.academic_year_id,
            term=assessment.term,
            component="Formative",
            max_marks=50,
            status="Open",
        )
        db.session.add(formative_assessment)
        db.session.flush()
        activity_assessment = Assessment(
            name="Activity of Integration",
            academic_year_id=assessment.academic_year_id,
            term=assessment.term,
            component="Formative",
            max_marks=100,
            status="Open",
        )
        db.session.add(activity_assessment)
        db.session.flush()
        enrolled_student = Student.query.filter_by(
            student_no="MX-DEMO-BASE-001"
        ).one()
        other_student = Student(
            student_no="MX-2025-003",
            first_name="Enrolled",
            last_name="Elsewhere",
            dob=datetime(2010, 2, 1),
            entry_class=other_room.name,
            status="Enrolled",
        )
        db.session.add(other_student)
        db.session.flush()
        db.session.add(
            StudentClassPlacement(
                student_id=enrolled_student.id,
                class_room_id=assigned_room.id,
            )
        )
        db.session.add(
            StudentClassPlacement(
                student_id=other_student.id,
                class_room_id=other_room.id,
            )
        )
        second_assignment = TeachingAssignment(
            teacher_id=Teacher.query.filter_by(
                full_name="Demo Teacher Base"
            ).one().id,
            subject_id=subject.id,
            class_room_id=other_room.id,
        )
        db.session.add(second_assignment)
        db.session.commit()
        ids = (
            teacher.id,
            assigned_room.id,
            subject.id,
            assessment.id,
            enrolled_student.id,
            other_student.id,
            second_assignment.id,
            formative_assessment.id,
            activity_assessment.id,
        )
        policy = db.session.get(UserPasswordPolicy, teacher.user_id)
        assert policy.must_change_password

    response = admin.post(
        "/assignments/new",
        data={
            "teacher_id": ids[0],
            "subject_id": ids[2],
            "class_room_id": ids[1],
        },
    )
    assert response.status_code == 302
    with app.app_context():
        assignment_id = TeachingAssignment.query.filter_by(
            teacher_id=ids[0],
            subject_id=ids[2],
            class_room_id=ids[1],
        ).one().id

    teacher_client = app.test_client()
    response = teacher_client.post(
        "/login",
        data={"username": username, "password": temporary_password},
    )
    assert response.headers["Location"].endswith("/change-password")
    response = teacher_client.post(
        "/change-password",
        data={
            "current_password": temporary_password,
            "new_password": "TeacherSafePassword2026",
            "confirm_password": "TeacherSafePassword2026",
        },
    )
    assert response.headers["Location"].endswith("/my-teaching")
    assert b"Mathematics" in teacher_client.get("/my-teaching").data
    assert teacher_client.get("/assignments").status_code == 403
    assert (
        teacher_client.get(
            f"/assignments/{ids[6]}/marks"
        ).status_code
        == 403
    )

    response = teacher_client.post(
        f"/assignments/{assignment_id}/marks",
        data={
            "student_id": ids[4],
            "assessment_id": ids[3],
            "score": "88",
            "remarks": "Good progress",
        },
    )
    assert response.status_code == 302
    response = teacher_client.post(
        f"/assignments/{assignment_id}/marks",
        data={
            "student_id": ids[4],
            "assessment_id": ids[3],
            "score": "101",
            "remarks": "",
        },
    )
    assert response.status_code == 200
    response = teacher_client.post(
        f"/assignments/{assignment_id}/marks",
        data={
            "student_id": ids[5],
            "assessment_id": ids[3],
            "score": "75",
            "remarks": "",
        },
    )
    assert response.status_code == 200
    assert teacher_client.get("/results").status_code == 403

    partial_report = admin.get(f"/report-cards/{ids[4]}/{ids[3]}")
    assert b"Incomplete CA Record" in partial_report.data

    response = teacher_client.post(
        f"/assignments/{assignment_id}/marks",
        data={
            "student_id": ids[4],
            "assessment_id": ids[8],
            "score": "80",
            "remarks": "Activity of Integration",
        },
    )
    assert response.status_code == 302
    response = teacher_client.post(
        f"/assignments/{assignment_id}/marks",
        data={
            "student_id": ids[4],
            "assessment_id": ids[7],
            "score": "40",
            "remarks": "Continuous work",
        },
    )
    assert response.status_code == 302

    with app.app_context():
        result = ExamResult.query.filter_by(
            student_id=ids[4],
            subject_id=ids[2],
            assessment_id=ids[3],
        ).one()
        assert result.score == 88
        assert ExamResult.query.filter_by(
            student_id=ids[5],
            subject_id=ids[2],
            assessment_id=ids[3],
        ).count() == 0

    response = admin.get(
        f"/report-cards/{ids[4]}/{ids[3]}"
    )
    assert response.status_code == 200
    assert b"Student Report Card" in response.data
    assert b"Print report card" in response.data
    assert b"Good progress" in response.data
    assert b"Formative (scaled / 20)" in response.data
    assert b"16.00 / 20" in response.data
    assert b"70.40 / 80" in response.data
    assert b"86.40" in response.data
    assert b"Exceptional" in response.data
    assert b"Continuous work" in response.data
    assert b"Activity of Integration" in response.data


def test_admin_can_create_bursar_and_update_school_settings():
    app = create_app(test_config=True)
    admin = app.test_client()
    admin.post("/login", data={"username": "admin", "password": "admin123"})

    response = admin.post(
        "/accounts/staff/new",
        data={
            "first_name": "Boris",
            "last_name": "Bursar",
            "role": "Bursar",
        },
    )
    credentials = re.search(
        rb"<code>([^<]+)</code></td><td><code>([^<]+)</code>",
        response.data,
    )
    assert credentials
    bursar_username, bursar_password = (
        value.decode() for value in credentials.groups()
    )
    second_response = admin.post(
        "/accounts/staff/new",
        data={
            "first_name": "Boris",
            "last_name": "Bursar",
            "role": "Bursar",
        },
    )
    second_credentials = re.search(
        rb"<code>([^<]+)</code></td><td><code>([^<]+)</code>",
        second_response.data,
    )
    assert second_credentials
    second_username, second_password = (
        value.decode() for value in second_credentials.groups()
    )
    assert second_username != bursar_username
    assert second_password != bursar_password

    response = admin.post(
        "/settings",
        data={
            "name": "Malcolm X Secondary School",
            "slogan": "Learning together",
            "address": "Katwe, Kampala",
            "phone": "+256700000000",
            "alternative_phone": "+256414000000",
            "email": "office@example.org",
            "website": "https://example.org",
            "is_active": "y",
            "o_level_active": "y",
            "a_level_active": "y",
            "o_level_curriculum": "UNEB Competency-Based Curriculum (CBC)",
            "a_level_curriculum": "Advanced Frameworks",
            "cbc_formative_weight": "20",
            "cbc_summative_weight": "80",
            "co_education": "Mixed (Boys & Girls)",
            "moes_registered": "y",
            "uneb_exam_center_valid": "y",
            "profile_photo": (
                BytesIO(b"\x89PNG\r\n\x1a\nschool image content"),
                "school.png",
            ),
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"School information saved." in response.data

    bursar = app.test_client()
    response = bursar.post(
        "/login",
        data={"username": bursar_username, "password": bursar_password},
    )
    assert response.headers["Location"].endswith("/change-password")
    assert bursar.get("/finance").status_code == 200
    assert bursar.get("/settings").status_code == 403
    assert bursar.get("/accounts").status_code == 403

    from app.models import School

    with app.app_context():
        school = School.query.one()
        assert school.name == "Malcolm X Secondary School"
        assert school.alternative_phone == "+256414000000"
        assert school.cbc_formative_weight == 20
        assert school.cbc_summative_weight == 80
        assert school.o_level_grading_module == "CBC_20_80"
        assert school.moes_registered
        assert school.uneb_exam_center_valid
        assert school.profile_photo.startswith("uploads/school/")


def test_school_profile_registration_payload_is_saved():
    app = create_app(test_config=True)
    with app.app_context():
        school = register_school_profile()
        assert {
            field: getattr(school, field)
            for field in SCHOOL_PROFILE
        } == SCHOOL_PROFILE


def test_school_settings_rejects_weights_that_do_not_total_one_hundred():
    app = create_app(test_config=True)
    admin = app.test_client()
    admin.post("/login", data={"username": "admin", "password": "admin123"})

    response = admin.post(
        "/settings",
        data={
            "name": "MALCOLM X SECONDARY SCHOOL KATWE",
            "cbc_formative_weight": "30",
            "cbc_summative_weight": "80",
        },
    )

    assert response.status_code == 200
    assert b"must total 100%" in response.data
    from app.models import School

    with app.app_context():
        school = School.query.one()
        assert school.cbc_formative_weight == 20
        assert school.cbc_summative_weight == 80


def test_image_upload_rejects_unsupported_and_mismatched_files():
    from werkzeug.datastructures import FileStorage

    from app.uploads import save_image_upload

    app = create_app(test_config=True)
    with app.app_context():
        with pytest.raises(ValueError, match="JPG, PNG, or WebP"):
            save_image_upload(
                FileStorage(stream=BytesIO(b"not an image"), filename="photo.svg"),
                "students",
            )
        with pytest.raises(ValueError, match="does not match"):
            save_image_upload(
                FileStorage(stream=BytesIO(b"not a PNG"), filename="photo.png"),
                "students",
            )


def test_hm_can_assign_teaching_loads_and_view_results_but_not_edit_school_info():
    app = create_app(test_config=True)
    admin = app.test_client()
    admin.post("/login", data={"username": "admin", "password": "admin123"})
    response = admin.post(
        "/accounts/staff/new",
        data={
            "first_name": "Hannah",
            "last_name": "Head",
            "role": "Headmaster",
        },
    )
    credentials = re.search(
        rb"<code>([^<]+)</code></td><td><code>([^<]+)</code>",
        response.data,
    )
    assert credentials
    username, temporary_password = (
        value.decode() for value in credentials.groups()
    )

    hm = app.test_client()
    hm.post(
        "/login",
        data={"username": username, "password": temporary_password},
    )
    hm.post(
        "/change-password",
        data={
            "current_password": temporary_password,
            "new_password": "HeadmasterSafePass2026",
            "confirm_password": "HeadmasterSafePass2026",
        },
    )
    assert hm.get("/assignments").status_code == 200
    assert hm.get("/results").status_code == 200
    assert hm.get("/report-cards/1/1").status_code == 200
    assert hm.get("/settings").status_code == 403
    assert hm.get("/accounts").status_code == 403


def test_super_admin_can_configure_classes_subjects_years_and_assessments():
    app = create_app(test_config=True)
    admin = app.test_client()
    admin.post("/login", data={"username": "admin", "password": "admin123"})

    response = admin.post(
        "/academic-setup/classes",
        data={
            "name": "Senior 6",
            "stream": "West",
            "level": "A-Level",
            "academic_year": "2026",
            "capacity": "30",
        },
    )
    assert response.status_code == 302
    response = admin.post(
        "/academic-setup/subjects",
        data={
            "name": "Physics",
            "code": "PHY",
            "level": "A-Level",
            "category": "Science",
        },
    )
    assert response.status_code == 302
    response = admin.post(
        "/academic-setup/years",
        data={
            "name": "2026",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
    )
    assert response.status_code == 302

    from app.models import AcademicYear, Assessment, ClassRoom, Subject

    with app.app_context():
        year_id = AcademicYear.query.filter_by(name="2026").one().id

    response = admin.post(
        "/academic-setup/assessments",
        data={
            "name": "Term 1 Examination",
            "academic_year_id": str(year_id),
            "term": "Term 1",
            "component": "Formative",
            "max_marks": "100",
        },
    )
    assert response.status_code == 302
    with app.app_context():
        room = ClassRoom.query.filter_by(name="Senior 6", stream="West").one()
        subject = Subject.query.filter_by(code="PHY").one()
        assessment = Assessment.query.filter_by(
            name="Term 1 Examination"
        ).one()
        assert room.label == "Senior 6 West"
        assert subject.name == "Physics"
        assert assessment.status == "Open"
        created_assessment = Assessment.query.filter_by(
            name="Term 1 Examination"
        ).one()
        assert created_assessment.component == "Formative"


def test_sample_seed_creates_thirty_records_and_is_idempotent():
    app = create_app(test_config=True)
    with app.app_context():
        first_counts = seed_sample_data()
        second_counts = seed_sample_data()

    expected_counts = {
        "student": 30,
        "teacher": 30,
        "subject": 30,
        "class_room": 10,
        "student_class_placement": 30,
        "teaching_assignment": 30,
        "academic_year": 30,
        "assessment": 30,
        "exam_result": 30,
        "fee_type": 30,
        "fee_invoice": 30,
        "attendance_record": 30,
        "audit_log": 30,
        "school": 1,
    }
    assert first_counts == expected_counts
    assert second_counts == expected_counts
    from app.models import ClassRoom

    with app.app_context():
        assert {
            class_room.label
            for class_room in ClassRoom.query.all()
        } == {
            "S1 A",
            "S1 B",
            "S2 A",
            "S2 B",
            "S3",
            "S4",
            "S5 ARTS",
            "S5 SCIENCE",
            "S6 ARTS",
            "S6 SCIENCE",
        }


def test_sample_seed_command_refuses_non_demo_database():
    app = create_app(test_config=True)
    result = app.test_cli_runner().invoke(args=["seed-sample-data"])

    assert result.exit_code != 0
    assert "restricted to the isolated demo database" in result.output


def test_school_profile_cli_refuses_non_demo_database():
    app = create_app(test_config=True)
    result = app.test_cli_runner().invoke(args=["register-school-profile"])

    assert result.exit_code != 0
    assert "restricted to the isolated demo database" in result.output
