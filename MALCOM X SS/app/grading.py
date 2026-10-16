import re
from collections.abc import Sequence

from app.models import Assessment, ExamResult


CBC_COMPONENT_WEIGHTS = {
    "Formative": 20.0,
    "Summative": 80.0,
}
CBC_GRADING_MODULE_KEY = "CBC_20_80"

CBC_GRADE_BANDS = (
    (80, "A", "Exceptional"),
    (70, "B", "Outstanding"),
    (60, "C", "Satisfactory"),
    (50, "D", "Basic"),
    (0, "E", "Elementary"),
)


def is_lower_secondary_class(class_name: str) -> bool:
    match = re.fullmatch(r"(?:S|Senior\s*)([1-4])", class_name.strip(), re.IGNORECASE)
    return match is not None


def scale_component_scores(
    results: Sequence[tuple[ExamResult, Assessment]],
    component: str,
) -> float | None:
    matching_results = [
        (result, assessment)
        for result, assessment in results
        if assessment.component == component
    ]
    if not matching_results:
        return None
    weight = CBC_COMPONENT_WEIGHTS[component]
    average_percentage = sum(
        result.score / assessment.max_marks
        for result, assessment in matching_results
    ) / len(matching_results)
    return round(average_percentage * weight, 2)


def cbc_grade(total_score: float) -> tuple[str, str]:
    for minimum, grade, descriptor in CBC_GRADE_BANDS:
        if total_score >= minimum:
            return grade, descriptor
    return "E", "Elementary"
