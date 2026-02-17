import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.core.config import settings
from src.models import UserCreate
from src.services.user_service import create_user
from src.utils.utils import (
            generate_password_reset_token)

from test.utils import user_authentication_headers

# TODO: Change it so it creates user and doesn't use already existing user
@pytest.mark.parametrize("user_exists, expected_status, expected_response",
                         [
                          (True, 200, None),
                          (False, 400, "Incorrect email or password"),
                          ])
def test_get_access_token(client: TestClient, fake, db, user_exists, cleanup_user,
                          expected_status,
                          expected_response) -> None:
    # TODO: expects email as username, is this unintended?
    username = fake.company_email()
    password = fake.password()
    if user_exists:
        user_create = UserCreate(
            email=username,
            full_name=fake.name(),
            username=fake.user_name(),
            password=password,
            is_active=True,
            is_superuser=False,
            is_verified=True,
            )
        user = create_user(session=db, user_create=user_create)
        cleanup_user.append(username)

    response = client.post(f"{settings.API_V1_STR}/login/access-token", data={'username': username,
                                                                              'password': password})
    assert response.status_code == expected_status
    if expected_status == 200:
        tokens = response.json()
        assert "access_token" in tokens
        assert tokens["access_token"]
    else:
        response = response.json()
        assert response['detail']== expected_response
        
def test_reset_password(client: TestClient, db: Session, fake, cleanup_user ) -> None:

    email = fake.company_email()
    password = fake.password()
    full_name = fake.name()
    username = fake.user_name()
    new_password = fake.password(12)
    user_create = UserCreate(
        email=email,
        full_name=full_name,
        username=username,
        password=password,
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    user = create_user(session=db, user_create=user_create)
    token = generate_password_reset_token(email=email)
    headers = user_authentication_headers(client=client, email=email, password=password)
    data = {"new_password": new_password, "token": token}

    r = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        headers=headers,
        json=data,
    )
    cleanup_user.append(email)
    assert r.status_code == 200
    assert r.json() == {"message": "Password updated successfully"}

@pytest.mark.parametrize(
    "user_exists, expected_status, expected_response",
    [
        (True, 200, {"message": "Password recovery email sent"}),
        (False, 404, {"detail": "The user with this email does not exist in the system."}),
    ],
)
def test_password_recovery(client, db, fake, cleanup_user, user_exists, expected_status, expected_response):
    email = fake.company_email()
    if user_exists:
        password = fake.password()
        user_create = UserCreate(
            email=email,
            full_name=fake.name(),
            username=fake.user_name(),
            password=password,
            is_active=True,
            is_superuser=False,
            is_verified=True,
        )
        user = create_user(session=db, user_create=user_create)
        cleanup_user.append(email)

    response = client.post(f"{settings.API_V1_STR}/password-recovery/{email}")

    assert response.status_code == expected_status
    assert response.json() == expected_response
