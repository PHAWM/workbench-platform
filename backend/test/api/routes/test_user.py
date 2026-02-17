from src.core.config import settings
from src.models.users import User, UserCreate
from src.services.user_service import create_user
import pytest

def test_read_users(client, superuser_header):
    response = client.get(f"{settings.API_V1_STR}/users/", headers=superuser_header)
    assert response.status_code == 200
    data = response.json()
    assert "count" in data
    assert "data" in data

def test_read_user_me(client, superuser_header):
    response = client.get(f"{settings.API_V1_STR}/users/me", headers=superuser_header)
    assert response.status_code == 200
    user = response.json()
    assert "email" in user

@pytest.mark.parametrize(
    "user_exists, expected_status, expected_response",
    [
        (True, 400, {"detail": "The user with this email already exists in the system."}),
        (False, 200, None),
    ],
)
def test_create_user(client, db, fake, cleanup_user, superuser_header, 
                     user_exists, expected_status, expected_response):
    email = fake.company_email()
    user_data = {
            "email":email,
            "full_name":fake.name(),
            "username":fake.user_name(),
            "password":fake.password(),
            "is_active":True,
            "is_superuser":False,
        }
    if user_exists:
        user_create = UserCreate(**user_data)
        user = create_user(session=db, user_create=user_create)
        cleanup_user.append(email)
    response = client.post(f"{settings.API_V1_STR}/users/", json=user_data, headers=superuser_header)
    cleanup_user.append(email)
    assert response.status_code == expected_status
    if expected_response:
        assert response.json() == expected_response
    else:
        assert response.json()['email'] == email

def test_register_user_success(client, fake, cleanup_user):
    email = fake.company_email()
    user_data = {
        "email": email,
        "full_name": fake.name(),
        "username": fake.user_name(),
        "password": "superduperpassword",
    }
    response = client.post(f"{settings.API_V1_STR}/users/signup", json=user_data)
    cleanup_user.append(email)
    assert response.status_code == 200
    user = response.json()
    assert user["email"] == user_data["email"]


@pytest.mark.parametrize(
    "auth_headers, expected_status, expected_message",
    [
        ("superuser_header", 200, False),
        ("normaluser_header", 403, True),
    ]
)
def test_read_user_by_id(request, client, db, fake, cleanup_user,
    auth_headers, expected_status, expected_message
):
    email = fake.email()
    user_create = UserCreate(
        email=email,
        full_name=fake.name(),
        username=fake.user_name(),
        password="superduperpassword",
        is_active=True,
        is_superuser=False,
    )
    user = create_user(session=db, user_create=user_create)
    headers = request.getfixturevalue(auth_headers)

    response = client.get(f"{settings.API_V1_STR}/users/{user.id}", headers=headers)
    cleanup_user.append(email)
  
    assert response.status_code == expected_status

    if expected_status == 200:
        user_response = response.json()
        assert user_response["email"] == email
    elif expected_message:
        assert "privileges" in response.json()["detail"]
