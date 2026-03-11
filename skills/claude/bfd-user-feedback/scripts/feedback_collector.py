#!/usr/bin/env python3
"""
反馈收集器模块
用于收集和处理用户反馈
"""

import json
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any


class FeedbackType(Enum):
    USER_CONFIRMATION = "user_confirmation"
    ERROR_REPORT = "error_report"
    STATUS_UPDATE = "status_update"
    USER_REQUEST = "user_request"


class FeedbackCollector:
    """用户反馈收集器"""

    def __init__(self, project_name: str = "STM32_Project"):
        self.project_name = project_name
        self.feedback_history: list = []

    def collect_feedback(
        self,
        feedback_type: FeedbackType,
        summary: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        feedback_data = {
            "timestamp": datetime.now().isoformat(),
            "feedback_type": feedback_type.value,
            "project_name": self.project_name,
            "summary": summary,
            "details": details or {},
            "user_response": None
        }

        self.feedback_history.append(feedback_data)
        return feedback_data

    def format_for_mcp(
        self,
        feedback_data: Dict[str, Any]
    ) -> Dict[str, str]:
        return {
            "title": f"{self.project_name} - {feedback_data['feedback_type']}",
            "summary": feedback_data["summary"],
            "status": feedback_data["feedback_type"]
        }

    def record_user_response(
        self,
        feedback_index: int,
        response: str
    ) -> bool:
        if 0 <= feedback_index < len(self.feedback_history):
            self.feedback_history[feedback_index]["user_response"] = response
            return True
        return False

    def get_pending_feedbacks(self) -> list:
        return [
            fb for fb in self.feedback_history
            if fb["user_response"] is None
        ]

    def export_history(self, filepath: str) -> bool:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.feedback_history, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False


def create_confirmation_feedback(
    collector: FeedbackCollector,
    action: str,
    files_modified: list,
    result: str
) -> Dict[str, Any]:
    return collector.collect_feedback(
        feedback_type=FeedbackType.USER_CONFIRMATION,
        summary=f"操作完成: {action}",
        details={
            "action_taken": action,
            "files_modified": files_modified,
            "result": result
        }
    )


def create_error_feedback(
    collector: FeedbackCollector,
    error_type: str,
    error_message: str,
    affected_files: list
) -> Dict[str, Any]:
    return collector.collect_feedback(
        feedback_type=FeedbackType.ERROR_REPORT,
        summary=f"错误报告: {error_type}",
        details={
            "error_type": error_type,
            "error_message": error_message,
            "affected_files": affected_files
        }
    )


if __name__ == "__main__":
    collector = FeedbackCollector("RC2026_h7")

    feedback = create_confirmation_feedback(
        collector=collector,
        action="代码修改",
        files_modified=["main.c", "config.h"],
        result="成功"
    )

    print(json.dumps(feedback, ensure_ascii=False, indent=2))
