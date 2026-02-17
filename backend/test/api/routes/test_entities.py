import pytest
from fastapi import status

from src.core.config import settings

@pytest.mark.parametrize("name, num_individuals",
                        [("Test", 13),
                          ("Edge Case", 9999999)])
def test_create_entity(client, normaluser_header, name, num_individuals):
    data = {"name": name, "num_individuals": num_individuals}
    response = client.post(f"{settings.API_V1_STR}/entities/", params=data, headers=normaluser_header)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["name"] == name
    assert json_response["num_individuals"] == num_individuals
    assert "id" in json_response

@pytest.mark.parametrize("entity_exists, entity_id, expected_status",
                        [(True, 1 , 200),
                          (False,9999999, 404)])
def test_get_entity(client, normaluser_header, entity_exists, entity_id, expected_status):
    response = client.get(f"{settings.API_V1_STR}/entities/{entity_id}", headers=normaluser_header)
    assert response.status_code == expected_status
    if entity_exists:
        json_response = response.json()
        assert response.status_code == 200
        assert json_response["id"] == entity_id
    else:
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Entity not found"

def test_update_entity(client, normaluser_header, entities_data):
    entity_id = entities_data[0].id
    payload = {"name": "Updated Name", "num_individuals": 555}
    response = client.put(f"{settings.API_V1_STR}/entities/{entity_id}", json=payload, headers=normaluser_header)
    assert response.status_code == status.HTTP_200_OK
    json_response = response.json()
    assert json_response["name"]
