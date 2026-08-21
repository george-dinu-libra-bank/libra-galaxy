import json

from app.core.envelope import error_response, new_request_id, success
from app.core.errors import ResourceNotFoundError, ValidationError


def test_success_envelope_shape():
    response = success({"foo": "bar"}, request_id="req_test")
    payload = json.loads(response.body)

    assert payload["success"] is True
    assert payload["body"] == {"foo": "bar"}
    assert payload["request_id"] == "req_test"
    assert response.headers["X-Request-ID"] == "req_test"


def test_error_envelope_maps_code_and_status():
    error = ValidationError("camp invalid", details={"fields": ["text"]})
    response = error_response(error, request_id="req_test")
    payload = json.loads(response.body)

    assert response.status_code == 422
    assert payload["success"] is False
    assert payload["error"]["code"] == "VALIDATION_ERROR"
    assert payload["error"]["details"] == {"fields": ["text"]}


def test_resource_not_found_maps_to_404():
    error = ResourceNotFoundError("nu exista")
    response = error_response(error, request_id="req_test")
    assert response.status_code == 404


def test_new_request_id_has_stable_prefix():
    request_id = new_request_id()
    assert request_id.startswith("req_")
    assert len(request_id) == len("req_") + 16
