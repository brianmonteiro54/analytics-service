import os
import json
import pytest
from unittest.mock import patch

os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_SQS_URL"] = "dummy-queue-url"
os.environ["AWS_DYNAMODB_TABLE"] = "dummy"

with patch("threading.Thread.start"):
    import app


def make_valid_message():
    return {
        "MessageId": "msg-123",
        "ReceiptHandle": "receipt-123",
        "Body": json.dumps({
            "user_id": "user-1",
            "flag_name": "enable-new-dashboard",
            "result": True,
            "timestamp": "2026-03-15T23:00:00Z"
        })
    }


def test_process_message_success():
    message = make_valid_message()

    with patch.object(app, "dynamodb_client") as mock_dynamodb, \
         patch.object(app, "sqs_client") as mock_sqs, \
         patch.object(app.uuid, "uuid4", return_value="fixed-event-id"):

        app.process_message(message)

        mock_dynamodb.put_item.assert_called_once_with(
            TableName=app.DYNAMODB_TABLE_NAME,
            Item={
                "event_id": {"S": "fixed-event-id"},
                "user_id": {"S": "user-1"},
                "flag_name": {"S": "enable-new-dashboard"},
                "result": {"BOOL": True},
                "timestamp": {"S": "2026-03-15T23:00:00Z"},
            },
        )

        mock_sqs.delete_message.assert_called_once_with(
            QueueUrl=app.SQS_QUEUE_URL,
            ReceiptHandle="receipt-123",
        )


def test_process_message_invalid_json_does_not_delete_message():
    message = {
        "MessageId": "msg-123",
        "ReceiptHandle": "receipt-123",
        "Body": "{invalid-json"
    }

    with patch.object(app, "dynamodb_client") as mock_dynamodb, \
         patch.object(app, "sqs_client") as mock_sqs:

        app.process_message(message)

        mock_dynamodb.put_item.assert_not_called()
        mock_sqs.delete_message.assert_not_called()


def test_process_message_dynamodb_error_does_not_delete_message():
    message = make_valid_message()

    fake_error = app.ClientError(
        error_response={"Error": {"Code": "500", "Message": "DynamoDB failure"}},
        operation_name="PutItem",
    )

    with patch.object(app, "dynamodb_client") as mock_dynamodb, \
         patch.object(app, "sqs_client") as mock_sqs:

        mock_dynamodb.put_item.side_effect = fake_error

        app.process_message(message)

        mock_dynamodb.put_item.assert_called_once()
        mock_sqs.delete_message.assert_not_called()


def test_sqs_worker_loop_processes_received_messages():
    message = make_valid_message()

    with patch.object(app, "sqs_client") as mock_sqs, \
         patch.object(app, "process_message") as mock_process:

        mock_sqs.receive_message.side_effect = [
            {"Messages": [message]},
            KeyboardInterrupt()
        ]

        with pytest.raises(KeyboardInterrupt):
            app.sqs_worker_loop()

        mock_process.assert_called_once_with(message)


def test_sqs_worker_loop_client_error_sleeps_before_retry():
    fake_error = app.ClientError(
        error_response={"Error": {"Code": "500", "Message": "SQS receive failure"}},
        operation_name="ReceiveMessage",
    )

    with patch.object(app, "sqs_client") as mock_sqs, \
         patch.object(app.time, "sleep", side_effect=KeyboardInterrupt) as mock_sleep:

        mock_sqs.receive_message.side_effect = fake_error

        with pytest.raises(KeyboardInterrupt):
            app.sqs_worker_loop()

        mock_sleep.assert_called_once_with(10)
