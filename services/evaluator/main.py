"""
Ragas Evaluation Service
独立的 RAG 评估服务，使用 Ragas 框架进行评估
"""
import os
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio

# Ragas imports
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    context_entity_recall,
    answer_similarity,
    answer_correctness,
)
from datasets import Dataset

# LangChain imports for LLM
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ragas Evaluation Service",
    description="RAG 评估服务，使用 Ragas 框架",
    version="1.0.0"
)

# Configuration from environment
LLM_API_KEY = os.getenv("UPSTREAM_LLM_API_KEY", os.getenv("DASHSCOPE_API_KEY", ""))
LLM_BASE_URL = os.getenv("UPSTREAM_LLM_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_MODEL = os.getenv("DEFAULT_MODEL", "qwen-plus")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")


# ==================== Request/Response Models ====================

class EvaluationRequest(BaseModel):
    """Single evaluation request"""
    question: str
    answer: str
    contexts: List[str]
    ground_truth: Optional[str] = None
    reference_answer: Optional[str] = None


class BatchEvaluationRequest(BaseModel):
    """Batch evaluation request"""
    items: List[EvaluationRequest]
    metrics: List[str] = ["faithfulness", "answer_relevancy", "context_precision"]


class EvaluationScore(BaseModel):
    """Individual metric score"""
    metric: str
    score: float
    

class EvaluationResponse(BaseModel):
    """Evaluation response"""
    scores: Dict[str, float]
    overall_score: float
    details: Optional[Dict[str, Any]] = None


class BatchEvaluationResponse(BaseModel):
    """Batch evaluation response"""
    results: List[EvaluationResponse]
    aggregate_scores: Dict[str, float]


class HealthResponse(BaseModel):
    status: str
    version: str


# ==================== LLM Setup ====================

def get_llm():
    """Get LangChain LLM instance"""
    # Adjust base URL for LangChain compatibility
    base_url = LLM_BASE_URL
    if base_url.endswith("/chat/completions"):
        base_url = base_url.replace("/chat/completions", "")
    
    return ChatOpenAI(
        model=LLM_MODEL,
        openai_api_key=LLM_API_KEY,
        openai_api_base=base_url,
        temperature=0.1,
    )


def get_embeddings():
    """Get LangChain Embeddings instance"""
    base_url = LLM_BASE_URL
    if base_url.endswith("/chat/completions"):
        base_url = base_url.replace("/chat/completions", "")
    
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=LLM_API_KEY,
        openai_api_base=base_url,
    )


# ==================== Metrics Registry ====================

AVAILABLE_METRICS = {
    "faithfulness": faithfulness,
    "answer_relevancy": answer_relevancy,
    "context_precision": context_precision,
    "context_recall": context_recall,
    "context_entity_recall": context_entity_recall,
    "answer_similarity": answer_similarity,
    "answer_correctness": answer_correctness,
}


# ==================== API Endpoints ====================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(status="healthy", version="1.0.0")


@app.get("/metrics")
async def list_metrics():
    """List available evaluation metrics"""
    return {
        "metrics": list(AVAILABLE_METRICS.keys()),
        "descriptions": {
            "faithfulness": "衡量答案是否基于给定上下文（幻觉检测）",
            "answer_relevancy": "衡量答案与问题的相关性",
            "context_precision": "衡量检索到的上下文的精确度",
            "context_recall": "衡量检索到的上下文的召回率（需要 ground_truth）",
            "context_entity_recall": "衡量上下文中实体的召回率",
            "answer_similarity": "衡量答案与参考答案的语义相似度",
            "answer_correctness": "衡量答案的正确性（需要 ground_truth）",
        }
    }


@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_single(request: EvaluationRequest):
    """
    Evaluate a single question-answer pair
    """
    try:
        # Prepare data for Ragas
        data = {
            "question": [request.question],
            "answer": [request.answer],
            "contexts": [request.contexts],
        }
        
        # Add ground truth if provided
        if request.ground_truth:
            data["ground_truth"] = [request.ground_truth]
        elif request.reference_answer:
            data["ground_truth"] = [request.reference_answer]
        
        dataset = Dataset.from_dict(data)
        
        # Select metrics based on available data
        metrics_to_use = [faithfulness, answer_relevancy, context_precision]
        
        if request.ground_truth or request.reference_answer:
            metrics_to_use.extend([context_recall, answer_correctness])
        
        # Run evaluation
        llm = get_llm()
        embeddings = get_embeddings()
        
        result = evaluate(
            dataset,
            metrics=metrics_to_use,
            llm=llm,
            embeddings=embeddings,
        )
        
        # Extract scores
        scores = {}
        for metric_name in result.scores.columns:
            if metric_name != "question":
                scores[metric_name] = float(result.scores[metric_name].iloc[0])
        
        # Calculate overall score (weighted average)
        weights = {
            "faithfulness": 0.3,
            "answer_relevancy": 0.3,
            "context_precision": 0.2,
            "context_recall": 0.1,
            "answer_correctness": 0.1,
        }
        
        total_weight = 0
        weighted_sum = 0
        for metric, score in scores.items():
            weight = weights.get(metric, 0.1)
            weighted_sum += score * weight
            total_weight += weight
        
        overall_score = weighted_sum / total_weight if total_weight > 0 else 0.5
        
        return EvaluationResponse(
            scores=scores,
            overall_score=overall_score,
            details={
                "metrics_used": [m.__class__.__name__ for m in metrics_to_use],
                "has_ground_truth": bool(request.ground_truth or request.reference_answer),
            }
        )
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/evaluate/batch", response_model=BatchEvaluationResponse)
async def evaluate_batch(request: BatchEvaluationRequest):
    """
    Evaluate multiple question-answer pairs in batch
    """
    try:
        # Prepare batch data
        questions = []
        answers = []
        contexts_list = []
        ground_truths = []
        has_ground_truth = False
        
        for item in request.items:
            questions.append(item.question)
            answers.append(item.answer)
            contexts_list.append(item.contexts)
            
            gt = item.ground_truth or item.reference_answer or ""
            ground_truths.append(gt)
            if gt:
                has_ground_truth = True
        
        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts_list,
        }
        
        if has_ground_truth:
            data["ground_truth"] = ground_truths
        
        dataset = Dataset.from_dict(data)
        
        # Select metrics
        metrics_to_use = []
        for metric_name in request.metrics:
            if metric_name in AVAILABLE_METRICS:
                # Skip metrics that require ground_truth if not available
                if metric_name in ["context_recall", "answer_correctness"] and not has_ground_truth:
                    continue
                metrics_to_use.append(AVAILABLE_METRICS[metric_name])
        
        if not metrics_to_use:
            metrics_to_use = [faithfulness, answer_relevancy, context_precision]
        
        # Run evaluation
        llm = get_llm()
        embeddings = get_embeddings()
        
        result = evaluate(
            dataset,
            metrics=metrics_to_use,
            llm=llm,
            embeddings=embeddings,
        )
        
        # Process results
        results = []
        aggregate_scores = {}
        
        for i in range(len(request.items)):
            scores = {}
            for col in result.scores.columns:
                if col != "question":
                    score = float(result.scores[col].iloc[i])
                    scores[col] = score
                    
                    if col not in aggregate_scores:
                        aggregate_scores[col] = []
                    aggregate_scores[col].append(score)
            
            # Calculate overall for this item
            overall = sum(scores.values()) / len(scores) if scores else 0.5
            
            results.append(EvaluationResponse(
                scores=scores,
                overall_score=overall,
            ))
        
        # Calculate aggregate
        for metric, score_list in aggregate_scores.items():
            aggregate_scores[metric] = sum(score_list) / len(score_list)
        
        return BatchEvaluationResponse(
            results=results,
            aggregate_scores=aggregate_scores,
        )
        
    except Exception as e:
        logger.error(f"Batch evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/evaluate/retrieval")
async def evaluate_retrieval_only(
    question: str,
    contexts: List[str],
    ground_truth: Optional[str] = None
):
    """
    Evaluate retrieval quality only (without answer generation)
    """
    try:
        # For retrieval-only evaluation, we use context_precision
        # and optionally context_recall if ground_truth is provided
        
        data = {
            "question": [question],
            "answer": [""],  # Empty answer for retrieval-only
            "contexts": [contexts],
        }
        
        metrics_to_use = [context_precision]
        
        if ground_truth:
            data["ground_truth"] = [ground_truth]
            metrics_to_use.append(context_recall)
        
        dataset = Dataset.from_dict(data)
        
        llm = get_llm()
        embeddings = get_embeddings()
        
        result = evaluate(
            dataset,
            metrics=metrics_to_use,
            llm=llm,
            embeddings=embeddings,
        )
        
        scores = {}
        for col in result.scores.columns:
            if col != "question":
                scores[col] = float(result.scores[col].iloc[0])
        
        overall = sum(scores.values()) / len(scores) if scores else 0.5
        
        return {
            "scores": scores,
            "overall_score": overall,
            "num_contexts": len(contexts),
        }
        
    except Exception as e:
        logger.error(f"Retrieval evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

