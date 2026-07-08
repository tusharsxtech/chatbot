from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    user_role: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description=(
            "Identifies the caller's role. This is an authorization check, not a "
            "style hint — requests are only processed when this equals the "
            "server's configured required role (see REQUIRED_USER_ROLE)."
        ),
    )
    device_id: str = Field(..., min_length=1, max_length=128)
