from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    FileField,
    FloatField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    InputRequired,
    Length,
    NumberRange,
    Optional,
)


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=40)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")


class StudentPasswordForm(FlaskForm):
    current_password = PasswordField("Temporary password", validators=[DataRequired()])
    new_password = PasswordField(
        "New password",
        validators=[DataRequired(), Length(min=12, max=128)],
    )
    confirm_password = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit = SubmitField("Update password")


class StaffPasswordForm(FlaskForm):
    current_password = PasswordField("Current password", validators=[DataRequired()])
    new_password = PasswordField(
        "New password",
        validators=[DataRequired(), Length(min=12, max=128)],
    )
    confirm_password = PasswordField(
        "Confirm new password",
        validators=[DataRequired(), EqualTo("new_password", message="Passwords must match.")],
    )
    submit = SubmitField("Update password")


class StudentForm(FlaskForm):
    student_no = StringField("Student number", validators=[DataRequired(), Length(min=3, max=30)])
    first_name = StringField("First name", validators=[DataRequired(), Length(min=2, max=60)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(min=2, max=60)])
    gender = SelectField("Gender", choices=[("Male", "Male"), ("Female", "Female"), ("Other", "Other")], validators=[DataRequired()])
    dob = DateField("Date of birth", format="%Y-%m-%d", validators=[DataRequired()])
    email = StringField("Email", validators=[Optional(), Email()])
    phone = StringField("Phone")
    nationality = StringField("Nationality", default="Ugandan")
    class_room_id = SelectField(
        "Class and stream",
        coerce=int,
        validators=[DataRequired()],
    )
    status = SelectField("Admission status", choices=[("Applied", "Applied"), ("Under Review", "Under Review"), ("Accepted", "Accepted"), ("Enrolled", "Enrolled"), ("Rejected", "Rejected")], default="Applied")
    notes = TextAreaField("Notes")
    passport_photo = FileField("Passport photo")
    submit = SubmitField("Save student")


class StudentPhotoForm(FlaskForm):
    passport_photo = FileField("Passport photo")
    submit = SubmitField("Upload passport photo")


class TeacherForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=80)])
    department = StringField("Department", validators=[DataRequired(), Length(max=80)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    submit = SubmitField("Create teacher account")


class StaffAccountForm(FlaskForm):
    first_name = StringField("First name", validators=[DataRequired(), Length(max=80)])
    last_name = StringField("Last name", validators=[DataRequired(), Length(max=80)])
    role = SelectField(
        "Account role",
        choices=[
            ("Director of Studies", "Director of Studies (DOS)"),
            ("Headmaster", "Headmaster (HM)"),
            ("Bursar", "Bursar"),
        ],
        validators=[DataRequired()],
    )
    submit = SubmitField("Create account")


class TeachingAssignmentForm(FlaskForm):
    teacher_id = SelectField("Teacher", coerce=int, validators=[DataRequired()])
    subject_id = SelectField("Subject", coerce=int, validators=[DataRequired()])
    class_room_id = SelectField("Class and stream", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Assign subject")


class MarkEntryForm(FlaskForm):
    student_id = SelectField("Student", coerce=int, validators=[DataRequired()])
    assessment_id = SelectField("Assessment", coerce=int, validators=[DataRequired()])
    score = FloatField(
        "Mark",
        validators=[InputRequired(), NumberRange(min=0)],
    )
    remarks = StringField("Teacher comment", validators=[Optional(), Length(max=500)])
    submit = SubmitField("Save mark")


class SchoolSettingsForm(FlaskForm):
    name = StringField("School name", validators=[DataRequired(), Length(max=150)])
    slogan = StringField("Slogan", validators=[Optional(), Length(max=150)])
    address = TextAreaField("Address", validators=[Optional(), Length(max=2000)])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    alternative_phone = StringField(
        "Alternative phone",
        validators=[Optional(), Length(max=30)],
    )
    profile_photo = FileField("School profile picture")
    email = StringField("Email", validators=[Optional(), Email(), Length(max=120)])
    website = StringField("Website", validators=[Optional(), Length(max=120)])
    is_active = BooleanField("School is active")
    o_level_active = BooleanField("O-Level track is active")
    a_level_active = BooleanField("A-Level track is active")
    o_level_curriculum = StringField(
        "O-Level curriculum",
        validators=[Optional(), Length(max=100)],
    )
    a_level_curriculum = StringField(
        "A-Level curriculum",
        validators=[Optional(), Length(max=100)],
    )
    cbc_formative_weight = IntegerField(
        "CBC formative weight (%)",
        validators=[InputRequired(), NumberRange(min=0, max=100)],
    )
    cbc_summative_weight = IntegerField(
        "CBC summative weight (%)",
        validators=[InputRequired(), NumberRange(min=0, max=100)],
    )
    co_education = StringField(
        "Co-education type",
        validators=[Optional(), Length(max=40)],
    )
    moes_registered = BooleanField("Registered with MoES")
    uneb_exam_center_valid = BooleanField("Valid UNEB examination centre")
    submit = SubmitField("Save school information")


class ClassRoomForm(FlaskForm):
    name = StringField("Class", validators=[DataRequired(), Length(max=80)])
    stream = StringField("Stream", validators=[Optional(), Length(max=30)])
    level = StringField("Level", validators=[DataRequired(), Length(max=30)])
    academic_year = StringField("Academic year", validators=[DataRequired(), Length(max=20)])
    capacity = IntegerField("Capacity", validators=[InputRequired(), NumberRange(min=1)])
    submit = SubmitField("Add class and stream")


class SubjectForm(FlaskForm):
    name = StringField("Subject name", validators=[DataRequired(), Length(max=100)])
    code = StringField("Subject code", validators=[DataRequired(), Length(max=20)])
    level = StringField("Level", validators=[DataRequired(), Length(max=40)])
    category = StringField("Category", validators=[DataRequired(), Length(max=30)])
    submit = SubmitField("Add subject")


class AcademicYearForm(FlaskForm):
    name = StringField("Academic year", validators=[DataRequired(), Length(max=30)])
    start_date = DateField("Start date", format="%Y-%m-%d", validators=[DataRequired()])
    end_date = DateField("End date", format="%Y-%m-%d", validators=[DataRequired()])
    submit = SubmitField("Add academic year")


class AssessmentForm(FlaskForm):
    name = StringField("Assessment name", validators=[DataRequired(), Length(max=80)])
    academic_year_id = SelectField("Academic year", coerce=int, validators=[DataRequired()])
    term = StringField("Term", validators=[DataRequired(), Length(max=40)])
    component = SelectField(
        "CBC component",
        choices=[
            ("Formative", "Formative assessment (20%)"),
            ("Summative", "Summative assessment (80%)"),
        ],
        validators=[DataRequired()],
    )
    max_marks = IntegerField(
        "Maximum mark",
        validators=[InputRequired(), NumberRange(min=1)],
    )
    submit = SubmitField("Add assessment")
