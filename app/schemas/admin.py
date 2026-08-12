from pydantic import BaseModel, ConfigDict, Field


class AdminProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    email: str
    display_name: str | None = None


class AdminProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=255)
