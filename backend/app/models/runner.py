from pydantic import BaseModel


class RunnerPairingRequestCreate(BaseModel):
    label: str | None = None


class RunnerPairingRequestResponse(BaseModel):
    user_code: str
    # Returned exactly once, to the runner that asked for it — never shown
    # in the browser UI, never logged. See migration 017's header comment
    # for the full pairing flow.
    runner_token: str
    expires_in_seconds: int
    poll_interval_seconds: int


class RunnerPairingApprove(BaseModel):
    user_code: str
    label: str | None = None


class RunnerPairingPoll(BaseModel):
    user_code: str


class RunnerPairingStatusResponse(BaseModel):
    status: str  # "pending" | "approved" | "denied" | "expired" | "not_found"


class RunnerConnectionResponse(BaseModel):
    id: str
    label: str
    created_at: str
    last_used_at: str | None = None
    revoked_at: str | None = None
