"""Regression test models"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from pydantic import BaseModel

from ..db import Base


# ==================== SQLAlchemy Models ====================

class RegressionTestCase(Base):
    """Test case definition for regression testing"""
    __tablename__ = 'regression_test_cases'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    category = Column(String(50), nullable=False)  # rag/llm/e2e
    query = Column(Text, nullable=False)
    expected_ku_ids = Column(JSON, default=list)
    expected_answer = Column(Text)
    evaluation_criteria = Column(JSON, default=dict)
    tags = Column(JSON, default=list)
    is_active = Column(Boolean, default=True)
    created_by = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    results = relationship("RegressionTestResult", back_populates="case")


class RegressionTestRun(Base):
    """Test execution run"""
    __tablename__ = 'regression_test_runs'
    
    id = Column(Integer, primary_key=True)
    run_id = Column(String(50), unique=True, nullable=False)
    status = Column(String(20), default='running')  # running/completed/failed
    total_cases = Column(Integer, default=0)
    passed_cases = Column(Integer, default=0)
    failed_cases = Column(Integer, default=0)
    review_cases = Column(Integer, default=0)
    pass_rate = Column(Float)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    triggered_by = Column(String(50))
    config = Column(JSON, default=dict)
    
    # Relationships
    results = relationship("RegressionTestResult", back_populates="run", cascade="all, delete-orphan")


class RegressionTestResult(Base):
    """Individual test result"""
    __tablename__ = 'regression_test_results'
    
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey('regression_test_runs.id', ondelete='CASCADE'), nullable=False)
    case_id = Column(Integer, ForeignKey('regression_test_cases.id', ondelete='CASCADE'), nullable=False)
    actual_answer = Column(Text)
    retrieved_ku_ids = Column(JSON, default=list)
    retrieval_score = Column(Float)
    answer_score = Column(Float)
    llm_evaluation = Column(JSON)
    manual_review = Column(String(20), default='pending')  # pending/pass/fail
    manual_comment = Column(Text)
    reviewed_by = Column(String(50))
    reviewed_at = Column(DateTime)
    execution_time_ms = Column(Integer)
    status = Column(String(20), default='pending')  # pass/fail/review/pending
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    run = relationship("RegressionTestRun", back_populates="results")
    case = relationship("RegressionTestCase", back_populates="results")


# ==================== Pydantic Schemas ====================

class TestCaseCreate(BaseModel):
    name: str
    category: str  # rag/llm/e2e
    query: str
    expected_ku_ids: List[str] = []
    expected_answer: Optional[str] = None
    evaluation_criteria: Dict[str, Any] = {}
    tags: List[str] = []
    is_active: bool = True


class TestCaseUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    query: Optional[str] = None
    expected_ku_ids: Optional[List[str]] = None
    expected_answer: Optional[str] = None
    evaluation_criteria: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = None


class TestCaseResponse(BaseModel):
    id: int
    name: str
    category: str
    query: str
    expected_ku_ids: List[str]
    expected_answer: Optional[str]
    evaluation_criteria: Dict[str, Any]
    tags: List[str]
    is_active: bool
    created_by: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]
    
    class Config:
        from_attributes = True


class TestRunCreate(BaseModel):
    category_filter: Optional[str] = None  # Filter by category
    tag_filter: Optional[List[str]] = None  # Filter by tags
    case_ids: Optional[List[int]] = None  # Specific case IDs to run


class TestRunResponse(BaseModel):
    id: int
    run_id: str
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    review_cases: int
    pass_rate: Optional[float]
    started_at: Optional[str]
    completed_at: Optional[str]
    triggered_by: Optional[str]
    
    class Config:
        from_attributes = True


class LLMEvaluation(BaseModel):
    accuracy: float
    completeness: float
    relevance: float
    clarity: float
    overall: float
    comment: str


class TestResultResponse(BaseModel):
    id: int
    run_id: int
    case_id: int
    case_name: Optional[str] = None
    case_query: Optional[str] = None
    case_category: Optional[str] = None
    actual_answer: Optional[str]
    retrieved_ku_ids: List[str]
    retrieval_score: Optional[float]
    answer_score: Optional[float]
    llm_evaluation: Optional[Dict[str, Any]]
    manual_review: str
    manual_comment: Optional[str]
    reviewed_by: Optional[str]
    reviewed_at: Optional[str]
    execution_time_ms: Optional[int]
    status: str
    error_message: Optional[str]
    created_at: Optional[str]
    
    class Config:
        from_attributes = True


class ManualReviewRequest(BaseModel):
    review: str  # pass/fail
    comment: Optional[str] = None


class TestCaseImport(BaseModel):
    cases: List[TestCaseCreate]

