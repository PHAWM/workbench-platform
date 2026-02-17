from enum import IntEnum

class AuditStatus(IntEnum):
    NOT_STARTED = 0
    IN_PROGRESS = 1
    FINISHED = 2

class RecommendationStatus(IntEnum):
    NOT_EVALUATED = 0
    INCONCLUSIVE = 1
    FAIL = 2
    PASS = 3

STATUS_TEXT_MAP = {
    AuditStatus.NOT_STARTED: "Not Started",
    AuditStatus.IN_PROGRESS: "In Progress", 
    AuditStatus.FINISHED: "Finished"
}

RECOMMENDATION_TEXT_MAP = {
    RecommendationStatus.NOT_EVALUATED: "Not Evaluated",
    RecommendationStatus.INCONCLUSIVE: "Inconclusive",
    RecommendationStatus.FAIL: "Fail",
    RecommendationStatus.PASS: "Pass"
}