"""
Regression Testing API endpoints
回归测试管理 API
"""
import uuid
import asyncio
import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..db import get_db
from ..models.regression import (
    RegressionTestCase,
    RegressionTestRun,
    RegressionTestResult,
    TestCaseCreate,
    TestCaseUpdate,
    TestCaseResponse,
    TestRunCreate,
    TestRunResponse,
    TestResultResponse,
    ManualReviewRequest,
    TestCaseImport,
)
from ..services.regression_evaluator import get_evaluator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/regression", tags=["regression"])


# ==================== Helper Functions ====================

def case_to_response(case: RegressionTestCase) -> TestCaseResponse:
    """Convert SQLAlchemy model to Pydantic response"""
    return TestCaseResponse(
        id=case.id,
        name=case.name,
        category=case.category,
        query=case.query,
        expected_ku_ids=case.expected_ku_ids or [],
        expected_answer=case.expected_answer,
        evaluation_criteria=case.evaluation_criteria or {},
        tags=case.tags or [],
        is_active=case.is_active,
        created_by=case.created_by,
        created_at=case.created_at.isoformat() if case.created_at else None,
        updated_at=case.updated_at.isoformat() if case.updated_at else None,
    )


def run_to_response(run: RegressionTestRun) -> TestRunResponse:
    """Convert SQLAlchemy model to Pydantic response"""
    return TestRunResponse(
        id=run.id,
        run_id=run.run_id,
        status=run.status,
        total_cases=run.total_cases,
        passed_cases=run.passed_cases,
        failed_cases=run.failed_cases,
        review_cases=run.review_cases,
        pass_rate=run.pass_rate,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        triggered_by=run.triggered_by,
    )


def result_to_response(result: RegressionTestResult, case: RegressionTestCase = None) -> TestResultResponse:
    """Convert SQLAlchemy model to Pydantic response"""
    return TestResultResponse(
        id=result.id,
        run_id=result.run_id,
        case_id=result.case_id,
        case_name=case.name if case else None,
        case_query=case.query if case else None,
        case_category=case.category if case else None,
        actual_answer=result.actual_answer,
        retrieved_ku_ids=result.retrieved_ku_ids or [],
        retrieval_score=result.retrieval_score,
        answer_score=result.answer_score,
        llm_evaluation=result.llm_evaluation,
        manual_review=result.manual_review,
        manual_comment=result.manual_comment,
        reviewed_by=result.reviewed_by,
        reviewed_at=result.reviewed_at.isoformat() if result.reviewed_at else None,
        execution_time_ms=result.execution_time_ms,
        status=result.status,
        error_message=result.error_message,
        created_at=result.created_at.isoformat() if result.created_at else None,
    )


# ==================== Test Case Endpoints ====================

@router.get("/cases", response_model=List[TestCaseResponse])
def list_test_cases(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List all test cases with optional filters"""
    query = db.query(RegressionTestCase)
    
    if category:
        query = query.filter(RegressionTestCase.category == category)
    
    if is_active is not None:
        query = query.filter(RegressionTestCase.is_active == is_active)
    
    if tag:
        query = query.filter(RegressionTestCase.tags.contains([tag]))
    
    cases = query.order_by(RegressionTestCase.created_at.desc()).offset(skip).limit(limit).all()
    
    return [case_to_response(c) for c in cases]


@router.post("/cases", response_model=TestCaseResponse)
def create_test_case(
    request: TestCaseCreate,
    db: Session = Depends(get_db),
):
    """Create a new test case"""
    case = RegressionTestCase(
        name=request.name,
        category=request.category,
        query=request.query,
        expected_ku_ids=request.expected_ku_ids,
        expected_answer=request.expected_answer,
        evaluation_criteria=request.evaluation_criteria,
        tags=request.tags,
        is_active=request.is_active,
        created_by="admin",  # TODO: Get from auth
    )
    
    db.add(case)
    db.commit()
    db.refresh(case)
    
    return case_to_response(case)


@router.get("/cases/{case_id}", response_model=TestCaseResponse)
def get_test_case(case_id: int, db: Session = Depends(get_db)):
    """Get a specific test case"""
    case = db.query(RegressionTestCase).filter(RegressionTestCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")
    return case_to_response(case)


@router.put("/cases/{case_id}", response_model=TestCaseResponse)
def update_test_case(
    case_id: int,
    request: TestCaseUpdate,
    db: Session = Depends(get_db),
):
    """Update a test case"""
    case = db.query(RegressionTestCase).filter(RegressionTestCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")
    
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(case, key, value)
    
    case.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(case)
    
    return case_to_response(case)


@router.delete("/cases/{case_id}")
def delete_test_case(case_id: int, db: Session = Depends(get_db)):
    """Delete a test case"""
    case = db.query(RegressionTestCase).filter(RegressionTestCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")
    
    db.delete(case)
    db.commit()
    
    return {"message": "Test case deleted"}


@router.post("/cases/import")
def import_test_cases(
    request: TestCaseImport,
    db: Session = Depends(get_db),
):
    """Bulk import test cases"""
    imported = 0
    errors = []
    
    for i, case_data in enumerate(request.cases):
        try:
            case = RegressionTestCase(
                name=case_data.name,
                category=case_data.category,
                query=case_data.query,
                expected_ku_ids=case_data.expected_ku_ids,
                expected_answer=case_data.expected_answer,
                evaluation_criteria=case_data.evaluation_criteria,
                tags=case_data.tags,
                is_active=case_data.is_active,
                created_by="import",
            )
            db.add(case)
            imported += 1
        except Exception as e:
            errors.append({"index": i, "error": str(e)})
    
    db.commit()
    
    return {
        "imported": imported,
        "total": len(request.cases),
        "errors": errors,
    }


# ==================== Test Run Endpoints ====================

async def execute_test_run(run_id: int, case_ids: List[int], db_url: str):
    """
    Background task to execute test cases.
    This runs asynchronously and updates the database as it progresses.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    evaluator = get_evaluator()
    
    try:
        run = db.query(RegressionTestRun).filter(RegressionTestRun.id == run_id).first()
        if not run:
            logger.error(f"Test run {run_id} not found")
            return
        
        passed = 0
        failed = 0
        review = 0
        
        for case_id in case_ids:
            case = db.query(RegressionTestCase).filter(RegressionTestCase.id == case_id).first()
            if not case:
                continue
            
            try:
                # Execute evaluation
                result = await evaluator.evaluate_case(
                    query=case.query,
                    expected_ku_ids=case.expected_ku_ids or [],
                    expected_answer=case.expected_answer,
                    evaluation_criteria=case.evaluation_criteria or {},
                    category=case.category,
                )
                
                # Create result record
                test_result = RegressionTestResult(
                    run_id=run_id,
                    case_id=case_id,
                    actual_answer=result.actual_answer,
                    retrieved_ku_ids=result.retrieved_ku_ids,
                    retrieval_score=result.retrieval_score,
                    answer_score=result.answer_score,
                    llm_evaluation=result.ragas_scores,
                    execution_time_ms=result.execution_time_ms,
                    status=result.status,
                    error_message=result.error_message,
                    manual_review="pending" if result.status == "review" else "pending",
                )
                
                db.add(test_result)
                
                # Update counters
                if result.status == "pass":
                    passed += 1
                elif result.status == "fail":
                    failed += 1
                else:
                    review += 1
                
                # Update run progress
                run.passed_cases = passed
                run.failed_cases = failed
                run.review_cases = review
                db.commit()
                
            except Exception as e:
                logger.error(f"Error evaluating case {case_id}: {e}")
                
                # Record failed result
                test_result = RegressionTestResult(
                    run_id=run_id,
                    case_id=case_id,
                    status="fail",
                    error_message=str(e),
                )
                db.add(test_result)
                failed += 1
                db.commit()
        
        # Finalize run
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        run.pass_rate = (passed / run.total_cases * 100) if run.total_cases > 0 else 0
        db.commit()
        
        logger.info(f"Test run {run.run_id} completed: {passed} passed, {failed} failed, {review} review")
        
    except Exception as e:
        logger.error(f"Test run failed: {e}")
        run = db.query(RegressionTestRun).filter(RegressionTestRun.id == run_id).first()
        if run:
            run.status = "failed"
            run.completed_at = datetime.utcnow()
            db.commit()
    finally:
        await evaluator.close()
        db.close()


@router.post("/runs", response_model=TestRunResponse)
def create_test_run(
    request: TestRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create and start a new test run"""
    # Get test cases to run
    query = db.query(RegressionTestCase).filter(RegressionTestCase.is_active == True)
    
    if request.category_filter:
        query = query.filter(RegressionTestCase.category == request.category_filter)
    
    if request.case_ids:
        query = query.filter(RegressionTestCase.id.in_(request.case_ids))
    
    if request.tag_filter:
        for tag in request.tag_filter:
            query = query.filter(RegressionTestCase.tags.contains([tag]))
    
    cases = query.all()
    
    if not cases:
        raise HTTPException(status_code=400, detail="No test cases match the criteria")
    
    # Create run record
    run = RegressionTestRun(
        run_id=f"run-{uuid.uuid4().hex[:8]}",
        status="running",
        total_cases=len(cases),
        triggered_by="admin",  # TODO: Get from auth
        config={
            "category_filter": request.category_filter,
            "tag_filter": request.tag_filter,
            "case_ids": request.case_ids,
        },
    )
    
    db.add(run)
    db.commit()
    db.refresh(run)
    
    # Get database URL for background task
    from ..config import settings
    db_url = settings.database_url
    
    # Start background execution
    case_ids = [c.id for c in cases]
    
    # Use asyncio to run the background task
    async def run_task():
        await execute_test_run(run.id, case_ids, db_url)
    
    background_tasks.add_task(asyncio.run, run_task())
    
    return run_to_response(run)


@router.get("/runs", response_model=List[TestRunResponse])
def list_test_runs(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """List test runs"""
    query = db.query(RegressionTestRun)
    
    if status:
        query = query.filter(RegressionTestRun.status == status)
    
    runs = query.order_by(RegressionTestRun.started_at.desc()).offset(skip).limit(limit).all()
    
    return [run_to_response(r) for r in runs]


@router.get("/runs/{run_id}", response_model=TestRunResponse)
def get_test_run(run_id: int, db: Session = Depends(get_db)):
    """Get a specific test run"""
    run = db.query(RegressionTestRun).filter(RegressionTestRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run_to_response(run)


@router.get("/runs/{run_id}/results", response_model=List[TestResultResponse])
def get_run_results(
    run_id: int,
    status: Optional[str] = None,
    manual_review: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get results for a test run"""
    query = db.query(RegressionTestResult).filter(RegressionTestResult.run_id == run_id)
    
    if status:
        query = query.filter(RegressionTestResult.status == status)
    
    if manual_review:
        query = query.filter(RegressionTestResult.manual_review == manual_review)
    
    results = query.all()
    
    # Get case details
    case_ids = [r.case_id for r in results]
    cases = {c.id: c for c in db.query(RegressionTestCase).filter(RegressionTestCase.id.in_(case_ids)).all()}
    
    return [result_to_response(r, cases.get(r.case_id)) for r in results]


# ==================== Manual Review Endpoints ====================

@router.post("/results/{result_id}/review")
def submit_manual_review(
    result_id: int,
    request: ManualReviewRequest,
    db: Session = Depends(get_db),
):
    """Submit manual review for a test result"""
    result = db.query(RegressionTestResult).filter(RegressionTestResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Test result not found")
    
    result.manual_review = request.review
    result.manual_comment = request.comment
    result.reviewed_by = "admin"  # TODO: Get from auth
    result.reviewed_at = datetime.utcnow()
    
    # Update status based on manual review
    if request.review == "pass":
        result.status = "pass"
    elif request.review == "fail":
        result.status = "fail"
    
    db.commit()
    
    # Update run statistics
    run = db.query(RegressionTestRun).filter(RegressionTestRun.id == result.run_id).first()
    if run:
        # Recalculate pass rate
        results = db.query(RegressionTestResult).filter(RegressionTestResult.run_id == run.id).all()
        passed = sum(1 for r in results if r.status == "pass")
        failed = sum(1 for r in results if r.status == "fail")
        review = sum(1 for r in results if r.status == "review")
        
        run.passed_cases = passed
        run.failed_cases = failed
        run.review_cases = review
        run.pass_rate = (passed / run.total_cases * 100) if run.total_cases > 0 else 0
        db.commit()
    
    return {"message": "Review submitted", "status": result.status}


# ==================== Statistics Endpoints ====================

@router.get("/stats")
def get_regression_stats(db: Session = Depends(get_db)):
    """Get overall regression test statistics"""
    # Count test cases by category
    case_counts = db.query(
        RegressionTestCase.category,
        func.count(RegressionTestCase.id)
    ).filter(RegressionTestCase.is_active == True).group_by(RegressionTestCase.category).all()
    
    # Recent runs
    recent_runs = db.query(RegressionTestRun).order_by(
        RegressionTestRun.started_at.desc()
    ).limit(5).all()
    
    # Average pass rate
    avg_pass_rate = db.query(func.avg(RegressionTestRun.pass_rate)).filter(
        RegressionTestRun.status == "completed"
    ).scalar() or 0
    
    # Pending reviews count
    pending_reviews = db.query(func.count(RegressionTestResult.id)).filter(
        RegressionTestResult.manual_review == "pending",
        RegressionTestResult.status == "review"
    ).scalar() or 0
    
    return {
        "total_cases": sum(c[1] for c in case_counts),
        "cases_by_category": {c[0]: c[1] for c in case_counts},
        "total_runs": db.query(func.count(RegressionTestRun.id)).scalar() or 0,
        "avg_pass_rate": round(avg_pass_rate, 1),
        "pending_reviews": pending_reviews,
        "recent_runs": [run_to_response(r) for r in recent_runs],
    }


@router.get("/evaluator/health")
async def check_evaluator_health():
    """Check Ragas evaluator service health"""
    evaluator = get_evaluator()
    is_healthy = await evaluator.check_evaluator_health()
    await evaluator.close()
    
    return {
        "evaluator_healthy": is_healthy,
        "evaluator_url": evaluator.evaluator_url,
    }

