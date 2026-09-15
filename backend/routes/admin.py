"""
routes/admin.py — organisation administration.

POST /admin/users creates an account inside the caller's organisation. The
organisation is never part of the request: it is read from the verified token,
and an `organization_id` in the body is rejected outright rather than ignored.
"""
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from auth import Principal, require_roles
from database import insert, select, select_one
from logger import get_logger
from services.user_provisioning import (
    EmailAlreadyRegistered,
    ProvisioningError,
    create_auth_user,
    delete_auth_user,
)

log = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["Administration"])

# Must stay within the users_role_check constraint — pinned by
# tests/test_schema_contract.py.
HOSPITAL_ROLES = frozenset({"admin", "auditor", "coder", "rcm"})
PAYER_ROLES = frozenset({"admin", "payer"})

_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
_GENERIC_FAILURE = "Could not create the account. Please try again."


class CreateUserRequest(BaseModel):
    # extra="forbid": anything unexpected — an organization_id above all — is a
    # 422, so a client cannot even attempt to pick the tenant.
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254, pattern=_EMAIL_PATTERN)
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=72)  # bcrypt ignores bytes past 72
    role: Literal["admin", "auditor", "coder", "rcm", "payer"]
    branch_id: Optional[uuid.UUID] = None

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("full_name")
    @classmethod
    def _full_name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class CreatedUser(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    branch_id: Optional[str] = None


@router.post(
    "/users",
    status_code=status.HTTP_201_CREATED,
    response_model=CreatedUser,
    summary="Create a user in the caller's organisation",
)
async def create_user(
    body: CreateUserRequest,
    principal: Principal = Depends(require_roles("admin")),
) -> CreatedUser:
    org_id = str(principal.organization_id)

    allowed = PAYER_ROLES if principal.is_payer else HOSPITAL_ROLES
    if body.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Role '{body.role}' is not available in this organisation.",
        )

    branch_id = str(body.branch_id) if body.branch_id else None
    if branch_id:
        if principal.is_payer:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Payer organisations do not have branches.",
            )
        branch = await select_one(
            "branches",
            query="id",
            filters={"id": f"eq.{branch_id}", "organization_id": f"eq.{org_id}"},
        )
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Branch not found in your organisation.",
            )

    # Checked before any account exists, so the common duplicate never leaves
    # an Auth account behind to clean up.
    if await select("users", query="id", filters={"email": f"eq.{body.email}"}, limit=1):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists.")

    try:
        auth_id = await create_auth_user(body.email, body.password, body.full_name)
    except EmailAlreadyRegistered:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A user with this email already exists.")
    except ProvisioningError as exc:
        log.error("admin_create_user_auth_failed", caller=principal.auth_id, status=exc.status)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=_GENERIC_FAILURE)

    try:
        row = await insert("users", {
            "auth_id": auth_id,
            "organization_id": org_id,  # from the token — never the request
            "branch_id": branch_id,
            "email": body.email,
            "full_name": body.full_name,
            "role": body.role,
        })
        if not row:
            raise RuntimeError("insert returned no row")
    except Exception as exc:
        # Never leave half an account: an Auth login with no application
        # profile can authenticate but belongs to no organisation.
        log.error("admin_create_user_row_failed", auth_id=auth_id, error_type=type(exc).__name__)
        try:
            await delete_auth_user(auth_id)
        except Exception:
            log.error("admin_create_user_compensation_failed", auth_id=auth_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=_GENERIC_FAILURE)

    log.info("admin_user_created", caller=principal.auth_id, created_auth_id=auth_id, role=body.role)
    return CreatedUser(
        id=str(row.get("id") or auth_id),
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        branch_id=branch_id,
    )
