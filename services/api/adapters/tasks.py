import re
from datetime import datetime

from google.api_core import exceptions as gax
from google.cloud import tasks_v2

from domain.clock import require_aware

TASK_ID = re.compile(r"^[A-Za-z0-9_-]+$")


class InvalidTaskId(Exception):
    pass


class DeadlineScheduler:
    def __init__(
        self,
        client,
        project: str,
        location: str,
        queue: str,
        api_url: str,
        invoker_email: str,
    ):
        self._client = client
        self._queue_path = client.queue_path(project, location, queue)
        self._api_url = api_url.rstrip("/")
        self._invoker_email = invoker_email

    def schedule(self, task_id: str, deadline_at: datetime) -> str:
        if not TASK_ID.match(task_id):
            raise InvalidTaskId(f"invalid task id: {task_id!r}")
        task = tasks_v2.Task(
            http_request=tasks_v2.HttpRequest(
                http_method=tasks_v2.HttpMethod.POST,
                url=f"{self._api_url}/api/internal/deadline/{task_id}",
                oidc_token=tasks_v2.OidcToken(
                    service_account_email=self._invoker_email,
                    audience=self._api_url,
                ),
            ),
            schedule_time=require_aware(deadline_at),
        )
        created = self._client.create_task(parent=self._queue_path, task=task)
        return created.name

    def cancel(self, cloud_task_name: str | None) -> None:
        if cloud_task_name is None:
            return
        try:
            self._client.delete_task(name=cloud_task_name)
        except gax.NotFound:
            return
