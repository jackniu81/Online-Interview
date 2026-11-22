"""Exam management endpoints (capability: exam-management) - implemented in group 5."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/admin/exams", tags=["exam-management"])
