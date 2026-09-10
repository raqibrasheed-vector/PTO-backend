from datetime import datetime
from typing import ClassVar, Optional

from pydantic import BaseModel


class AbstractTableData(BaseModel):
    """Abstract data model for all the tables"""

    created_at: Optional[datetime] = datetime.now()
    last_modified: Optional[datetime] = datetime.now()


class UserLogging(AbstractTableData):
    user_name: str

    __partition_key__ = "/user_name"
    __table_name__ = "pto_user_login_log"

    def __repr__(self):
        return f"pto_user_login_log"

    def __str__(self):
        return f"pto_user_login_log"


class PTOLogging(AbstractTableData):
    user_name: str
    employee_id: str
    start_date: datetime
    end_date: datetime
    employee_name: str
    client_name: str
    total_hours: float
    total_leaves_used: float
    state: str
    leaves_available: float
    file_name: str
    session_id: str

    __partition_key__ = "/user_name"
    __table_name__ = "pto_logging"

    CONTAINER_NAME: ClassVar[str] = "pto_logging"

    def __repr__(self):
        return f"pto_logging"

    def __str__(self):
        return f"pto_logging"


class PTOFeedBackForm(AbstractTableData):
    pto_logging_id: str
    user_name: str
    feedback: str
    feedback_type: str
    file_name: str
    employee_id: str
    start_date: str
    end_date: str
    employee_name: str
    client_name: str
    total_hours: float
    total_leaves_used: float
    state: str
    leaves_available: float
    session_id: str

    __partition_key__ = "/user_name"
    __table_name__ = "PTO_feedback"

    CONTAINER_NAME: ClassVar[str] = "PTO_feedback"

    def __repr__(self):
        return f"PTO_feedback"

    def __str__(self):
        return f"PTO_feedback"


tables_list = [PTOLogging,UserLogging,PTOFeedBackForm]