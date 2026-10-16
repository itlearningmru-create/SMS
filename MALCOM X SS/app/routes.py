from datetime import datetime, time

from flask import (
    Blueprint,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from app.extensions import db
from app.forms import (
    AcademicYearForm,
    AssessmentForm,
    ClassRoomForm,
    LoginForm,
    MarkEntryForm,
    SchoolSettingsForm,
    StaffAccountForm,
    StaffPasswordForm,
    StudentForm,
    StudentPhotoForm,
    StudentPasswordForm,
    SubjectForm,
    TeacherForm,
    TeachingAssignmentForm,
)
from app.grading import (
    CBC_GRADING_MODULE_KEY,
    cbc_grade,
    is_lower_secondary_class,
    scale_component_scores,
)
from app.models import (
    AcademicYear,
    Assessment,
    AuditLog,
    AttendanceRecord,
    ClassRoom,
    ExamResult,
    FeeType,
    Role,
    School,
    Student,
    StudentAccount,
    StudentClassPlacement,
    Subject,
    Teacher,
    TeachingAssignment,
    User,
    UserPasswordPolicy,
)
from app.uploads import get_student_photo_path, save_image_upload
from secrets import token_urlsafe
import re

main = Blueprint("main", __name__)

STUDENT_ENDPOINTS = {
    "main.student_portal",
    "main.student_change_password",
    "main.student_passport_photo",
    "main.logout",
}

ROLE_ENDPOINTS = {
    "Teacher": {
        "main.login",
        "main.dashboard",
        "main.teacher_work",
        "main.enter_marks",
        "main.student_passport_photo",
        "main.staff_change_password",
        "main.logout",
    },
    "Director of Studies": {
        "main.login",
        "main.dashboard",
        "main.assignments",
        "main.save_assignment",
        "main.results",
        "main.report_card",
        "main.student_detail",
        "main.upload_student_passport_photo",
        "main.student_passport_photo",
        "main.classes",
        "main.subjects",
        "main.examinations",
        "main.reports",
        "main.staff_change_password",
        "main.logout",
    },
    "Headmaster": {
        "main.login",
        "main.dashboard",
        "main.assignments",
        "main.save_assignment",
        "main.results",
        "main.report_card",
        "main.student_detail",
        "main.upload_student_passport_photo",
        "main.student_passport_photo",
        "main.classes",
        "main.subjects",
        "main.examinations",
        "main.reports",
        "main.staff_change_password",
        "main.logout",
    },
    "Bursar": {
        "main.login",
        "main.dashboard",
        "main.finance",
        "main.staff_change_password",
        "main.logout",
    },
}

MODULES = [
    {"slug": "dashboard", "label": "Dashboard", "icon": "bi-speedometer2", "route": "main.dashboard"},
    {"slug": "teacher-work", "label": "My Teaching", "icon": "bi-journal-check", "route": "main.teacher_work"},
    {"slug": "assignments", "label": "Teaching Assignments", "icon": "bi-person-workspace", "route": "main.assignments"},
    {"slug": "results", "label": "Results and Report Cards", "icon": "bi-clipboard-data", "route": "main.results"},
    {"slug": "accounts", "label": "Staff Accounts", "icon": "bi-person-lock", "route": "main.staff_accounts"},
    {"slug": "academic-setup", "label": "Academic Setup", "icon": "bi-journal-plus", "route": "main.academic_setup"},
    {"slug": "students", "label": "Student Management", "icon": "bi-people", "route": "main.students"},
    {"slug": "admissions", "label": "Admissions", "icon": "bi-person-plus", "route": "main.admissions"},
    {"slug": "academics", "label": "Academics", "icon": "bi-mortarboard", "route": "main.academics"},
    {"slug": "classes", "label": "Classes and Streams", "icon": "bi-door-open", "route": "main.classes"},
    {"slug": "subjects", "label": "Subjects and Teachers", "icon": "bi-book", "route": "main.subjects"},
    {"slug": "attendance", "label": "Attendance", "icon": "bi-calendar-check", "route": "main.attendance"},
    {"slug": "examinations", "label": "Examinations and Results", "icon": "bi-clipboard-data", "route": "main.examinations"},
    {"slug": "finance", "label": "Fees and Finance", "icon": "bi-cash", "route": "main.finance"},
    {"slug": "hr", "label": "Human Resources", "icon": "bi-person-badge", "route": "main.hr"},
    {"slug": "timetable", "label": "Timetable", "icon": "bi-calendar3", "route": "main.timetable"},
    {"slug": "parent-portal", "label": "Parent and Guardian Portal", "icon": "bi-house-door", "route": "main.parent_portal"},
    {"slug": "student-portal", "label": "Student Portal", "icon": "bi-person-video3", "route": "main.student_portal"},
    {"slug": "library", "label": "Library", "icon": "bi-bookshelf", "route": "main.library"},
    {"slug": "ict", "label": "Computer Laboratory and ICT", "icon": "bi-laptop", "route": "main.ict"},
    {"slug": "inventory", "label": "School Inventory", "icon": "bi-box", "route": "main.inventory"},
    {"slug": "transport", "label": "Transport", "icon": "bi-bus-front", "route": "main.transport"},
    {"slug": "boarding", "label": "Boarding and Accommodation", "icon": "bi-hospital", "route": "main.boarding"},
    {"slug": "discipline", "label": "Discipline", "icon": "bi-shield-check", "route": "main.discipline"},
    {"slug": "health", "label": "Health and Welfare", "icon": "bi-heart-pulse", "route": "main.health"},
    {"slug": "communication", "label": "Communication", "icon": "bi-chat-dots", "route": "main.communication"},
    {"slug": "reports", "label": "Reports and Analytics", "icon": "bi-bar-chart", "route": "main.reports"},
    {"slug": "security", "label": "User Management and Security", "icon": "bi-lock", "route": "main.security"},
    {"slug": "settings", "label": "School Settings", "icon": "bi-gear", "route": "main.settings"},
    {"slug": "audit", "label": "Audit Logs and Backup Management", "icon": "bi-journal-text", "route": "main.audit"},
]


def role_name(user=None):
    user = user or current_user._get_current_object()
    if isinstance(user, StudentAccount):
        return "Student"
    user_role = getattr(user, "role", None)
    return user_role.name if user_role else None


def role_for(name):
    role = Role.query.filter_by(name=name).first()
    if role is None:
        role = Role(name=name, description=f"{name} account")
        db.session.add(role)
        db.session.flush()
    return role


def unique_username(prefix, full_name):
    slug = re.sub(r"[^a-z0-9]+", ".", full_name.lower()).strip(".")
    base = f"{prefix}.{slug}"[:40].rstrip(".")
    username = base
    suffix = 2
    while User.query.filter_by(username=username).first():
        tail = f".{suffix}"
        username = f"{base[:40 - len(tail)]}{tail}"
        suffix += 1
    return username


def create_staff_user(username, first_name, last_name, role, email=None):
    if email is None:
        email = f"{username}@mxss.local"
        suffix = 2
        while User.query.filter_by(email=email).first():
            email = f"{username}.{suffix}@mxss.local"
            suffix += 1
    user = User(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        role=role_for(role),
    )
    temporary_password = token_urlsafe(18)
    user.set_password(temporary_password)
    db.session.add(user)
    db.session.flush()
    db.session.add(UserPasswordPolicy(user_id=user.id, must_change_password=True))
    return user, temporary_password


def staff_credentials_response(credentials, account_label):
    response = make_response(
        render_template(
            "staff_credentials.html",
            credentials=credentials,
            account_label=account_label,
        )
    )
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


def teachers_with_accounts():
    return (
        Teacher.query.join(User, Teacher.user_id == User.id)
        .join(Role, User.role_id == Role.id)
        .filter(Role.name == "Teacher", User.is_active.is_(True))
        .order_by(Teacher.full_name)
        .all()
    )


@main.before_request
def restrict_student_access():
    if not current_user.is_authenticated:
        return None

    user = current_user._get_current_object()
    endpoint = request.endpoint
    if isinstance(user, StudentAccount):
        if endpoint not in STUDENT_ENDPOINTS:
            return redirect(url_for("main.student_portal"))
        return None

    role = role_name(user)
    if role == "Super Administrator":
        return None
    if endpoint not in ROLE_ENDPOINTS.get(role, set()):
        abort(403)
    return None


@main.context_processor
def inject_globals():
    user_role = role_name()
    if user_role == "Student":
        allowed_slugs = {"student-portal"}
    elif user_role == "Teacher":
        allowed_slugs = {"dashboard", "teacher-work"}
    elif user_role in {"Director of Studies", "Headmaster"}:
        allowed_slugs = {
            "dashboard",
            "assignments",
            "results",
            "classes",
            "subjects",
            "examinations",
            "reports",
        }
    elif user_role == "Bursar":
        allowed_slugs = {"dashboard", "finance"}
    else:
        allowed_slugs = {module["slug"] for module in MODULES}
    school = School.query.first()
    return {
        "module_nav": [module for module in MODULES if module["slug"] in allowed_slugs],
        "is_student_user": user_role == "Student",
        "user_role": user_role,
        "school": school,
        "school_name": school.name if school else "MALCOLM X SECONDARY SCHOOL KATWE",
    }


@main.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("main.login"))


@main.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        user = current_user._get_current_object()
        if isinstance(user, StudentAccount):
            if user.must_change_password:
                return redirect(url_for("main.student_change_password"))
            return redirect(url_for("main.student_portal"))
        policy = db.session.get(UserPasswordPolicy, user.id)
        if policy and policy.must_change_password:
            return redirect(url_for("main.staff_change_password"))
        if role_name(user) == "Teacher":
            return redirect(url_for("main.teacher_work"))
        if role_name(user) == "Bursar":
            return redirect(url_for("main.finance"))
        return redirect(url_for("main.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None:
            student_account = (
                StudentAccount.query.join(Student)
                .filter(Student.student_no == form.username.data)
                .first()
            )
            if student_account and student_account.check_password(form.password.data):
                login_user(student_account, remember=True)
                if student_account.must_change_password:
                    flash("Set a new password before continuing.", "info")
                    return redirect(url_for("main.student_change_password"))
                return redirect(url_for("main.student_portal"))
        if user and user.is_active and user.check_password(form.password.data):
            login_user(user, remember=True)
            policy = db.session.get(UserPasswordPolicy, user.id)
            if policy and policy.must_change_password:
                flash("Set a new password before continuing.", "info")
                return redirect(url_for("main.staff_change_password"))
            audit = AuditLog(actor=user.username, action="login", details="User signed in to MX-SMS")
            db.session.add(audit)
            db.session.commit()
            flash("Login successful.", "success")
            if role_name(user) == "Teacher":
                return redirect(url_for("main.teacher_work"))
            if role_name(user) == "Bursar":
                return redirect(url_for("main.finance"))
            return redirect(url_for("main.dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html", form=form)


@main.route("/logout")
@login_required
def logout():
    audit = AuditLog(actor=current_user.username, action="logout", details="User signed out from MX-SMS")
    db.session.add(audit)
    db.session.commit()
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.login"))


@main.route("/dashboard")
@login_required
def dashboard():
    school = School.query.first()
    total_students = Student.query.count()
    total_classes = ClassRoom.query.count()
    total_subjects = Subject.query.count()
    total_teachers = Teacher.query.count()
    latest_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(5).all()
    return render_template(
        "dashboard.html",
        school=school,
        total_students=total_students,
        total_classes=total_classes,
        total_subjects=total_subjects,
        total_teachers=total_teachers,
        latest_logs=latest_logs,
    )


@main.route("/students")
@login_required
def students():
    students_list = Student.query.order_by(Student.created_at.desc()).all()
    return render_template("students.html", students=students_list)


@main.route("/students/new", methods=["GET", "POST"])
@login_required
def new_student():
    form = StudentForm()
    class_rooms = ClassRoom.query.order_by(ClassRoom.name, ClassRoom.stream).all()
    form.class_room_id.choices = [(room.id, room.label) for room in class_rooms]
    if form.validate_on_submit():
        if User.query.filter_by(username=form.student_no.data).first():
            flash("That student number is already used as a staff username.", "danger")
            return render_template("student_form.html", form=form, title="Register new student")
        class_room = db.session.get(ClassRoom, form.class_room_id.data)
        if class_room is None:
            abort(400)
        try:
            passport_photo = save_image_upload(
                form.passport_photo.data,
                "students",
            )
        except ValueError as error:
            flash(str(error), "danger")
            return render_template(
                "student_form.html",
                form=form,
                title="Register new student",
            )
        student = Student(
            student_no=form.student_no.data,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            gender=form.gender.data,
            dob=form.dob.data,
            email=form.email.data,
            phone=form.phone.data,
            nationality=form.nationality.data,
            entry_class=class_room.name,
            status=form.status.data,
            notes=form.notes.data,
            passport_photo=passport_photo or "",
        )
        db.session.add(student)
        db.session.flush()
        db.session.add(
            StudentClassPlacement(student_id=student.id, class_room_id=class_room.id)
        )
        temporary_password = token_urlsafe(18)
        student_account = StudentAccount(student=student)
        student_account.set_password(temporary_password)
        db.session.add(student_account)
        db.session.commit()
        audit = AuditLog(actor=current_user.username, action="student_created", details=f"Created student profile {student.student_no}")
        db.session.add(audit)
        db.session.commit()
        flash(
            f"Student record created. Student portal username: {student.student_no}. "
            f"One-time temporary password: {temporary_password}. Share it securely; "
            "the student must change it at first sign-in.",
            "success",
        )
        return redirect(url_for("main.students"))
    return render_template("student_form.html", form=form, title="Register new student")


@main.route("/students/<int:student_id>")
@login_required
def student_detail(student_id):
    student = Student.query.get_or_404(student_id)
    return render_template(
        "student_detail.html",
        student=student,
        photo_form=StudentPhotoForm(),
    )


@main.route("/students/<int:student_id>/passport-photo")
@login_required
def student_passport_photo(student_id):
    student = Student.query.get_or_404(student_id)
    logged_in_user = current_user._get_current_object()
    if isinstance(logged_in_user, StudentAccount):
        if logged_in_user.student_id != student.id:
            abort(403)
    elif role_name() not in {
        "Super Administrator",
        "Director of Studies",
        "Headmaster",
        "Teacher",
    }:
        abort(403)

    photo_path = get_student_photo_path(student.passport_photo)
    if photo_path is None:
        abort(404)
    return send_file(photo_path, conditional=True)


@main.route(
    "/students/<int:student_id>/passport-photo",
    methods=["POST"],
)
@login_required
def upload_student_passport_photo(student_id):
    if role_name() not in {
        "Super Administrator",
        "Director of Studies",
        "Headmaster",
    }:
        abort(403)

    student = Student.query.get_or_404(student_id)
    form = StudentPhotoForm()
    if form.validate_on_submit():
        try:
            photo_path = save_image_upload(form.passport_photo.data, "students")
        except ValueError as error:
            flash(str(error), "danger")
        else:
            if photo_path is None:
                flash("Choose a passport photo to upload.", "warning")
            else:
                student.passport_photo = photo_path
                db.session.commit()
                flash("Student passport photo uploaded.", "success")
    else:
        flash("Choose a valid passport photo to upload.", "danger")
    return redirect(url_for("main.student_detail", student_id=student.id))


@main.route("/accounts")
@login_required
def staff_accounts():
    users = User.query.order_by(User.username).all()
    teachers = Teacher.query.order_by(Teacher.full_name).all()
    unlinked_teachers = [teacher for teacher in teachers if teacher.user_id is None]
    return render_template(
        "staff_accounts.html",
        users=users,
        teachers=teachers,
        unlinked_teachers=unlinked_teachers,
        staff_form=StaffAccountForm(),
        teacher_form=TeacherForm(),
    )


@main.route("/accounts/teachers/new", methods=["POST"])
@login_required
def create_teacher_account():
    form = TeacherForm()
    if form.validate_on_submit():
        full_name = f"{form.first_name.data.strip()} {form.last_name.data.strip()}"
        username = unique_username("teacher", full_name)
        first_name, last_name = form.first_name.data.strip(), form.last_name.data.strip()
        user, password = create_staff_user(
            username,
            first_name,
            last_name,
            "Teacher",
        )
        teacher = Teacher(
            user_id=user.id,
            full_name=full_name,
            title="Teacher",
            department=form.department.data.strip(),
            phone=(form.phone.data or "").strip(),
        )
        db.session.add(teacher)
        db.session.add(
            AuditLog(
                actor=current_user.username,
                action="teacher_account_created",
                details=f"Created teacher account {username}.",
            )
        )
        db.session.commit()
        return staff_credentials_response(
            [(username, password)],
            f"Teacher account for {full_name}",
        )
    flash("Please correct the teacher account details and try again.", "danger")
    return redirect(url_for("main.staff_accounts"))


@main.route("/accounts/staff/new", methods=["POST"])
@login_required
def create_staff_account():
    form = StaffAccountForm()
    if form.validate_on_submit():
        first_name = form.first_name.data.strip()
        last_name = form.last_name.data.strip()
        role = form.role.data
        prefix = {
            "Director of Studies": "dos",
            "Headmaster": "hm",
            "Bursar": "bursar",
        }[role]
        username = unique_username(prefix, f"{first_name} {last_name}")
        user, password = create_staff_user(
            username,
            first_name,
            last_name,
            role,
        )
        db.session.add(
            AuditLog(
                actor=current_user.username,
                action="staff_account_created",
                details=f"Created {role} account {username}.",
            )
        )
        db.session.commit()
        return staff_credentials_response(
            [(username, password)],
            f"{role} account for {user.full_name}",
        )
    flash("Please correct the account details and try again.", "danger")
    return redirect(url_for("main.staff_accounts"))


@main.route("/accounts/teachers/provision", methods=["POST"])
@login_required
def provision_teacher_accounts():
    teachers = Teacher.query.filter(Teacher.user_id.is_(None)).order_by(Teacher.id).all()
    credentials = []
    for teacher in teachers:
        parts = teacher.full_name.strip().split(maxsplit=1)
        first_name = parts[0] if parts else "Teacher"
        last_name = parts[1] if len(parts) > 1 else "Staff"
        username = unique_username("teacher", teacher.full_name)
        user, password = create_staff_user(
            username,
            first_name,
            last_name,
            "Teacher",
        )
        teacher.user_id = user.id
        credentials.append((username, password))

    if credentials:
        db.session.add(
            AuditLog(
                actor=current_user.username,
                action="teacher_accounts_provisioned",
                details=f"Provisioned {len(credentials)} teacher accounts.",
            )
        )
        db.session.commit()
    else:
        db.session.rollback()
        flash("All existing teachers already have accounts.", "info")
        return redirect(url_for("main.staff_accounts"))

    return staff_credentials_response(credentials, "Teacher accounts")


@main.route("/change-password", methods=["GET", "POST"])
@login_required
def staff_change_password():
    form = StaffPasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("The current password is incorrect.", "danger")
        else:
            current_user.set_password(form.new_password.data)
            policy = db.session.get(UserPasswordPolicy, current_user.id)
            if policy:
                policy.must_change_password = False
            db.session.commit()
            flash("Password updated successfully.", "success")
            if role_name() == "Teacher":
                return redirect(url_for("main.teacher_work"))
            if role_name() == "Bursar":
                return redirect(url_for("main.finance"))
            return redirect(url_for("main.dashboard"))
    return render_template("staff_change_password.html", form=form)


@main.route("/admissions")
@login_required
def admissions():
    return render_template("module.html", module={"label": "Admissions", "icon": "bi-person-plus"}, records=Student.query.order_by(Student.created_at.desc()).limit(10).all())


@main.route("/academics")
@login_required
def academics():
    years = AcademicYear.query.all()
    assessments = Assessment.query.order_by(Assessment.id.desc()).all()
    return render_template("module.html", module={"label": "Academics", "icon": "bi-mortarboard"}, years=years, assessments=assessments)


@main.route("/classes")
@login_required
def classes():
    class_list = ClassRoom.query.order_by(ClassRoom.name).all()
    return render_template("module.html", module={"label": "Classes and Streams", "icon": "bi-door-open"}, records=class_list)


@main.route("/subjects")
@login_required
def subjects():
    subject_list = Subject.query.order_by(Subject.name).all()
    return render_template("module.html", module={"label": "Subjects and Teachers", "icon": "bi-book"}, records=subject_list)


@main.route("/academic-setup")
@login_required
def academic_setup():
    assessment_form = AssessmentForm()
    academic_years = AcademicYear.query.order_by(AcademicYear.name.desc()).all()
    assessment_form.academic_year_id.choices = [
        (year.id, year.name) for year in academic_years
    ]
    return render_template(
        "academic_setup.html",
        class_form=ClassRoomForm(),
        subject_form=SubjectForm(),
        year_form=AcademicYearForm(),
        assessment_form=assessment_form,
        classes=ClassRoom.query.order_by(ClassRoom.name, ClassRoom.stream).all(),
        subjects=Subject.query.order_by(Subject.name).all(),
        years=AcademicYear.query.order_by(AcademicYear.name.desc()).all(),
        assessments=Assessment.query.order_by(Assessment.id.desc()).all(),
    )


@main.route("/academic-setup/classes", methods=["POST"])
@login_required
def create_class_room():
    form = ClassRoomForm()
    if form.validate_on_submit():
        name = form.name.data.strip()
        stream = (form.stream.data or "").strip()
        duplicate = ClassRoom.query.filter_by(name=name, stream=stream).first()
        if duplicate:
            flash("That class and stream already exists.", "warning")
        else:
            db.session.add(
                ClassRoom(
                    name=name,
                    stream=stream,
                    level=form.level.data.strip(),
                    academic_year=form.academic_year.data.strip(),
                    capacity=form.capacity.data,
                )
            )
            db.session.commit()
            flash("Class and stream added.", "success")
    else:
        flash("Please provide valid class and stream details.", "danger")
    return redirect(url_for("main.academic_setup"))


@main.route("/academic-setup/subjects", methods=["POST"])
@login_required
def create_subject():
    form = SubjectForm()
    if form.validate_on_submit():
        code = form.code.data.strip().upper()
        if Subject.query.filter_by(code=code).first():
            flash("That subject code already exists.", "warning")
        else:
            db.session.add(
                Subject(
                    name=form.name.data.strip(),
                    code=code,
                    level=form.level.data.strip(),
                    category=form.category.data.strip(),
                )
            )
            db.session.commit()
            flash("Subject added.", "success")
    else:
        flash("Please provide valid subject details.", "danger")
    return redirect(url_for("main.academic_setup"))


@main.route("/academic-setup/years", methods=["POST"])
@login_required
def create_academic_year():
    form = AcademicYearForm()
    if form.validate_on_submit():
        if form.end_date.data < form.start_date.data:
            flash("The academic year end date must be after its start date.", "danger")
        elif AcademicYear.query.filter_by(name=form.name.data.strip()).first():
            flash("That academic year already exists.", "warning")
        else:
            db.session.add(
                AcademicYear(
                    name=form.name.data.strip(),
                    start_date=datetime.combine(form.start_date.data, time.min),
                    end_date=datetime.combine(form.end_date.data, time.min),
                )
            )
            db.session.commit()
            flash("Academic year added.", "success")
    else:
        flash("Please provide valid academic-year details.", "danger")
    return redirect(url_for("main.academic_setup"))


@main.route("/academic-setup/assessments", methods=["POST"])
@login_required
def create_assessment():
    form = AssessmentForm()
    years = AcademicYear.query.order_by(AcademicYear.name.desc()).all()
    form.academic_year_id.choices = [(year.id, year.name) for year in years]
    if form.validate_on_submit():
        db.session.add(
            Assessment(
                name=form.name.data.strip(),
                academic_year_id=form.academic_year_id.data,
                term=form.term.data.strip(),
                component=form.component.data,
                max_marks=form.max_marks.data,
                status="Open",
            )
        )
        db.session.commit()
        flash("Assessment added and opened for mark entry.", "success")
    else:
        flash("Please provide valid assessment details.", "danger")
    return redirect(url_for("main.academic_setup"))


@main.route("/assignments")
@login_required
def assignments():
    assignment_list = TeachingAssignment.query.join(Teacher).join(Subject).join(ClassRoom).order_by(
        ClassRoom.name,
        ClassRoom.stream,
        Subject.name,
        Teacher.full_name,
    ).all()
    form = TeachingAssignmentForm()
    form.teacher_id.choices = [
        (teacher.id, teacher.full_name) for teacher in teachers_with_accounts()
    ]
    form.subject_id.choices = [
        (subject.id, f"{subject.name} ({subject.code})")
        for subject in Subject.query.order_by(Subject.name).all()
    ]
    form.class_room_id.choices = [
        (room.id, room.label)
        for room in ClassRoom.query.order_by(ClassRoom.name, ClassRoom.stream).all()
    ]
    return render_template(
        "assignments.html",
        assignments=assignment_list,
        form=form,
        can_assign=role_name() in {
            "Super Administrator",
            "Director of Studies",
            "Headmaster",
        },
    )


@main.route("/assignments/new", methods=["POST"])
@login_required
def save_assignment():
    form = TeachingAssignmentForm()
    teachers = teachers_with_accounts()
    subjects = Subject.query.order_by(Subject.name).all()
    class_rooms = ClassRoom.query.order_by(ClassRoom.name, ClassRoom.stream).all()
    form.teacher_id.choices = [(teacher.id, teacher.full_name) for teacher in teachers]
    form.subject_id.choices = [(subject.id, subject.name) for subject in subjects]
    form.class_room_id.choices = [(room.id, room.label) for room in class_rooms]
    if form.validate_on_submit():
        teacher = db.session.get(Teacher, form.teacher_id.data)
        linked_user = db.session.get(User, teacher.user_id) if teacher else None
        if (
            teacher is None
            or linked_user is None
            or not linked_user.is_active
            or role_name(linked_user) != "Teacher"
        ):
            flash("Choose a teacher with an active teacher login.", "danger")
        elif TeachingAssignment.query.filter_by(
            teacher_id=teacher.id,
            subject_id=form.subject_id.data,
            class_room_id=form.class_room_id.data,
        ).first():
            flash("That teacher is already assigned this subject and class/stream.", "warning")
        else:
            db.session.add(
                TeachingAssignment(
                    teacher_id=teacher.id,
                    subject_id=form.subject_id.data,
                    class_room_id=form.class_room_id.data,
                )
            )
            db.session.add(
                AuditLog(
                    actor=current_user.username,
                    action="teaching_assignment_created",
                    details=(
                        f"Assigned {teacher.full_name} to subject "
                        f"{form.subject_id.data} for class/stream {form.class_room_id.data}."
                    ),
                )
            )
            db.session.commit()
            flash("Teaching assignment saved.", "success")
    else:
        flash("Choose a teacher, subject, and class/stream.", "danger")
    return redirect(url_for("main.assignments"))


@main.route("/my-teaching")
@login_required
def teacher_work():
    teacher = Teacher.query.filter_by(user_id=current_user.id).first()
    assignment_list = (
        TeachingAssignment.query.filter_by(teacher_id=teacher.id)
        .order_by(TeachingAssignment.id)
        .all()
        if teacher
        else []
    )
    assignment_rows = [
        (
            assignment,
            Student.query.join(StudentClassPlacement)
            .filter(
                StudentClassPlacement.class_room_id == assignment.class_room_id,
                Student.status == "Enrolled",
            )
            .count(),
        )
        for assignment in assignment_list
    ]
    return render_template(
        "teacher_work.html",
        teacher=teacher,
        assignment_rows=assignment_rows,
    )


@main.route("/assignments/<int:assignment_id>/marks", methods=["GET", "POST"])
@login_required
def enter_marks(assignment_id):
    assignment = TeachingAssignment.query.get_or_404(assignment_id)
    if role_name() == "Teacher":
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        if teacher is None or assignment.teacher_id != teacher.id:
            abort(403)

    students = (
        Student.query.join(StudentClassPlacement)
        .filter(
            StudentClassPlacement.class_room_id == assignment.class_room_id,
            Student.status == "Enrolled",
        )
        .order_by(Student.last_name, Student.first_name)
        .all()
    )
    assessments = Assessment.query.filter_by(status="Open").order_by(
        Assessment.id.desc()
    ).all()
    form = MarkEntryForm()
    form.student_id.choices = [
        (student.id, f"{student.student_no} — {student.full_name}")
        for student in students
    ]
    form.assessment_id.choices = [
        (
            assessment.id,
            f"{assessment.name} — {assessment.term} ({assessment.component})",
        )
        for assessment in assessments
    ]
    if form.validate_on_submit():
        student = db.session.get(Student, form.student_id.data)
        assessment = db.session.get(Assessment, form.assessment_id.data)
        if student not in students or assessment not in assessments:
            abort(400)
        if form.score.data > assessment.max_marks:
            form.score.errors.append(
                f"Mark cannot exceed this assessment's maximum of {assessment.max_marks}."
            )
        else:
            result = ExamResult.query.filter_by(
                student_id=student.id,
                subject_id=assignment.subject_id,
                assessment_id=assessment.id,
            ).first()
            if result is None:
                result = ExamResult(
                    student_id=student.id,
                    subject_id=assignment.subject_id,
                    assessment_id=assessment.id,
                )
                db.session.add(result)
            result.score = form.score.data
            result.remarks = (form.remarks.data or "").strip()
            result.status = "Submitted"
            db.session.add(
                AuditLog(
                    actor=current_user.username,
                    action="student_mark_saved",
                    details=(
                        f"Saved {assignment.subject.name} mark for "
                        f"{student.student_no} in {assessment.name}."
                    ),
                )
            )
            db.session.commit()
            flash("Student mark saved.", "success")
            return redirect(
                url_for("main.enter_marks", assignment_id=assignment.id)
            )
    return render_template(
        "mark_entry.html",
        assignment=assignment,
        students=students,
        assessments=assessments,
        form=form,
    )


@main.route("/results")
@login_required
def results():
    submitted_pairs = (
        db.session.query(Student, Assessment)
        .join(ExamResult, ExamResult.student_id == Student.id)
        .join(Assessment, Assessment.id == ExamResult.assessment_id)
        .filter(ExamResult.status == "Submitted")
        .distinct()
        .order_by(Assessment.id.desc(), Student.last_name, Student.first_name)
        .all()
    )
    report_pairs = {}
    for student, assessment in submitted_pairs:
        period_key = (
            student.id,
            assessment.academic_year_id,
            assessment.term,
        )
        report_pairs.setdefault(period_key, (student, assessment))
    return render_template(
        "results.html",
        report_pairs=list(report_pairs.values()),
    )


@main.route("/report-cards/<int:student_id>/<int:assessment_id>")
@login_required
def report_card(student_id, assessment_id):
    student = Student.query.get_or_404(student_id)
    assessment = Assessment.query.get_or_404(assessment_id)
    class_name = (
        student.placement.class_room.name
        if student.placement
        else student.entry_class
    )
    school = School.query.first()
    cbc_mode = (
        is_lower_secondary_class(class_name)
        and school is not None
        and school.o_level_active
        and school.o_level_grading_module == CBC_GRADING_MODULE_KEY
    )
    if cbc_mode:
        period_results = (
            db.session.query(ExamResult, Assessment, Subject)
            .join(Assessment, Assessment.id == ExamResult.assessment_id)
            .join(Subject, Subject.id == ExamResult.subject_id)
            .filter(
                ExamResult.student_id == student.id,
                Assessment.academic_year_id == assessment.academic_year_id,
                Assessment.term == assessment.term,
                ExamResult.status == "Submitted",
            )
            .order_by(Subject.name, Assessment.id)
            .all()
        )
        results_by_subject = {}
        for result, component_assessment, subject in period_results:
            results_by_subject.setdefault(subject, []).append(
                (result, component_assessment)
            )

        cbc_marks = []
        for subject, component_results in results_by_subject.items():
            formative_score = scale_component_scores(
                component_results,
                "Formative",
            )
            summative_score = scale_component_scores(
                component_results,
                "Summative",
            )
            incomplete = formative_score is None or summative_score is None
            total = (
                None
                if incomplete
                else round(formative_score + summative_score, 2)
            )
            grade, descriptor = (
                cbc_grade(total) if total is not None else ("—", "Incomplete CA Record")
            )
            comments = list(
                dict.fromkeys(
                    result.remarks.strip()
                    for result, _component_assessment in component_results
                    if result.remarks.strip()
                )
            )
            cbc_marks.append(
                {
                    "subject": subject,
                    "formative_score": formative_score,
                    "summative_score": summative_score,
                    "total": total,
                    "grade": grade,
                    "descriptor": descriptor,
                    "incomplete": incomplete,
                    "comments": "; ".join(comments),
                }
            )
        has_incomplete = any(mark["incomplete"] for mark in cbc_marks)
        marks = []
        total_score = 0
        total_maximum = 0
    else:
        marks = (
            db.session.query(ExamResult, Subject)
            .join(Subject, Subject.id == ExamResult.subject_id)
            .filter(
                ExamResult.student_id == student.id,
                ExamResult.assessment_id == assessment.id,
                ExamResult.status == "Submitted",
            )
            .order_by(Subject.name)
            .all()
        )
        total_score = sum(result.score for result, _subject in marks)
        total_maximum = sum(assessment.max_marks for _result, _subject in marks)
        cbc_marks = []
        has_incomplete = False
    return render_template(
        "report_card.html",
        student=student,
        assessment=assessment,
        marks=marks,
        total_score=total_score,
        total_maximum=total_maximum,
        cbc_mode=cbc_mode,
        cbc_marks=cbc_marks,
        has_incomplete=has_incomplete,
    )


@main.route("/attendance")
@login_required
def attendance():
    records = AttendanceRecord.query.order_by(AttendanceRecord.date.desc()).limit(20).all()
    return render_template("module.html", module={"label": "Attendance", "icon": "bi-calendar-check"}, records=records)


@main.route("/examinations")
@login_required
def examinations():
    assessments = Assessment.query.order_by(Assessment.id.desc()).all()
    return render_template("module.html", module={"label": "Examinations and Results", "icon": "bi-clipboard-data"}, records=assessments)


@main.route("/finance")
@login_required
def finance():
    fee_types = FeeType.query.all()
    return render_template("module.html", module={"label": "Fees and Finance", "icon": "bi-cash"}, records=fee_types)


@main.route("/hr")
@login_required
def hr():
    staff = Teacher.query.order_by(Teacher.full_name).all()
    return render_template("module.html", module={"label": "Human Resources", "icon": "bi-person-badge"}, records=staff)


@main.route("/timetable")
@login_required
def timetable():
    return render_template("module.html", module={"label": "Timetable", "icon": "bi-calendar3"}, records=[{"name": "Monday"}, {"name": "Tuesday"}, {"name": "Wednesday"}, {"name": "Thursday"}, {"name": "Friday"}])


@main.route("/parent-portal")
@login_required
def parent_portal():
    return render_template("module.html", module={"label": "Parent and Guardian Portal", "icon": "bi-house-door"}, records=["Fee statements", "Attendance alerts", "Academic reports"])


@main.route("/student-portal")
@login_required
def student_portal():
    if not isinstance(current_user._get_current_object(), StudentAccount):
        return redirect(url_for("main.dashboard"))
    if current_user.must_change_password:
        return redirect(url_for("main.student_change_password"))
    return render_template("student_portal.html", student=current_user.student)


@main.route("/student-portal/change-password", methods=["GET", "POST"])
@login_required
def student_change_password():
    if not isinstance(current_user._get_current_object(), StudentAccount):
        return redirect(url_for("main.dashboard"))
    form = StudentPasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("The temporary password is incorrect.", "danger")
        else:
            current_user.set_password(form.new_password.data)
            current_user.must_change_password = False
            db.session.commit()
            flash("Password updated successfully.", "success")
            return redirect(url_for("main.student_portal"))
    return render_template("student_change_password.html", form=form)


@main.route("/library")
@login_required
def library():
    return render_template("module.html", module={"label": "Library", "icon": "bi-bookshelf"}, records=["Catalog", "Issue records", "Book returns"])


@main.route("/ict")
@login_required
def ict():
    return render_template("module.html", module={"label": "Computer Laboratory and ICT", "icon": "bi-laptop"}, records=["Computers", "Lab bookings", "IT support tickets"])


@main.route("/inventory")
@login_required
def inventory():
    return render_template("module.html", module={"label": "School Inventory", "icon": "bi-box"}, records=["Stock items", "Procurement", "Asset register"])


@main.route("/transport")
@login_required
def transport():
    return render_template("module.html", module={"label": "Transport", "icon": "bi-bus-front"}, records=["Routes", "Vehicle log", "Transport fees"])


@main.route("/boarding")
@login_required
def boarding():
    return render_template("module.html", module={"label": "Boarding and Accommodation", "icon": "bi-hospital"}, records=["Hostels", "Bed allocation", "Welfare updates"])


@main.route("/discipline")
@login_required
def discipline():
    return render_template("module.html", module={"label": "Discipline", "icon": "bi-shield-check"}, records=["Incident register", "Warnings", "Detentions"])


@main.route("/health")
@login_required
def health():
    return render_template("module.html", module={"label": "Health and Welfare", "icon": "bi-heart-pulse"}, records=["Medical records", "Clinic visits", "Nurse notes"])


@main.route("/communication")
@login_required
def communication():
    return render_template("module.html", module={"label": "Communication", "icon": "bi-chat-dots"}, records=["Announcements", "SMS", "Email campaigns"])


@main.route("/reports")
@login_required
def reports():
    return render_template("module.html", module={"label": "Reports and Analytics", "icon": "bi-bar-chart"}, records=["Term report", "Enrollment summary", "Attendance overview"])


@main.route("/security")
@login_required
def security():
    users = User.query.order_by(User.username).all()
    roles = Role.query.order_by(Role.name).all()
    return render_template("module.html", module={"label": "User Management and Security", "icon": "bi-lock"}, users=users, roles=roles)


@main.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    school = School.query.first()
    form = SchoolSettingsForm(obj=school)
    if form.validate_on_submit():
        if (
            form.cbc_formative_weight.data
            + form.cbc_summative_weight.data
            != 100
        ):
            flash("CBC formative and summative weights must total 100%.", "danger")
            return render_template(
                "school_settings.html",
                form=form,
                school=school,
            )
        school_name = form.name.data.strip()
        conflicting_school = School.query.filter(
            School.name == school_name,
            School.id != (school.id if school else None),
        ).first()
        if conflicting_school:
            flash("That school name is already registered.", "danger")
            return render_template(
                "school_settings.html",
                form=form,
                school=school,
            )
        try:
            profile_photo = save_image_upload(
                form.profile_photo.data,
                "school",
            )
        except ValueError as error:
            flash(str(error), "danger")
            return render_template(
                "school_settings.html",
                form=form,
                school=school,
            )
        if school is None:
            school = School(name=school_name)
            db.session.add(school)
        school.name = school_name
        school.slogan = (form.slogan.data or "").strip()
        school.address = (form.address.data or "").strip()
        school.phone = (form.phone.data or "").strip()
        school.alternative_phone = (form.alternative_phone.data or "").strip()
        school.email = (form.email.data or "").strip()
        school.website = (form.website.data or "").strip()
        school.is_active = form.is_active.data
        school.o_level_active = form.o_level_active.data
        school.a_level_active = form.a_level_active.data
        school.o_level_curriculum = (
            form.o_level_curriculum.data or ""
        ).strip()
        school.a_level_curriculum = (
            form.a_level_curriculum.data or ""
        ).strip()
        school.o_level_grading_module = CBC_GRADING_MODULE_KEY
        school.cbc_formative_weight = form.cbc_formative_weight.data
        school.cbc_summative_weight = form.cbc_summative_weight.data
        school.co_education = (form.co_education.data or "").strip()
        school.moes_registered = form.moes_registered.data
        school.uneb_exam_center_valid = form.uneb_exam_center_valid.data
        if profile_photo:
            school.profile_photo = profile_photo
        db.session.add(
            AuditLog(
                actor=current_user.username,
                action="school_information_updated",
                details="Updated school profile information.",
            )
        )
        db.session.commit()
        flash("School information saved.", "success")
        return redirect(url_for("main.settings"))
    return render_template(
        "school_settings.html",
        form=form,
        school=school,
    )


@main.route("/audit")
@login_required
def audit():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(25).all()
    return render_template("module.html", module={"label": "Audit Logs and Backup Management", "icon": "bi-journal-text"}, records=logs)
