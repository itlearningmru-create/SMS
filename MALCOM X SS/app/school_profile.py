from app.extensions import db
from app.models import School


SCHOOL_PROFILE = {
    "name": "Malcolm X Senior Secondary School",
    "address": (
        "West Kifamba Zone, Makindye Division, Kampala, Uganda"
    ),
    "phone": "+256 705 991752",
    "alternative_phone": "+256 414 388627",
    "email": "malcolmsecsch@yahoo.com",
    "is_active": True,
    "o_level_active": True,
    "a_level_active": True,
    "o_level_curriculum": "UNEB Competency-Based Curriculum (CBC)",
    "a_level_curriculum": "Advanced Frameworks",
    "o_level_grading_module": "CBC_20_80",
    "cbc_formative_weight": 20,
    "cbc_summative_weight": 80,
    "co_education": "Mixed (Boys & Girls)",
    "moes_registered": True,
    "uneb_exam_center_valid": True,
}


def register_school_profile() -> School:
    school = School.query.first()
    name_conflict = School.query.filter(
        School.name == SCHOOL_PROFILE["name"],
        School.id != (school.id if school else None),
    ).first()
    if name_conflict:
        raise ValueError(
            f"A different school record already uses {SCHOOL_PROFILE['name']!r}."
        )

    if school is None:
        school = School(**SCHOOL_PROFILE)
    else:
        for field, value in SCHOOL_PROFILE.items():
            setattr(school, field, value)
    db.session.add(school)
    db.session.commit()
    return school
