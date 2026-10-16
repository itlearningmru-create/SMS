import click
from secrets import token_urlsafe
from flask import Flask
from sqlalchemy import inspect, text

from app.config import Config, DemoConfig, TestConfig
from app.extensions import csrf, db, login_manager, migrate


def create_app(test_config=None, config_class=None):
    app = Flask(__name__)
    app.config.from_object(
        config_class or (TestConfig if test_config else Config)
    )

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from app.models import AcademicYear, Assessment, AuditLog, ClassRoom, FeeType, Permission, Role, School, Student, StudentAccount, Subject, Teacher, User

    with app.app_context():
        db.create_all()
        ensure_assessment_component_column()
        ensure_school_profile_columns()
        ensure_student_passport_photo_column()
        ensure_school_name_is_unique()
        if app.config["SEED_DEMO_DATA"]:
            seed_demo_data()

    from app.routes import main

    app.register_blueprint(main)

    @app.cli.command("create-admin")
    def create_admin():
        """Create an administrator interactively."""
        username = click.prompt("Admin username").strip()
        email = click.prompt("Admin email").strip()
        first_name = click.prompt("First name").strip()
        last_name = click.prompt("Last name").strip()
        password = click.prompt(
            "Password", hide_input=True, confirmation_prompt=True
        )

        if not username or len(username) > 40:
            raise click.ClickException("Username must be between 1 and 40 characters.")
        if not email or len(email) > 120 or "@" not in email:
            raise click.ClickException("Enter a valid email address (max 120 characters).")
        if not first_name or len(first_name) > 80:
            raise click.ClickException("First name must be between 1 and 80 characters.")
        if not last_name or len(last_name) > 80:
            raise click.ClickException("Last name must be between 1 and 80 characters.")
        if len(password) < 12:
            raise click.ClickException("Password must be at least 12 characters.")
        if User.query.filter(
            (User.username == username) | (User.email == email)
        ).first():
            raise click.ClickException("An account with that username or email already exists.")

        role = Role.query.filter_by(name="Super Administrator").first()
        if role is None:
            role = Role(
                name="Super Administrator",
                description="System-wide admin",
            )
            db.session.add(role)

        admin = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        click.echo(f"Administrator account created for {username}.")

    @app.cli.command("create-student-logins")
    def create_student_logins():
        """Create missing student logins and print temporary credentials once."""
        from sqlalchemy import select

        from app.models import Student, StudentAccount, User

        students = db.session.scalars(
            select(Student)
            .outerjoin(StudentAccount, StudentAccount.student_id == Student.id)
            .where(StudentAccount.id.is_(None))
            .order_by(Student.student_no)
        ).all()
        if not students:
            if Student.query.first() is None:
                click.echo("No student records exist yet.")
            else:
                click.echo("Every student already has a portal account.")
            return

        conflicting_numbers = {
            username
            for (username,) in db.session.query(User.username).all()
            if any(student.student_no == username for student in students)
        }
        if conflicting_numbers:
            raise click.ClickException(
                "Student number conflicts with a staff username: "
                + ", ".join(sorted(conflicting_numbers))
            )

        credentials = []
        for student in students:
            password = token_urlsafe(18)
            account = StudentAccount(student=student)
            account.set_password(password)
            db.session.add(account)
            credentials.append((student.student_no, password))

        db.session.commit()
        click.echo("Temporary student credentials (shown once; distribute securely):")
        for student_number, password in credentials:
            click.echo(f"{student_number}\t{password}")
        click.echo("Students must change their temporary password at first sign-in.")

    @app.cli.command("seed-sample-data")
    def seed_sample_data_command():
        """Add repeatable sample school records to the isolated demo database."""
        if not app.config["DEMO_DATABASE"]:
            raise click.ClickException(
                "Sample seeding is restricted to the isolated demo database. "
                "Run this command with: flask --app app:create_demo_app seed-sample-data"
            )
        counts = seed_sample_data()
        click.echo("Sample data added to the local demo database:")
        for table_name, count in counts.items():
            click.echo(f"  {table_name}: {count}")
        click.echo(
            "Staff and student passwords were not generated by this seed. "
            "Create teacher logins from Staff Accounts or run create-student-logins."
        )

    @app.cli.command("register-school-profile")
    def register_school_profile_command():
        """Register the supplied institution profile in the isolated demo database."""
        if not app.config["DEMO_DATABASE"]:
            raise click.ClickException(
                "School profile registration is restricted to the isolated demo "
                "database. Run this command with: "
                "flask --app app:create_demo_app register-school-profile"
            )

        from app.school_profile import register_school_profile

        register_school_profile()
        click.echo(
            "Malcolm X Senior Secondary School registered in the local demo database."
        )

    @login_manager.user_loader
    def load_user(user_id):
        if user_id.startswith("student:"):
            student_id = user_id.removeprefix("student:")
            if not student_id.isdecimal():
                return None
            return StudentAccount.query.get(int(student_id))
        return User.query.get(int(user_id))

    return app


def ensure_assessment_component_column():
    columns = {
        column["name"] for column in inspect(db.engine).get_columns("assessment")
    }
    if "component" not in columns:
        db.session.execute(
            text(
                "ALTER TABLE assessment ADD COLUMN "
                "component VARCHAR(20) NOT NULL DEFAULT 'Summative'"
            )
        )
        db.session.commit()


def ensure_school_profile_columns():
    column_definitions = {
        "alternative_phone": "VARCHAR(30) NOT NULL DEFAULT ''",
        "profile_photo": "VARCHAR(255) NOT NULL DEFAULT ''",
        "is_active": "BOOLEAN NOT NULL DEFAULT 1",
        "o_level_active": "BOOLEAN NOT NULL DEFAULT 1",
        "a_level_active": "BOOLEAN NOT NULL DEFAULT 1",
        "o_level_curriculum": (
            "VARCHAR(100) NOT NULL DEFAULT "
            "'UNEB Competency-Based Curriculum (CBC)'"
        ),
        "a_level_curriculum": (
            "VARCHAR(100) NOT NULL DEFAULT 'Advanced Frameworks'"
        ),
        "o_level_grading_module": (
            "VARCHAR(40) NOT NULL DEFAULT 'CBC_20_80'"
        ),
        "cbc_formative_weight": "INTEGER NOT NULL DEFAULT 20",
        "cbc_summative_weight": "INTEGER NOT NULL DEFAULT 80",
        "co_education": "VARCHAR(40) NOT NULL DEFAULT 'Mixed'",
        "moes_registered": "BOOLEAN NOT NULL DEFAULT 0",
        "uneb_exam_center_valid": "BOOLEAN NOT NULL DEFAULT 0",
    }
    existing_columns = {
        column["name"] for column in inspect(db.engine).get_columns("school")
    }
    for column_name, definition in column_definitions.items():
        if column_name not in existing_columns:
            db.session.execute(
                text(f"ALTER TABLE school ADD COLUMN {column_name} {definition}")
            )
    db.session.commit()


def ensure_student_passport_photo_column():
    columns = {
        column["name"]
        for column in inspect(db.engine).get_columns("student")
    }
    if "passport_photo" not in columns:
        db.session.execute(
            text(
                "ALTER TABLE student ADD COLUMN "
                "passport_photo VARCHAR(255) NOT NULL DEFAULT ''"
            )
        )
        db.session.commit()


def ensure_school_name_is_unique():
    inspector = inspect(db.engine)
    unique_name_exists = any(
        constraint.get("column_names") == ["name"]
        for constraint in inspector.get_unique_constraints("school")
    ) or any(
        index.get("unique")
        and index.get("column_names") == ["name"]
        for index in inspector.get_indexes("school")
    )
    if unique_name_exists:
        return

    duplicate_name = db.session.execute(
        text(
            "SELECT name FROM school GROUP BY name "
            "HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate_name:
        raise RuntimeError(
            "Cannot enforce unique school names: duplicate profile "
            f"{duplicate_name[0]!r} already exists."
        )
    db.session.execute(
        text("CREATE UNIQUE INDEX uq_school_name ON school (name)")
    )
    db.session.commit()


def create_demo_app():
    """Create the local-demo app without using the configured production database."""
    return create_app(config_class=DemoConfig)


def seed_demo_data():
    from datetime import datetime

    from app.models import AcademicYear, Assessment, AuditLog, ClassRoom, FeeType, Permission, Role, School, Student, Subject, Teacher, User

    if not Role.query.first():
        admin_role = Role(name="Super Administrator", description="System-wide admin")
        teacher_role = Role(name="Subject Teacher", description="Academic teacher")
        bursar_role = Role(name="Bursar", description="Finance and fees")
        parent_role = Role(name="Parent", description="Parent portal access")
        student_role = Role(name="Student", description="Student portal access")
        db.session.add_all([admin_role, teacher_role, bursar_role, parent_role, student_role])
        db.session.flush()

        permission_names = [
            "view_students",
            "manage_students",
            "view_results",
            "manage_results",
            "view_fees",
            "manage_fees",
            "view_users",
            "manage_users",
            "view_reports",
            "manage_settings",
        ]
        permissions = [Permission(name=name, description=name.replace("_", " ").title()) for name in permission_names]
        db.session.add_all(permissions)
        db.session.flush()

        admin_role.permissions.extend(permissions)
        teacher_role.permissions.extend([Permission.query.filter_by(name="view_students").first(), Permission.query.filter_by(name="view_results").first(), Permission.query.filter_by(name="manage_results").first()])
        bursar_role.permissions.extend([Permission.query.filter_by(name="view_fees").first(), Permission.query.filter_by(name="manage_fees").first()])
        parent_role.permissions.extend([Permission.query.filter_by(name="view_students").first()])
        student_role.permissions.extend([Permission.query.filter_by(name="view_results").first()])

    if not School.query.first():
        db.session.add(School(name="MALCOLM X SECONDARY SCHOOL KATWE", slogan="Education for Character and Service", address="Katwe, Kampala, Uganda", phone="+256 414 000 000", email="info@mxss.ac.ug", website="https://mxss.ac.ug"))

    if not User.query.filter_by(username="admin").first():
        admin_role = Role.query.filter_by(name="Super Administrator").first()
        admin = User(username="admin", email="admin@mxss.ac.ug", first_name="System", last_name="Administrator")
        admin.set_password("admin123")
        admin.role = admin_role
        db.session.add(admin)

    if not Student.query.first():
        student_one = Student(student_no="MX-DEMO-BASE-001", first_name="Demo Student Base One", last_name="Sample", gender="Female", dob=datetime(2009, 4, 12), nationality="Ugandan", email="student1@example.test", phone="", entry_class="Senior 2", status="Enrolled", notes="Generated sample record; not a real student.")
        student_two = Student(student_no="MX-DEMO-BASE-002", first_name="Demo Student Base Two", last_name="Sample", gender="Male", dob=datetime(2010, 8, 2), nationality="Ugandan", email="student2@example.test", phone="", entry_class="Senior 2", status="Accepted", notes="Generated sample record; not a real student.")
        db.session.add_all([student_one, student_two])

    if not Teacher.query.first():
        teacher = Teacher(full_name="Demo Teacher Base", title="Teacher", department="Mathematics", phone="")
        db.session.add(teacher)

    if not Subject.query.first():
        db.session.add_all([
            Subject(name="Mathematics", code="MATH", level="O-Level", category="Core"),
            Subject(name="Biology", code="BIO", level="O-Level", category="Core"),
            Subject(name="English Language", code="ENG", level="O-Level", category="Core"),
            Subject(name="Computer Studies", code="COMP", level="O-Level", category="Elective"),
            Subject(name="Economics", code="ECON", level="A-Level", category="Elective"),
        ])

    if not ClassRoom.query.first():
        db.session.add_all(
            [
                ClassRoom(
                    name=name,
                    stream=stream,
                    level=name,
                    academic_year="2026",
                    capacity=40,
                    class_teacher="",
                )
                for name, stream in sample_class_groups()
            ]
        )

    if not AcademicYear.query.first():
        academic_year = AcademicYear(name="2025", start_date=datetime(2025, 1, 1), end_date=datetime(2025, 12, 31))
        db.session.add(academic_year)
        db.session.flush()

        assessment = Assessment(name="Midterm Exam", academic_year_id=academic_year.id, term="Term 2", max_marks=100, status="Open")
        db.session.add(assessment)

    if not FeeType.query.first():
        db.session.add_all([
            FeeType(name="School Fees", amount=420000.0, description="Termly school fee"),
            FeeType(name="Boarding Fees", amount=600000.0, description="Accommodation and meals"),
            FeeType(name="Exam Fees", amount=50000.0, description="Examination administration"),
        ])

    if not AuditLog.query.first():
        db.session.add(AuditLog(actor="admin", action="System initialized", details="Initial school demo data created."))

    db.session.commit()


def seed_sample_data():
    """Ensure the local demo database contains 30 records in each sample table."""
    from datetime import datetime

    from app.models import (
        AcademicYear,
        Assessment,
        AttendanceRecord,
        AuditLog,
        ClassRoom,
        ExamResult,
        FeeInvoice,
        FeeType,
        School,
        Student,
        StudentClassPlacement,
        Subject,
        Teacher,
        TeachingAssignment,
    )

    seed_demo_data()

    canonical_classrooms = {}
    for name, stream in sample_class_groups():
        class_room = ClassRoom.query.filter_by(name=name, stream=stream).first()
        if class_room is None:
            class_room = ClassRoom(
                name=name,
                stream=stream,
                level=name,
                academic_year="2026",
                capacity=40,
                class_teacher="",
            )
            db.session.add(class_room)
            db.session.flush()
        canonical_classrooms[(name, stream)] = class_room

    old_sample_classrooms = (
        ClassRoom.query.filter(
            (ClassRoom.stream.like("Demo %"))
            | (
                (ClassRoom.name == "Senior 2")
                & (ClassRoom.stream == "East")
            )
            | (
                (ClassRoom.name == "Senior 4")
                & (ClassRoom.stream == "North")
            )
        )
        .order_by(ClassRoom.id)
        .all()
    )
    class_group_values = sample_class_groups()
    for index, old_room in enumerate(old_sample_classrooms):
        target = canonical_classrooms[class_group_values[index % len(class_group_values)]]
        StudentClassPlacement.query.filter_by(
            class_room_id=old_room.id
        ).update(
            {"class_room_id": target.id},
            synchronize_session=False,
        )
        TeachingAssignment.query.filter_by(class_room_id=old_room.id).update(
            {"class_room_id": target.id},
            synchronize_session=False,
        )
        db.session.delete(old_room)

    legacy_sample_students = {
        "MX-2025-001": {
            "student_no": "MX-DEMO-BASE-001",
            "first_name": "Demo Student Base One",
            "last_name": "Sample",
            "email": "student1@example.test",
            "phone": "",
            "notes": "Generated sample record; not a real student.",
        },
        "MX-2025-002": {
            "student_no": "MX-DEMO-BASE-002",
            "first_name": "Demo Student Base Two",
            "last_name": "Sample",
            "email": "student2@example.test",
            "phone": "",
            "notes": "Generated sample record; not a real student.",
        },
    }
    for old_number, sample_values in legacy_sample_students.items():
        legacy_student = Student.query.filter_by(student_no=old_number).first()
        if legacy_student:
            for field, value in sample_values.items():
                setattr(legacy_student, field, value)

    legacy_teacher = Teacher.query.filter_by(full_name="Miriam Kintu").first()
    if legacy_teacher:
        legacy_teacher.full_name = "Demo Teacher Base"
        legacy_teacher.title = "Teacher"
        legacy_teacher.phone = ""
        ClassRoom.query.filter(
            ClassRoom.class_teacher.in_(["Miriam Kintu", "Mariam Kyalimpa"])
        ).update({"class_teacher": "Demo Teacher Base"}, synchronize_session=False)

    index = 1
    while Subject.query.count() < 30:
        code = f"DEMO{index:02d}"
        index += 1
        if not Subject.query.filter_by(code=code).first():
            db.session.add(
                Subject(
                    name=f"Sample Subject {index:02d}",
                    code=code,
                    level="O-Level",
                    category="Sample",
                )
            )
            db.session.flush()

    index = 1
    while Teacher.query.count() < 30:
        full_name = f"Demo Teacher {index:02d}"
        index += 1
        if not Teacher.query.filter_by(full_name=full_name).first():
            db.session.add(
                Teacher(
                    full_name=full_name,
                    title="Teacher",
                    department="Sample Department",
                    phone=f"+25670000{index:04d}",
                )
            )
            db.session.flush()

    index = 1
    while Student.query.count() < 30:
        student_no = f"MX-DEMO-{index:04d}"
        index += 1
        if not Student.query.filter_by(student_no=student_no).first():
            db.session.add(
                Student(
                    student_no=student_no,
                    first_name=f"Demo Student {index:02d}",
                    last_name="Sample",
                    gender="Female" if index % 2 else "Male",
                    dob=datetime(2008 + index % 6, (index - 1) % 12 + 1, 10),
                    nationality="Ugandan",
                    email=f"student{index:04d}@example.test",
                    phone=f"+25671100{index:04d}",
                    entry_class=f"Senior {(index - 1) % 6 + 1}",
                    status="Enrolled",
                    notes="Generated sample record; not a real student.",
                )
            )
            db.session.flush()

    index = 1
    while AcademicYear.query.count() < 30:
        year = str(1996 + index)
        index += 1
        if not AcademicYear.query.filter_by(name=year).first():
            db.session.add(
                AcademicYear(
                    name=year,
                    start_date=datetime(int(year), 1, 1),
                    end_date=datetime(int(year), 12, 31),
                )
            )
            db.session.flush()

    academic_years = AcademicYear.query.order_by(AcademicYear.name).all()
    index = 1
    while Assessment.query.count() < 30:
        academic_year = academic_years[(index - 1) % len(academic_years)]
        name = f"Sample Assessment {index:02d}"
        index += 1
        if not Assessment.query.filter_by(
            name=name,
            academic_year_id=academic_year.id,
        ).first():
            db.session.add(
                Assessment(
                    name=name,
                    academic_year_id=academic_year.id,
                    term=f"Term {(index - 1) % 3 + 1}",
                    max_marks=100,
                    status="Open",
                )
            )
            db.session.flush()

    index = 1
    while FeeType.query.count() < 30:
        name = f"Sample Fee Type {index:02d}"
        index += 1
        if not FeeType.query.filter_by(name=name).first():
            db.session.add(
                FeeType(
                    name=name,
                    amount=50000 + index * 10000,
                    description="Generated sample fee type for demo use.",
                )
            )
            db.session.flush()

    db.session.flush()
    students = Student.query.order_by(Student.id).limit(30).all()
    teachers = Teacher.query.order_by(Teacher.id).limit(30).all()
    subjects = Subject.query.order_by(Subject.id).limit(30).all()
    class_rooms = ClassRoom.query.order_by(ClassRoom.id).limit(30).all()
    assessments = Assessment.query.order_by(Assessment.id).limit(30).all()
    fee_types = FeeType.query.order_by(FeeType.id).limit(30).all()

    for index, student in enumerate(students):
        class_room = class_rooms[index % len(class_rooms)]
        if not StudentClassPlacement.query.filter_by(
            student_id=student.id
        ).first():
            db.session.add(
                StudentClassPlacement(
                    student_id=student.id,
                    class_room_id=class_room.id,
                )
            )

    for index, teacher in enumerate(teachers):
        subject = subjects[index % len(subjects)]
        class_room = class_rooms[index % len(class_rooms)]
        if not TeachingAssignment.query.filter_by(
            teacher_id=teacher.id,
            subject_id=subject.id,
            class_room_id=class_room.id,
        ).first():
            db.session.add(
                TeachingAssignment(
                    teacher_id=teacher.id,
                    subject_id=subject.id,
                    class_room_id=class_room.id,
                )
            )

    for index, student in enumerate(students):
        subject = subjects[index % len(subjects)]
        assessment = assessments[index % len(assessments)]
        if not ExamResult.query.filter_by(
            student_id=student.id,
            subject_id=subject.id,
            assessment_id=assessment.id,
        ).first():
            score = float(60 + index % 41)
            db.session.add(
                ExamResult(
                    student_id=student.id,
                    subject_id=subject.id,
                    assessment_id=assessment.id,
                    score=score,
                    grade="A" if score >= 80 else "B" if score >= 60 else "C",
                    remarks="Generated sample result.",
                    status="Submitted",
                )
            )

    for index, student in enumerate(students):
        fee_type = fee_types[index % len(fee_types)]
        if not FeeInvoice.query.filter_by(
            student_id=student.id,
            fee_type_id=fee_type.id,
        ).first():
            amount = fee_type.amount
            paid = (index % 4) * amount / 4
            db.session.add(
                FeeInvoice(
                    student_id=student.id,
                    fee_type_id=fee_type.id,
                    amount=amount,
                    balance=amount - paid,
                    status="Paid" if paid == amount else "Partially paid" if paid else "Unpaid",
                )
            )

        if not AttendanceRecord.query.filter_by(student_id=student.id).first():
            db.session.add(
                AttendanceRecord(
                    student_id=student.id,
                    date=datetime(2026, 9, (index - 1) % 28 + 1),
                    status="Present" if index % 7 else "Late",
                )
            )

    while AuditLog.query.count() < 30:
        index = AuditLog.query.count() + 1
        db.session.add(
            AuditLog(
                actor="demo.admin",
                action="sample_data_created",
                details=f"Generated sample activity record {index:02d}.",
            )
        )
        db.session.flush()

    db.session.commit()

    return {
        "student": Student.query.count(),
        "teacher": Teacher.query.count(),
        "subject": Subject.query.count(),
        "class_room": ClassRoom.query.count(),
        "student_class_placement": StudentClassPlacement.query.count(),
        "teaching_assignment": TeachingAssignment.query.count(),
        "academic_year": AcademicYear.query.count(),
        "assessment": Assessment.query.count(),
        "exam_result": ExamResult.query.count(),
        "fee_type": FeeType.query.count(),
        "fee_invoice": FeeInvoice.query.count(),
        "attendance_record": AttendanceRecord.query.count(),
        "audit_log": AuditLog.query.count(),
        "school": School.query.count(),
    }


def sample_class_groups():
    """The school's configured classes and streams used by local demo data."""
    return [
        ("S1", "A"),
        ("S1", "B"),
        ("S2", "A"),
        ("S2", "B"),
        ("S3", ""),
        ("S4", ""),
        ("S5", "ARTS"),
        ("S5", "SCIENCE"),
        ("S6", "ARTS"),
        ("S6", "SCIENCE"),
    ]
