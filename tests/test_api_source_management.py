import unittest
from unittest.mock import patch

import api_lambda


class AdminSourceApiTests(unittest.TestCase):
    def test_admin_group_is_required(self):
        self.assertTrue(api_lambda.is_admin({
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "cognito:groups": ["JobSyncAdmins"]
                        }
                    }
                }
            }
        }))
        self.assertFalse(api_lambda.is_admin({
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "cognito:groups": ["OtherUsers"]
                        }
                    }
                }
            }
        }))

    def test_admin_group_is_read_from_http_api_v1_claims(self):
        event = {
            "requestContext": {
                "authorizer": {
                    "claims": {
                        "sub": "test-admin",
                        "cognito:groups": '["JobSyncAdmins"]',
                    }
                }
            }
        }
        self.assertTrue(api_lambda.is_admin(event))

    def test_admin_group_stringified_as_bracketed_list(self):
        self.assertTrue(api_lambda.is_admin({
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "cognito:groups": "[JobSyncAdmins]"
                        }
                    }
                }
            }
        }))

    def test_admin_group_stringified_with_multiple_groups(self):
        self.assertTrue(api_lambda.is_admin({
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "cognito:groups": "[OtherUsers JobSyncAdmins]"
                        }
                    }
                }
            }
        }))

    def test_non_admin_stringified_group_is_rejected(self):
        self.assertFalse(api_lambda.is_admin({
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "cognito:groups": "[OtherUsers]"
                        }
                    }
                }
            }
        }))

    def test_admin_routes_are_detected(self):
        self.assertTrue(api_lambda.is_admin_route("GET /admin/metrics", "/admin/metrics"))
        self.assertTrue(api_lambda.is_admin_route("POST /admin/sources", "/admin/sources"))
        self.assertFalse(api_lambda.is_admin_route("GET /jobs", "/jobs"))

    def test_admin_endpoint_rejects_missing_claims(self):
        result = api_lambda.lambda_handler({
            "routeKey": "GET /admin/metrics",
            "rawPath": "/admin/metrics",
            "requestContext": {},
        }, None)
        self.assertEqual(result["statusCode"], 401)

    def test_admin_endpoint_rejects_non_admin_user(self):
        result = api_lambda.lambda_handler({
            "routeKey": "GET /admin/metrics",
            "rawPath": "/admin/metrics",
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": "test-user",
                            "cognito:groups": ["OtherUsers"],
                        }
                    }
                }
            },
        }, None)
        self.assertEqual(result["statusCode"], 403)

    def test_source_config_rejects_missing_required_field(self):
        with patch("api_lambda.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("8.8.8.8", 443))
        ]):
            with self.assertRaisesRegex(ValueError, "company"):
                api_lambda.validate_api_config({
                    "endpoint": "https://api.example.com/jobs",
                    "fields": {"title": "title"},
                })

    def test_source_config_caps_page_count(self):
        with patch("api_lambda.socket.getaddrinfo", return_value=[
            (2, 1, 6, "", ("8.8.8.8", 443))
        ]):
            with self.assertRaisesRegex(ValueError, "1–10 pages"):
                api_lambda.validate_api_config({
                    "endpoint": "https://api.example.com/jobs",
                    "fields": {"title": "title", "company": "company"},
                    "pagination": {
                        "type": "PAGE",
                        "page_parameter": "page",
                        "start_page": 1,
                        "max_pages": 11,
                    },
                })


    @patch("api_lambda.sqs_client.send_message", return_value={"MessageId": "test-message"})
    @patch("api_lambda.sources_table.get_item")
    def test_manual_sync_enqueues_source(self, mocked_get, mocked_send):
        mocked_get.return_value = {"Item": {
            "source_id": "custom-example-ab12cd34",
            "source_name": "Example",
            "status": "ACTIVE",
            "source_type": "CUSTOM_API",
        }}
        result = api_lambda.sync_admin_source({
            "pathParameters": {"source_id": "custom-example-ab12cd34"},
            "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "admin-123"}}}},
        })
        self.assertEqual(result["statusCode"], 202)
        mocked_send.assert_called_once()
        message = mocked_send.call_args.kwargs["MessageBody"]
        self.assertIn('"reason":"MANUAL_SYNC"', message)
        self.assertIn('"source_id":"custom-example-ab12cd34"', message)

    @patch("api_lambda.sqs_client.send_message")
    @patch("api_lambda.sources_table.get_item")
    def test_manual_sync_rejects_inactive_source(self, mocked_get, mocked_send):
        mocked_get.return_value = {"Item": {
            "source_id": "custom-example-ab12cd34",
            "source_name": "Example",
            "status": "DISABLED",
            "source_type": "CUSTOM_API",
        }}
        result = api_lambda.sync_admin_source({
            "pathParameters": {"source_id": "custom-example-ab12cd34"},
            "requestContext": {},
        })
        self.assertEqual(result["statusCode"], 409)
        mocked_send.assert_not_called()



if __name__ == "__main__":
    unittest.main()
