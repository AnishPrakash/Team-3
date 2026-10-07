import pytest
from fastapi.testclient import TestClient

def test_create_widget_route(client: TestClient):
    payload = {
        "id": "icon_pack",
        "appdev_key": "flutter_icon_pack",
        "display_name": "Icon Pack",
        "category": "media",
        "flutter_classes": ["Icon", "IconButton"],
        "is_free": True,
        "free_quantity": 5
    }
    response = client.post("/admin/widgets", json=payload)
    assert response.status_code == 201
    
    data = response.json()
    assert data["id"] == "icon_pack"
    assert data["status"] == "ACTIVE"
    assert data["version"] == 1


def test_get_public_widgets_route(client: TestClient):
    payload = {
        "id": "row_layout",
        "appdev_key": "flutter_row",
        "display_name": "Row Layout",
        "category": "layout"
    }
    client.post("/admin/widgets", json=payload)

    response = client.get("/widgets")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "row_layout"
    assert "internal_notes" not in data[0]
    assert "status" not in data[0]


def test_update_widget_version_conflict_route(client: TestClient):
    payload = {
        "id": "column_layout",
        "appdev_key": "flutter_column",
        "display_name": "Column Layout",
        "category": "layout"
    }
    client.post("/admin/widgets", json=payload)

    update_payload = {
        "display_name": "Updated Column",
        "expected_version": 99
    }
    response = client.patch("/admin/widgets/column_layout", json=update_payload)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "VERSION_CONFLICT"


def test_archive_widget_route(client: TestClient):
    payload = {
        "id": "deprecated_card",
        "appdev_key": "flutter_card",
        "display_name": "Old Card",
        "category": "layout"
    }
    client.post("/admin/widgets", json=payload)

    archive_res = client.post("/admin/widgets/deprecated_card/archive")
    assert archive_res.status_code == 200
    assert archive_res.json()["status"] == "ARCHIVED"

    public_res = client.get("/widgets/deprecated_card")
    assert public_res.status_code == 400
    assert public_res.json()["detail"]["code"] == "WIDGET_ARCHIVED"