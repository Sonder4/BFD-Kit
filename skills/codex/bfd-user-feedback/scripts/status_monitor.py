#!/usr/bin/env python3
"""
状态监控模块
用于监控 STM32 项目运行状态
"""

import json
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field


class ProjectStatus(Enum):
    IDLE = "idle"
    BUILDING = "building"
    DEBUGGING = "debugging"
    FLASHING = "flashing"
    ERROR = "error"
    WAITING_FEEDBACK = "waiting"


@dataclass
class StatusRecord:
    status: ProjectStatus
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class StatusMonitor:
    VALID_TRANSITIONS = {
        ProjectStatus.IDLE: [
            ProjectStatus.BUILDING,
            ProjectStatus.DEBUGGING,
            ProjectStatus.FLASHING
        ],
        ProjectStatus.BUILDING: [
            ProjectStatus.IDLE,
            ProjectStatus.ERROR,
            ProjectStatus.WAITING_FEEDBACK
        ],
        ProjectStatus.DEBUGGING: [
            ProjectStatus.IDLE,
            ProjectStatus.ERROR,
            ProjectStatus.WAITING_FEEDBACK
        ],
        ProjectStatus.FLASHING: [
            ProjectStatus.IDLE,
            ProjectStatus.ERROR,
            ProjectStatus.WAITING_FEEDBACK
        ],
        ProjectStatus.ERROR: [
            ProjectStatus.IDLE,
            ProjectStatus.BUILDING
        ],
        ProjectStatus.WAITING_FEEDBACK: [
            ProjectStatus.IDLE,
            ProjectStatus.BUILDING,
            ProjectStatus.ERROR
        ]
    }

    def __init__(self, project_name: str = "STM32_Project"):
        self.project_name = project_name
        self.current_status = ProjectStatus.IDLE
        self.status_history: List[StatusRecord] = []
        self._record_status(ProjectStatus.IDLE, "初始化监控器")

    def _record_status(
        self,
        status: ProjectStatus,
        message: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> StatusRecord:
        record = StatusRecord(
            status=status,
            message=message,
            details=details or {}
        )
        self.status_history.append(record)
        return record

    def can_transition_to(self, new_status: ProjectStatus) -> bool:
        valid_targets = self.VALID_TRANSITIONS.get(self.current_status, [])
        return new_status in valid_targets

    def set_status(
        self,
        new_status: ProjectStatus,
        message: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        if not self.can_transition_to(new_status):
            return False

        old_status = self.current_status
        self.current_status = new_status

        transition_details = details or {}
        transition_details["previous_status"] = old_status.value

        self._record_status(new_status, message, transition_details)
        return True

    def force_status(
        self,
        new_status: ProjectStatus,
        message: str = "",
        details: Optional[Dict[str, Any]] = None
    ) -> StatusRecord:
        old_status = self.current_status
        self.current_status = new_status

        transition_details = details or {}
        transition_details["previous_status"] = old_status.value
        transition_details["forced"] = True

        return self._record_status(new_status, message, transition_details)

    def get_current_status(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "status": self.current_status.value,
            "timestamp": datetime.now().isoformat(),
            "history_count": len(self.status_history)
        }

    def get_status_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        history = [
            {
                "status": record.status.value,
                "timestamp": record.timestamp,
                "message": record.message,
                "details": record.details
            }
            for record in self.status_history
        ]

        if limit:
            return history[-limit:]
        return history

    def is_busy(self) -> bool:
        busy_states = [
            ProjectStatus.BUILDING,
            ProjectStatus.DEBUGGING,
            ProjectStatus.FLASHING
        ]
        return self.current_status in busy_states

    def is_error(self) -> bool:
        return self.current_status == ProjectStatus.ERROR

    def export_status_report(self) -> Dict[str, Any]:
        return {
            "project_name": self.project_name,
            "current_status": self.get_current_status(),
            "is_busy": self.is_busy(),
            "is_error": self.is_error(),
            "history": self.get_status_history(limit=10)
        }


def monitor_build(monitor: StatusMonitor, build_command: str) -> StatusRecord:
    monitor.set_status(
        ProjectStatus.BUILDING,
        "开始构建",
        {"build_command": build_command}
    )
    return monitor.status_history[-1]


def monitor_flash(monitor: StatusMonitor, target_device: str) -> StatusRecord:
    monitor.set_status(
        ProjectStatus.FLASHING,
        "开始烧录",
        {"target_device": target_device}
    )
    return monitor.status_history[-1]


def report_error(
    monitor: StatusMonitor,
    error_type: str,
    error_message: str
) -> StatusRecord:
    return monitor.force_status(
        ProjectStatus.ERROR,
        f"错误: {error_type}",
        {
            "error_type": error_type,
            "error_message": error_message
        }
    )


if __name__ == "__main__":
    monitor = StatusMonitor("RC2026_h7")

    print("初始状态:", monitor.get_current_status())

    monitor_build(monitor, "arm-none-eabi-gcc")
    print("构建中:", monitor.get_current_status())

    monitor.set_status(ProjectStatus.WAITING_FEEDBACK, "构建完成，等待反馈")
    print("等待反馈:", monitor.get_current_status())

    print("\n状态报告:")
    print(json.dumps(monitor.export_status_report(), ensure_ascii=False, indent=2))
