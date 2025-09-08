from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

# --- Test POST /tasks/add-task ---

def test_add_task_success(client: TestClient, mock_mongo_manager, mocker):
    mock_delay = mocker.patch('workers.tasks.refine_and_plan_ai_task.delay')
    
    response = client.post(
        "/tasks/add-task",
        headers={"Authorization": "Bearer test-token"},
        json={"prompt": "Plan a marketing campaign"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["message"] == "Task accepted! I'll start planning it out."
    assert data["task_id"] == "new-task-id"
    
    # Check that the DB was called to create a placeholder task
    mock_mongo_manager.add_task.assert_called_once()
    call_args = mock_mongo_manager.add_task.call_args[0]
    assert call_args[0] == "test-user-123"
    assert call_args[1]["name"] == "Plan a marketing campaign"
    
    # Check that the async worker was triggered
    mock_delay.assert_called_once_with("new-task-id")

# --- Test POST /tasks/fetch-tasks ---

def test_fetch_tasks_success(client: TestClient, mock_mongo_manager):
    mock_tasks = [{"task_id": "1", "name": "Task 1"}, {"task_id": "2", "name": "Task 2"}]
    mock_mongo_manager.get_all_tasks_for_user.return_value = mock_tasks
    
    response = client.post("/tasks/fetch-tasks", headers={"Authorization": "Bearer test-token"})
    
    assert response.status_code == 200
    assert response.json() == {"tasks": mock_tasks}
    mock_mongo_manager.get_all_tasks_for_user.assert_called_once_with("test-user-123")

# --- Test POST /tasks/update-task ---

def test_update_task_success(client: TestClient, mock_mongo_manager):
    update_data = {"taskId": "some-task-id", "name": "Updated Name", "priority": 0}
    
    response = client.post(
        "/tasks/update-task",
        headers={"Authorization": "Bearer test-token"},
        json=update_data
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Task updated successfully."
    
    mock_mongo_manager.update_task.assert_called_once()
    call_args = mock_mongo_manager.update_task.call_args[0]
    assert call_args[0] == "some-task-id"
    assert call_args[1]["name"] == "Updated Name"
    assert call_args[1]["priority"] == 0

def test_update_task_not_found(client: TestClient, mock_mongo_manager):
    mock_mongo_manager.get_task.return_value = None
    
    response = client.post(
        "/tasks/update-task",
        headers={"Authorization": "Bearer test-token"},
        json={"taskId": "non-existent-id", "name": "New Name"}
    )
    
    assert response.status_code == 404

# --- Test POST /tasks/approve-task ---

def test_approve_task_run_immediately(client: TestClient, mock_mongo_manager, mocker):
    mock_execute = mocker.patch('workers.tasks.execute_task_plan.delay')
    
    response = client.post(
        "/tasks/approve-task",
        headers={"Authorization": "Bearer test-token"},
        json={"taskId": "some-task-id"}
    )
    
    assert response.status_code == 200
    assert "Task approved and scheduled/executed" in response.json()["message"]
    
    # Check that status is updated to 'processing'
    mock_mongo_manager.update_task.assert_called_once()
    update_call_args = mock_mongo_manager.update_task.call_args[0]
    assert update_call_args[1]["status"] == "processing"
    
    # Check that the executor was called
    mock_execute.assert_called_once_with("some-task-id", "test-user-123")

# --- Test POST /tasks/delete-task ---

def test_delete_task_success(client: TestClient, mock_mongo_manager):
    response = client.post(
        "/tasks/delete-task",
        headers={"Authorization": "Bearer test-token"},
        json={"taskId": "some-task-id"}
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Task deleted successfully."
    mock_mongo_manager.delete_task.assert_called_once_with("some-task-id", "test-user-123")