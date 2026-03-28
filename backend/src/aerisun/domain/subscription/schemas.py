from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from aerisun.core.schemas import ModelBase


class ContentSubscriptionPublicCreate(BaseModel):
    email: str = Field(description="Subscriber email address")
    content_types: list[str] = Field(description="Content types to subscribe to")


class ContentSubscriptionPublicRead(BaseModel):
    email: str = Field(description="Subscriber email address")
    content_types: list[str] = Field(description="Subscribed content types")
    subscribed: bool = Field(default=True, description="Whether the subscription is active")


class ContentSubscriptionConfigAdminRead(ModelBase):
    id: str = Field(description="Subscription config id")
    enabled: bool = Field(description="Whether public subscription is enabled")
    smtp_auth_mode: Literal["password", "microsoft_oauth2"] = Field(description="SMTP authentication mode")
    smtp_host: str = Field(description="SMTP host")
    smtp_port: int = Field(description="SMTP port")
    smtp_username: str = Field(description="SMTP username")
    smtp_password: str = Field(description="SMTP password")
    smtp_oauth_tenant: str = Field(description="Microsoft OAuth tenant identifier")
    smtp_oauth_client_id: str = Field(description="Microsoft OAuth client id")
    smtp_oauth_client_secret: str = Field(description="Microsoft OAuth client secret")
    smtp_oauth_refresh_token: str = Field(description="Microsoft OAuth refresh token")
    smtp_from_email: str = Field(description="SMTP sender email")
    smtp_from_name: str = Field(description="SMTP sender display name")
    smtp_reply_to: str = Field(description="SMTP reply-to email")
    smtp_use_tls: bool = Field(description="Whether STARTTLS is enabled")
    smtp_use_ssl: bool = Field(description="Whether implicit SSL is enabled")
    subscriber_count: int = Field(default=0, description="Number of active subscribers")
    created_at: datetime = Field(description="Creation time")
    updated_at: datetime = Field(description="Last update time")


class ContentSubscriptionConfigAdminUpdate(BaseModel):
    enabled: bool | None = Field(default=None, description="Whether public subscription is enabled")
    smtp_auth_mode: Literal["password", "microsoft_oauth2"] | None = Field(
        default=None, description="SMTP authentication mode"
    )
    smtp_host: str | None = Field(default=None, description="SMTP host")
    smtp_port: int | None = Field(default=None, description="SMTP port")
    smtp_username: str | None = Field(default=None, description="SMTP username")
    smtp_password: str | None = Field(default=None, description="SMTP password")
    smtp_oauth_tenant: str | None = Field(default=None, description="Microsoft OAuth tenant identifier")
    smtp_oauth_client_id: str | None = Field(default=None, description="Microsoft OAuth client id")
    smtp_oauth_client_secret: str | None = Field(default=None, description="Microsoft OAuth client secret")
    smtp_oauth_refresh_token: str | None = Field(default=None, description="Microsoft OAuth refresh token")
    smtp_from_email: str | None = Field(default=None, description="SMTP sender email")
    smtp_from_name: str | None = Field(default=None, description="SMTP sender display name")
    smtp_reply_to: str | None = Field(default=None, description="SMTP reply-to email")
    smtp_use_tls: bool | None = Field(default=None, description="Whether STARTTLS is enabled")
    smtp_use_ssl: bool | None = Field(default=None, description="Whether implicit SSL is enabled")


class ContentSubscriptionTestResult(BaseModel):
    recipient: str = Field(description="Recipient email used for the test delivery")
