from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db


roles_permissions = db.Table(
    "roles_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("role.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permission.id"), primary_key=True),
)


class Role(db.Model):
    __tablename__ = "role"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    permissions: Mapped[list["Permission"]] = relationship(
        "Permission",
        secondary=roles_permissions,
        back_populates="roles",
        cascade="all, delete",
    )
    users: Mapped[list["User"]] = relationship("User", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


class Permission(db.Model):
    __tablename__ = "permission"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    roles: Mapped[list[Role]] = relationship(
        "Role",
        secondary=roles_permissions,
        back_populates="permissions",
        cascade="all, delete",
    )

    def __repr__(self) -> str:
        return f"<Permission {self.name}>"


class User(UserMixin, db.Model):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    role_id: Mapped[int | None] = mapped_column(ForeignKey("role.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    role: Mapped[Role | None] = relationship("Role", back_populates="users")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def set_password(self, password: str) -> None:
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


class School(db.Model):
    __tablename__ = "school"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    slogan: Mapped[str] = mapped_column(String(150), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    alternative_phone: Mapped[str] = mapped_column(String(30), default="")
    email: Mapped[str] = mapped_column(String(120), default="")
    website: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    o_level_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    a_level_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    o_level_curriculum: Mapped[str] = mapped_column(
        String(100),
        default="UNEB Competency-Based Curriculum (CBC)",
    )
    a_level_curriculum: Mapped[str] = mapped_column(
        String(100),
        default="Advanced Frameworks",
    )
    o_level_grading_module: Mapped[str] = mapped_column(
        String(40),
        default="CBC_20_80",
    )
    cbc_formative_weight: Mapped[int] = mapped_column(Integer, default=20)
    cbc_summative_weight: Mapped[int] = mapped_column(Integer, default=80)
    co_education: Mapped[str] = mapped_column(String(40), default="Mixed")
    moes_registered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uneb_exam_center_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    profile_photo: Mapped[str] = mapped_column(String(255), default="")


class Student(db.Model):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_no: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    gender: Mapped[str] = mapped_column(String(20), default="Male")
    dob: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    nationality: Mapped[str] = mapped_column(String(50), default="Ugandan")
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    entry_class: Mapped[str] = mapped_column(String(40), default="Senior 1")
    status: Mapped[str] = mapped_column(String(30), default="Applied")
    notes: Mapped[str] = mapped_column(Text, default="")
    passport_photo: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    account: Mapped["StudentAccount | None"] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        uselist=False,
    )
    placement: Mapped["StudentClassPlacement | None"] = relationship(
        back_populates="student",
        cascade="all, delete-orphan",
        uselist=False,
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class StudentAccount(UserMixin, db.Model):
    __tablename__ = "student_account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("student.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    student: Mapped["Student"] = relationship(back_populates="account")

    @property
    def username(self) -> str:
        return self.student.student_no

    @property
    def full_name(self) -> str:
        return self.student.full_name

    def get_id(self) -> str:
        return f"student:{self.id}"

    def set_password(self, password: str) -> None:
        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, password)


class Teacher(db.Model):
    __tablename__ = "teacher"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(50), default="Teacher")
    department: Mapped[str] = mapped_column(String(80), default="Academic")
    phone: Mapped[str] = mapped_column(String(30), default="")
    assignments: Mapped[list["TeachingAssignment"]] = relationship(
        back_populates="teacher",
        cascade="all, delete-orphan",
    )


class Subject(db.Model):
    __tablename__ = "subject"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    level: Mapped[str] = mapped_column(String(40), default="O-Level")
    category: Mapped[str] = mapped_column(String(30), default="Core")
    assignments: Mapped[list["TeachingAssignment"]] = relationship(
        back_populates="subject",
        cascade="all, delete-orphan",
    )


class ClassRoom(db.Model):
    __tablename__ = "class_room"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    stream: Mapped[str] = mapped_column(String(30), default="A")
    level: Mapped[str] = mapped_column(String(30), default="Senior 1")
    academic_year: Mapped[str] = mapped_column(String(20), default="2025")
    capacity: Mapped[int] = mapped_column(Integer, default=40)
    class_teacher: Mapped[str] = mapped_column(String(120), default="")
    placements: Mapped[list["StudentClassPlacement"]] = relationship(
        back_populates="class_room",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list["TeachingAssignment"]] = relationship(
        back_populates="class_room",
        cascade="all, delete-orphan",
    )

    @property
    def label(self) -> str:
        return f"{self.name} {self.stream}".strip()


class StudentClassPlacement(db.Model):
    __tablename__ = "student_class_placement"

    student_id: Mapped[int] = mapped_column(
        ForeignKey("student.id", ondelete="CASCADE"),
        primary_key=True,
    )
    class_room_id: Mapped[int] = mapped_column(
        ForeignKey("class_room.id", ondelete="CASCADE"),
        nullable=False,
    )
    student: Mapped["Student"] = relationship(back_populates="placement")
    class_room: Mapped["ClassRoom"] = relationship(back_populates="placements")


class TeachingAssignment(db.Model):
    __tablename__ = "teaching_assignment"
    __table_args__ = (
        UniqueConstraint(
            "teacher_id",
            "subject_id",
            "class_room_id",
            name="uq_teaching_assignment_load",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teacher.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subject.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_room_id: Mapped[int] = mapped_column(
        ForeignKey("class_room.id", ondelete="CASCADE"),
        nullable=False,
    )
    teacher: Mapped["Teacher"] = relationship(back_populates="assignments")
    subject: Mapped["Subject"] = relationship(back_populates="assignments")
    class_room: Mapped["ClassRoom"] = relationship(back_populates="assignments")


class UserPasswordPolicy(db.Model):
    __tablename__ = "user_password_policy"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    must_change_password: Mapped[bool] = mapped_column(default=True, nullable=False)


class AcademicYear(db.Model):
    __tablename__ = "academic_year"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    start_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Assessment(db.Model):
    __tablename__ = "assessment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    academic_year_id: Mapped[int] = mapped_column(ForeignKey("academic_year.id"), nullable=False)
    term: Mapped[str] = mapped_column(String(40), default="Term 1")
    component: Mapped[str] = mapped_column(
        String(20),
        default="Summative",
        server_default="Summative",
        nullable=False,
    )
    max_marks: Mapped[int] = mapped_column(Integer, default=100)
    status: Mapped[str] = mapped_column(String(20), default="Open")
    academic_year: Mapped["AcademicYear"] = relationship()


class ExamResult(db.Model):
    __tablename__ = "exam_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subject.id"), nullable=False)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessment.id"), nullable=False)
    score: Mapped[float] = mapped_column(default=0.0)
    grade: Mapped[str] = mapped_column(String(10), default="-")
    remarks: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="Draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeeType(db.Model):
    __tablename__ = "fee_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    amount: Mapped[float] = mapped_column(default=0.0)
    description: Mapped[str] = mapped_column(Text, default="")


class FeeInvoice(db.Model):
    __tablename__ = "fee_invoice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), nullable=False)
    fee_type_id: Mapped[int] = mapped_column(ForeignKey("fee_type.id"), nullable=False)
    amount: Mapped[float] = mapped_column(default=0.0)
    balance: Mapped[float] = mapped_column(default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="Unpaid")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AttendanceRecord(db.Model):
    __tablename__ = "attendance_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("student.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="Present")


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(160), nullable=False)
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
