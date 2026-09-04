"""Data models for rubric types and grading."""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RubricType(str, Enum):
    """Available rubric types."""
    SC = "SC"  # Simulated Conversation
    QA_OP_SO = "QA_OP_SO"  # Question & Answer, Oral Presentation, Situation/Opinion


class RubricScores(BaseModel):
    """Scores for each rubric dimension (0-3 scale)."""
    task_completion: int = Field(..., ge=0, le=3, description="Task completion score")
    topic_development: int = Field(..., ge=0, le=3, description="Topic development score")
    language_use: int = Field(..., ge=0, le=3, description="Language use score")
    
    @property
    def total_score(self) -> int:
        """Calculate total score."""
        return self.task_completion + self.topic_development + self.language_use
    
    @property
    def average_score(self) -> float:
        """Calculate average score."""
        return self.total_score / 3


class Grade(BaseModel):
    """Grade model for storing evaluation results."""
    id: Optional[str] = None
    audio_id: str = Field(..., description="ID of the audio file being graded")
    rubric_type: RubricType = Field(..., description="Type of rubric used")
    scores: RubricScores = Field(..., description="Scores for each dimension")
    score_penalty: int = Field(default=0, ge=-9, le=0, description="Penalty applied to total score (0 = none, -1 = length violation)")
    comments: Optional[str] = Field(None, description="Additional feedback/comments")
    grader_name: Optional[str] = Field(None, description="Name of the grader")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "audio_id": "abc123",
                "rubric_type": "SC",
                "scores": {
                    "task_completion": 3,
                    "topic_development": 2,
                    "language_use": 3
                },
                "comments": "Excellent conversational skills with minor hesitations.",
                "grader_name": "Prof. Smith"
            }
        }


class RubricCriteria(BaseModel):
    """Detailed criteria for a rubric level."""
    score: int = Field(..., ge=0, le=3)
    level_name: str
    task_completion: list[str]
    topic_development: list[str]
    language_use: list[str]


class RubricDefinition(BaseModel):
    """Complete rubric definition with all criteria."""
    rubric_type: RubricType
    name: str
    description: str
    criteria: list[RubricCriteria]


# Rubric definitions based on the PDFs
SC_RUBRIC = RubricDefinition(
    rubric_type=RubricType.SC,
    name="Simulated Conversation",
    description="For interactive, back-and-forth conversational tasks",
    criteria=[
        RubricCriteria(
            score=3,
            level_name="High",
            task_completion=[
                "Fully addresses and completes the task",
                "Responds fully to all or almost all of the parts/prompts of the conversation"
            ],
            topic_development=[
                "Responses relate directly to the topic",
                "Include a well-developed treatment of all or almost all the elements in the thread of the conversation"
            ],
            language_use=[
                "Demonstrates high or mid-high degree of control of a variety of structures",
                "A few grammatical errors occur with no evident patterns",
                "Varied vocabulary appropriate for the content used with precision",
                "High level of fluency",
                "Very good pronunciation",
                "Well-organized, generally coherent responses",
                "Register is appropriate (accurate social and/or cultural references included)"
            ]
        ),
        RubricCriteria(
            score=2,
            level_name="Mid-High",
            task_completion=[
                "Addresses and completes the task",
                "Responds to all or almost all of the parts/prompts of the conversation"
            ],
            topic_development=[
                "Responses relate to the topic",
                "Include most elements in the thread of the conversation"
            ],
            language_use=[
                "Demonstrates a moderate degree of control of a variety of structures",
                "Some grammatical errors occur",
                "Appropriate vocabulary with occasional errors such as making up words or code-switching",
                "Moderate level of fluency with occasional hesitance",
                "Some successful self correction",
                "Good pronunciation",
                "Organized responses with some coherence",
                "Register is usually appropriate"
            ]
        ),
        RubricCriteria(
            score=1,
            level_name="Mid-Low",
            task_completion=[
                "Addresses and completes some parts of the task",
                "Responds to most parts/prompts of the conversation"
            ],
            topic_development=[
                "Responses relate moderately to the topic",
                "Include some elements in the thread of the conversation"
            ],
            language_use=[
                "Demonstrates a lack of control of a variety of structures",
                "Frequent grammatical errors occur",
                "Limited vocabulary, frequent errors such as making up words and code-switching",
                "Low level of fluency with frequent hesitance",
                "Fair pronunciation with interference from another language",
                "Disorganized responses with little coherence",
                "Register is inappropriate"
            ]
        ),
        RubricCriteria(
            score=0,
            level_name="Low",
            task_completion=[
                "Partially addresses and/or partially completes the task",
                "Responds inappropriately to some parts/prompts of the conversation"
            ],
            topic_development=[
                "Responses relate minimally to the topic",
                "Include few elements in the thread of the conversation"
            ],
            language_use=[
                "Demonstrates a lack of control of numerous structures",
                "Numerous grammatical errors impede communication",
                "Insufficient vocabulary; constant interference from another language",
                "Poor fluency with labored expression",
                "Poor pronunciation, which affects comprehension",
                "Disorganized responses with no coherence",
                "Minimal to no attention to register"
            ]
        )
    ]
)

QA_OP_SO_RUBRIC = RubricDefinition(
    rubric_type=RubricType.QA_OP_SO,
    name="Question & Answer / Oral Presentation / Situation-Opinion",
    description="For monologue-style responses and presentations",
    criteria=[
        RubricCriteria(
            score=3,
            level_name="High",
            task_completion=[
                "Fully addresses and completes the task"
            ],
            topic_development=[
                "Directly relates to the topic, well-developed treatment of the topic",
                "All or almost all supporting details or examples are appropriate and effective",
                "All or almost all content information is accurate"
            ],
            language_use=[
                "Demonstrates high or mid-high degree of control of a variety of structures",
                "A very few grammatical errors occur with no evident patterns",
                "Varied vocabulary appropriate for the content used with precision",
                "High level of fluency",
                "Very good pronunciation",
                "Well-organized, generally coherent response",
                "Register is appropriate (accurate social and/or cultural references included)"
            ]
        ),
        RubricCriteria(
            score=2,
            level_name="Mid-High",
            task_completion=[
                "Addresses and completes the task"
            ],
            topic_development=[
                "Relates to the topic",
                "Most supporting details or examples are well defined",
                "Most content is accurate with occasional inaccurate information"
            ],
            language_use=[
                "Demonstrates a moderate degree of control of a variety of structures",
                "Some grammatical errors occur",
                "Appropriate vocabulary with occasional errors such as making up words or code-switching",
                "Moderate level of fluency with occasional hesitance",
                "Some successful self correction",
                "Good pronunciation",
                "Organized response with some coherence",
                "Register is usually appropriate"
            ]
        ),
        RubricCriteria(
            score=1,
            level_name="Mid-Low",
            task_completion=[
                "Addresses and completes the task"
            ],
            topic_development=[
                "Moderately relates to the topic",
                "Some supporting details or examples are vague or not well defined",
                "Some content is accurate with significant inaccurate information"
            ],
            language_use=[
                "Demonstrates a lack of control of a variety of structures",
                "Frequent grammatical errors occur",
                "Limited vocabulary; frequent errors such as making up words and code-switching",
                "Low level of fluency with frequent hesitance",
                "Fair pronunciation with interference from another language",
                "Disorganized response with little coherence",
                "Register is inappropriate"
            ]
        ),
        RubricCriteria(
            score=0,
            level_name="Low",
            task_completion=[
                "Partially addresses and/or partially completes the task"
            ],
            topic_development=[
                "Minimally relates to the topic",
                "Most supporting details or examples are irrelevant or not effective",
                "Most content information is inaccurate"
            ],
            language_use=[
                "Demonstrates a lack of control of numerous structures",
                "Numerous grammatical errors impede communication",
                "Insufficient vocabulary; constant interference from another language",
                "Poor fluency with labored expression",
                "Poor pronunciation, which affects comprehension",
                "Disorganized response with no coherence",
                "Minimal to no attention to register"
            ]
        )
    ]
)


def get_rubric_definition(rubric_type: RubricType) -> RubricDefinition:
    """Get rubric definition by type."""
    if rubric_type == RubricType.SC:
        return SC_RUBRIC
    elif rubric_type == RubricType.QA_OP_SO:
        return QA_OP_SO_RUBRIC
    else:
        raise ValueError(f"Unknown rubric type: {rubric_type}")
