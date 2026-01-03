"""
Regression test evaluation engine
Integrates with the Ragas evaluation service for RAG quality assessment
"""
import json
import logging
import time
import httpx
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from ..config import settings
from .retrieval import search

logger = logging.getLogger(__name__)

# Ragas evaluator service URL
EVALUATOR_SERVICE_URL = "http://evaluator:8002"


@dataclass
class EvaluationResult:
    """Result from evaluating a single test case"""
    retrieval_score: float
    answer_score: float
    ragas_scores: Dict[str, float]  # Detailed Ragas metrics
    actual_answer: str
    retrieved_ku_ids: List[str]
    retrieved_contexts: List[str]
    status: str  # pass/fail/review
    execution_time_ms: int
    error_message: Optional[str] = None


class RegressionEvaluator:
    """
    Evaluator for regression test cases.
    Uses Ragas service for evaluation metrics.
    """
    
    # Thresholds for automatic pass/fail
    RETRIEVAL_PASS_THRESHOLD = 0.6
    ANSWER_PASS_THRESHOLD = 0.7
    REVIEW_THRESHOLD = 0.5
    
    # Ragas metrics weights for overall score
    METRIC_WEIGHTS = {
        "faithfulness": 0.25,
        "answer_relevancy": 0.25,
        "context_precision": 0.20,
        "context_recall": 0.15,
        "answer_correctness": 0.15,
    }
    
    def __init__(self, evaluator_url: str = None):
        self.evaluator_url = evaluator_url or EVALUATOR_SERVICE_URL
        self.http_client = None
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=120.0)
        return self.http_client
    
    async def check_evaluator_health(self) -> bool:
        """Check if the Ragas evaluator service is healthy"""
        try:
            client = self._get_client()
            response = await client.get(f"{self.evaluator_url}/health")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Evaluator service health check failed: {e}")
            return False
    
    async def evaluate_with_ragas(
        self,
        question: str,
        answer: str,
        contexts: List[str],
        ground_truth: Optional[str] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Call Ragas service for evaluation.
        
        Args:
            question: The test question
            answer: Generated answer
            contexts: Retrieved context documents
            ground_truth: Optional expected answer
            
        Returns:
            Tuple of (overall_score, detailed_scores)
        """
        try:
            client = self._get_client()
            
            payload = {
                "question": question,
                "answer": answer,
                "contexts": contexts,
            }
            
            if ground_truth:
                payload["ground_truth"] = ground_truth
            
            response = await client.post(
                f"{self.evaluator_url}/evaluate",
                json=payload,
            )
            
            if response.status_code != 200:
                logger.error(f"Ragas evaluation failed: {response.text}")
                return 0.5, {"error": response.text}
            
            result = response.json()
            return result.get("overall_score", 0.5), result.get("scores", {})
            
        except httpx.ConnectError:
            logger.warning("Cannot connect to Ragas evaluator service, using fallback")
            return await self._fallback_evaluation(question, answer, ground_truth)
        except Exception as e:
            logger.error(f"Ragas evaluation error: {e}")
            return 0.5, {"error": str(e)}
    
    async def _fallback_evaluation(
        self,
        question: str,
        answer: str,
        ground_truth: Optional[str] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Fallback evaluation when Ragas service is unavailable.
        Uses simple heuristics.
        """
        scores = {}
        
        # Simple length-based relevancy
        if len(answer) > 50:
            scores["answer_relevancy"] = 0.6
        elif len(answer) > 20:
            scores["answer_relevancy"] = 0.4
        else:
            scores["answer_relevancy"] = 0.2
        
        # Simple keyword overlap for faithfulness (if answer contains question keywords)
        question_words = set(question.lower().split())
        answer_words = set(answer.lower().split())
        overlap = len(question_words & answer_words) / len(question_words) if question_words else 0
        scores["faithfulness"] = min(0.8, overlap + 0.3)
        
        # If ground truth provided, simple similarity
        if ground_truth:
            gt_words = set(ground_truth.lower().split())
            similarity = len(gt_words & answer_words) / len(gt_words) if gt_words else 0
            scores["answer_correctness"] = similarity
        
        overall = sum(scores.values()) / len(scores) if scores else 0.5
        scores["_fallback"] = True
        
        return overall, scores
    
    def evaluate_retrieval_f1(
        self, 
        expected_ku_ids: List[str], 
        actual_ku_ids: List[str]
    ) -> float:
        """
        Evaluate retrieval quality using F1 score.
        """
        if not expected_ku_ids:
            return 1.0 if actual_ku_ids else 0.5
        
        expected_set = set(str(x) for x in expected_ku_ids)
        actual_set = set(str(x) for x in actual_ku_ids)
        
        hits = len(expected_set & actual_set)
        
        recall = hits / len(expected_set) if expected_set else 1.0
        precision = hits / len(actual_set) if actual_set else 0.0
        
        if recall + precision == 0:
            return 0.0
        
        return 2 * recall * precision / (recall + precision)
    
    async def generate_answer(self, query: str, context_docs: List[Dict]) -> str:
        """
        Generate answer using the main API's RAG approach.
        This calls the existing conversation endpoint or generates directly.
        """
        from openai import OpenAI
        
        try:
            client = OpenAI(
                api_key=settings.upstream_llm_key,
                base_url=settings.upstream_llm_url.replace("/chat/completions", ""),
            )
            
            # Build context
            context_parts = []
            for i, doc in enumerate(context_docs[:5], 1):
                title = doc.get("title", "")
                content = doc.get("full_text", doc.get("summary", ""))[:1000]
                context_parts.append(f"[{i}] {title}\n{content}")
            
            context = "\n\n".join(context_parts)
            
            prompt = f"""基于以下参考资料回答用户问题。

参考资料:
{context}

用户问题: {query}

请根据参考资料提供准确、完整的答案。"""

            response = client.chat.completions.create(
                model=settings.default_model,
                messages=[
                    {"role": "system", "content": "你是一个专业的知识助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Answer generation failed: {e}")
            return f"[生成答案失败: {str(e)}]"
    
    async def evaluate_case(
        self,
        query: str,
        expected_ku_ids: List[str],
        expected_answer: Optional[str],
        evaluation_criteria: Dict[str, Any],
        category: str = "e2e"
    ) -> EvaluationResult:
        """
        Evaluate a single test case end-to-end using Ragas.
        
        Args:
            query: Test query
            expected_ku_ids: Expected KU IDs to retrieve
            expected_answer: Expected answer for comparison
            evaluation_criteria: Additional evaluation criteria
            category: Test category (rag/llm/e2e)
            
        Returns:
            EvaluationResult with scores and details
        """
        start_time = time.time()
        
        try:
            # Step 1: Retrieve documents
            search_results = search(query, top_k=10)
            retrieved_docs = search_results.get("results", [])
            retrieved_ku_ids = [
                str(doc.get("ku_id", doc.get("_id", ""))) 
                for doc in retrieved_docs
            ]
            
            # Extract contexts for Ragas
            contexts = []
            for doc in retrieved_docs[:5]:
                content = doc.get("full_text", doc.get("summary", ""))
                if content:
                    contexts.append(content[:2000])  # Limit context length
            
            # Step 2: Calculate retrieval F1 score
            retrieval_f1 = self.evaluate_retrieval_f1(expected_ku_ids, retrieved_ku_ids)
            
            # Step 3: Generate answer (for llm and e2e tests)
            if category in ["llm", "e2e"]:
                actual_answer = await self.generate_answer(query, retrieved_docs)
            else:
                actual_answer = "[RAG测试 - 仅评估检索]"
            
            # Step 4: Evaluate with Ragas (for llm and e2e tests)
            if category in ["llm", "e2e"] and contexts:
                answer_score, ragas_scores = await self.evaluate_with_ragas(
                    question=query,
                    answer=actual_answer,
                    contexts=contexts,
                    ground_truth=expected_answer,
                )
            else:
                answer_score = retrieval_f1
                ragas_scores = {"context_precision": retrieval_f1}
            
            # Use context_precision from Ragas if available
            retrieval_score = ragas_scores.get("context_precision", retrieval_f1)
            
            # Step 5: Determine status
            status = self._determine_status(retrieval_score, answer_score, category)
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return EvaluationResult(
                retrieval_score=retrieval_score,
                answer_score=answer_score,
                ragas_scores=ragas_scores,
                actual_answer=actual_answer,
                retrieved_ku_ids=retrieved_ku_ids,
                retrieved_contexts=contexts,
                status=status,
                execution_time_ms=execution_time,
            )
            
        except Exception as e:
            logger.error(f"Test case evaluation failed: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            
            return EvaluationResult(
                retrieval_score=0.0,
                answer_score=0.0,
                ragas_scores={"error": str(e)},
                actual_answer="",
                retrieved_ku_ids=[],
                retrieved_contexts=[],
                status="fail",
                execution_time_ms=execution_time,
                error_message=str(e),
            )
    
    def _determine_status(
        self, 
        retrieval_score: float, 
        answer_score: float,
        category: str
    ) -> str:
        """Determine test status based on scores."""
        if category == "rag":
            if retrieval_score >= self.RETRIEVAL_PASS_THRESHOLD:
                return "pass"
            elif retrieval_score >= self.REVIEW_THRESHOLD:
                return "review"
            else:
                return "fail"
        else:
            if (retrieval_score >= self.RETRIEVAL_PASS_THRESHOLD and 
                answer_score >= self.ANSWER_PASS_THRESHOLD):
                return "pass"
            elif (retrieval_score >= self.REVIEW_THRESHOLD or 
                  answer_score >= self.REVIEW_THRESHOLD):
                return "review"
            else:
                return "fail"
    
    async def close(self):
        """Close HTTP client"""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None


# Singleton instance
_evaluator: Optional[RegressionEvaluator] = None


def get_evaluator() -> RegressionEvaluator:
    """Get singleton evaluator instance"""
    global _evaluator
    if _evaluator is None:
        _evaluator = RegressionEvaluator()
    return _evaluator
