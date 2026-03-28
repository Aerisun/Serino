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


class ContentSubscriptionPublicStatusRead(BaseModel):
    email: str = Field(description="Subscriber email address")
    content_types: list[str] = Field(description="Subscribed content types")
    subscribed: bool = Field(description="Whether the subscription is active")


class ContentSubscriptionPublicUnsubscribeResult(BaseModel):
    email: str = Field(description="Subscriber email address")
    unsubscribed: bool = Field(description="Whether unsubscribe succeeded")


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
    smtp_test_passed: bool = Field(description="Whether SMTP test delivery succeeded for current settings")
    smtp_tested_at: datetime | None = Field(description="Last successful SMTP test timestamp")
    allowed_content_types: list[str] = Field(description="Content types users can subscribe to")
    mail_subject_template: str = Field(description="Email subject template")
    mail_body_template: str = Field(description="Email body template")
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
    allowed_content_types: list[str] | None = Field(default=None, description="Content types users can subscribe to")
    mail_subject_template: str | None = Field(default=None, description="Email subject template")
    mail_body_template: str | None = Field(default=None, description="Email body template")


class ContentSubscriptionTestResult(BaseModel):
    recipient: str = Field(description="Recipient email used for the test delivery")


class ContentSubscriberAdminRead(ModelBase):
    email: str = Field(description="Subscriber email")
    is_active: bool = Field(description="Whether subscription is active")
    content_types: list[str] = Field(default_factory=list, description="Subscribed content types")
    auth_mode: Literal["email", "binding", "unknown"] = Field(
        description="Whether the subscriber email maps to email-only user, bound account user, or unknown user"
    )
    display_name: str | None = Field(default=None, description="Matched site user display name")
    avatar_url: str | None = Field(default=None, description="Matched site user avatar")
    primary_auth_provider: str | None = Field(default=None, description="Matched site user primary auth provider")
    oauth_providers: list[str] = Field(default_factory=list, description="Matched OAuth providers")
    sent_count: int = Field(default=0, description="Number of successful deliveries")
    last_sent_at: datetime | None = Field(default=None, description="Last successful delivery time")
    created_at: datetime = Field(description="Creation time")
    updated_at: datetime = Field(description="Last update time")


class ContentNotificationDeliveryAdminRead(ModelBase):
    id: str = Field(description="Delivery id")
    subscriber_email: str = Field(description="Subscriber email")
    content_type: str = Field(description="Content type")
    content_slug: str = Field(description="Content slug")
    content_title: str = Field(description="Content title")
    content_url: str = Field(description="Public content URL")
    status: str = Field(description="Delivery status")
    error_message: str | None = Field(default=None, description="Delivery error detail")
    sent_at: datetime | None = Field(default=None, description="Delivery time")
    created_at: datetime = Field(description="Creation time")
    updated_at: datetime = Field(description="Last update time")
